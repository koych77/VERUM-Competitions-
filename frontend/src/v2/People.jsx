import React,{useState} from 'react';
import { api } from '../api/client';
import {Button,Field,Select,CheckField,Notice,Row,Heading,Empty,roleNames} from './ui';

export const blank={full_name:'',nickname:'',birth_date:'',gender:'unspecified',phone:'',city:'',club:'',trainer:''};

export function People({data,role,go}){
  const [query,setQuery]=useState(''),[archive,setArchive]=useState(false);
  const linkRole=role==='parent'?'parent':role==='coach'?'coach':'self';
  const people=data.people.filter(p=>p.role===linkRole&&(archive?p.link_status==='archived':p.link_status==='verified')&&p.profile.full_name.toLowerCase().includes(query.toLowerCase()));
  return <><Heading title={role==='parent'?'Мои дети':role==='coach'?'Моя команда':'Мой профиль'} subtitle="Сохранённые профили подставляются в заявки."/>
    <Field label="Поиск" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Имя участника"/>
    {role==='coach'&&<CheckField checked={archive} onChange={e=>setArchive(e.target.checked)}>Показать архив</CheckField>}
    {!people.length&&<Empty title={query?'Никого не найдено':'Пока нет профилей'}>Добавьте участника или примите приглашение к существующему профилю.</Empty>}
    <div className="rows">{people.map(p=><Row key={p.id+p.role} title={p.profile.full_name} description={[p.profile.nickname,p.profile.club].filter(Boolean).join(' · ')} status={p.link_status} onClick={()=>go('person',{person:p})}/>)}</div>
    <div className="actions"><Button onClick={()=>go('person',{linkRole})}>{role==='parent'?'Добавить ребёнка':role==='coach'?'Добавить ученика':'Создать профиль'}</Button><Button secondary onClick={()=>go('invites')}>Приглашения и доступ</Button></div></>;
}

export function PersonForm({person,linkRole,go,run,refresh}){
  const [form,setForm]=useState({...blank,...person?.profile}),[declaration,setDeclaration]=useState(false),[saved,setSaved]=useState(false),[version,setVersion]=useState(person?.version||0);
  const [duplicate,setDuplicate]=useState(false),[busy,setBusy]=useState(false);
  const role=linkRole||person?.role||'self';
  const update=key=>e=>{setForm(f=>({...f,[key]:e.target.value}));setSaved(false)};
  async function save(event){event.preventDefault();setBusy(true);try{await run(async()=>{try{const result=await api(person?`/api/v2/people/${person.id}`:'/api/v2/people',{method:person?'PUT':'POST',body:JSON.stringify({profile:form,role,parent_declaration:declaration,version})});setVersion(result.version||1);setSaved(true);await refresh();if(!person)go('people')}catch(e){if(e.status===409)setDuplicate(true);throw e}})}finally{setBusy(false)}}
  return <><Heading title={person?'Проверьте профиль':role==='parent'?'Добавить ребёнка':role==='coach'?'Добавить ученика':'Ваш профиль'} subtitle="Заполните один раз. Для ребёнка укажите телефон контактного взрослого." onBack={()=>go('people')}/>
    <form onSubmit={save} className="stack">
      <Field label="ФИО *" value={form.full_name} onChange={update('full_name')} required maxLength={160} autoComplete="name"/>
      <Field label="Никнейм" value={form.nickname} onChange={update('nickname')} maxLength={48} hint="Без автоматической приставки Bboy / Bgirl"/>
      <Field label="Дата рождения *" type="date" value={form.birth_date} onChange={update('birth_date')} required max={new Date().toISOString().slice(0,10)}/>
      <Select label="Пол для допуска в номинацию" value={form.gender} onChange={v=>setForm(f=>({...f,gender:v}))} options={[['unspecified','Не указан'],['male','Мужской'],['female','Женский']]}/>
      <Field label="Город *" value={form.city} onChange={update('city')} required maxLength={100}/>
      <Field label="Телефон контактного взрослого" type="tel" value={form.phone} onChange={update('phone')} placeholder="+375291234567" hint="Нужен для подачи заявки. Не показывается публично."/>
      <Field label="Клуб" value={form.club} onChange={update('club')} maxLength={100}/>
      <Field label="Тренер" value={form.trainer} onChange={update('trainer')} maxLength={100} hint="Запись имени тренера не выдаёт ему доступ к профилю."/>
      {!person&&role==='parent'&&<CheckField checked={declaration} onChange={e=>setDeclaration(e.target.checked)} required>Я законный представитель ребёнка</CheckField>}
      {saved&&<Notice tone="success" title="Профиль сохранён">Данные подтверждены сервером и доступны с другого устройства после входа.</Notice>}
      {duplicate&&<Notice tone="warn" title="Нужна проверка">Если участник уже добавлен другим представителем, используйте приглашение. Совпадения имён не объединяются автоматически.</Notice>}
      <Button type="submit" disabled={busy}>{busy?'Сохраняем…':'Сохранить профиль'}</Button>
      {duplicate&&<Button secondary onClick={()=>go('support',{kind:'identity',profile:form})}>Запросить проверку профиля</Button>}
    </form>
    {person&&<div className="actions"><Button secondary onClick={()=>go('links',{person})}>Кто имеет доступ</Button><Button secondary onClick={()=>go('invite-create',{person})}>Пригласить представителя</Button>{person.role==='coach'&&<Button secondary onClick={()=>go('confirm',{title:person.link_status==='archived'?'Вернуть ученика в команду?':'Архивировать ученика?',message:'Изменится только ваш состав. Профиль и заявки не удалятся.',action:async()=>{await api(`/api/v2/people/${person.id}/archive`,{method:'POST',body:JSON.stringify({archived:person.link_status!=='archived'})});await refresh();go('people')}})}>{person.link_status==='archived'?'Вернуть в команду':'Архивировать в моей команде'}</Button>}</div>}
  </>;
}

