from uuid import uuid4
import json

import pytest
from fastapi.testclient import TestClient
from support import Database,make_app,seed


@pytest.fixture
def client():
    db=seed(Database())
    with TestClient(make_app(db)) as client:
        yield client
    db.connection.close()


def headers(who=4): return {'Authorization':f'Bearer test-{who}'}
def profile(child=False,name=None):
    return {'full_name':name or ('Алиса Иванова' if child else 'Алексей Иванов'),'nickname':'Alice' if child else 'Alex','birth_date':'2017-04-08' if child else '2002-10-13','gender':'female' if child else 'male','phone':'+375290000000','city':'Минск','club':'Street Masters','trainer':''}
def create(client,who=4,child=False,name=None,role=None):
    response=client.post('/api/v2/people',headers=headers(who),json={'profile':profile(child,name),'role':role or ('parent' if child else 'self'),'parent_declaration':child})
    assert response.status_code==200,response.text
    return response.json()['id']
def payload(pid,**kwargs):
    return {'person_id':pid,'request_key':uuid4().hex,'nomination_ids':[1],'rules_consent':True,'rules_version':1,**kwargs}
def submit(client,pid,who=4,**kwargs):
    return client.post('/api/v2/events/1/registrations',headers=headers(who),json=payload(pid,**kwargs))


def test_auth_required(client): assert client.get('/api/v2/bootstrap').status_code==401
def test_no_admin_self_assignment(client):
    res=client.get('/api/v2/bootstrap',headers=headers()).json()
    assert res['roles']==['participant','parent','coach']
    assert client.get('/api/v2/admin/users',headers=headers()).status_code==403


def test_saved_profile_and_new_session(client):
    pid=create(client)
    data=client.get('/api/v2/bootstrap',headers=headers()).json()
    assert data['people'][0]['id']==pid
    assert data['people'][0]['profile']['full_name']=='Алексей Иванов'


def test_duplicate_person_does_not_leak(client):
    create(client)
    response=client.post('/api/v2/people',headers=headers(5),json={'profile':profile(),'role':'self'})
    assert response.status_code==409
    assert 'person_id' not in response.text
    assert len(client.get('/api/v2/bootstrap',headers=headers(5)).json()['people'])==0


def test_self_unique_and_transaction_rolls_back(client):
    create(client)
    response=client.post('/api/v2/people',headers=headers(),json={'profile':profile(name='Другой человек'),'role':'self'})
    assert response.status_code==409
    assert client.app.state.db.connection.execute('SELECT COUNT(*) FROM v2_people').fetchone()[0]==1


def test_validation(client):
    p=profile();p['birth_date']='2099-01-01'
    assert client.post('/api/v2/people',headers=headers(),json={'profile':p,'role':'self'}).status_code==422
    p=profile();p['phone']='123'
    assert client.post('/api/v2/people',headers=headers(),json={'profile':p,'role':'self'}).status_code==422


def test_duplicate_registration_and_idempotency(client):
    pid=create(client); data=payload(pid)
    first=client.post('/api/v2/events/1/registrations',headers=headers(),json=data)
    assert first.status_code==200,first.text
    again=client.post('/api/v2/events/1/registrations',headers=headers(),json=data)
    assert first.json()['id']==again.json()['id']
    assert submit(client,pid).json()['id']==first.json()['id']
    data['nomination_ids']=[2]
    assert client.post('/api/v2/events/1/registrations',headers=headers(),json=data).status_code==409
    assert first.json()['status']=='submitted'


def test_foreign_profile_denied(client):
    pid=create(client)
    assert submit(client,pid,who=5).status_code==403
    assert client.put(f'/api/v2/people/{pid}',headers=headers(5),json={'profile':profile(),'version':1}).status_code==403


def test_age_rules_and_consent(client):
    pid=create(client,who=2,child=True)
    assert submit(client,pid,who=2).status_code==422
    assert submit(client,pid,who=2,nomination_ids=[2],rules_consent=False).status_code==422
    reg=submit(client,pid,who=2,nomination_ids=[2]).json()
    assert reg['status']=='awaiting_consent'
    response=client.post(f"/api/v2/registrations/{reg['id']}/consent",headers=headers(2),json={'parent_consent':True,'rules_consent':True,'rules_version':1,'version':reg['version']})
    assert response.status_code==200,response.text
    assert response.json()['status']=='submitted'
    assert response.json()['id']==reg['id']


def test_draft_version_and_cross_user(client):
    pid=create(client)
    path=f'/api/v2/drafts/1/{pid}'
    assert client.put(path,headers=headers(),json={'version':0,'payload':{'nomination_ids':[1]}}).status_code==200
    assert client.put(path,headers=headers(),json={'version':0,'payload':{}}).status_code==409
    assert client.put(path,headers=headers(5),json={'version':1,'payload':{}}).status_code==403


