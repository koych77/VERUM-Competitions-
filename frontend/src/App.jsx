import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Archive, Download, Edit, HelpCircle, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { adminHeaders, api, getTelegramUser, login } from "./api/client";
import "./styles/main.css";

const emptyParticipant = {
  full_name: "",
  nickname: "",
  birth_date: "",
  gender: "male",
  phone: "",
  city: "",
  club: "",
  trainer: "",
};

const emptyEvent = {
  title: "",
  event_date: "",
  place: "",
  description: "",
  image_url: null,
  registration_opens_at: "",
  registration_closes_at: "",
  status: "draft",
  allow_full_registration: true,
  allow_short_registration: true,
  allow_coach_registration: true,
};

const emptyNomination = {
  title: "",
  min_age: 6,
  max_age: 99,
  gender_rule: "any",
  experience: "",
  description: "",
  is_active: true,
  sort_order: 100,
};

function ruToIso(value) {
  if (!value) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const match = value.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  return match ? `${match[3]}-${match[2]}-${match[1]}` : "";
}

function formatDate(value) {
  if (!value) return "";
  if (/^\d{2}\.\d{2}\.\d{4}$/.test(value)) return value;
  const [year, month, day] = value.split("-");
  return day && month && year ? `${day}.${month}.${year}` : value;
}

function telegramUserPayload(user) {
  return {
    telegram_id: user.telegram_id,
    telegram_username: user.telegram_username,
    first_name: user.first_name,
    last_name: user.last_name,
  };
}

function genderLabel(value) {
  return value === "female" ? "Женский" : "Мужской";
}

function genderRuleLabel(value) {
  if (value === "male") return "мужской";
  if (value === "female") return "женский";
  return "любой пол";
}

function registrationTypeLabel(value) {
  if (value === "full") return "полная";
  if (value === "short") return "короткая";
  return "ученики";
}

const fieldHints = {
  "ФИО": "Полное имя и фамилия участника. Пример: Иванов Иван.",
  "Никнейм": "Имя, под которым участника называют на соревнованиях. Пример: Bboy Max.",
  "Дата рождения": "Дата нужна для автоматического расчета возраста. Пример: 15.04.2012.",
  "Пол": "Используется для подбора подходящих номинаций. Пример: Мужской.",
  "Телефон": "Контакт для связи при необходимости. Можно оставить пустым, если поле необязательное.",
  "Город": "Город участника, тренера или команды. Пример: Минск.",
  "Клуб/команда": "Название клуба, школы или команды. Пример: VERUM Crew.",
  "Тренер": "ФИО тренера участника. Пример: Петров Петр.",
  "Название": "Название мероприятия или номинации. Пример: VERUM Battle 2026.",
  "Дата проведения": "День, когда пройдет мероприятие. Пример: 20.09.2026.",
  "Место": "Город, зал или адрес проведения. Пример: Минск, Дворец спорта.",
  "Логотип/картинка мероприятия": "Изображение для карточки мероприятия. Загрузите JPG, PNG или WEBP до 5 МБ.",
  "Дата открытия регистрации": "С какого дня мероприятие видно участникам для регистрации.",
  "Дата закрытия регистрации": "После этой даты участники уже не смогут подать заявку.",
  "Описание": "Краткая информация, которую увидят участники. Пример: открытый баттл для детей и юниоров.",
  "Статус": "Черновик скрыт от участников. Открыто доступно для регистрации. Архив убирает мероприятие.",
  "Возраст от": "Минимальный возраст для номинации на дату мероприятия. Пример: 10.",
  "Возраст до": "Максимальный возраст для номинации на дату мероприятия. Пример: 13.",
  "Опыт": "Текстовое условие по опыту. Пример: начинающие до 1 года занятий.",
};

function Field({ label, hint, children }) {
  const [open, setOpen] = useState(false);
  const text = hint || fieldHints[label];
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {text && (
          <button
            type="button"
            className="hint-button"
            aria-label={`Подсказка: ${label}`}
            onClick={(event) => {
              event.preventDefault();
              setOpen(!open);
            }}
          >
            <HelpCircle size={15} />
          </button>
        )}
      </span>
      {open && text && <span className="field-hint">{text}</span>}
      {children}
    </label>
  );
}

