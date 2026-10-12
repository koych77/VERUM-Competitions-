import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, ArrowRight, CalendarDays, Check, Clock3, MapPin, ShieldCheck, UserRound } from "lucide-react";
import { api, login } from "./api/client";
import "./styles/index.css";

const demoEvent = {
  id: 1, title: "VERUM OPEN 2026", event_date: "2026-10-20", place: "Минск · Спортивный центр",
  registration_closes_at: "2026-10-15", status: "open", allow_full_registration: true,
  nominations: [
    { id: 1, title: "Breaking Kids 7–9", min_age: 7, max_age: 9, gender_rule: "any", battle_type: "solo" },
    { id: 2, title: "Breaking Kids 10–12", min_age: 10, max_age: 12, gender_rule: "any", battle_type: "solo" },
    { id: 3, title: "Breaking Juniors 13–15", min_age: 13, max_age: 15, gender_rule: "any", battle_type: "solo" },
  ],
};

const blankProfile = { full_name: "", nickname: "", birth_date: "", gender: "male", phone: "", city: "", club: "", trainer: "" };
const steps = ["Мероприятие", "Профиль", "Номинации", "Проверка"];

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" }).format(new Date(`${value}T12:00:00`));
}

function Progress({ step }) {
  return <div className="progress" aria-label={`Шаг ${step + 1} из 4`}>
    {steps.map((label, index) => <div className={`progress-item ${index <= step ? "is-active" : ""}`} key={label}>
      <span>{index < step ? <Check size={15} /> : index + 1}</span><small>{label}</small>
    </div>)}
  </div>;
}

function Shell({ user, children }) {
  return <main className="app-shell">
    <header className="topbar"><div className="wordmark">VERUM<span>.</span></div><div className="identity"><div className="avatar">{(user?.first_name || "V")[0]}</div><div><b>{user?.first_name || "Участник"}</b><small>ID: {user?.telegram_id || "—"}</small></div></div></header>
    {children}
  </main>;
}

function EventHome({ user, events, registrations, onSelect, onOpen }) {
  const event = events[0];
  const existing = event && registrations.find(item => Number(item.event_id) === Number(event.id));
  return <Shell user={user}>
    <Progress step={0} />
    <section className="intro"><p className="eyebrow">Регистрация на соревнования</p><h1>Выберите<br/>мероприятие</h1><p>Профиль сохранится один раз. Для каждого события мы создаём только одну актуальную заявку.</p></section>
    {!event ? <section className="empty"><CalendarDays/><h2>Пока нет открытых мероприятий</h2><p>Как только организатор откроет регистрацию, событие появится здесь.</p></section> : <>
      <article className="event-hero">
        <img src="/verum-breaker-hero.png" alt="Брейкер на сцене"/>
        <div className="event-shade"/><div className="event-content"><span className="event-status">Открыта регистрация</span><h2>{event.title}</h2>
          <dl><div><dt><CalendarDays/></dt><dd><small>Дата</small><b>{formatDate(event.event_date)}</b></dd></div><div><dt><MapPin/></dt><dd><small>Место</small><b>{event.place}</b></dd></div><div><dt><Clock3/></dt><dd><small>Регистрация до</small><b>{formatDate(event.registration_closes_at)}</b></dd></div></dl>
          <button className="primary" onClick={() => existing ? onOpen(existing) : onSelect(event)}>{existing ? "Открыть заявку" : "Начать регистрацию"}<ArrowRight/></button>
        </div>
      </article>
      <section className={`application-row ${existing ? "is-done" : ""}`}><div className="status-icon">{existing ? <Check/> : <ShieldCheck/>}</div><div><span>{existing ? "Вы уже зарегистрированы" : "Без повторных заявок"}</span><b>{existing ? event.title : "Черновик сохранится автоматически"}</b><small>{existing ? "Повторная отправка заблокирована" : "Вернуться можно в любой момент"}</small></div>{existing && <button onClick={() => onOpen(existing)}>Посмотреть <ArrowRight/></button>}</section>
    </>}
  </Shell>;
}

