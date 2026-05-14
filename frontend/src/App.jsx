import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Archive, Download, Edit, HelpCircle, Plus, RefreshCw, Save, Send, Trash2 } from "lucide-react";
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
  is_republic_championship: false,
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

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

const makeEmptyNomination = (index = 0) => ({
  ...emptyNomination,
  sort_order: (index + 1) * 10,
});

const makeEmptyEvent = () => ({
  ...emptyEvent,
  registration_opens_at: todayIso(),
  status: "open",
  nomination_count: 1,
  nominations: [makeEmptyNomination(0)],
});

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
  "Чемпионат республики": "Включите для чемпионатов республики: возраст будет считаться по году рождения. Например, если в 2026 году участнику исполняется 14, он не подходит в категорию до 13 даже до дня рождения.",
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

function ParticipantForm({ value, onChange, short = false, showPhone = true }) {
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
      {showPhone && (
        <Field label="Телефон">
          <input value={value.phone || ""} onChange={(event) => set("phone", event.target.value)} />
        </Field>
      )}
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

function normalizeIdentity(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function RegistrationFlow({ event, type, user, onDone, onBack }) {
  const [form, setForm] = useState(emptyParticipant);
  const [nominations, setNominations] = useState([]);
  const [selected, setSelected] = useState([]);
  const [existing, setExisting] = useState(null);
  const [existingRegistrations, setExistingRegistrations] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    setExisting(null);
    setExistingRegistrations([]);
    if (type === "short") {
      api(`/api/users/${user.telegram_id}/events/${event.id}/registrations`)
        .then(setExistingRegistrations)
        .catch(() => setExistingRegistrations([]));
    } else {
      api(`/api/users/${user.telegram_id}/events/${event.id}/registration`).then(setExisting).catch(() => {});
    }
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
      const saved = await api(`/api/events/${event.id}/register/${path}`, { method: "POST", body: JSON.stringify(body) });
      setExisting(saved);
      if (type === "short") {
        setExistingRegistrations((current) => {
          const exists = current.some((item) => item.id === saved.id);
          return exists ? current.map((item) => (item.id === saved.id ? saved : item)) : [saved, ...current];
        });
      }
      setSelected([]);
      onDone(saved);
    } catch (err) {
      setError(err.message);
    }
  };

  const currentShortRegistration =
    type === "short"
      ? existingRegistrations.find(
          (item) =>
            normalizeIdentity(item.full_name) === normalizeIdentity(form.full_name) &&
            normalizeIdentity(item.nickname) === normalizeIdentity(form.nickname) &&
            item.birth_date === ruToIso(form.birth_date),
        )
      : null;
  const activeExisting = currentShortRegistration || existing;
  const chosenIds = new Set(activeExisting?.nominations?.map((item) => item.nomination_id) || []);
  const availableForAdd = nominations.filter((item) => !chosenIds.has(item.id));

  return (
    <div>
      <button className="ghost" onClick={onBack}>Назад</button>
      <h1 className="title">{type === "short" ? "Короткая регистрация" : "Полная регистрация"}</h1>
      {type === "short" && !!existingRegistrations.length && (
        <div className="notice">
          <strong>Уже зарегистрированы с этого аккаунта:</strong>
          <br />
          {existingRegistrations.map((item) => `${item.full_name} / ${item.nickname}`).join("; ")}
          <br />
          Чтобы добавить другого ребенка, впишите его ФИО, никнейм и дату рождения.
        </div>
      )}
      {activeExisting && (
        <div className="notice">
          <strong>{type === "short" ? "Этот участник уже зарегистрирован." : "Вы уже зарегистрированы."}</strong>
          <br />
          Выбранные номинации: {activeExisting.nominations.map((item) => item.title).join(", ")}
          <br />
          Можно добавить еще подходящие номинации.
        </div>
      )}
      <ParticipantForm value={form} onChange={setForm} short={type === "short"} showPhone={type === "full"} />
      <h3>Доступные номинации</h3>
      <NominationPicker nominations={availableForAdd} selected={selected} setSelected={setSelected} />
      {error && <div className="notice">{error}</div>}
      <div className="actions">
        <button className="button primary" onClick={submit}>Зарегистрироваться</button>
      </div>
    </div>
  );
}

function createCoachStudentDraft(source = {}) {
  return {
    local_id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
    saved_id: source.id || null,
    full_name: source.full_name || "",
    nickname: source.nickname || "",
    birth_date: source.birth_date || "",
    gender: source.gender || "male",
    city: source.city || "",
    club: source.club || "",
    trainer: source.trainer || "",
    available: [],
    selected: [],
  };
}