function ParticipantForm({ value, onChange, short = false }) {
  const set = (key, next) => onChange({ ...value, [key]: next });
  return (
    <div className="form">
      <Field label="ФИО">
        <input value={value.full_name || ""} onChange={(event) => set("full_name", event.target.value)} required />
      </Field>
      <Field label="Никнейм">
        <input value={value.nickname || ""} onChange={(event) => set("nickname", event.target.value)} required />
      </Field>
      <Field label="Дата рождения">
        <input
          value={value.birth_date || ""}
          placeholder="дд.мм.гггг"
          onChange={(event) => set("birth_date", event.target.value)}
          required
        />
      </Field>
      <Field label="Пол">
        <select value={value.gender || "male"} onChange={(event) => set("gender", event.target.value)}>
          <option value="male">Мужской</option>
          <option value="female">Женский</option>
        </select>
      </Field>
      <Field label="Телефон">
        <input value={value.phone || ""} onChange={(event) => set("phone", event.target.value)} />
      </Field>
      {!short && (
        <>
          <Field label="Город">
            <input value={value.city || ""} onChange={(event) => set("city", event.target.value)} required />
          </Field>
          <Field label="Клуб/команда">
            <input value={value.club || ""} onChange={(event) => set("club", event.target.value)} required />
          </Field>
          <Field label="Тренер">
            <input value={value.trainer || ""} onChange={(event) => set("trainer", event.target.value)} required />
          </Field>
        </>
      )}
    </div>
  );
}

function NominationPicker({ nominations, selected, setSelected }) {
  const toggle = (id) => {
    setSelected(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id]);
  };

  if (!nominations.length) {
    return <div className="notice">Для этих данных нет доступных номинаций.</div>;
  }

  return (
    <div className="checklist">
      {nominations.map((nomination) => (
        <label className="check" key={nomination.id}>
          <input type="checkbox" checked={selected.includes(nomination.id)} onChange={() => toggle(nomination.id)} />
          <span>
            <strong>{nomination.title}</strong>
            <br />
            <span className="muted">
              {nomination.min_age}-{nomination.max_age}, {genderRuleLabel(nomination.gender_rule)}
            </span>
            {nomination.experience && (
              <>
                <br />
                <span className="muted">Опыт: {nomination.experience}</span>
              </>
            )}
            {nomination.description && (
              <>
                <br />
                <span className="muted">{nomination.description}</span>
              </>
            )}
          </span>
        </label>
      ))}
    </div>
  );
}

function validateParticipant(form, short) {
  const required = short
    ? ["full_name", "nickname", "birth_date", "gender"]
    : ["full_name", "nickname", "birth_date", "gender", "city", "club", "trainer"];
  const missing = required.filter((key) => !String(form[key] || "").trim());
  if (missing.length) return "Заполните все обязательные поля.";
  if (!ruToIso(form.birth_date)) return "Проверьте дату рождения. Формат: дд.мм.гггг";
  return "";
}