export function Invitations({data,go,run,refresh,person,create=false}){
  const [code,setCode]=useState(new URLSearchParams(location.search).get('invite')||''),[role,setRole]=useState('coach'),[result,setResult]=useState(null),[list,setList]=useState(null);
  React.useEffect(()=>{run(async()=>setList(await api('/api/v2/invites')))},[]);
  const reload=async()=>{setList(await api('/api/v2/invites'));await refresh()};
  return <><Heading title={create?'Пригласить представителя':'Приглашения и доступ'} subtitle={person?.profile.full_name||'Доступ появляется только после подтверждения связи.'} onBack={()=>go('people')}/>
    {create?<><Select label="Кого приглашаем" value={role} onChange={setRole} options={[['coach','Тренер'],['parent','Родитель'],['self','Сам участник']]}/><Notice title="Кому можно передать ссылку">Только нужному человеку. После принятия проверьте получателя; родительские связи подтверждает администратор.</Notice><Button onClick={()=>run(async()=>setResult(await api(`/api/v2/people/${person.id}/invites`,{method:'POST',body:JSON.stringify({role})})))}>Создать приглашение</Button>{result&&<section className="stack"><Field label="Код приглашения" value={result.code} readOnly/><Button secondary onClick={()=>run(async()=>{await navigator.clipboard.writeText(result.code);setResult(r=>({...r,copied:true}))})}>{result.copied?'Скопировано':'Скопировать код'}</Button><p className="hint">Срок действия: 24 часа. Получатель открывает VERUM и вставляет код в «Приглашения».</p></section>}</>:<form onSubmit={e=>{e.preventDefault();run(async()=>{const r=await api('/api/v2/invites/accept',{method:'POST',body:JSON.stringify({code:code.includes('invite=')?new URL(code).searchParams.get('invite'):code.trim()})});setResult(r);await reload()})}} className="stack"><Field label="Код приглашения" value={code} onChange={e=>setCode(e.target.value)} required/><Button type="submit">Принять приглашение</Button>{result&&<Notice tone="success" title="Запрос отправлен">{result.message}</Notice>}</form>}
    <h2>Ваши приглашения</h2>{list?.length===0&&<p className="hint">Приглашений пока нет.</p>}{list?.map(i=><section className="record" key={i.token_hash}><Row title={i.first_name?`${i.first_name} ${i.last_name||''}`:'Ожидает получателя'} description={`Роль: ${roleNames[i.role]||'Владелец профиля'}`} status={i.status}/>{i.status==='claimed'&&(i.created_by===data.user.id||data.user.is_admin)&&<><Notice title="Проверьте получателя">Telegram ID: {i.telegram_id}. Подтверждайте только знакомую, проверенную связь.</Notice>{(i.role==='coach'||data.user.is_admin)&&<Button onClick={()=>go('confirm',{title:'Подтвердить доступ?',message:`Получатель: ${i.first_name||''}, Telegram ID ${i.telegram_id}. Он получит доступ к связанному профилю и заявкам.`,action:async()=>{await api(`/api/v2/invites/${i.token_hash}/decide`,{method:'POST',body:JSON.stringify({approve:true})});await reload();go('invites')}})}>Подтвердить получателя</Button>}{i.role!=='coach'&&!data.user.is_admin&&<p className="hint">Ожидается проверка администратором.</p>}</>}{['pending','claimed'].includes(i.status)&&(i.created_by===data.user.id||data.user.is_admin)&&<Button secondary onClick={()=>run(async()=>{await api(`/api/v2/invites/${i.token_hash}/decide`,{method:'POST',body:JSON.stringify({approve:false})});await reload()})}>Отозвать приглашение</Button>}</section>)}
  </>;
}

export function Links({person,data,go,run,refresh}){
  const [links,setLinks]=useState(null);
  React.useEffect(()=>{run(async()=>setLinks(await api(`/api/v2/people/${person.id}/links`)))},[person.id]);
  return <><Heading title="Кто имеет доступ" subtitle={person.profile.full_name} onBack={()=>go('person',{person})}/>{links?.map(l=><section key={l.user_id+l.role} className="record"><Row title={[l.first_name,l.last_name].filter(Boolean).join(' ')||'Участник'} description={l.role==='self'?'Владелец профиля':roleNames[l.role]} status={l.status}/>{l.role==='coach'&&l.status==='verified'&&(person.role==='self'||person.role==='parent')&&<Button secondary onClick={()=>go('confirm',{title:'Отозвать доступ тренера?',message:'Заявки и история останутся. Тренер больше не сможет изменять профиль.',action:async()=>{await api(`/api/v2/people/${person.id}/revoke`,{method:'POST',body:JSON.stringify({user_id:l.user_id})});await refresh();go('people')}})}>Отозвать доступ</Button>}</section>)}<Button onClick={()=>go('invite-create',{person})}>Пригласить представителя</Button></>;
}