function isBlankCoachStudentDraft(student) {
  return ["full_name", "nickname", "birth_date", "city", "club", "trainer"].every((key) => !String(student[key] || "").trim())
    && !(student.selected || []).length
    && !student.saved_id;
}

function CoachFlow({ event, user, onBack, onDone }) {
  const [coach, setCoach] = useState({ full_name: "", phone: "", city: "", club: "" });
  const [coachProfile, setCoachProfile] = useState(null);
  const [students, setStudents] = useState([]);
  const [draftStudents, setDraftStudents] = useState([createCoachStudentDraft()]);
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
    setError("");
    const missing = ["full_name", "city", "club"].filter((key) => !String(coach[key] || "").trim());
    if (missing.length) {
      setError("Заполните ФИО, город и клуб/команду тренера.");
      return;
    }
    const saved = await api("/api/profiles/coach", {
      method: "POST",
      body: JSON.stringify({ user_in: telegramUserPayload(user), coach: { ...coach, phone: coach.phone || null } }),
    });
    setCoachProfile(saved);
    await reloadStudents(saved);
    return saved;
  };

  const archiveStudent = async (student) => {
    await api(`/api/profiles/students/${student.id}/archive`, { method: "POST" });
    await reloadStudents();
  };

  const loadDraftNominations = async (student) => {
    const birthDate = ruToIso(student.birth_date);
    if (!birthDate || !student.gender) return [];
    return api(`/api/events/${event.id}/available-nominations?birth_date=${birthDate}&gender=${student.gender}`).catch(() => []);
  };

  const updateDraftStudent = async (index, next) => {
    const normalized = { ...next, selected: next.selected || [], available: next.available || [] };
    setDraftStudents((current) => current.map((item, itemIndex) => (itemIndex === index ? normalized : item)));
    if (ruToIso(normalized.birth_date) && normalized.gender) {
      const available = await loadDraftNominations(normalized);
      setDraftStudents((current) =>
        current.map((item, itemIndex) =>
          itemIndex === index
            ? {
                ...item,
                available,
                selected: item.selected.filter((id) => available.some((nomination) => nomination.id === id)),
              }
            : item,
        ),
      );
    }
  };

  const addDraftStudent = () => {
    setDraftStudents((current) => [...current, createCoachStudentDraft()]);
  };

  const addSavedStudent = async (student) => {
    if (draftStudents.some((item) => item.saved_id === student.id)) return;
    const draft = createCoachStudentDraft(student);
    const available = await loadDraftNominations(draft);
    setDraftStudents((current) => {
      const next = { ...draft, available };
      return current.length === 1 && isBlankCoachStudentDraft(current[0]) ? [next] : [...current, next];
    });
  };

  const removeDraftStudent = (index) => {
    setDraftStudents((current) => (current.length === 1 ? current : current.filter((_, itemIndex) => itemIndex !== index)));
  };

  const setDraftSelectedNominations = (index, selected) => {
    setDraftStudents((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, selected } : item)),
    );
  };

  const submit = async () => {
    setError("");
    const missingCoach = ["full_name", "city", "club"].filter((key) => !String(coach[key] || "").trim());
    if (missingCoach.length) {
      setError("Заполните ФИО, город и клуб/команду тренера.");
      return;
    }
    if (!draftStudents.length) {
      setError("Добавьте хотя бы одного ученика.");
      return;
    }
    const invalidStudent = draftStudents.find((student) => validateParticipant(student, false));
    if (invalidStudent) {
      setError("Заполните обязательные поля каждого ученика.");
      return;
    }
    if (draftStudents.some((student) => !student.selected.length)) {
      setError("У каждого ученика должна быть выбрана хотя бы одна номинация.");
      return;
    }
    const savedCoach = await saveCoach();
    const registrations = [];
    for (const student of draftStudents) {
      let studentId = student.saved_id;
      if (!studentId) {
        const { local_id, saved_id, available, selected, ...studentPayload } = student;
        const savedStudent = await api(`/api/profiles/coach/${savedCoach.id}/students`, {
          method: "POST",
          body: JSON.stringify({ ...studentPayload, birth_date: ruToIso(studentPayload.birth_date) }),
        });
        studentId = savedStudent.id;
      }
      registrations.push({ student_id: studentId, nomination_ids: student.selected });
    }
    const saved = await api(`/api/events/${event.id}/register/coach`, {
      method: "POST",
      body: JSON.stringify({ user: telegramUserPayload(user), coach: { ...coach, phone: coach.phone || null }, registrations }),
    });
    setDraftStudents([createCoachStudentDraft()]);
    await reloadStudents(savedCoach);
    onDone(saved);
  };

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
          </div>
        </div>

        <div className="card">
          <h3>Ученики для регистрации</h3>
          <p className="muted">Добавьте учеников и выберите номинации для текущего мероприятия.</p>
          <button className="button" onClick={addDraftStudent}><Plus size={18} /> Добавить ученика</button>
        </div>
      </div>

      <div className="form" style={{ marginTop: 14 }}>
        {draftStudents.map((student, index) => (
          <div className="card" key={student.local_id}>
            <h3>Ученик {index + 1}</h3>
            <ParticipantForm value={student} onChange={(next) => updateDraftStudent(index, { ...student, ...next })} showPhone={false} />
            <h3>Номинации</h3>
            <NominationPicker
              nominations={student.available || []}
              selected={student.selected || []}
              setSelected={(ids) => setDraftSelectedNominations(index, ids)}
            />
            <div className="actions">
              <button className="ghost" onClick={() => removeDraftStudent(index)}>Убрать ученика</button>
            </div>
          </div>
        ))}
      </div>

      {!!students.length && (
        <>
          <h3>Сохраненные ученики</h3>
          <div className="grid">
            {students.map((student) => (
              <div className="card" key={student.id}>
                <strong>{student.full_name}</strong> / {student.nickname}
                <p className="muted">{student.birth_date}, {genderLabel(student.gender)}</p>
                <div className="actions">
                  <button className="button" onClick={() => addSavedStudent(student)}>Добавить в заявку</button>
                  <button className="ghost" onClick={() => archiveStudent(student)}><Archive size={16} /> Архив</button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {error && <div className="notice">{error}</div>}
      <div className="actions">
        <button className="button primary" onClick={submit}><Save size={18} /> Сохранить регистрацию учеников</button>
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

function RegistrationSuccess({ event, result, onHome, onMore }) {
  const registrations = Array.isArray(result) ? result : result ? [result] : [];
  const nominationTitles = registrations
    .flatMap((item) => item.nominations || [])
    .map((item) => item.title)
    .filter(Boolean);
  const uniqueTitles = [...new Set(nominationTitles)];

  return (
    <div className="card success-card">
      <h1 className="title">Регистрация сохранена</h1>
      <p className="muted">Данные сразу добавлены в список мероприятия.</p>
      {event && (
        <div className="notice">
          <strong>{event.title}</strong>
          <br />
          {event.place}, {formatDate(event.event_date)}
        </div>
      )}
      {!!registrations.length && (
        <div className="checklist">
          {registrations.map((registration) => (
            <div className="check" key={registration.id}>
              <span>
                <strong>{registration.full_name}</strong> / {registration.nickname}
                <br />
                <span className="muted">
                  {registration.nominations.map((item) => item.title).join(", ")}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}
      {!!uniqueTitles.length && <p className="muted">Выбранные номинации: {uniqueTitles.join(", ")}</p>}
      <div className="actions">
        <button className="button primary" onClick={onHome}>На главную</button>
        <button className="ghost" onClick={onMore}>Добавить еще</button>
      </div>
    </div>
  );
}

function EventList({ events, onSelect }) {
  const [expandedEvents, setExpandedEvents] = useState({});
  const toggleExpanded = (eventId) => {
    setExpandedEvents((current) => ({ ...current, [eventId]: !current[eventId] }));
  };

  return (
    <div>
      <h1 className="title">Мероприятия VERUM</h1>
      <p className="muted">Выберите мероприятие, затем тип регистрации.</p>
      <div className="grid">
        {events.map((event) => {
          const nominations = [...(event.nominations || [])]
            .filter((item) => item.is_active)
            .sort((a, b) => a.sort_order - b.sort_order || a.title.localeCompare(b.title));
          const isExpanded = Boolean(expandedEvents[event.id]);
          const visibleNominations = isExpanded ? nominations : nominations.slice(0, 3);
          const hiddenNominationsCount = Math.max(0, nominations.length - visibleNominations.length);
          return (
            <article className="card event-card" key={event.id}>
              {event.image_url && <img className="event-image" src={event.image_url} alt={event.title} />}
              <div className="event-card-header">
                <h3>{event.title}</h3>
                {event.is_republic_championship && <span className="event-badge">Республика</span>}
              </div>
              <div className="event-meta">
                <div><span>Дата</span><strong>{formatDate(event.event_date)}</strong></div>
                <div><span>Место</span><strong>{event.place}</strong></div>
                <div><span>Регистрация до</span><strong>{formatDate(event.registration_closes_at)}</strong></div>
              </div>
              {!!nominations.length && (
                <section className="event-section">
                  <h4>Номинации</h4>
                  <div className="nomination-preview-list">
                    {visibleNominations.map((nomination) => (
                      <div className="nomination-preview" key={nomination.id}>
                        <strong>{nomination.title}</strong>
                        <span>
                          {nomination.min_age}-{nomination.max_age} лет · {genderRuleLabel(nomination.gender_rule)}
                        </span>
                        {isExpanded && nomination.experience && <small>{nomination.experience}</small>}
                      </div>
                    ))}
                  </div>
                  {!isExpanded && hiddenNominationsCount > 0 && (
                    <p className="event-more-count">Еще {hiddenNominationsCount} номинаций</p>
                  )}
                </section>
              )}
              {isExpanded && event.description && (
                <section className="event-section">
                  <h4>Описание</h4>
                  <p className="event-description">{event.description}</p>
                </section>
              )}
              <div className="event-card-buttons">
                <button className="ghost" type="button" onClick={() => toggleExpanded(event.id)}>
                  {isExpanded ? "Свернуть" : "Подробнее"}
                </button>
                <button className="button primary" type="button" onClick={() => onSelect(event)}>
                  Выбрать
                </button>
              </div>
            </article>
          );
        })}
      </div>
      {!events.length && <div className="notice">Сейчас нет открытых мероприятий.</div>}
    </div>
  );
}

function NumberSelect({ value, onChange, min, max }) {
  return (
    <select value={value} onChange={(event) => onChange(Number(event.target.value))}>
      {Array.from({ length: max - min + 1 }, (_, index) => min + index).map((number) => (
        <option key={number} value={number}>{number}</option>
      ))}
    </select>
  );
}

function NominationFields({ value, onChange }) {
  const set = (key, next) => onChange({ ...value, [key]: next });
  return (
    <div className="form">
      <Field label="Название"><input value={value.title} onChange={(event) => set("title", event.target.value)} /></Field>
      <Field label="Возраст от">
        <NumberSelect value={value.min_age} min={0} max={99} onChange={(next) => set("min_age", next)} />
      </Field>
      <Field label="Возраст до">
        <NumberSelect value={value.max_age} min={0} max={99} onChange={(next) => set("max_age", next)} />
      </Field>
      <Field label="Пол">
        <select value={value.gender_rule} onChange={(event) => set("gender_rule", event.target.value)}>
          <option value="any">Любой</option>
          <option value="male">Мужской</option>
          <option value="female">Женский</option>
        </select>
      </Field>
      <Field label="Опыт"><textarea value={value.experience} onChange={(event) => set("experience", event.target.value)} /></Field>
      <Field label="Описание"><textarea value={value.description} onChange={(event) => set("description", event.target.value)} /></Field>
    </div>
  );
}

function EventForm({ value, onChange, onSave, isEditing, isSaving }) {
  const set = (key, next) => onChange({ ...value, [key]: next });
  const setEventDate = (next) => {
    onChange({
      ...value,
      event_date: next,
      registration_closes_at: value.registration_closes_at || next,
    });
  };
  const setNominationCount = (next) => {
    const count = Math.max(1, Math.min(30, Number(next) || 1));
    const current = value.nominations || [];
    const nominations = Array.from({ length: count }, (_, index) => current[index] || makeEmptyNomination(index));
    onChange({ ...value, nomination_count: count, nominations });
  };
  const setNomination = (index, next) => {
    const nominations = [...(value.nominations || [])];
    nominations[index] = { ...next, sort_order: (index + 1) * 10 };
    onChange({ ...value, nominations });
  };
  return (
    <div className="card">
      <h3>{isEditing ? "Редактировать мероприятие" : "Создать мероприятие"}</h3>
      <div className="form">
        {value.image_preview && <img className="event-image" src={value.image_preview} alt="Картинка мероприятия" />}
        <Field label="Название"><input value={value.title} onChange={(event) => set("title", event.target.value)} /></Field>
        <Field label="Дата проведения"><input type="date" value={value.event_date} onChange={(event) => setEventDate(event.target.value)} /></Field>
        <Field label="Место"><input value={value.place} onChange={(event) => set("place", event.target.value)} /></Field>
        <Field label="Логотип/картинка мероприятия">
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(event) => {
              const file = event.target.files?.[0] || null;
              onChange({
                ...value,
                image_file: file,
                image_preview: file ? URL.createObjectURL(file) : value.image_url || null,
              });
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
        <Field label="Чемпионат республики">
          <label className="check">
            <input
              type="checkbox"
              checked={Boolean(value.is_republic_championship)}
              onChange={(event) => set("is_republic_championship", event.target.checked)}
            />
            Возраст считать по году рождения
          </label>
        </Field>
        <label className="check"><input type="checkbox" checked={value.allow_full_registration} onChange={(event) => set("allow_full_registration", event.target.checked)} /> Полная регистрация</label>
        <label className="check"><input type="checkbox" checked={value.allow_short_registration} onChange={(event) => set("allow_short_registration", event.target.checked)} /> Короткая регистрация</label>
        <label className="check"><input type="checkbox" checked={value.allow_coach_registration} onChange={(event) => set("allow_coach_registration", event.target.checked)} /> Регистрация учеников</label>
        {!isEditing && (
          <div className="nomination-batch">
            <Field
              label="Количество номинаций"
              hint="Выберите, сколько номинаций нужно добавить к мероприятию сразу. После выбора ниже появится нужное количество блоков."
            >
              <NumberSelect value={value.nomination_count || 1} min={1} max={30} onChange={setNominationCount} />
            </Field>
            {(value.nominations || []).map((nomination, index) => (
              <div className="nomination-panel" key={index}>
                <h4>Номинация {index + 1}</h4>
                <NominationFields value={nomination} onChange={(next) => setNomination(index, next)} />
              </div>
            ))}
          </div>
        )}
        <button className="button primary" onClick={onSave} disabled={isSaving}>
          <Save size={18} /> {isSaving ? "Сохраняю..." : isEditing ? "Сохранить мероприятие" : "Добавить мероприятие"}
        </button>
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
  const [eventForm, setEventForm] = useState(makeEmptyEvent);
  const [editingEventId, setEditingEventId] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [participantsEvent, setParticipantsEvent] = useState(null);
  const [adminPanel, setAdminPanel] = useState(null);
  const [registrations, setRegistrations] = useState([]);
  const [editRegistration, setEditRegistration] = useState(null);
  const [message, setMessage] = useState("");
  const [uploadingEventId, setUploadingEventId] = useState(null);
  const [importPreview, setImportPreview] = useState(null);
  const [importErrors, setImportErrors] = useState([]);
  const [savingEvent, setSavingEvent] = useState(false);
  const [savingImport, setSavingImport] = useState(false);
  const [broadcasting, setBroadcasting] = useState(false);
  const [editingNominationId, setEditingNominationId] = useState(null);
  const [editingNominationDraft, setEditingNominationDraft] = useState(null);

  const headers = useMemo(() => adminHeaders(user), [user]);
  const nominationStats = useMemo(() => {
    const counts = new Map();
    registrations.forEach((registration) => {
      (registration.nominations || []).forEach((nomination) => {
        const key = nomination.nomination_id;
        const current = counts.get(key) || { id: key, title: nomination.title, count: 0 };
        current.count += 1;
        counts.set(key, current);
      });
    });
    return Array.from(counts.values()).sort((a, b) => b.count - a.count || a.title.localeCompare(b.title));
  }, [registrations]);

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

  const downloadEventTemplate = async () => {
    const url = new URL("/api/events/admin/import-template.xlsx", window.location.origin).href;
    if (window.Telegram?.WebApp?.openLink) {
      window.Telegram.WebApp.openLink(url);
      return;
    }
    window.open(url, "_blank", "noopener,noreferrer") || window.location.assign(url);
  };

  const previewEventImport = async (file) => {
    if (!file) return;
    setMessage("");
    setImportPreview(null);
    setImportErrors([]);
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("/api/events/admin/import-preview", {
      method: "POST",
      headers,
      body: formData,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setImportErrors([body.detail || "Не удалось прочитать Excel-файл."]);
      return;
    }
    setImportErrors(body.errors || []);
    setImportPreview(body.payload || null);
  };

  const createImportedEvent = async () => {
    if (!importPreview || importErrors.length || savingImport) return;
    setSavingImport(true);
    try {
      const savedEvent = await api("/api/events/admin", {
        method: "POST",
        headers,
        body: JSON.stringify(importPreview),
      });
      const normalized = mergeUpdatedEvent(savedEvent);
      setImportPreview(null);
      setImportErrors([]);
      setMessage(`Мероприятие "${normalized.title}" создано из Excel и сразу отображается для регистрации.`);
      await refresh(normalized.id);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setSavingImport(false);
    }
  };

  const sendRegistrationFixedBroadcast = async () => {
    const confirmed = window.confirm("Отправить уведомление об исправлении ошибки всем пользователям, которые уже запускали бота?");
    if (!confirmed || broadcasting) return;
    setBroadcasting(true);
    setMessage("");
    try {
      const result = await api("/api/admin/broadcasts/registration-fixed", {
        method: "POST",
        headers,
      });
      setMessage(
        `Рассылка завершена. Отправлено: ${result.sent}. Не доставлено/бот недоступен: ${result.blocked + result.failed}. Всего в базе: ${result.total}.`,
      );
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBroadcasting(false);
    }
  };

  const saveEvent = async () => {
    if (savingEvent) return;
    setMessage("");
    setSavingEvent(true);
    try {
      const nominationsToCreate = (eventForm.nominations || []).map((item, index) => ({
        ...item,
        title: String(item.title || "").trim(),
        min_age: Number(item.min_age),
        max_age: Number(item.max_age),
        sort_order: (index + 1) * 10,
      }));
      if (!editingEventId) {
        const firstError = nominationsToCreate.map(validateNomination).find(Boolean);
        if (firstError) {
          setMessage(firstError);
          setSavingEvent(false);
          return;
        }
      }
      const method = editingEventId ? "PUT" : "POST";
      const path = editingEventId ? `/api/events/admin/${editingEventId}` : "/api/events/admin";
      const wasEditing = Boolean(editingEventId);
      const { image_file, image_preview, nomination_count, nominations, ...eventPayload } = eventForm;
      const body = editingEventId ? eventPayload : { ...eventPayload, nominations: nominationsToCreate };
      const savedEvent = await api(path, { method, headers, body: JSON.stringify(body) });
      const eventWithImage = image_file ? await uploadEventImage(savedEvent.id, image_file) : savedEvent;
      const normalized = mergeUpdatedEvent(eventWithImage);
      setEventForm(makeEmptyEvent());
      setEditingEventId(null);
      setEditRegistration(null);
      setMessage(`Мероприятие "${normalized.title}" сохранено и сразу отображается для регистрации.`);
      await refresh(normalized.id);
      if (wasEditing) {
        await loadRegistrations(normalized);
      } else {
        setRegistrations([]);
        setSelectedEvent(normalized);
      }
    } catch (error) {
      setMessage(error.message);
    } finally {
      setSavingEvent(false);
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

  const deleteEvent = async (event) => {
    const confirmed = window.confirm(`Полностью удалить мероприятие "${event.title}" вместе с номинациями и регистрациями?`);
    if (!confirmed) return;
    await api(`/api/events/admin/${event.id}`, { method: "DELETE", headers });
    if (selectedEvent?.id === event.id) {
      setSelectedEvent(null);
      setParticipantsEvent(null);
      setAdminPanel(null);
      setRegistrations([]);
      setEditRegistration(null);
    }
    if (editingEventId === event.id) {
      setEditingEventId(null);
      setEventForm(makeEmptyEvent());
    }
    setMessage("Мероприятие полностью удалено.");
    await refresh(null);
  };

  const toggleNomination = async (nomination) => {
    const updatedEvent = await api(`/api/events/admin/nominations/${nomination.id}/toggle`, { method: "POST", headers });
    mergeUpdatedEvent(updatedEvent);
  };

  const startEditNomination = (nomination) => {
    setEditingNominationId(nomination.id);
    setEditingNominationDraft({ ...nomination });
  };

  const saveNomination = async () => {
    const error = validateNomination(editingNominationDraft);
    if (error) {
      setMessage(error);
      return;
    }
    const updatedEvent = await api(`/api/events/admin/nominations/${editingNominationId}`, {
      method: "PUT",
      headers,
      body: JSON.stringify({
        ...editingNominationDraft,
        min_age: Number(editingNominationDraft.min_age),
        max_age: Number(editingNominationDraft.max_age),
      }),
    });
    mergeUpdatedEvent(updatedEvent);
    setEditingNominationId(null);
    setEditingNominationDraft(null);
    setMessage("Номинация обновлена. Регистрации участников сохранены.");
  };

  const loadRegistrations = async (event) => {
    setSelectedEvent(event);
    setParticipantsEvent(event);
    setAdminPanel("participants");
    const rows = await api(`/api/events/${event.id}/registrations`, { headers });
    setRegistrations(rows);
    setEditRegistration(null);
  };

  const downloadExport = async (event) => {
    const url = new URL(`/api/events/${event.id}/export`, window.location.origin);
    url.searchParams.set("admin_id", String(user.telegram_id));
    url.searchParams.set("v", String(Date.now()));
    if (window.Telegram?.WebApp?.openLink) {
      window.Telegram.WebApp.openLink(url.href);
      return;
    }
    const link = document.createElement("a");
    link.href = url.href;
    link.download = `verum_event_${event.id}_participants.xlsx`;
    document.body.appendChild(link);
    link.click();
    link.remove();
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
          <div className="card">
            <h3>Рассылка участникам</h3>
            <p className="muted">Отправить персональное сообщение: ошибка исправлена, а сохраненные регистрации будут перечислены по мероприятиям, участникам и номинациям.</p>
            <div className="actions">
              <button className="button primary" disabled={broadcasting} onClick={sendRegistrationFixedBroadcast}>
                <Send size={16} /> {broadcasting ? "Отправляю..." : "Разослать уведомление"}
              </button>
            </div>
          </div>

          <div className="card">
            <h3>Импорт мероприятия из Excel</h3>
            <p className="muted">Скачайте шаблон, передайте организатору, затем загрузите заполненный файл для проверки.</p>
            <div className="actions">
              <button className="button" onClick={downloadEventTemplate}><Download size={16} /> Скачать шаблон</button>
              <label className="button">
                Загрузить Excel
                <input
                  type="file"
                  accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  style={{ display: "none" }}
                  onChange={(event) => {
                    previewEventImport(event.target.files?.[0]);
                    event.target.value = "";
                  }}
                />
              </label>
            </div>
            {!!importErrors.length && (
              <div className="notice">
                <strong>Нужно исправить файл:</strong>
                <ul>
                  {importErrors.map((error) => <li key={error}>{error}</li>)}
                </ul>
              </div>
            )}
            {importPreview && (
              <div className="notice">
                <strong>{importPreview.title}</strong>
                <br />
                {importPreview.place}, {formatDate(importPreview.event_date)}
                <br />
                Номинаций: {importPreview.nominations.length}
                <div className="actions">
                  <button className="button primary" disabled={!!importErrors.length || savingImport} onClick={createImportedEvent}>
                    <Plus size={18} /> {savingImport ? "Создаю..." : "Создать из Excel"}
                  </button>
                  <button className="ghost" onClick={() => { setImportPreview(null); setImportErrors([]); }}>Сбросить</button>
                </div>
              </div>
            )}
          </div>

          <EventForm value={eventForm} onChange={setEventForm} onSave={saveEvent} isEditing={Boolean(editingEventId)} isSaving={savingEvent} />
          {editingEventId && <button className="ghost" onClick={() => { setEditingEventId(null); setEventForm(makeEmptyEvent()); }}>Создать новое вместо редактирования</button>}

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
                  <button className="button" onClick={() => { setSelectedEvent(event); setParticipantsEvent(null); setAdminPanel("nominations"); }}>Номинации</button>
                  <button className="button" onClick={() => loadRegistrations(event)}>Участники</button>
                  <button className="button" onClick={() => downloadExport(event)}><Download size={16} /> Excel</button>
                  <button className="ghost" onClick={() => archiveEvent(event)}><Archive size={16} /> Архив</button>
                  <button className="ghost danger" onClick={() => deleteEvent(event)}><Trash2 size={16} /> Удалить</button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          {adminPanel === "nominations" && selectedEvent && (
            <div className="card">
              <h3>Номинации: {selectedEvent.title}</h3>
              <div className="checklist">
                {(selectedEvent.nominations || []).map((nomination) => (
                  <div className="check" key={nomination.id}>
                    {editingNominationId === nomination.id ? (
                      <div className="nomination-editor">
                        <NominationFields value={editingNominationDraft} onChange={setEditingNominationDraft} />
                        <div className="actions">
                          <button className="button primary" onClick={saveNomination}><Save size={16} /> Сохранить</button>
                          <button className="ghost" onClick={() => { setEditingNominationId(null); setEditingNominationDraft(null); }}>Отмена</button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <span>
                          <strong>{nomination.title}</strong>
                          <br />
                          <span className="muted">
                            {nomination.min_age}-{nomination.max_age}, {genderRuleLabel(nomination.gender_rule)}
                            {nomination.is_active ? "" : " · отключена"}
                          </span>
                        </span>
                        <div className="actions">
                          <button className="ghost" onClick={() => startEditNomination(nomination)}><Edit size={16} /> Изменить</button>
                          <button className="ghost" onClick={() => toggleNomination(nomination)}>
                            {nomination.is_active ? "Отключить" : "Включить"}
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {adminPanel === "participants" && participantsEvent && (
        <div className="card participants-panel" style={{ marginTop: 14 }}>
          <div className="participants-head">
            <div>
              <h3>Участники: {participantsEvent.title}</h3>
              <p className="muted">Всего участников: <strong>{registrations.length}</strong></p>
            </div>
            <div className="actions compact">
              <button className="ghost" onClick={() => loadRegistrations(participantsEvent)}><RefreshCw size={16} /> Обновить</button>
              <button className="button" onClick={() => downloadExport(participantsEvent)}><Download size={16} /> Excel</button>
            </div>
          </div>

          <div className="nomination-stats">
            {nominationStats.length ? (
              nominationStats.map((item) => (
                <div className="stat-chip" key={item.id}>
                  <span>{item.title}</span>
                  <strong>{item.count}</strong>
                </div>
              ))
            ) : (
              <div className="notice">Пока нет зарегистрированных участников.</div>
            )}
          </div>

          <div className="participant-list">
            {registrations.map((row) => (
              <article className="participant-card" key={row.id}>
                <div className="participant-card-head">
                  <div>
                    <h4>{row.full_name}</h4>
                    <p>{row.nickname || "Без никнейма"}</p>
                  </div>
                  <span className="age-pill">{row.age_on_event} лет</span>
                </div>
                <div className="participant-meta">
                  <span>{genderLabel(row.gender)}</span>
                  <span>{registrationTypeLabel(row.registration_type)}</span>
                  {row.city && <span>{row.city}</span>}
                  {row.club && <span>{row.club}</span>}
                  {row.trainer && <span>Тренер: {row.trainer}</span>}
                  {row.phone && <span>{row.phone}</span>}
                </div>
                <div className="participant-tags">
                  {row.nominations.map((item) => (
                    <span className="tag" key={item.id}>{item.title}</span>
                  ))}
                </div>
                <div className="actions compact">
                  <button className="ghost" onClick={() => setEditRegistration({ ...row, birth_date: formatDate(row.birth_date) })}>Изменить</button>
                  <button className="ghost danger" onClick={() => deleteRegistration(row)}><Trash2 size={16} /> Удалить</button>
                </div>
              </article>
            ))}
          </div>
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
  const [registrationResult, setRegistrationResult] = useState(null);

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
    setRegistrationResult(null);
    reloadEvents();
  };

  const registerMore = () => {
    setRegistrationType(null);
    setRegistrationResult(null);
    reloadEvents();
  };

  return (
    <main className="app">
      <div className="shell">
        <header className="topbar">
          <img className="logo" src="/verum-logo-white.png" alt="VERUM" />
          <nav className="tabs">
            <button className={`tab ${mode === "user" ? "active" : ""}`} onClick={() => { setMode("user"); reloadEvents(); }}>Регистрация</button>
            {user.is_admin && <button className={`tab ${mode === "admin" ? "active" : ""}`} onClick={() => setMode("admin")}>Админка</button>}
          </nav>
        </header>
        <p className="muted" style={{ marginTop: -16 }}>
          Telegram ID: {user.telegram_id}{user.is_admin ? " · админ" : ""}
        </p>

        {mode === "admin" && user.is_admin ? (
          <Admin user={user} />
        ) : registrationResult ? (
          <RegistrationSuccess
            event={selectedEvent}
            result={registrationResult}
            onHome={reset}
            onMore={registerMore}
          />
        ) : !selectedEvent ? (
          <EventList events={events} onSelect={setSelectedEvent} />
        ) : !registrationType ? (
          <RegistrationTypeSelect event={selectedEvent} onSelect={setRegistrationType} onBack={() => setSelectedEvent(null)} />
        ) : registrationType === "coach" ? (
          <CoachFlow event={selectedEvent} user={user} onBack={() => setRegistrationType(null)} onDone={setRegistrationResult} />
        ) : (
          <RegistrationFlow
            event={selectedEvent}
            type={registrationType}
            user={user}
            onBack={() => setRegistrationType(null)}
            onDone={setRegistrationResult}
          />
        )}
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