function RegistrationFlow({ event, type, user, onDone, onBack }) {
  const [form, setForm] = useState(emptyParticipant);
  const [nominations, setNominations] = useState([]);
  const [selected, setSelected] = useState([]);
  const [existing, setExisting] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/api/users/${user.telegram_id}/events/${event.id}/registration`).then(setExisting).catch(() => {});
    if (type === "full") {
      api(`/api/profiles/participant/${user.telegram_id}`).then((profile) => {
        if (profile) setForm({ ...profile, birth_date: formatDate(profile.birth_date), phone: profile.phone || "" });
      });
    }
  }, [event.id, type, user.telegram_id]);

  useEffect(() => {
    const birthDate = ruToIso(form.birth_date);
    if (!birthDate || !form.gender) {
      setNominations([]);
      return;
    }
    api(`/api/events/${event.id}/available-nominations?birth_date=${birthDate}&gender=${form.gender}`)
      .then(setNominations)
      .catch(() => setNominations([]));
  }, [event.id, form.birth_date, form.gender]);

  const submit = async () => {
    setError("");
    const validationError = validateParticipant(form, type === "short");
    if (validationError) {
      setError(validationError);
      return;
    }
    if (!selected.length) {
      setError("Выберите хотя бы одну номинацию.");
      return;
    }

    const clean = { ...form, birth_date: ruToIso(form.birth_date), phone: form.phone || null };
    try {
      const path = type === "short" ? "short" : "full";
      const body =
        type === "short"
          ? { user: telegramUserPayload(user), ...clean, nomination_ids: selected }
          : { user: telegramUserPayload(user), profile: clean, nomination_ids: selected };
      await api(`/api/events/${event.id}/register/${path}`, { method: "POST", body: JSON.stringify(body) });
      onDone();
    } catch (err) {
      setError(err.message);
    }
  };

  const chosenIds = new Set(existing?.nominations?.map((item) => item.nomination_id) || []);
  const availableForAdd = nominations.filter((item) => !chosenIds.has(item.id));

  return (
    <div>
      <button className="ghost" onClick={onBack}>Назад</button>
      <h1 className="title">{type === "short" ? "Короткая регистрация" : "Полная регистрация"}</h1>
      {existing && (
        <div className="notice">
          <strong>Вы уже зарегистрированы.</strong>
          <br />
          Выбранные номинации: {existing.nominations.map((item) => item.title).join(", ")}
          <br />
          Можно добавить еще подходящие номинации.
        </div>
      )}
      <ParticipantForm value={form} onChange={setForm} short={type === "short"} />
      <h3>Доступные номинации</h3>
      <NominationPicker nominations={availableForAdd} selected={selected} setSelected={setSelected} />
      {error && <div className="notice">{error}</div>}
      <div className="actions">
        <button className="button primary" onClick={submit}>Зарегистрироваться</button>
      </div>
    </div>
  );
}

function CoachFlow({ event, user, onBack, onDone }) {
  const [coach, setCoach] = useState({ full_name: "", phone: "", city: "", club: "" });
  const [coachProfile, setCoachProfile] = useState(null);
  const [students, setStudents] = useState([]);
  const [studentForm, setStudentForm] = useState(emptyParticipant);
  const [editingStudent, setEditingStudent] = useState(null);
  const [selectedStudents, setSelectedStudents] = useState([]);
  const [studentNominations, setStudentNominations] = useState({});
  const [error, setError] = useState("");

  const reloadStudents = async (profile = coachProfile) => {
    if (!profile) return;
    const rows = await api(`/api/profiles/coach/${profile.id}/students`);
    setStudents(rows.map((item) => ({ ...item, birth_date: formatDate(item.birth_date) })));
  };

  useEffect(() => {
    api(`/api/profiles/coach/${user.telegram_id}`).then((profile) => {
      if (profile) {
        setCoachProfile(profile);
        setCoach({ full_name: profile.full_name, phone: profile.phone || "", city: profile.city, club: profile.club });
        reloadStudents(profile);
      }
    });
  }, [user.telegram_id]);

  const saveCoach = async () => {
    const saved = await api("/api/profiles/coach", {
      method: "POST",
      body: JSON.stringify({ user_in: telegramUserPayload(user), coach: { ...coach, phone: coach.phone || null } }),
    });
    setCoachProfile(saved);
    await reloadStudents(saved);
  };

  const saveStudent = async () => {
    setError("");
    if (!coachProfile) {
      setError("Сначала сохраните профиль тренера.");
      return;
    }
    const source = editingStudent || studentForm;
    const validationError = validateParticipant(source, false);
    if (validationError) {
      setError(validationError);
      return;
    }
    const payload = { ...source, birth_date: ruToIso(source.birth_date), phone: undefined };
    if (editingStudent) {
      await api(`/api/profiles/students/${editingStudent.id}`, { method: "PUT", body: JSON.stringify(payload) });
      setEditingStudent(null);
    } else {
      await api(`/api/profiles/coach/${coachProfile.id}/students`, { method: "POST", body: JSON.stringify(payload) });
      setStudentForm(emptyParticipant);
    }
    await reloadStudents();
  };

  const archiveStudent = async (student) => {
    await api(`/api/profiles/students/${student.id}/archive`, { method: "POST" });
    setSelectedStudents(selectedStudents.filter((id) => id !== student.id));
    await reloadStudents();
  };

  const toggleStudent = async (student) => {
    const next = selectedStudents.includes(student.id)
      ? selectedStudents.filter((id) => id !== student.id)
      : [...selectedStudents, student.id];
    setSelectedStudents(next);
    if (!studentNominations[student.id]) {
      const rows = await api(
        `/api/events/${event.id}/available-nominations?birth_date=${ruToIso(student.birth_date)}&gender=${student.gender}`,
      );
      setStudentNominations({ ...studentNominations, [student.id]: { available: rows, selected: [] } });
    }
  };

  const setStudentSelectedNominations = (studentId, selected) => {
    setStudentNominations({ ...studentNominations, [studentId]: { ...studentNominations[studentId], selected } });
  };

  const submit = async () => {
    setError("");
    const registrations = selectedStudents.map((studentId) => ({
      student_id: studentId,
      nomination_ids: studentNominations[studentId]?.selected || [],
    }));
    if (!registrations.length || registrations.some((item) => !item.nomination_ids.length)) {
      setError("У каждого выбранного ученика должна быть хотя бы одна номинация.");
      return;
    }
    await api(`/api/events/${event.id}/register/coach`, {
      method: "POST",
      body: JSON.stringify({ user: telegramUserPayload(user), coach: { ...coach, phone: coach.phone || null }, registrations }),
    });
    onDone();
  };

  const visibleStudentForm = editingStudent || studentForm;

  return (
    <div>
      <button className="ghost" onClick={onBack}>Назад</button>
      <h1 className="title">Регистрация учеников</h1>
      <div className="split">
        <div className="card">
          <h3>Профиль тренера</h3>
          <div className="form">
            {["full_name", "city", "club", "phone"].map((key) => (
              <Field key={key} label={{ full_name: "ФИО", city: "Город", club: "Клуб/команда", phone: "Телефон" }[key]}>
                <input value={coach[key]} onChange={(event) => setCoach({ ...coach, [key]: event.target.value })} />
              </Field>
            ))}
            <button className="button primary" onClick={saveCoach}><Save size={18} /> Сохранить тренера</button>
          </div>
        </div>

        <div className="card">
          <h3>{editingStudent ? "Редактировать ученика" : "Добавить ученика"}</h3>
          <ParticipantForm value={visibleStudentForm} onChange={editingStudent ? setEditingStudent : setStudentForm} />
          <div className="actions">
            <button className="button primary" onClick={saveStudent}><Save size={18} /> Сохранить</button>
            {editingStudent && <button className="ghost" onClick={() => setEditingStudent(null)}>Отмена</button>}
          </div>
        </div>
      </div>

      <h3>Ученики</h3>
      <div className="grid">
        {students.map((student) => (
          <div className="card" key={student.id}>
            <label className="check">
              <input type="checkbox" checked={selectedStudents.includes(student.id)} onChange={() => toggleStudent(student)} />
              <span>
                <strong>{student.full_name}</strong> / {student.nickname}
                <br />
                <span className="muted">{student.birth_date}, {genderLabel(student.gender)}</span>
              </span>
            </label>
            <div className="actions">
              <button className="ghost" onClick={() => setEditingStudent(student)}><Edit size={16} /> Изменить</button>
              <button className="ghost" onClick={() => archiveStudent(student)}><Archive size={16} /> Архив</button>
            </div>
            {selectedStudents.includes(student.id) && (
              <NominationPicker
                nominations={studentNominations[student.id]?.available || []}
                selected={studentNominations[student.id]?.selected || []}
                setSelected={(ids) => setStudentSelectedNominations(student.id, ids)}
              />
            )}
          </div>
        ))}
      </div>
      {error && <div className="notice">{error}</div>}
      <div className="actions">
        <button className="button primary" onClick={submit}>Зарегистрировать выбранных</button>
      </div>
    </div>
  );
}

function RegistrationTypeSelect({ event, onSelect, onBack }) {
  const options = [
    event.allow_full_registration && ["full", "Полная регистрация", "Профиль сохранится для будущих мероприятий."],
    event.allow_short_registration && ["short", "Короткая регистрация", "Только основные данные на это мероприятие."],
    event.allow_coach_registration && ["coach", "Регистрация учеников", "Массовая регистрация учеников тренером."],
  ].filter(Boolean);

  return (
    <div>
      <button className="ghost" onClick={onBack}>Назад</button>
      <h1 className="title">{event.title}</h1>
      <p className="muted">{event.place}, {formatDate(event.event_date)}</p>
      <div className="grid">
        {options.map(([key, title, description]) => (
          <button className="card" key={key} onClick={() => onSelect(key)}>
            <h3>{title}</h3>
            <p className="muted">{description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

function EventList({ events, onSelect }) {
  return (
    <div>
      <h1 className="title">Мероприятия VERUM</h1>
      <p className="muted">Выберите мероприятие, затем тип регистрации.</p>
      <div className="grid">
        {events.map((event) => (
          <button className="card" key={event.id} onClick={() => onSelect(event)}>
            {event.image_url && <img className="event-image" src={event.image_url} alt={event.title} />}
            <h3>{event.title}</h3>
            <p>{event.description}</p>
            <div className="card-row"><span>Дата</span><strong>{formatDate(event.event_date)}</strong></div>
            <div className="card-row"><span>Место</span><strong>{event.place}</strong></div>
            <div className="card-row"><span>Регистрация до</span><strong>{formatDate(event.registration_closes_at)}</strong></div>
          </button>
        ))}
      </div>
      {!events.length && <div className="notice">Сейчас нет открытых мероприятий.</div>}
    </div>
  );
}

function EventForm({ value, onChange, onSave, isEditing }) {
  const set = (key, next) => onChange({ ...value, [key]: next });
  return (
    <div className="card">
      <h3>{isEditing ? "Редактировать мероприятие" : "Создать мероприятие"}</h3>
      <div className="form">
        {value.image_preview && <img className="event-image" src={value.image_preview} alt="Картинка мероприятия" />}
        <Field label="Название"><input value={value.title} onChange={(event) => set("title", event.target.value)} /></Field>
        <Field label="Дата проведения"><input type="date" value={value.event_date} onChange={(event) => set("event_date", event.target.value)} /></Field>
        <Field label="Место"><input value={value.place} onChange={(event) => set("place", event.target.value)} /></Field>
        <Field label="Логотип/картинка мероприятия">
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(event) => {
              const file = event.target.files?.[0] || null;
              set("image_file", file);
              set("image_preview", file ? URL.createObjectURL(file) : value.image_url || null);
            }}
          />
        </Field>
        <Field label="Дата открытия регистрации"><input type="date" value={value.registration_opens_at} onChange={(event) => set("registration_opens_at", event.target.value)} /></Field>
        <Field label="Дата закрытия регистрации"><input type="date" value={value.registration_closes_at} onChange={(event) => set("registration_closes_at", event.target.value)} /></Field>
        <Field label="Описание"><textarea value={value.description} onChange={(event) => set("description", event.target.value)} /></Field>
        <Field label="Статус">
          <select value={value.status} onChange={(event) => set("status", event.target.value)}>
            <option value="draft">Черновик</option>
            <option value="open">Открыто</option>
            <option value="closed">Закрыто</option>
            <option value="archived">Архив</option>
          </select>
        </Field>
        <label className="check"><input type="checkbox" checked={value.allow_full_registration} onChange={(event) => set("allow_full_registration", event.target.checked)} /> Полная регистрация</label>
        <label className="check"><input type="checkbox" checked={value.allow_short_registration} onChange={(event) => set("allow_short_registration", event.target.checked)} /> Короткая регистрация</label>
        <label className="check"><input type="checkbox" checked={value.allow_coach_registration} onChange={(event) => set("allow_coach_registration", event.target.checked)} /> Регистрация учеников</label>
        <button className="button primary" onClick={onSave}><Save size={18} /> Сохранить</button>
      </div>
    </div>
  );
}

function NominationForm({ value, onChange, onSave, disabled, isEditing }) {
  const set = (key, next) => onChange({ ...value, [key]: next });
  return (
    <div className="card">
      <h3>{isEditing ? "Редактировать номинацию" : "Добавить номинацию"}</h3>
      <div className="form">
        <Field label="Название"><input value={value.title} onChange={(event) => set("title", event.target.value)} /></Field>
        <Field label="Возраст от"><input type="number" value={value.min_age} onChange={(event) => set("min_age", Number(event.target.value))} /></Field>
        <Field label="Возраст до"><input type="number" value={value.max_age} onChange={(event) => set("max_age", Number(event.target.value))} /></Field>
        <Field label="Пол">
          <select value={value.gender_rule} onChange={(event) => set("gender_rule", event.target.value)}>
            <option value="any">Любой</option>
            <option value="male">Мужской</option>
            <option value="female">Женский</option>
          </select>
        </Field>
        <Field label="Опыт"><textarea value={value.experience} onChange={(event) => set("experience", event.target.value)} /></Field>
        <Field label="Описание"><textarea value={value.description} onChange={(event) => set("description", event.target.value)} /></Field>
        <button className="button primary" disabled={disabled} onClick={onSave}><Save size={18} /> Сохранить</button>
      </div>
    </div>
  );
}

function validateNomination(form) {
  if (!String(form.title || "").trim()) return "Введите название номинации.";
  if (!Number.isFinite(Number(form.min_age)) || !Number.isFinite(Number(form.max_age))) {
    return "Укажите возрастные границы.";
  }
  if (Number(form.min_age) < 0 || Number(form.max_age) < 0) return "Возраст не может быть меньше 0.";
  if (Number(form.min_age) > Number(form.max_age)) return "Возраст от не может быть больше возраста до.";
  return "";
}

function Admin({ user }) {
  const [events, setEvents] = useState([]);
  const [eventForm, setEventForm] = useState(emptyEvent);
  const [editingEventId, setEditingEventId] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [nominationForm, setNominationForm] = useState(emptyNomination);
  const [editingNominationId, setEditingNominationId] = useState(null);
  const [registrations, setRegistrations] = useState([]);
  const [editRegistration, setEditRegistration] = useState(null);
  const [message, setMessage] = useState("");
  const [uploadingEventId, setUploadingEventId] = useState(null);

  const headers = useMemo(() => adminHeaders(user), [user]);
  const refresh = async (preferredEventId = selectedEvent?.id) => {
    const rows = await api("/api/events/admin", { headers });
    setEvents(rows);
    applySelectedEvent(rows, preferredEventId);
  };

  const applySelectedEvent = (rows, preferredEventId = selectedEvent?.id) => {
    if (!preferredEventId) return;
    const fresh = rows.find((item) => item.id === preferredEventId);
    if (!fresh) return;
    fresh.nominations = [...(fresh.nominations || [])].sort((a, b) => a.sort_order - b.sort_order || a.title.localeCompare(b.title));
    setSelectedEvent(fresh);
  };

  const mergeUpdatedEvent = (updatedEvent) => {
    const normalized = {
      ...updatedEvent,
      nominations: [...(updatedEvent.nominations || [])].sort((a, b) => a.sort_order - b.sort_order || a.title.localeCompare(b.title)),
    };
    setEvents((current) => {
      const exists = current.some((item) => item.id === normalized.id);
      return exists ? current.map((item) => (item.id === normalized.id ? normalized : item)) : [normalized, ...current];
    });
    setSelectedEvent(normalized);
    return normalized;
  };

  useEffect(() => {
    refresh();
  }, []);

  const uploadEventImage = async (eventId, file) => {
    if (!file) return null;
    setUploadingEventId(eventId);
    const formData = new FormData();
    formData.append("image", file);
    const response = await fetch(`/api/events/admin/${eventId}/image`, {
      method: "POST",
      headers,
      body: formData,
    });
    setUploadingEventId(null);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "Не удалось загрузить картинку.");
    }
    return response.json();
  };

  const saveEvent = async () => {
    setMessage("");
    try {
      const method = editingEventId ? "PUT" : "POST";
      const path = editingEventId ? `/api/events/admin/${editingEventId}` : "/api/events/admin";
      const { image_file, image_preview, nominations, ...eventPayload } = eventForm;
      const body = editingEventId ? eventPayload : { ...eventPayload, nominations: [] };
      const savedEvent = await api(path, { method, headers, body: JSON.stringify(body) });
      const eventWithImage = image_file ? await uploadEventImage(savedEvent.id, image_file) : savedEvent;
      const normalized = mergeUpdatedEvent(eventWithImage);
      setEventForm(emptyEvent);
      setEditingEventId(null);
      setMessage("Мероприятие сохранено.");
      if (!editingEventId) setSelectedEvent(normalized);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const startEditEvent = (event) => {
    setEditingEventId(event.id);
    const { nominations, ...editable } = event;
    setEventForm({ ...editable, image_preview: editable.image_url || null, image_file: null });
    setSelectedEvent(event);
  };

  const archiveEvent = async (event) => {
    await api(`/api/events/admin/${event.id}/archive`, { method: "POST", headers });
    setMessage("Мероприятие отправлено в архив.");
    await refresh();
  };

  const saveNomination = async () => {
    if (!selectedEvent) return;
    setMessage("");
    const validationError = validateNomination(nominationForm);
    if (validationError) {
      setMessage(validationError);
      return;
    }
    const method = editingNominationId ? "PUT" : "POST";
    const path = editingNominationId
      ? `/api/events/admin/nominations/${editingNominationId}`
      : `/api/events/admin/${selectedEvent.id}/nominations`;
    const updatedEvent = await api(path, { method, headers, body: JSON.stringify({
      ...nominationForm,
      min_age: Number(nominationForm.min_age),
      max_age: Number(nominationForm.max_age),
      sort_order: editingNominationId
        ? Number(nominationForm.sort_order || 100)
        : ((selectedEvent.nominations || []).length + 1) * 10,
    }) });
    setNominationForm(emptyNomination);
    setEditingNominationId(null);
    setMessage("Номинация сохранена.");
    mergeUpdatedEvent(updatedEvent);
  };

  const startEditNomination = (nomination) => {
    setEditingNominationId(nomination.id);
    setNominationForm({ ...nomination });
  };

  const toggleNomination = async (nomination) => {
    const updatedEvent = await api(`/api/events/admin/nominations/${nomination.id}/toggle`, { method: "POST", headers });
    mergeUpdatedEvent(updatedEvent);
  };

  const loadRegistrations = async (event) => {
    setSelectedEvent(event);
    const rows = await api(`/api/events/${event.id}/registrations`, { headers });
    setRegistrations(rows);
    setEditRegistration(null);
  };

  const downloadExport = async (event) => {
    const response = await fetch(`/api/events/${event.id}/export`, { headers });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `verum_event_${event.id}_participants.xlsx`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const saveRegistrationEdit = async () => {
    const payload = {
      ...editRegistration,
      birth_date: ruToIso(editRegistration.birth_date),
      nomination_ids: editRegistration.nominations.map((item) => item.nomination_id),
    };
    await api(`/api/admin/registrations/${editRegistration.id}`, { method: "PUT", headers, body: JSON.stringify(payload) });
    setMessage("Регистрация обновлена.");
    await loadRegistrations(selectedEvent);
  };

  const deleteRegistration = async (row) => {
    await api(`/api/admin/registrations/${row.id}`, { method: "DELETE", headers });
    await loadRegistrations(selectedEvent);
  };

  return (
    <div>
      <h1 className="title">Админка</h1>
      {message && <div className="notice">{message}</div>}
      <div className="split">
        <div>
          <EventForm value={eventForm} onChange={setEventForm} onSave={saveEvent} isEditing={Boolean(editingEventId)} />
          {editingEventId && <button className="ghost" onClick={() => { setEditingEventId(null); setEventForm(emptyEvent); }}>Создать новое вместо редактирования</button>}

          <h3>Мероприятия</h3>
          <div className="grid">
            {events.map((event) => (
              <div className="card" key={event.id}>
                {event.image_url && <img className="event-image" src={event.image_url} alt={event.title} />}
                <h3>{event.title}</h3>
                <p className="muted">{event.place}, {formatDate(event.event_date)} · {event.status}</p>
                {uploadingEventId === event.id && <p className="muted">Загружаю картинку...</p>}
                <div className="actions">
                  <button className="button" onClick={() => startEditEvent(event)}><Edit size={16} /> Изменить</button>
                  <button className="button" onClick={() => setSelectedEvent(event)}>Номинации</button>
                  <button className="button" onClick={() => loadRegistrations(event)}>Участники</button>
                  <button className="button" onClick={() => downloadExport(event)}><Download size={16} /> Excel</button>
                  <button className="ghost" onClick={() => archiveEvent(event)}><Archive size={16} /> Архив</button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <NominationForm
            value={nominationForm}
            onChange={setNominationForm}
            onSave={saveNomination}
            disabled={!selectedEvent}
            isEditing={Boolean(editingNominationId)}
          />
          {editingNominationId && <button className="ghost" onClick={() => { setEditingNominationId(null); setNominationForm(emptyNomination); }}>Добавить новую вместо редактирования</button>}
          {selectedEvent && (
            <div className="card" style={{ marginTop: 14 }}>
              <h3>Номинации: {selectedEvent.title}</h3>
              <div className="checklist">
                {(selectedEvent.nominations || []).map((nomination) => (
                  <div className="check" key={nomination.id}>
                    <span>
                      <strong>{nomination.title}</strong>
                      <br />
                      <span className="muted">
                        {nomination.min_age}-{nomination.max_age}, {genderRuleLabel(nomination.gender_rule)}
                        {nomination.is_active ? "" : " · отключена"}
                      </span>
                    </span>
                    <div className="actions">
                      <button className="ghost" onClick={() => startEditNomination(nomination)}>Изменить</button>
                      <button className="ghost" onClick={() => toggleNomination(nomination)}>
                        {nomination.is_active ? "Отключить" : "Включить"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {selectedEvent && (
        <div className="card" style={{ marginTop: 14 }}>
          <h3>Участники: {selectedEvent.title}</h3>
          <button className="ghost" onClick={() => loadRegistrations(selectedEvent)}><RefreshCw size={16} /> Обновить список</button>
          <table className="table">
            <thead>
              <tr>
                <th>ФИО</th>
                <th>Никнейм</th>
                <th>Возраст</th>
                <th>Пол</th>
                <th>Номинации</th>
                <th>Тип</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {registrations.map((row) => (
                <tr key={row.id}>
                  <td>{row.full_name}</td>
                  <td>{row.nickname}</td>
                  <td>{row.age_on_event}</td>
                  <td>{genderLabel(row.gender)}</td>
                  <td>{row.nominations.map((item) => item.title).join(", ")}</td>
                  <td>{registrationTypeLabel(row.registration_type)}</td>
                  <td>
                    <button className="ghost" onClick={() => setEditRegistration({ ...row, birth_date: formatDate(row.birth_date) })}>Изменить</button>
                    <button className="ghost" onClick={() => deleteRegistration(row)}><Trash2 size={16} /> Удалить</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editRegistration && selectedEvent && (
        <div className="card" style={{ marginTop: 14 }}>
          <h3>Редактировать регистрацию</h3>
          <ParticipantForm value={editRegistration} onChange={setEditRegistration} />
          <h3>Номинации</h3>
          <NominationPicker
            nominations={(selectedEvent.nominations || []).filter((item) => item.is_active)}
            selected={editRegistration.nominations.map((item) => item.nomination_id)}
            setSelected={(ids) =>
              setEditRegistration({
                ...editRegistration,
                nominations: ids.map((id) => {
                  const nomination = selectedEvent.nominations.find((item) => item.id === id);
                  return { nomination_id: id, title: nomination?.title || "" };
                }),
              })
            }
          />
          <div className="actions">
            <button className="button primary" onClick={saveRegistrationEdit}>Сохранить</button>
            <button className="ghost" onClick={() => setEditRegistration(null)}>Отмена</button>
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  const [user, setUser] = useState(getTelegramUser());
  const [events, setEvents] = useState([]);
  const [mode, setMode] = useState("user");
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [registrationType, setRegistrationType] = useState(null);
  const [done, setDone] = useState(false);

  const reloadEvents = () => api("/api/events").then(setEvents).catch(() => setEvents([]));

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    tg?.ready?.();
    tg?.expand?.();
    tg?.disableVerticalSwipes?.();
    login().then(setUser).catch(() => {});
    reloadEvents();
  }, []);

  const reset = () => {
    setSelectedEvent(null);
    setRegistrationType(null);
    setDone(false);
    reloadEvents();
  };

  return (
    <main className="app">
      <div className="shell">
        <header className="topbar">
          <img className="logo" src="/verum-logo-white.png" alt="VERUM" />
          <nav className="tabs">
            <button className={`tab ${mode === "user" ? "active" : ""}`} onClick={() => setMode("user")}>Регистрация</button>
            {user.is_admin && <button className={`tab ${mode === "admin" ? "active" : ""}`} onClick={() => setMode("admin")}>Админка</button>}
          </nav>
        </header>
        <p className="muted" style={{ marginTop: -16 }}>
          Telegram ID: {user.telegram_id}{user.is_admin ? " · админ" : ""}
        </p>

        {mode === "admin" && user.is_admin ? (
          <Admin user={user} />
        ) : done ? (
          <div className="card">
            <h1 className="title">Регистрация сохранена</h1>
            <p className="muted">Данные добавлены в список мероприятия.</p>
            <button className="button primary" onClick={reset}>На главную</button>
          </div>
        ) : !selectedEvent ? (
          <EventList events={events} onSelect={setSelectedEvent} />
        ) : !registrationType ? (
          <RegistrationTypeSelect event={selectedEvent} onSelect={setRegistrationType} onBack={() => setSelectedEvent(null)} />
        ) : registrationType === "coach" ? (
          <CoachFlow event={selectedEvent} user={user} onBack={() => setRegistrationType(null)} onDone={() => setDone(true)} />
        ) : (
          <RegistrationFlow
            event={selectedEvent}
            type={registrationType}
            user={user}
            onBack={() => setRegistrationType(null)}
            onDone={() => setDone(true)}
          />
        )}
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