def test_profile_conflict(client):
    pid=create(client)
    assert client.put(f'/api/v2/people/{pid}',headers=headers(),json={'profile':profile(),'version':1}).status_code==200
    assert client.put(f'/api/v2/people/{pid}',headers=headers(),json={'profile':profile(),'version':1}).status_code==409


def test_close_deadline(client):
    pid=create(client)
    client.app.state.db.connection.execute("UPDATE events SET registration_closes_at='2000-01-01'")
    assert submit(client,pid).status_code==409


def test_capacity_and_waitlist(client):
    client.app.state.db.connection.execute('UPDATE v2_nomination_settings SET capacity=1 WHERE nomination_id=1')
    a=create(client);b=create(client,who=5,name='Второй участник')
    assert submit(client,a).status_code==200
    assert submit(client,b,who=5).status_code==409
    assert client.app.state.db.connection.execute('SELECT COUNT(*) FROM v2_registrations').fetchone()[0]==1
    assert submit(client,b,who=5,waitlist=True).json()['status']=='waitlisted'


def test_cancel_restore_same_record(client):
    pid=create(client); reg=submit(client,pid).json()
    cancel=client.post(f"/api/v2/registrations/{reg['id']}/cancel",headers=headers(),json={'version':1}).json()
    assert cancel['status']=='cancelled'
    restored=submit(client,pid,version=cancel['version'])
    assert restored.status_code==200,restored.text
    assert restored.json()['id']==reg['id']


def test_organizer_scoped_decision(client):
    pid=create(client);reg=submit(client,pid).json()
    path=f"/api/v2/manage/registrations/{reg['id']}/decision"
    assert client.post(path,headers=headers(3),json={'status':'confirmed','version':1}).status_code==403
    assert client.post('/api/v2/admin/access',headers=headers(1),json={'telegram_id':9003,'event_id':1,'enabled':True}).status_code==200
    approved=client.post(path,headers=headers(3),json={'status':'confirmed','version':1})
    assert approved.status_code==200,approved.text
    assert approved.json()['status']=='confirmed'
    assert client.post(path,headers=headers(3),json={'status':'rejected','version':1,'comment':'Причина'}).status_code==409
    assert client.get('/api/v2/bootstrap',headers=headers()).json()['notifications']


def test_invitation_requires_confirmation_and_prevents_coach_parent_consent(client):
    pid=create(client,who=2,child=True)
    invite=client.post(f'/api/v2/people/{pid}/invites',headers=headers(2),json={'role':'coach'}).json()
    claim=client.post('/api/v2/invites/accept',headers=headers(3),json={'code':invite['code']})
    assert claim.status_code==200,claim.text
    assert submit(client,pid,who=3,nomination_ids=[2]).status_code==403
    invitation=client.get('/api/v2/invites',headers=headers(2)).json()[0]
    assert client.post(f"/api/v2/invites/{invitation['token_hash']}/decide",headers=headers(2),json={'approve':True}).status_code==200
    assert submit(client,pid,who=3,nomination_ids=[2],parent_consent=True).status_code==403
    child=submit(client,pid,who=3,nomination_ids=[2])
    assert child.status_code==200,child.text
    assert child.json()['status']=='awaiting_consent'
    assert submit(client,pid,who=2,nomination_ids=[2]).json()['id']==child.json()['id']


def test_partial_batch(client):
    a=create(client,who=3,name='Ученик взрослый',role='coach')
    b=create(client,who=3,child=True,role='coach')
    response=client.post('/api/v2/events/1/batch',headers=headers(3),json={'items':[payload(a),payload(b)]})
    assert response.status_code==200,response.text
    assert [r['ok'] for r in response.json()['results']]==[True,False]


def test_export_escapes_formula_and_scoped(client):
    pid=create(client,name='=HYPERLINK(опасно)');submit(client,pid)
    export=client.get('/api/v2/export',headers=headers())
    assert "'=HYPERLINK" in export.text
    assert 'Алексей' not in client.get('/api/v2/export',headers=headers(5)).text
    assert client.get('/api/v2/export?scope=event&event_id=1',headers=headers(5)).status_code==403


def test_legacy_preserved(client):
    db=client.app.state.db.connection
    db.execute("INSERT INTO registrations(event_id,user_id,registration_type,payload) VALUES(1,4,'full',?)",(json.dumps({'full_name':'Legacy'}),))
    data=client.get('/api/v2/bootstrap',headers=headers()).json()
    assert data['legacy'][0]['payload']['full_name']=='Legacy'