function Field({ label, hint, ...props }) { return <label className="field"><span>{label}</span><input {...props}/>{hint && <small>{hint}</small>}</label>; }

function RegistrationFlow({ user, event, initial, onBack, onSaved }) {
  const [step, setStep] = useState(initial ? 3 : 1);
  const [profile, setProfile] = useState(() => initial ? { ...blankProfile, ...initial } : blankProfile);
  const [selected, setSelected] = useState(() => initial?.nominations?.map(n => n.id) || []);
  const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  const nominations = event.nominations || [];
  const update = key => e => setProfile(current => ({ ...current, [key]: e.target.value }));
  const validateProfile = () => {
    if (!profile.full_name.trim()) return "Введите ФИО.";
    if (!profile.nickname.trim()) return "Введите никнейм.";
    if (!profile.birth_date) return "Укажите дату рождения.";
    if (!profile.phone.trim()) return "Введите телефон.";
    if (!profile.city.trim()) return "Укажите город.";
    return "";
  };
  const next = () => { const message = step === 1 ? validateProfile() : step === 2 && !selected.length ? "Выберите хотя бы одну номинацию." : ""; if (message) return setError(message); setError(""); setStep(value => Math.min(3, value + 1)); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const submit = async () => {
    if (saving || initial) return;
    setSaving(true); setError("");
    try { const saved = await api(`/api/events/${event.id}/register/full`, { method: "POST", body: JSON.stringify({ user: { telegram_id: user.telegram_id, telegram_username: user.telegram_username, first_name: user.first_name, last_name: user.last_name }, profile, nomination_ids: selected, team_name: null, team_members: null }) }); onSaved(saved); }
    catch (e) { setError(e.message); } finally { setSaving(false); }
  };
  return <Shell user={user}><button className="back" onClick={step === 1 || initial ? onBack : () => setStep(s => s - 1)}><ArrowLeft/>Назад</button><div className="flow-event"><small>Выбранное мероприятие</small><h2>{event.title}</h2><span><CalendarDays/>{formatDate(event.event_date)}</span><span><MapPin/>{event.place}</span></div><Progress step={step}/>
    {initial && <div className="duplicate-note"><ShieldCheck/><div><b>Заявка уже существует</b><p>Повторная регистрация заблокирована. Ниже показана ваша актуальная заявка.</p></div></div>}
    {step === 1 && <section className="form-section"><div className="section-heading"><div><p className="eyebrow">Шаг 2 из 4</p><h1>Ваш профиль</h1><p>Заполните один раз — данные подставятся на следующих мероприятиях.</p></div><span className="autosave"><Check/> Сохраняется</span></div><div className="form-grid"><Field label="ФИО *" value={profile.full_name} onChange={update("full_name")} placeholder="Как в документах"/><Field label="Никнейм *" value={profile.nickname} onChange={update("nickname")} placeholder="Без Bboy / Bgirl"/><Field label="Дата рождения *" type="date" value={profile.birth_date} onChange={update("birth_date")}/><label className="field"><span>Пол *</span><div className="segmented"><button className={profile.gender === "male" ? "active" : ""} onClick={() => setProfile(p => ({...p, gender:"male"}))}>Мужской</button><button className={profile.gender === "female" ? "active" : ""} onClick={() => setProfile(p => ({...p, gender:"female"}))}>Женский</button></div></label><Field label="Телефон *" type="tel" value={profile.phone} onChange={update("phone")} placeholder="+375 29 123 45 67"/><Field label="Город *" value={profile.city} onChange={update("city")} placeholder="Минск"/><Field label="Клуб / команда" value={profile.club} onChange={update("club")}/><Field label="Тренер" value={profile.trainer} onChange={update("trainer")}/></div></section>}
    {step === 2 && <section className="form-section"><p className="eyebrow">Шаг 3 из 4</p><h1>Номинации</h1><p>Доступны категории, подходящие по возрасту и полу.</p><div className="nomination-list">{nominations.map(n => <button key={n.id} className={selected.includes(n.id) ? "selected" : ""} onClick={() => setSelected(ids => ids.includes(n.id) ? ids.filter(id => id !== n.id) : [...ids, n.id])}><span className="checkmark">{selected.includes(n.id) && <Check/>}</span><span><b>{n.title}</b><small>{n.min_age}–{n.max_age} лет · {n.battle_type === "team" ? "Команда" : "Соло"}</small></span></button>)}</div></section>}
    {step === 3 && <section className="review"><p className="eyebrow">Шаг 4 из 4</p><h1>{initial ? "Ваша заявка" : "Проверьте данные"}</h1><div className="review-status"><Check/><div><b>{initial ? "Заявка принята" : "Готово к отправке"}</b><p>{initial ? "Вы уже зарегистрированы на это мероприятие." : "После отправки повторная заявка не создастся."}</p></div></div><dl><div><dt>Участник</dt><dd>{profile.full_name}<small>{profile.nickname}</small></dd></div><div><dt>Контакты</dt><dd>{profile.phone}<small>{profile.city}</small></dd></div><div><dt>Номинации</dt><dd>{nominations.filter(n => selected.includes(n.id)).map(n => n.title).join(", ") || initial?.nominations?.map(n => n.title).join(", ") || "—"}</dd></div></dl>{!initial && <button className="primary" onClick={submit} disabled={saving}>{saving ? "Отправляем…" : "Подтвердить регистрацию"}<ArrowRight/></button>}<button className="secondary" onClick={onBack}>На главную</button></section>}
    {error && <div className="error" role="alert">{error}</div>}{!initial && step < 3 && <div className="sticky-action"><button className="primary" onClick={next}>Далее: {step === 1 ? "номинации" : "проверка"}<ArrowRight/></button></div>}
  </Shell>;
}

function App() {
  const [user, setUser] = useState(null), [events, setEvents] = useState([]), [registrations, setRegistrations] = useState([]), [screen, setScreen] = useState("home"), [event, setEvent] = useState(null), [current, setCurrent] = useState(null), [error, setError] = useState("");
  const demo = new URLSearchParams(location.search).has("demo");
  useEffect(() => { window.Telegram?.WebApp?.ready?.(); window.Telegram?.WebApp?.expand?.(); (async () => { try { const session = demo ? { telegram_id: 1001, first_name: "Алексей", telegram_username: "frost" } : await login(); setUser(session); const loaded = demo ? [demoEvent] : await api("/api/events"); setEvents(loaded); if (!demo) setRegistrations(await api("/api/registrations/me")); } catch (e) { setError(e.message); } })(); }, []);
  const chosen = useMemo(() => event || events[0], [event, events]);
  if (!user && !error) return <div className="loading"><div className="wordmark">VERUM<span>.</span></div><p>Загружаем регистрацию…</p></div>;
  if (error && !user) return <div className="loading"><div className="wordmark">VERUM<span>.</span></div><h1>Не удалось войти</h1><p>{error}</p><button className="primary" onClick={() => location.reload()}>Повторить</button></div>;
  if (screen === "flow") return <RegistrationFlow user={user} event={chosen} initial={current} onBack={() => { setScreen("home"); setCurrent(null); }} onSaved={saved => { setRegistrations(items => [saved, ...items.filter(x => x.id !== saved.id)]); setCurrent(saved); }} />;
  return <EventHome user={user} events={events} registrations={registrations} onSelect={value => { setEvent(value); setCurrent(null); setScreen("flow"); }} onOpen={value => { setEvent(events.find(e => Number(e.id) === Number(value.event_id)) || events[0]); setCurrent(value); setScreen("flow"); }}/>
}

createRoot(document.getElementById("root")).render(<App/>);
