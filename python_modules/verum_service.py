"""VERUM domain API. Same SQL and routes run in D1 and isolated SQLite tests."""
import csv
import hashlib
import io
import json
import re
import time
import unicodedata
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.responses import Response


def uid():
    return uuid4().hex


def pack(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def plain(row):
    if row is None:
        return None
    return row.to_py() if hasattr(row, 'to_py') else dict(row)


async def one(db, sql, *args):
    return plain(await db.prepare(sql).bind(*args).first())


async def many(db, sql, *args):
    result = await db.prepare(sql).bind(*args).all()
    return [plain(r) for r in result.results]


def stmt(db, sql, *args):
    return db.prepare(sql).bind(*args)


def guard(db, condition, *args):
    return stmt(db, 'INSERT INTO v2_guard(value) SELECT CASE WHEN (' + condition + ') THEN 1 ELSE 0 END', *args)


def audit(db, actor, action, obj, details):
    return stmt(db, 'INSERT INTO v2_audit(id,actor_id,action,object_id,details) VALUES(?,?,?,?,?)', uid(), actor['id'], action, str(obj), pack(details))


async def atomic(db, statements):
    try:
        await db.batch([*statements, stmt(db, 'DELETE FROM v2_guard')])
    except Exception as exc:
        message = str(exc).lower()
        if 'capacity_exceeded' in message:
            raise HTTPException(409, 'Места закончились. Обновите номинации или выберите лист ожидания.') from None
        if any(s in message for s in ('constraint', 'unique', 'v2_guard')):
            raise HTTPException(409, 'Данные уже изменились или запись существует. Обновите экран; ваш ввод не удалён.') from None
        raise


async def body(request):
    raw = await request.body()
    if len(raw) > 1_500_000:
        raise HTTPException(413, 'Слишком большой запрос')
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise HTTPException(422, 'Ожидается JSON-объект') from None


def text(value, label, maximum=160, required=False):
    value = ' '.join(str(value or '').strip().split())
    if len(value) > maximum or (required and not value):
        raise HTTPException(422, f'{label}: заполните поле (до {maximum} символов)')
    return value


def integer(value, label, minimum=0, maximum=1_000_000):
    try:
        result = int(value)
        if isinstance(value, bool) or str(result) != str(value) or not minimum <= result <= maximum:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise HTTPException(422, f'{label}: укажите целое число от {minimum} до {maximum}') from None


def profile_data(value):
    if not isinstance(value, dict):
        raise HTTPException(422, 'Заполните профиль')
    result = {k: text(value.get(k), k, 160 if k == 'full_name' else 100, k in ('full_name', 'city')) for k in ('full_name', 'nickname', 'city', 'club', 'trainer', 'phone')}
    try:
        born = date.fromisoformat(str(value.get('birth_date', '')))
        if born > datetime.now(timezone.utc).date() or born.year < 1900:
            raise ValueError()
    except ValueError:
        raise HTTPException(422, 'Укажите настоящую дату рождения, не в будущем') from None
    result['birth_date'] = born.isoformat()
    result['gender'] = value.get('gender', 'unspecified')
    if result['gender'] not in ('male', 'female', 'unspecified'):
        raise HTTPException(422, 'Выберите значение пола')
    if result['phone']:
        result['phone'] = re.sub(r'[\s()\-]', '', result['phone'])
        if not re.fullmatch(r'\+[1-9][0-9]{6,14}', result['phone']):
            raise HTTPException(422, 'Телефон: международный формат, например +375291234567')
    return result


def fingerprint(profile):
    name = unicodedata.normalize('NFKC', profile['full_name']).casefold().replace('ё', 'е')
    return hashlib.sha256((name + '|' + profile['birth_date']).encode()).hexdigest()


def age_on(birth, on):
    born, event = date.fromisoformat(birth), date.fromisoformat(on[:10])
    return event.year - born.year - ((event.month, event.day) < (born.month, born.day))


def timestamp(value, closing=False):
    if not value:
        return 0
    if len(value) == 10:
        value += 'T23:59:59+03:00' if closing else 'T00:00:00+03:00'
    elif not re.search(r'(Z|[+-]\d\d:\d\d)$', value):
        value += '+03:00'
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except ValueError:
        raise HTTPException(422, 'Некорректная дата или время') from None


def is_admin(actor, env):
    values = str(getattr(env, 'ADMIN_IDS', '')).replace(';', ',').split(',')
    return str(actor['telegram_id']) in [x.strip() for x in values]


async def person_access(db, actor, person_id):
    links = await many(db, "SELECT role FROM v2_links WHERE user_id=? AND person_id=? AND status='verified'", actor['id'], person_id)
    person = await one(db, 'SELECT * FROM v2_people WHERE id=? AND merged_into IS NULL', person_id)
    if not links or not person:
        raise HTTPException(403, 'Нет подтверждённого доступа к этому профилю')
    person['profile'] = json.loads(person['profile'])
    person['roles'] = [x['role'] for x in links]
    return person


async def organizer(db, actor, env, event_id=None):
    if is_admin(actor, env):
        return
    if event_id is not None and await one(db, 'SELECT 1 FROM v2_event_access WHERE user_id=? AND event_id=?', actor['id'], event_id):
        return
    raise HTTPException(403, 'Раздел доступен только назначенному организатору')


async def event_data(db, event_id):
    event = await one(db, 'SELECT * FROM events WHERE id=?', event_id)
    if not event:
        raise HTTPException(404, 'Мероприятие не найдено')
    settings = await one(db, 'SELECT * FROM v2_event_settings WHERE event_id=?', event_id)
    event.update(settings or {'rules': '', 'rules_version': 1, 'minor_age': 18, 'require_parent': 1, 'version': 0, 'timezone': 'Europe/Minsk', 'edit_closes_at': None})
    event['nominations'] = await many(db, 'SELECT n.*,s.capacity,COALESCE(s.waitlist,0) AS waitlist,COALESCE(s.team_size,1) AS team_size,(SELECT COUNT(*) FROM v2_entries e WHERE e.nomination_id=n.id AND e.status IN (\'pending\',\'confirmed\')) AS occupied FROM nominations n LEFT JOIN v2_nomination_settings s ON s.nomination_id=n.id WHERE n.event_id=? ORDER BY n.sort_order,n.id', event_id)
    return event


async def registration_data(db, rid):
    row = await one(db, 'SELECT r.*,e.title AS event_title,e.event_date,e.registration_closes_at FROM v2_registrations r JOIN events e ON e.id=r.event_id WHERE r.id=?', rid)
    if not row:
        raise HTTPException(404, 'Заявка не найдена')
    row['snapshot'] = json.loads(row['snapshot'])
    row['nominations'] = await many(db, 'SELECT n.*,i.status AS entry_status,i.team_id FROM v2_entries i JOIN nominations n ON n.id=i.nomination_id WHERE i.registration_id=?', rid)
    return row


def permission_guard(db, actor, person):
    return guard(db, "EXISTS(SELECT 1 FROM v2_links WHERE user_id=? AND person_id=? AND status='verified') AND EXISTS(SELECT 1 FROM v2_people WHERE id=? AND version=? AND merged_into IS NULL)", actor['id'], person['id'], person['id'], person['version'])


async def notify_statements(db, person_id, title, message, rid):
    links = await many(db, "SELECT DISTINCT user_id FROM v2_links WHERE person_id=? AND status='verified'", person_id)
    return [stmt(db, 'INSERT INTO v2_notifications(id,user_id,title,body,registration_id) VALUES(?,?,?,?,?)', uid(), l['user_id'], title, message, rid) for l in links]


def install(app, env_get, authenticate):
    async def context(request):
        env = env_get(request)
        return env.DB, plain(await authenticate(request)), env

    @app.get('/api/v2/bootstrap')
    async def bootstrap(request: Request):
        db, actor, env = await context(request)
        links = await many(db, "SELECT p.*,l.role,l.status AS link_status FROM v2_links l JOIN v2_people p ON p.id=l.person_id WHERE l.user_id=? AND l.status IN ('verified','archived') AND p.merged_into IS NULL ORDER BY p.created_at", actor['id'])
        for p in links:
            p['profile'] = json.loads(p['profile'])
        access = await many(db, 'SELECT event_id FROM v2_event_access WHERE user_id=?', actor['id'])
        events = await many(db, "SELECT id FROM events WHERE status!='draft' ORDER BY event_date DESC LIMIT 100")
        regs = await many(db, "SELECT DISTINCT r.id FROM v2_registrations r JOIN v2_links l ON l.person_id=r.person_id WHERE l.user_id=? AND l.status='verified' ORDER BY r.created_at DESC LIMIT 300", actor['id'])
        drafts = await many(db, "SELECT d.* FROM v2_drafts d JOIN v2_links l ON l.person_id=d.person_id AND l.user_id=d.user_id WHERE d.user_id=? AND l.status='verified' GROUP BY d.user_id,d.person_id,d.event_id", actor['id'])
        for draft in drafts:
            draft['payload'] = json.loads(draft['payload'])
        notes = await many(db, 'SELECT * FROM v2_notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 100', actor['id'])
        settings = await one(db, 'SELECT preferences FROM v2_settings WHERE user_id=?', actor['id'])
        legacy = await many(db, 'SELECT id,event_id,payload,created_at FROM registrations WHERE user_id=? AND id NOT IN (SELECT legacy_id FROM v2_legacy_map WHERE registration_id IS NOT NULL)', actor['id'])
        for item in legacy:
            item['payload'] = json.loads(item['payload'])
        return {'user': {**actor, 'is_admin': is_admin(actor, env)}, 'roles': ['participant','parent','coach'] + (['organizer'] if access or is_admin(actor, env) else []) + (['admin'] if is_admin(actor, env) else []), 'people': links, 'events': [await event_data(db, r['id']) for r in events], 'registrations': [await registration_data(db, r['id']) for r in regs], 'drafts': drafts, 'notifications': notes, 'settings': json.loads(settings['preferences']) if settings else {}, 'legacy': legacy}

    @app.post('/api/v2/people')
    async def create_person(request: Request):
        db, actor, env = await context(request)
        data = await body(request)
        profile = profile_data(data.get('profile'))
        role = data.get('role')
        if role not in ('self','parent','coach'):
            raise HTTPException(422, 'Выберите отношение к участнику')
        if role == 'parent' and not data.get('parent_declaration'):
            raise HTTPException(422, 'Подтвердите, что вы законный представитель ребёнка')
        key = fingerprint(profile)
        match = await one(db, 'SELECT person_id FROM v2_identity_keys WHERE fingerprint=?', key)
        if match:
            existing = await one(db, "SELECT 1 FROM v2_links WHERE user_id=? AND person_id=? AND status='verified'", actor['id'], match['person_id'])
            if existing:
                return {'id': match['person_id'], 'existing': True}
            raise HTTPException(409, 'Возможно, профиль уже существует. Используйте приглашение или запросите проверку. Чужие данные не раскрываются.')
        pid = uid()
        await atomic(db, [stmt(db, 'INSERT INTO v2_people(id,profile,fingerprint,created_by) VALUES(?,?,?,?)', pid, pack(profile), key, actor['id']), stmt(db, 'INSERT INTO v2_identity_keys VALUES(?,?)', key, pid), stmt(db, "INSERT INTO v2_links(user_id,person_id,role,status) VALUES(?,?,?,'verified')", actor['id'], pid, role), audit(db, actor, 'person.create', pid, {'role': role, 'parent_declaration': bool(data.get('parent_declaration'))})])
        return {'id': pid, 'existing': False}

    @app.put('/api/v2/people/{pid}')
    async def update_person(pid: str, request: Request):
        db, actor, env = await context(request)
        person = await person_access(db, actor, pid)
        data = await body(request)
        profile = profile_data(data.get('profile'))
        version = integer(data.get('version'), 'Версия', 1)
        changed_identity = fingerprint(profile) != person['fingerprint']
        if changed_identity:
            active = await one(db, "SELECT 1 FROM v2_registrations WHERE person_id=? AND status NOT IN ('cancelled','rejected')", pid)
            if active:
                raise HTTPException(409, 'ФИО или дата рождения меняются через проверку администратора: уже есть активная заявка.')
        statements = [permission_guard(db, actor, person), guard(db, 'EXISTS(SELECT 1 FROM v2_people WHERE id=? AND version=?)', pid, version)]
        if changed_identity:
            statements += [stmt(db, 'DELETE FROM v2_identity_keys WHERE person_id=?', pid), stmt(db, 'INSERT INTO v2_identity_keys VALUES(?,?)', fingerprint(profile), pid)]
        statements += [stmt(db, 'UPDATE v2_people SET profile=?,fingerprint=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=?', pack(profile), fingerprint(profile), pid), audit(db, actor, 'person.update', pid, {'version': version, 'identity_changed': changed_identity})]
        await atomic(db, statements)
        return {'id': pid, 'version': version+1, 'profile': profile}

    @app.post('/api/v2/people/{pid}/archive')
    async def archive(pid: str, request: Request):
        db, actor, env = await context(request)
        data = await body(request)
        status = 'archived' if data.get('archived') else 'verified'
        await atomic(db, [guard(db, "EXISTS(SELECT 1 FROM v2_links WHERE user_id=? AND person_id=? AND role='coach' AND status IN ('verified','archived'))", actor['id'], pid), stmt(db, "UPDATE v2_links SET status=? WHERE user_id=? AND person_id=? AND role='coach'", status, actor['id'], pid), audit(db, actor, 'link.archive', pid, {'status': status})])
        return {'ok': True}

    @app.put('/api/v2/drafts/{event_id}/{pid}')
    async def save_draft(event_id: int, pid: str, request: Request):
        db, actor, env = await context(request)
        person = await person_access(db, actor, pid)
        event = await event_data(db, event_id)
        if event['status'] == 'draft':
            raise HTTPException(404, 'Мероприятие не опубликовано')
        data = await body(request)
        version = integer(data.get('version', 0), 'Версия', 0)
        payload = data.get('payload', {})
        if not isinstance(payload, dict) or len(pack(payload)) > 12000:
            raise HTTPException(422, 'Некорректный черновик')
        await atomic(db, [permission_guard(db, actor, person), guard(db, 'COALESCE((SELECT version FROM v2_drafts WHERE user_id=? AND person_id=? AND event_id=?),0)=?', actor['id'], pid, event_id, version), stmt(db, 'INSERT INTO v2_drafts(user_id,person_id,event_id,payload) VALUES(?,?,?,?) ON CONFLICT(user_id,person_id,event_id) DO UPDATE SET payload=excluded.payload,version=v2_drafts.version+1,updated_at=CURRENT_TIMESTAMP', actor['id'], pid, event_id, pack(payload))])
        return {'version': version+1, 'saved': True}

    @app.delete('/api/v2/drafts/{event_id}/{pid}')
    async def delete_draft(event_id: int, pid: str, request: Request):
        db, actor, env = await context(request)
        await person_access(db, actor, pid)
        await stmt(db, 'DELETE FROM v2_drafts WHERE user_id=? AND person_id=? AND event_id=?', actor['id'], pid, event_id).run()
        return {'ok': True}

    async def submit_one(db, actor, env, event_id, data):
        pid = str(data.get('person_id', ''))
        person = await person_access(db, actor, pid)
        key = text(data.get('request_key'), 'Ключ запроса', 100, True)
        digest = hashlib.sha256(pack({k:v for k,v in data.items() if k != 'request_key'}).encode()).hexdigest()
        previous = await one(db, 'SELECT * FROM v2_requests WHERE user_id=? AND request_key=?', actor['id'], key)
        if previous:
            if previous['digest'] != digest:
                raise HTTPException(409, 'Этот ключ уже использован для другого содержимого')
            return await registration_data(db, previous['resource_id'])
        event = await event_data(db, event_id)
        now = time.time()
        if event['status'] != 'open' or not timestamp(event['registration_opens_at']) <= now <= timestamp(event['registration_closes_at'], True):
            raise HTTPException(409, 'Регистрация на мероприятие закрыта')
        existing = await one(db, 'SELECT * FROM v2_registrations WHERE event_id=? AND person_id=?', event_id, pid)
        if existing and data.get('version') is None:
            return {**await registration_data(db, existing['id']), 'existing': True}
        if existing and time.time() > timestamp(event.get('edit_closes_at') or event['registration_closes_at'], True):
            raise HTTPException(409, 'Срок изменения заявки завершён')
        if not event['rules'].strip():
            raise HTTPException(409, 'Организатор ещё не опубликовал регламент')
        if not data.get('rules_consent') or data.get('rules_version') != event['rules_version']:
            raise HTTPException(422, 'Прочитайте и подтвердите актуальный регламент')
        profile = person['profile']
        if not profile['phone']:
            raise HTTPException(422, 'Укажите контактный телефон взрослого в профиле')
        ids = data.get('nomination_ids')
        if not isinstance(ids, list) or not ids or len(ids) > 20 or len(set(ids)) != len(ids):
            raise HTTPException(422, 'Выберите от 1 до 20 разных номинаций')
        age = age_on(profile['birth_date'], event['event_date'])
        noms = []
        for nid in ids:
            n = next((n for n in event['nominations'] if n['id'] == nid and n['is_active']), None)
            if not n or not n['min_age'] <= age <= n['max_age'] or n['gender_rule'] not in ('any',profile['gender']):
                raise HTTPException(422, 'Номинация недоступна по возрасту, полу или состоянию')
            if n['battle_type'] != 'solo' or n['team_size'] != 1:
                raise HTTPException(422, 'Командная номинация требует подтверждённого состава')
            noms.append(n)
        minor = bool(event['require_parent'] and age < event['minor_age'])
        parent_consent = bool(data.get('parent_consent') and 'parent' in person['roles'])
        if data.get('parent_consent') and not parent_consent:
            raise HTTPException(403, 'Тренер не может подписать согласие родителя')
        needs_parent = minor and not parent_consent
        waitlist = bool(data.get('waitlist'))
        if waitlist and not all(n['waitlist'] for n in noms):
            raise HTTPException(422, 'Лист ожидания не включён для выбранной номинации')
        status = 'awaiting_consent' if needs_parent else ('waitlisted' if waitlist else 'submitted')
        rid = existing['id'] if existing else uid()
        statements = [permission_guard(db, actor, person), guard(db, "EXISTS(SELECT 1 FROM events WHERE id=? AND status='open' AND registration_closes_at=?)", event_id, event['registration_closes_at'])]
        if existing:
            version = integer(data.get('version'), 'Версия', 1)
            statements += [guard(db, 'EXISTS(SELECT 1 FROM v2_registrations WHERE id=? AND version=?)', rid, version), stmt(db, 'DELETE FROM v2_entries WHERE registration_id=?', rid), stmt(db, 'DELETE FROM v2_consents WHERE registration_id=?', rid), stmt(db, 'UPDATE v2_registrations SET snapshot=?,status=?,rules_version=?,version=version+1,comment=\'\',updated_at=CURRENT_TIMESTAMP WHERE id=?', pack(profile), status, event['rules_version'], rid)]
        else:
            statements += [stmt(db, 'INSERT INTO v2_registrations(id,event_id,person_id,submitted_by,status,snapshot,rules_version) VALUES(?,?,?,?,?,?,?)', rid, event_id, pid, actor['id'], status, pack(profile), event['rules_version'])]
        entry_status = 'waitlisted' if waitlist or needs_parent else 'pending'
        statements += [stmt(db, 'INSERT INTO v2_entries(registration_id,nomination_id,status) VALUES(?,?,?)', rid, n['id'], entry_status) for n in noms]
        statements += [stmt(db, "INSERT INTO v2_consents(registration_id,user_id,kind,rules_version) VALUES(?,?,'rules',?)", rid, actor['id'], event['rules_version'])]
        if parent_consent:
            statements += [stmt(db, "INSERT INTO v2_consents(registration_id,user_id,kind,rules_version) VALUES(?,?,'parent',?)", rid, actor['id'], event['rules_version'])]
        statements += [stmt(db, 'INSERT INTO v2_requests(user_id,request_key,digest,resource_id) VALUES(?,?,?,?)', actor['id'], key, digest, rid), stmt(db, 'DELETE FROM v2_drafts WHERE user_id=? AND person_id=? AND event_id=?', actor['id'], pid, event_id), audit(db, actor, 'registration.submit', rid, {'status':status,'person_id':pid})]
        statements += await notify_statements(db,pid,'Заявка сохранена', 'Нужно согласие родителя' if needs_parent else 'Ожидается решение организатора',rid)
        try:
            await atomic(db, statements)
        except HTTPException as exc:
            if exc.status_code == 409:
                replay = await one(db, 'SELECT * FROM v2_requests WHERE user_id=? AND request_key=?', actor['id'], key)
                if replay and replay['digest'] == digest:
                    return await registration_data(db, replay['resource_id'])
            raise
        return await registration_data(db, rid)

    @app.post('/api/v2/events/{event_id}/registrations')
    async def submit(event_id: int, request: Request):
        db, actor, env = await context(request)
        return await submit_one(db, actor, env, event_id, await body(request))

    @app.post('/api/v2/events/{event_id}/batch')
    async def batch_submit(event_id: int, request: Request):
        db, actor, env = await context(request)
        data = await body(request)
        items = data.get('items')
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            raise HTTPException(422, 'За один раз можно отправить от 1 до 20 заявок')
        results=[]
        for item in items:
            try:
                result = await submit_one(db, actor, env, event_id, item)
                results.append({'person_id':item.get('person_id'), 'ok':True, 'registration':result})
            except HTTPException as exc:
                results.append({'person_id':item.get('person_id'), 'ok':False, 'error':exc.detail, 'status':exc.status_code})
        return {'results':results}

    @app.get('/api/v2/registrations/{rid}')
    async def get_registration(rid: str, request: Request):
        db, actor, env = await context(request)
        registration = await registration_data(db, rid)
        try:
            await person_access(db, actor, registration['person_id'])
        except HTTPException:
            await organizer(db, actor, env, registration['event_id'])
        return registration

    @app.post('/api/v2/registrations/{rid}/cancel')
    async def cancel(rid: str, request: Request):
        db, actor, env = await context(request)
        reg = await registration_data(db, rid)
        person = await person_access(db, actor, reg['person_id'])
        data = await body(request)
        if reg['status'] == 'cancelled':
            return reg
        await atomic(db, [permission_guard(db, actor, person), guard(db, 'EXISTS(SELECT 1 FROM v2_registrations WHERE id=? AND version=?)',rid,integer(data.get('version'),'Версия',1)), stmt(db,"UPDATE v2_registrations SET status='cancelled',version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",rid), stmt(db,"UPDATE v2_entries SET status='cancelled' WHERE registration_id=?",rid), audit(db,actor,'registration.cancel',rid,{'reason':text(data.get('reason'),'Причина',1000)})])
        return await registration_data(db,rid)

    @app.post('/api/v2/people/{pid}/invites')
    async def create_invite(pid: str, request: Request):
        db, actor, env = await context(request)
        person = await person_access(db,actor,pid)
        data = await body(request)
        role = data.get('role')
        if role not in ('parent','coach','self'):
            raise HTTPException(422,'Выберите роль приглашённого')
        token = uid()+uid()
        expires = int(time.time())+86400
        await atomic(db,[permission_guard(db,actor,person),stmt(db,'INSERT INTO v2_invites(token_hash,person_id,created_by,role,expires_at) VALUES(?,?,?,?,?)',hashlib.sha256(token.encode()).hexdigest(),pid,actor['id'],role,expires),audit(db,actor,'invite.create',pid,{'role':role})])
        return {'code':token,'expires_at':expires,'url':str(getattr(env,'WEBAPP_URL','')).split('?')[0]+'?invite='+token}

    @app.post('/api/v2/invites/accept')
    async def accept_invite(request: Request):
        db, actor, env = await context(request)
        data=await body(request)
        hashed=hashlib.sha256(text(data.get('code'),'Код',200,True).encode()).hexdigest()
        invite=await one(db,'SELECT * FROM v2_invites WHERE token_hash=?',hashed)
        if not invite or invite['expires_at']<time.time() or invite['status']!='pending':
            raise HTTPException(410,'Приглашение истекло, отозвано или уже использовано')
        if invite['created_by']==actor['id']:
            raise HTTPException(422,'Это ваше приглашение. Передайте его другому человеку')
        await atomic(db,[guard(db,"EXISTS(SELECT 1 FROM v2_invites WHERE token_hash=? AND status='pending' AND expires_at>?)",hashed,int(time.time())),stmt(db,"UPDATE v2_invites SET claimed_by=?,status='claimed' WHERE token_hash=?",actor['id'],hashed),audit(db,actor,'invite.claim',invite['person_id'],{'role':invite['role']})])
        return {'status':'pending','message':'Запрос принят. Доступ появится после подтверждения отправителем; родительскую связь проверяет администратор.'}

    @app.get('/api/v2/invites')
    async def invites(request: Request):
        db, actor, env = await context(request)
        condition = '1=1' if is_admin(actor,env) else '(i.created_by=? OR i.claimed_by=?)'
        args=[] if is_admin(actor,env) else [actor['id'],actor['id']]
        rows=await many(db,'SELECT i.*,u.first_name,u.last_name,u.telegram_id FROM v2_invites i LEFT JOIN users u ON u.id=i.claimed_by WHERE '+condition+' ORDER BY i.expires_at DESC LIMIT 100',*args)
        # Hash identifies the record but cannot be used as the invitation bearer token.
        return rows

    @app.post('/api/v2/invites/{invite_id}/decide')
    async def decide_invite(invite_id: str,request: Request):
        db, actor, env = await context(request)
        data=await body(request)
        invite=await one(db,'SELECT * FROM v2_invites WHERE token_hash=?',invite_id)
        if not invite:
            raise HTTPException(404,'Приглашение не найдено')
        admin=is_admin(actor,env)
        if not admin and invite['created_by']!=actor['id']:
            raise HTTPException(403,'Недостаточно прав')
        approve=data.get('approve') is True
        if approve and invite['role'] in ('parent','self') and not admin:
            raise HTTPException(403,'Связь родителя или владельца подтверждает администратор')
        if approve and (invite['status']!='claimed' or invite['expires_at']<time.time()):
            raise HTTPException(409,'Приглашение уже недействительно')
        statements=[guard(db,'EXISTS(SELECT 1 FROM v2_invites WHERE token_hash=? AND status=?)',invite_id,invite['status'])]
        if not admin:
            person=await person_access(db,actor,invite['person_id'])
            statements.append(permission_guard(db,actor,person))
        if approve:
            statements.append(stmt(db,"INSERT INTO v2_links(user_id,person_id,role,status) VALUES(?,?,?,'verified') ON CONFLICT(user_id,person_id,role) DO UPDATE SET status='verified'",invite['claimed_by'],invite['person_id'],invite['role']))
        statements += [stmt(db,'UPDATE v2_invites SET status=? WHERE token_hash=?','accepted' if approve else 'revoked',invite_id),audit(db,actor,'invite.decide',invite['person_id'],{'role':invite['role'],'recipient':invite['claimed_by'],'approve':approve})]
        await atomic(db,statements)
        return {'ok':True}

    @app.get('/api/v2/people/{pid}/links')
    async def get_links(pid: str,request: Request):
        db, actor, env = await context(request)
        await person_access(db,actor,pid)
        return await many(db,"SELECT l.user_id,l.role,l.status,u.first_name,u.last_name FROM v2_links l JOIN users u ON u.id=l.user_id WHERE l.person_id=?",pid)

    @app.post('/api/v2/people/{pid}/revoke')
    async def revoke_link(pid: str,request: Request):
        db, actor, env = await context(request)
        person=await person_access(db,actor,pid)
        data=await body(request)
        target=integer(data.get('user_id'),'Пользователь',1)
        if not is_admin(actor,env) and not any(r in person['roles'] for r in ('self','parent')):
            raise HTTPException(403,'Недостаточно прав')
        await atomic(db,[permission_guard(db,actor,person),stmt(db,"UPDATE v2_links SET status='revoked' WHERE person_id=? AND user_id=? AND role='coach'",pid,target),audit(db,actor,'link.revoke',pid,{'user_id':target,'role':'coach'})])
        return {'ok':True}

    @app.post('/api/v2/cases')
    async def create_case(request: Request):
        db, actor, env = await context(request)
        data=await body(request)
        kind=data.get('kind','support')
        if kind not in ('support','identity','deletion','restore'):
            raise HTTPException(422,'Неизвестный тип обращения')
        message=text(data.get('message'),'Сообщение',2000,True)
        pending=await one(db,"SELECT COUNT(*) AS count FROM v2_cases WHERE user_id=? AND status='pending'",actor['id'])
        if pending['count']>=10:
            raise HTTPException(429,'Дождитесь ответа на открытые обращения')
        cid=uid()
        profile=profile_data(data['profile']) if data.get('profile') else None
        await stmt(db,'INSERT INTO v2_cases(id,user_id,kind,payload) VALUES(?,?,?,?)',cid,actor['id'],kind,pack({'message':message,'profile':profile})).run()
        return {'id':cid,'status':'pending'}

    @app.get('/api/v2/cases')
    async def list_cases(request: Request):
        db, actor, env = await context(request)
        rows=await many(db,'SELECT * FROM v2_cases WHERE user_id=? ORDER BY created_at DESC LIMIT 100',actor['id'])
        for row in rows: row['payload']=json.loads(row['payload'])
        return rows

    @app.put('/api/v2/settings')
    async def settings(request: Request):
        db, actor, env = await context(request)
        data=await body(request)
        value={k:bool(data.get(k,True)) for k in ('telegram_notifications','reminders')}
        await stmt(db,'INSERT INTO v2_settings VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET preferences=excluded.preferences',actor['id'],pack(value)).run()
        return value

    @app.post('/api/v2/notifications/read')
    async def read_notifications(request: Request):
        db, actor, env = await context(request)
        await stmt(db,'UPDATE v2_notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=? AND read_at IS NULL',actor['id']).run()
        return {'ok':True}

    @app.get('/api/v2/manage/events')
    async def manage_events(request: Request):
        db, actor, env = await context(request)
        rows=await many(db,'SELECT id FROM events ORDER BY event_date DESC LIMIT 200') if is_admin(actor,env) else await many(db,'SELECT event_id AS id FROM v2_event_access WHERE user_id=?',actor['id'])
        return [await event_data(db,row['id']) for row in rows]

    @app.post('/api/v2/manage/events')
    async def create_event(request: Request):
        db, actor, env = await context(request)
        await organizer(db,actor,env)
        data=await body(request)
        title=text(data.get('title'),'Название',160,True)
        event_date=text(data.get('event_date'),'Дата',10,True)
        try: date.fromisoformat(event_date)
        except ValueError: raise HTTPException(422,'Укажите дату события') from None
        result=await stmt(db,"INSERT INTO events(title,event_date,place,registration_opens_at,registration_closes_at,status) VALUES(?,?,?,?,?,'draft')",title,event_date,text(data.get('place'),'Место',250),event_date,event_date).run()
        event_id=int(result.meta.last_row_id)
        await stmt(db,'INSERT INTO v2_event_settings(event_id) VALUES(?)',event_id).run()
        await audit(db,actor,'event.create',event_id,{'title':title}).run()
        return await event_data(db,event_id)

    @app.put('/api/v2/manage/events/{event_id}')
    async def update_event(event_id: int,request: Request):
        db, actor, env = await context(request)
        await organizer(db,actor,env,event_id)
        current=await event_data(db,event_id)
        data=await body(request)
        version=integer(data.get('version'),'Версия',0)
        title=text(data.get('title'),'Название',160,True)
        place=text(data.get('place'),'Место',250,True)
        event_date=text(data.get('event_date'),'Дата',10,True)
        try: date.fromisoformat(event_date)
        except ValueError: raise HTTPException(422,'Укажите дату события') from None
        opens=text(data.get('registration_opens_at'),'Открытие',40,True)
        closes=text(data.get('registration_closes_at'),'Закрытие',40,True)
        edit=text(data.get('edit_closes_at') or closes,'Срок правок',40,True)
        if timestamp(opens)>=timestamp(closes,True) or timestamp(closes,True)>timestamp(event_date,True) or timestamp(edit,True)>timestamp(event_date,True):
            raise HTTPException(422,'Проверьте порядок дат: открытие, закрытие, мероприятие')
        rules=str(data.get('rules','')).strip()
        if len(rules)>20000:
            raise HTTPException(422,'Регламент: максимум 20000 символов')
        status=data.get('status','draft')
        if status not in ('draft','open','closed','archived','cancelled'):
            raise HTTPException(422,'Некорректный статус')
        if status=='open' and (not rules or not any(n['is_active'] for n in current['nominations'])):
            raise HTTPException(422,'Для открытия нужны регламент и хотя бы одна номинация')
        active=await one(db,"SELECT COUNT(*) AS count FROM v2_registrations WHERE event_id=? AND status NOT IN ('cancelled','rejected')",event_id)
        require_parent=1 if data.get('require_parent',True) else 0
        minor_age=integer(data.get('minor_age',18),'Возраст согласия',0,21)
        if active['count'] and (event_date!=current['event_date'] or rules!=current['rules'] or require_parent!=current['require_parent'] or minor_age!=current['minor_age'] or status=='draft'):
            raise HTTPException(409,'Есть активные заявки. Изменение даты, регламента и правил согласия требует отдельной проверки.')
        statements=[guard(db,'COALESCE((SELECT version FROM v2_event_settings WHERE event_id=?),0)=?',event_id,version)]
        if not is_admin(actor,env): statements.append(guard(db,'EXISTS(SELECT 1 FROM v2_event_access WHERE event_id=? AND user_id=?)',event_id,actor['id']))
        statements += [stmt(db,'UPDATE events SET title=?,place=?,event_date=?,description=?,registration_opens_at=?,registration_closes_at=?,status=? WHERE id=?',title,place,event_date,text(data.get('description'),'Описание',5000),opens,closes,status,event_id),stmt(db,'INSERT INTO v2_event_settings(event_id,rules,rules_version,minor_age,require_parent,edit_closes_at,version) VALUES(?,?,?,?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET rules=excluded.rules,rules_version=excluded.rules_version,minor_age=excluded.minor_age,require_parent=excluded.require_parent,edit_closes_at=excluded.edit_closes_at,version=excluded.version',event_id,rules,current['rules_version']+(rules!=current['rules']),minor_age,require_parent,edit,version+1),audit(db,actor,'event.update',event_id,{'status':status,'version':version})]
        await atomic(db,statements)
        return await event_data(db,event_id)

    @app.put('/api/v2/manage/events/{event_id}/nominations')
    async def save_nomination(event_id: int,request: Request):
        db, actor, env = await context(request)
        await organizer(db,actor,env,event_id)
        event=await event_data(db,event_id)
        data=await body(request)
        nid=data.get('id')
        active=await one(db,"SELECT 1 FROM v2_entries WHERE nomination_id=? AND status!='cancelled'",nid) if nid else None
        if active:
            raise HTTPException(409,'В номинации есть заявки. Правила нельзя менять без проверки участников.')
        minimum=integer(data.get('min_age',0),'Минимальный возраст',0,120)
        maximum=integer(data.get('max_age',99),'Максимальный возраст',minimum,120)
        gender=data.get('gender_rule','any')
        if gender not in ('any','male','female'): raise HTTPException(422,'Выберите правило пола')
        capacity=integer(data['capacity'],'Лимит',1,100000) if data.get('capacity') not in ('',None) else None
        title=text(data.get('title'),'Название',120,True)
        # Team nominations are kept out of publication until team consent is implemented.
        if data.get('battle_type','solo')!='solo':
            raise HTTPException(422,'Сейчас доступны индивидуальные номинации. Командные требуют отдельного состава и согласий.')
        if nid and not any(n['id']==nid for n in event['nominations']): raise HTTPException(404,'Номинация не найдена')
        values=(title,minimum,maximum,gender,int(data.get('is_active',True)),integer(data.get('sort_order',100),'Порядок',0,10000))
        if nid:
            await stmt(db,'UPDATE nominations SET title=?,min_age=?,max_age=?,gender_rule=?,is_active=?,sort_order=? WHERE id=? AND event_id=?',*values,nid,event_id).run()
        else:
            result=await stmt(db,'INSERT INTO nominations(title,min_age,max_age,gender_rule,is_active,sort_order,event_id) VALUES(?,?,?,?,?,?,?)',*values,event_id).run()
            nid=int(result.meta.last_row_id)
        await stmt(db,'INSERT INTO v2_nomination_settings(nomination_id,capacity,waitlist) VALUES(?,?,?) ON CONFLICT(nomination_id) DO UPDATE SET capacity=excluded.capacity,waitlist=excluded.waitlist',nid,capacity,int(data.get('waitlist',False))).run()
        await audit(db,actor,'nomination.save',nid,{'event_id':event_id}).run()
        return await event_data(db,event_id)

    @app.get('/api/v2/manage/events/{event_id}/registrations')
    async def event_registrations(event_id: int,request: Request):
        db, actor, env = await context(request)
        await organizer(db,actor,env,event_id)
        rows=await many(db,'SELECT id FROM v2_registrations WHERE event_id=? ORDER BY created_at DESC LIMIT 1000',event_id)
        return [await registration_data(db,r['id']) for r in rows]

    @app.post('/api/v2/manage/registrations/{rid}/decision')
    async def decision(rid: str,request: Request):
        db, actor, env = await context(request)
        reg=await registration_data(db,rid)
        await organizer(db,actor,env,reg['event_id'])
        data=await body(request)
        status=data.get('status')
        if status not in ('confirmed','needs_changes','rejected'): raise HTTPException(422,'Выберите решение')
        comment=text(data.get('comment'),'Комментарий',1000,status!='confirmed')
        if reg['status'] in ('cancelled','awaiting_consent'):
            raise HTTPException(409,'Сначала нужны активная заявка и согласия')
        event=await event_data(db,reg['event_id'])
        if reg['rules_version']!=event['rules_version']: raise HTTPException(409,'Нужен актуальный регламент')
        statements=[guard(db,'EXISTS(SELECT 1 FROM v2_registrations WHERE id=? AND version=?)',rid,integer(data.get('version'),'Версия',1))]
        if not is_admin(actor,env): statements.append(guard(db,'EXISTS(SELECT 1 FROM v2_event_access WHERE event_id=? AND user_id=?)',reg['event_id'],actor['id']))
        statements += [stmt(db,'UPDATE v2_registrations SET status=?,comment=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=?',status,comment,rid),stmt(db,'UPDATE v2_entries SET status=? WHERE registration_id=?','confirmed' if status=='confirmed' else 'cancelled' if status=='rejected' else 'pending',rid),audit(db,actor,'registration.decision',rid,{'status':status,'comment':comment})]
        statements += await notify_statements(db,reg['person_id'],'Статус заявки изменён',{'confirmed':'Участие подтверждено','needs_changes':'Нужно уточнение','rejected':'Заявка отклонена'}[status]+('. '+comment if comment else ''),rid)
        await atomic(db,statements)
        return await registration_data(db,rid)

    @app.get('/api/v2/export')
    async def export(request: Request,event_id: int | None=None,scope: str='mine',status: str='all'):
        db, actor, env = await context(request)
        if scope=='event':
            await organizer(db,actor,env,event_id)
            rows=await many(db,'SELECT id FROM v2_registrations WHERE event_id=?',event_id)
        else:
            rows=await many(db,"SELECT DISTINCT r.id FROM v2_registrations r JOIN v2_links l ON l.person_id=r.person_id WHERE l.user_id=? AND l.status='verified' AND (? IS NULL OR r.event_id=?)",actor['id'],event_id,event_id)
        output=io.StringIO(); writer=csv.writer(output,delimiter=';')
        writer.writerow(['Номер','Мероприятие','ФИО','Никнейм','Клуб','Номинации','Статус'])
        for row in rows:
            reg=await registration_data(db,row['id'])
            if status!='all' and reg['status']!=status: continue
            p=reg['snapshot']
            values=[reg['id'],reg['event_title'],p['full_name'],p['nickname'],p['club'],', '.join(n['title'] for n in reg['nominations']),reg['status']]
            writer.writerow(["'"+str(v) if str(v).lstrip().startswith(('=','+','-','@','\t','\r')) else v for v in values])
        await audit(db,actor,'export',event_id or 'mine',{'scope':scope,'status':status}).run()
        return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="verum-participants.csv"','Cache-Control':'no-store'})

    @app.get('/api/v2/admin/{section}')
    async def admin_list(section: str,request: Request):
        db, actor, env = await context(request)
        await organizer(db,actor,env)
        queries={'users':'SELECT id,telegram_id,first_name,last_name,telegram_username FROM users ORDER BY id DESC LIMIT 500','audit':'SELECT * FROM v2_audit ORDER BY created_at DESC LIMIT 300','cases':'SELECT c.*,u.first_name,u.telegram_id FROM v2_cases c JOIN users u ON u.id=c.user_id ORDER BY c.created_at DESC LIMIT 300','access':'SELECT a.*,u.telegram_id,u.first_name,e.title FROM v2_event_access a JOIN users u ON u.id=a.user_id JOIN events e ON e.id=a.event_id','people':'SELECT * FROM v2_people WHERE merged_into IS NULL ORDER BY created_at DESC LIMIT 500'}
        if section not in queries: raise HTTPException(404,'Раздел не найден')
        rows=await many(db,queries[section])
        for row in rows:
            for key in ('profile','payload','details'):
                if key in row: row[key]=json.loads(row[key])
        return rows

    @app.post('/api/v2/admin/access')
    async def set_access(request: Request):
        db, actor, env = await context(request)
        await organizer(db,actor,env)
        data=await body(request)
        target=await one(db,'SELECT id FROM users WHERE telegram_id=?',integer(data.get('telegram_id'),'Telegram ID',1,2**53-1))
        if not target: raise HTTPException(404,'Пользователь должен сначала открыть бота')
        event_id=integer(data.get('event_id'),'Событие',1)
        await event_data(db,event_id)
        sql='INSERT OR IGNORE INTO v2_event_access(user_id,event_id) VALUES(?,?)' if data.get('enabled') else 'DELETE FROM v2_event_access WHERE user_id=? AND event_id=?'
        await atomic(db,[stmt(db,sql,target['id'],event_id),audit(db,actor,'access.change',event_id,{'user_id':target['id'],'enabled':bool(data.get('enabled'))})])
        return {'ok':True}

    @app.post('/api/v2/admin/cases/{cid}')
    async def resolve_case(cid: str,request: Request):
        db, actor, env = await context(request)
        await organizer(db,actor,env)
        data=await body(request)
        case=await one(db,'SELECT * FROM v2_cases WHERE id=?',cid)
        if not case: raise HTTPException(404,'Обращение не найдено')
        resolution=text(data.get('resolution'),'Ответ',2000,True)
        await atomic(db,[guard(db,"EXISTS(SELECT 1 FROM v2_cases WHERE id=? AND status='pending')",cid),stmt(db,"UPDATE v2_cases SET status='resolved',resolution=? WHERE id=?",resolution,cid),stmt(db,'INSERT INTO v2_notifications(id,user_id,title,body) VALUES(?,?,?,?)',uid(),case['user_id'],'Ответ поддержки',resolution),audit(db,actor,'case.resolve',cid,{'resolution':resolution})])
        return {'ok':True}

    @app.get('/api/v2/my-data')
    async def my_data(request: Request):
        data=await bootstrap(request)
        data.pop('events',None)
        return Response(pack(data),media_type='application/json',headers={'Content-Disposition':'attachment; filename="verum-my-data.json"','Cache-Control':'no-store'})

    @app.post('/api/v2/registrations/{rid}/consent')
    async def consent(rid: str, request: Request):
        db, actor, env = await context(request)
        reg = await registration_data(db, rid)
        person = await person_access(db, actor, reg['person_id'])
        event = await event_data(db,reg['event_id'])
        data = await body(request)
        if 'parent' not in person['roles']:
            raise HTTPException(403,'Только подтверждённый родитель может дать согласие')
        if not data.get('parent_consent') or not data.get('rules_consent') or data.get('rules_version') != event['rules_version'] or reg['rules_version'] != event['rules_version']:
            raise HTTPException(422,'Подтвердите актуальный регламент и согласие родителя')
        if event['status']!='open' or time.time()>timestamp(event['registration_closes_at'],True):
            raise HTTPException(409,'Регистрация закрыта. Свяжитесь с организатором')
        if reg['status']!='awaiting_consent':
            raise HTTPException(409,'Статус заявки уже изменён')
        waitlist = bool(data.get('waitlist'))
        if waitlist and not all(n['waitlist'] for n in event['nominations'] if n['id'] in [x['id'] for x in reg['nominations']]):
            raise HTTPException(422,'Лист ожидания не включён')
        statements=[permission_guard(db,actor,person),guard(db,'EXISTS(SELECT 1 FROM v2_registrations WHERE id=? AND version=?)',rid,integer(data.get('version'),'Версия',1)),stmt(db,"INSERT INTO v2_consents(registration_id,user_id,kind,rules_version) VALUES(?,?,'parent',?)",rid,actor['id'],event['rules_version']),stmt(db,'UPDATE v2_registrations SET status=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=?','waitlisted' if waitlist else 'submitted',rid),stmt(db,'UPDATE v2_entries SET status=? WHERE registration_id=?','waitlisted' if waitlist else 'pending',rid),audit(db,actor,'registration.consent',rid,{'version':event['rules_version']})]
        statements+=await notify_statements(db,reg['person_id'],'Согласие получено','Заявка передана на проверку',rid)
        await atomic(db,statements)
        return await registration_data(db,rid)
