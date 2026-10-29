import React,{useState,useEffect,useCallback,useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {CalendarDays,Users,ClipboardList,Bell,Settings,ShieldCheck} from 'lucide-react';
import {api,login,downloadFile} from '../api/client';
import {Button,Field,Select,Heading,Notice,Row,Empty,Poster,roleNames,dateLabel} from './ui';
import {People,PersonForm,Invitations,Links} from './People';
import {SelectPeople,RegistrationFlow,Registrations,RegistrationDetail} from './Registration';
import {Manage,NewEvent,ManageEvent,Nominations,ManageRegistrations,Decision,Export,Admin,AdminList} from './Manage';
import './app.css';

function Support({go,run,kind:initial='support',message:initialMessage='',profile}){
  const [kind,setKind]=useState(initial),[message,setMessage]=useState(initialMessage),[cases,setCases]=useState(null),[busy,setBusy]=useState(false),[sent,setSent]=useState(false);
  const load=async()=>setCases(await api('/api/v2/cases'));
  useEffect(()=>{run(load)},[]);
  return <><Heading title="Помощь и обращения" subtitle="Не присылайте пароли, документы и токены. Ответ будет доступен здесь." onBack={()=>go('settings')}/><form className="stack" onSubmit={e=>{e.preventDefault();setBusy(true);run(async()=>{await api('/api/v2/cases',{method:'POST',body:JSON.stringify({kind,message,profile})});setSent(true);setMessage('');await load()}).finally(()=>setBusy(false))}}><Select label="Тема" value={kind} onChange={setKind} options={[['support','Вопрос'],['identity','Проверка профиля / дубля'],['restore','Восстановление'],['deletion','Запрос удаления данных']]}/><Field label="Сообщение"><textarea rows={5} value={message} onChange={e=>{setMessage(e.target.value);setSent(false)}} required maxLength={2000}/></Field><Button type="submit" disabled={busy}>{busy?'Отправляем…':'Отправить обращение'}</Button>{sent&&<Notice tone="success" title="Обращение сохранено">Администратор увидит его в очереди.</Notice>}</form><h2>Мои обращения</h2>{cases?.map(c=><section className="record" key={c.id}><Row title={c.payload.message} description={dateLabel(c.created_at)} status={c.status}/>{c.resolution&&<Notice title="Ответ">{c.resolution}</Notice>}</section>)}</>;
}
function Confirm({title,message,action,back,run}){const [busy,setBusy]=useState(false);return <><Heading title={title}/><Notice tone="warn" title="Проверьте действие">{message}</Notice><div className="actions"><Button disabled={busy} onClick={()=>{setBusy(true);run(action).finally(()=>setBusy(false))}}>{busy?'Выполняем…':'Подтвердить'}</Button><Button secondary disabled={busy} onClick={back}>Отмена</Button></div></>}

function App(){
  const [data,setData]=useState(null),[error,setError]=useState(null),[role,setRole]=useState('participant'),[route,setRoute]=useState({name:'home',props:{},key:0}),[online,setOnline]=useState(navigator.onLine),[loading,setLoading]=useState(true);
  const history=useRef([]),busyBoot=useRef(false),headingRef=useRef(null);
  const refresh=useCallback(async()=>{const fresh=await api('/api/v2/bootstrap');setData(fresh);return fresh},[]);
  const run=useCallback(async(action)=>{setError(null);try{return await action()}catch(e){setError({message:e.message,status:e.status});return null}},[]);
  const go=useCallback((name,props={})=>{setError(null);setRoute(prev=>{history.current.push(prev);return {name,props,key:prev.key+1}});window.scrollTo(0,0)},[]);
  const back=useCallback(()=>{setError(null);setRoute(prev=>({...history.current.pop()||{name:'home',props:{}},key:prev.key+1}));window.scrollTo(0,0)},[]);
  const boot=useCallback(async()=>{if(busyBoot.current)return;busyBoot.current=true;setLoading(true);setError(null);try{await login();const fresh=await refresh();const preferred=sessionStorage.getItem('verum-role');if(fresh.roles.includes(preferred))setRole(preferred);if(new URLSearchParams(location.search).has('invite'))go('invites')}catch(e){setError({message:e.message,status:e.status})}finally{setLoading(false);busyBoot.current=false}},[refresh,go]);
  useEffect(()=>{const tg=window.Telegram?.WebApp;tg?.ready?.();tg?.expand?.();tg?.setHeaderColor?.('#090909');tg?.setBackgroundColor?.('#090909');boot();const up=()=>setOnline(true),down=()=>setOnline(false);window.addEventListener('online',up);window.addEventListener('offline',down);return()=>{window.removeEventListener('online',up);window.removeEventListener('offline',down)}},[boot]);
  useEffect(()=>{const b=window.Telegram?.WebApp?.BackButton;if(!b)return;route.name==='home'?b.hide():b.show();b.onClick(back);return()=>b.offClick(back)},[route.name,back]);
  useEffect(()=>{headingRef.current?.focus({preventScroll:true})},[route.key]);
  const switchRole=value=>{setRole(value);sessionStorage.setItem('verum-role',value);history.current=[];go(value==='organizer'?'manage':value==='admin'?'admin':'home')};
  if(!data)return <main className="app-shell welcome"><img className="brand-logo" src="/verum-logo-white.png" alt="VERUM"/>{loading?<><h1>Открываем VERUM</h1><p role="status">Загружаем ваши профили и заявки…</p></>:<><Heading title="Вход в VERUM"/><Notice tone="warn" title="Не удалось войти">{error?.message||'Откройте приложение из Telegram-бота.'}</Notice><Button onClick={boot}>Повторить вход</Button><p className="hint">При истёкшей сессии закройте Mini App и откройте его заново из бота.</p></>}</main>;
  const props={data,go,run,refresh,role,back,...route.props};
  let content;
  switch(route.name){
    case 'people':content=<People {...props}/>;break;
    case 'person':content=<PersonForm {...props}/>;break;
    case 'invites':content=<Invitations {...props}/>;break;
    case 'invite-create':content=<Invitations {...props} create/>;break;
    case 'links':content=<Links {...props}/>;break;
    case 'select-people':content=<SelectPeople {...props}/>;break;
    case 'flow':content=<RegistrationFlow {...props}/>;break;
    case 'registrations':content=<Registrations {...props}/>;break;
    case 'registration':content=<RegistrationDetail {...props}/>;break;
    case 'manage':content=<Manage {...props}/>;break;
    case 'event-new':content=<NewEvent {...props}/>;break;
    case 'manage-event':content=<ManageEvent {...props}/>;break;
    case 'nominations':content=<Nominations {...props}/>;break;
    case 'manage-regs':content=<ManageRegistrations {...props}/>;break;
    case 'decision':content=<Decision {...props}/>;break;
    case 'export':content=<Export {...props}/>;break;
    case 'admin':content=<Admin {...props}/>;break;
    case 'admin-list':content=<AdminList {...props}/>;break;
    case 'support':content=<Support {...props}/>;break;
    case 'confirm':content=<Confirm {...props}/>;break;
    case 'notifications':content=<><Heading title="Уведомления" subtitle="Изменения статусов и ответы поддержки доступны здесь."/>{data.notifications.length?data.notifications.map(n=><Row key={n.id} title={n.title} description={n.body} onClick={n.registration_id?()=>run(async()=>go('registration',{registration:await api(`/api/v2/registrations/${n.registration_id}`)})):undefined}/>):<Empty title="Новых сообщений пока нет"/>}<Button secondary onClick={()=>run(async()=>{await api('/api/v2/notifications/read',{method:'POST'});await refresh()})}>Отметить прочитанными</Button></>;break;
    case 'settings':content=<><Heading title="Аккаунт и помощь" subtitle={`${data.user.first_name||''} · Telegram ID ${data.user.telegram_id}`}/><Row title="Приглашения и доступ" onClick={()=>go('invites')}/><Row title="Поддержка" onClick={()=>go('support')}/><Row title="Скачать мои данные" onClick={()=>run(()=>downloadFile('/api/v2/my-data','verum-my-data.json'))}/><Row title="Запросить удаление данных" onClick={()=>go('support',{kind:'deletion'})}/><Notice title="Данные защищены входом Telegram">Чужие профили недоступны без подтверждённой связи. Контакты не выводятся в публичные списки.</Notice><Button secondary onClick={()=>run(refresh)}>Обновить данные</Button></>;break;
    case 'event':{const event=data.events.find(e=>e.id===route.props.event.id)||route.props.event;content=<><Heading title="Мероприятие" onBack={()=>go('home')}/><Poster event={event}/><p className="event-description">{event.description}</p><h2>Номинации</h2>{event.nominations.filter(n=>n.is_active).map(n=><Row key={n.id} title={n.title} description={`${n.min_age}–${n.max_age} лет · ${n.capacity?`${n.occupied}/${n.capacity} мест`:'без лимита мест'}${n.battle_type!=='solo'?' · командная регистрация пока недоступна':''}`}/>)}<details className="regulations"><summary>Регламент</summary><p>{event.rules||'Организатор ещё не опубликовал регламент.'}</p></details>{event.status==='open'?<Button onClick={()=>go('select-people',{event})}>Выбрать участника</Button>:<Notice title="Регистрация недоступна">Следите за сроками и статусом события.</Notice>}</>;break}
    default:content=<><Heading title="Мероприятия" subtitle="Выберите событие. Сохранённые профили подставятся в заявку."/>{!data.events.length?<Empty title="Пока нет мероприятий">Организатор ещё не опубликовал события. Сейчас можно заполнить профиль.</Empty>:data.events.map(event=><section className="event-card" key={event.id}><Poster event={event}/><Button onClick={()=>go('event',{event})}>Подробнее и регистрация</Button></section>)}<Row title={role==='parent'?'Мои дети':role==='coach'?'Мои ученики':'Мой профиль'} description="Заполните один раз — используйте на следующих событиях" onClick={()=>go('people')}/>{data.drafts.length>0&&<Notice title="Есть сохранённые черновики">Выберите соответствующее событие и участника — выбранные номинации подставятся.</Notice>}</>;
  }
  const management=['organizer','admin'].includes(role);
  const nav=management?[[role==='admin'?'admin':'manage','Кабинет',ShieldCheck],['home','События',CalendarDays],['settings','Аккаунт',Settings]]:[['home','События',CalendarDays],['registrations','Заявки',ClipboardList],['people',role==='parent'?'Дети':role==='coach'?'Ученики':'Профиль',Users]];
  return <main className="app-shell"><header className="app-header"><div className="top-line"><button className="brand-button" aria-label="На главную" onClick={()=>go('home')}><img className="brand-logo" src="/verum-logo-white.png" alt="VERUM"/></button><div className="header-actions"><button className="icon-button" aria-label={`Уведомления${data.notifications.some(n=>!n.read_at)?', есть непрочитанные':''}`} onClick={()=>go('notifications')}><Bell size={21}/>{data.notifications.some(n=>!n.read_at)&&<span className="unread-label">новые</span>}</button><button className="icon-button" aria-label="Аккаунт и помощь" onClick={()=>go('settings')}><Settings size={21}/></button></div></div><label className="role-switch"><span>Мой режим</span><select aria-label="Мой режим" value={role} onChange={e=>switchRole(e.target.value)}>{data.roles.map(r=><option key={r} value={r}>{roleNames[r]}</option>)}</select></label></header>{import.meta.env.DEV&&<div className="dev-banner">Локальная проверка · вымышленные данные</div>}<div className="app-content" ref={headingRef} tabIndex={-1}>{!online&&<Notice tone="warn" title="Нет связи">Изменения не отправляются без интернета. Не закрывайте заполненную форму.</Notice>}{error&&<section className="error" role="alert"><b>{error.status===409?'Данные требуют проверки':error.status===401?'Вход устарел':'Не удалось выполнить действие'}</b><p>{error.message}</p>{error.status===401&&<Button secondary onClick={boot}>Войти заново</Button>}<button className="text-button" onClick={()=>setError(null)}>Закрыть сообщение</button></section>}<React.Fragment key={route.key}>{content}</React.Fragment></div><nav className="app-nav" aria-label="Основная навигация">{nav.map(([screen,label,Icon])=><button key={screen} aria-current={route.name===screen?'page':undefined} onClick={()=>go(screen)}><Icon size={20}/><span>{label}</span></button>)}</nav></main>;
}
class ErrorBoundary extends React.Component{state={failed:false};static getDerivedStateFromError(){return {failed:true}}render(){return this.state.failed?<main className="app-shell welcome"><Heading title="Не удалось открыть экран"/><p>Обновите приложение. Уже отправленные данные остаются на сервере.</p><Button onClick={()=>location.reload()}>Открыть заново</Button></main>:this.props.children}}
createRoot(document.getElementById('root')).render(<ErrorBoundary><App/></ErrorBoundary>);
