import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Download, Edit, Plus, Trash2 } from "lucide-react";
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
  if (!match) return "";
  return `${match[3]}-${match[2]}-${match[1]}`;
}

function formatDate(value) {
  if (!value) return "";
  const [year, month, day] = value.split("-");
  return `${day}.${month}.${year}`;
}

function telegramUserPayload(user) {
  return {
    telegram_id: user.telegram_id,
    telegram_username: user.telegram_username,
    first_name: user.first_name,
    last_name: user.last_name,
  };
}

function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function ParticipantForm({ value, onChange, short = false }) {
  const set = (key, next) => onChange({ ...value, [key]: next });
  return (
    <div className="form">
      <Field label="ФИО">
        <input value={value.full_name} onChange={(event) => set("full_name", event.target.value)} required />
      </Field>
      <Field label="Никнейм">
        <input value={value.nickname} onChange={(event) => set("nickname", event.target.value)} required />
      </Field>
      <Field label="Дата рождения">
        <input
          value={value.birth_date}
          placeholder="дд.мм.гггг"
          onChange={(event) => set("birth_date", event.target.value)}
          required
        />
      </Field>
      <Field label="Пол">
        <select value={value.gender} onChange={(event) => set("gender", event.target.value)}>
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
            <input value={value.city} onChange={(event) => set("city", event.target.value)} required />
          </Field>
          <Field label="Клуб/команда">
            <input value={value.club} onChange={(event) => set("club", event.target.value)} required />
          </Field>
          <Field label="Тренер">
            <input value={value.trainer} onChange={(event) => set("trainer", event.target.value)} required />
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
          <input
            type="checkbox"
            checked={selected.includes(nomination.id)}
            onChange={() => toggle(nomination.id)}
          />
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
          </span>
        </label>
      ))}
    </div>
  );
}

function genderRuleLabel(value) {
  if (value === "male") return "мужской";
  if (value === "female") return "женский";
  return "любой пол";
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
        if (profile) {
          setForm({ ...profile, birth_date: formatDate(profile.birth_date), phone: profile.phone || "" });
        }
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
    const birthDate = ruToIso(form.birth_date);
    if (!birthDate) {
      setError("Проверьте дату рождения. Формат: дд.мм.гггг");
      return;
    }
    if (!selected.length) {
      setError("Выберите хотя бы одну номинацию");
      return;
    }

    const clean = { ...form, birth_date: birthDate, phone: form.phone || null };
    try {
      if (type === "short") {
        await api(`/api/events/${event.id}/register/short`, {
          method: "POST",
          body: JSON.stringify({
            user: telegramUserPayload(user),
            ...clean,
            nomination_ids: selected,
          }),
        });
      } else {
        await api(`/api/events/${event.id}/register/full`, {
          method: "POST",
          body: JSON.stringify({
            user: telegramUserPayload(user),
            profile: clean,
            nomination_ids: selected,
          }),
        });
      }
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
  const [selectedStudents, setSelectedStudents] = useState([]);
  const [studentNominations, setStudentNominations] = useState({});
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/api/profiles/coach/${user.telegram_id}`).then((profile) => {
      if (profile) {
        setCoachProfile(profile);
        setCoach({ full_name: profile.full_name, phone: profile.phone || "", city: profile.city, club: profile.club });
        api(`/api/profiles/coach/${profile.id}/students`).then((rows) =>
          setStudents(rows.map((item) => ({ ...item, birth_date: formatDate(item.birth_date) }))),
        );
      }
    });
  }, [user.telegram_id]);

  const saveCoach = async () => {
    const saved = await api("/api/profiles/coach", {
      method: "POST",
      body: JSON.stringify({ user_in: telegramUserPayload(user), coach: { ...coach, phone: coach.phone || null } }),
    });
    setCoachProfile(saved);
  };

  const addStudent = async () => {
    setError("");
    if (!coachProfile) {
      setError("Сначала сохраните профиль тренера");
      return;
    }
    const birthDate = ruToIso(studentForm.birth_date);
    if (!birthDate) {
      setError("Проверьте дату рождения ученика");
      return;
    }
    const saved = await api(`/api/profiles/coach/${coachProfile.id}/students`, {
      method: "POST",
      body: JSON.stringify({ ...studentForm, birth_date: birthDate, phone: undefined }),
    });
    setStudents([...students, { ...saved, birth_date: formatDate(saved.birth_date) }]);
    setStudentForm(emptyParticipant);
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
    setStudentNominations({
      ...studentNominations,
      [studentId]: { ...studentNominations[studentId], selected },
    });
  };

  const submit = async () => {
    setError("");
    const registrations = selectedStudents.map((studentId) => ({
      student_id: studentId,
      nomination_ids: studentNominations[studentId]?.selected || [],
    }));
    if (!registrations.length || registrations.some((item) => !item.nomination_ids.length)) {
      setError("У каждого выбранного ученика должна быть хотя бы одна номинация");
      return;
    }
    await api(`/api/events/${event.id}/register/coach`, {
      method: "POST",
      body: JSON.stringify({
        user: telegramUserPayload(user),
        coach: { ...coach, phone: coach.phone || null },
        registrations,
      }),
    });
    onDone();
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
            <button className="button primary" onClick={saveCoach}>Сохранить тренера</button>
          </div>
        </div>
        <div className="card">
          <h3>Добавить ученика</h3>
          <ParticipantForm value={studentForm} onChange={setStudentForm} />
          <button className="button primary" onClick={addStudent}>Добавить</button>
        </div>
      </div>

      <h3>Ученики</h3>
      <div className="grid">
        {students.map((student) => (
          <div className="card" key={student.id}>
            <label className="check">
              <input
                type="checkbox"
                checked={selectedStudents.includes(student.id)}
                onChange={() => toggleStudent(student)}
              />
              <span>
                <strong>{student.full_name}</strong> / {student.nickname}
                <br />
                <span className="muted">{student.birth_date}, {student.gender === "male" ? "мужской" : "женский"}</span>
              </span>
            </label>
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

function Admin({ user }) {
  const [events, setEvents] = useState([]);
  const [eventForm, setEventForm] = useState(emptyEvent);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [nominationForm, setNominationForm] = useState(emptyNomination);
  const [registrations, setRegistrations] = useState([]);
  const [editRegistration, setEditRegistration] = useState(null);

  const headers = useMemo(() => adminHeaders(user), [user]);
  const refresh = () => api("/api/events/admin", { headers }).then(setEvents);

  useEffect(() => {
    refresh();
  }, []);

  const saveEvent = async () => {
    await api("/api/events/admin", {
      method: "POST",
      headers,
      body: JSON.stringify({ ...eventForm, nominations: [] }),
    });
    setEventForm(emptyEvent);
    refresh();
  };

  const addNomination = async () => {
    if (!selectedEvent) return;
    await api(`/api/events/admin/${selectedEvent.id}/nominations`, {
      method: "POST",
      headers,
      body: JSON.stringify(nominationForm),
    });
    setNominationForm(emptyNomination);
    refresh();
  };

  const loadRegistrations = async (event) => {
    setSelectedEvent(event);
    const rows = await api(`/api/events/${event.id}/registrations`, { headers });
    setRegistrations(rows);
    setEditRegistration(null);
  };

  const archiveEvent = async (event) => {
    await api(`/api/events/admin/${event.id}/archive`, { method: "POST", headers });
    refresh();
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
    await api(`/api/admin/registrations/${editRegistration.id}`, {
      method: "PUT",
      headers,
      body: JSON.stringify(payload),
    });
    await loadRegistrations(selectedEvent);
  };

  const deleteRegistration = async (row) => {
    await api(`/api/admin/registrations/${row.id}`, { method: "DELETE", headers });
    await loadRegistrations(selectedEvent);
  };

  return (
    <div>
      <h1 className="title">Админка</h1>
      <div className="split">
        <div>
          <div className="card">
            <h3>Создать мероприятие</h3>
            <div className="form">
              {[
                ["title", "Название"],
                ["event_date", "Дата проведения"],
                ["place", "Место"],
                ["registration_opens_at", "Дата открытия регистрации"],
                ["registration_closes_at", "Дата закрытия регистрации"],
              ].map(([key, label]) => (
                <Field key={key} label={label}>
                  <input
                    type={key.includes("date") || key.includes("_at") ? "date" : "text"}
                    value={eventForm[key]}
                    onChange={(event) => setEventForm({ ...eventForm, [key]: event.target.value })}
                  />
                </Field>
              ))}
              <Field label="Описание">
                <textarea
                  value={eventForm.description}
                  onChange={(event) => setEventForm({ ...eventForm, description: event.target.value })}
                />
              </Field>
              <Field label="Статус">
                <select value={eventForm.status} onChange={(event) => setEventForm({ ...eventForm, status: event.target.value })}>
                  <option value="draft">Черновик</option>
                  <option value="open">Открыто</option>
                  <option value="closed">Закрыто</option>
                  <option value="archived">Архив</option>
                </select>
              </Field>
              <button className="button primary" onClick={saveEvent}><Plus size={18} /> Создать</button>
            </div>
          </div>

          <h3>Мероприятия</h3>
          <div className="grid">
            {events.map((event) => (
              <div className="card" key={event.id}>
                <h3>{event.title}</h3>
                <p className="muted">{event.place}, {formatDate(event.event_date)} · {event.status}</p>
                <div className="actions">
                  <button className="button" onClick={() => setSelectedEvent(event)}><Edit size={16} /> Номинации</button>
                  <button className="button" onClick={() => loadRegistrations(event)}>Участники</button>
                  <button className="button" onClick={() => downloadExport(event)}>
                    <Download size={16} /> Excel
                  </button>
                  <button className="ghost" onClick={() => archiveEvent(event)}><Trash2 size={16} /> Архив</button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="card">
            <h3>Номинация</h3>
            {selectedEvent ? <p className="muted">{selectedEvent.title}</p> : <p className="muted">Выберите мероприятие</p>}
            <div className="form">
              <Field label="Название">
                <input value={nominationForm.title} onChange={(event) => setNominationForm({ ...nominationForm, title: event.target.value })} />
              </Field>
              <Field label="Возраст от">
                <input type="number" value={nominationForm.min_age} onChange={(event) => setNominationForm({ ...nominationForm, min_age: Number(event.target.value) })} />
              </Field>
              <Field label="Возраст до">
                <input type="number" value={nominationForm.max_age} onChange={(event) => setNominationForm({ ...nominationForm, max_age: Number(event.target.value) })} />
              </Field>
              <Field label="Пол">
                <select value={nominationForm.gender_rule} onChange={(event) => setNominationForm({ ...nominationForm, gender_rule: event.target.value })}>
                  <option value="any">Любой</option>
                  <option value="male">Мужской</option>
                  <option value="female">Женский</option>
                </select>
              </Field>
              <Field label="Опыт">
                <textarea value={nominationForm.experience} onChange={(event) => setNominationForm({ ...nominationForm, experience: event.target.value })} />
              </Field>
              <Field label="Описание">
                <textarea value={nominationForm.description} onChange={(event) => setNominationForm({ ...nominationForm, description: event.target.value })} />
              </Field>
              <button className="button primary" onClick={addNomination}>Добавить номинацию</button>
            </div>
          </div>
        </div>
      </div>

      {selectedEvent && (
        <div className="card" style={{ marginTop: 14 }}>
          <h3>Участники: {selectedEvent.title}</h3>
          <table className="table">
            <thead>
              <tr>
                <th>ФИО</th>
                <th>Никнейм</th>
                <th>Возраст</th>
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
                  <td>{row.nominations.map((item) => item.title).join(", ")}</td>
                  <td>{row.registration_type}</td>
                  <td>
                    <button className="ghost" onClick={() => setEditRegistration({ ...row, birth_date: formatDate(row.birth_date) })}>
                      Редактировать
                    </button>
                    <button className="ghost" onClick={() => deleteRegistration(row)}>Удалить</button>
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
            nominations={selectedEvent.nominations || []}
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

  useEffect(() => {
    window.Telegram?.WebApp?.ready?.();
    login().then(setUser).catch(() => {});
    api("/api/events").then(setEvents).catch(() => setEvents([]));
  }, []);

  const reset = () => {
    setSelectedEvent(null);
    setRegistrationType(null);
    setDone(false);
  };

  return (
    <main className="app">
      <div className="shell">
        <header className="topbar">
          <img className="logo" src="/verum-logo-white.png" alt="VERUM" />
          <nav className="tabs">
            <button className={`tab ${mode === "user" ? "active" : ""}`} onClick={() => setMode("user")}>Регистрация</button>
            {user.is_admin && (
              <button className={`tab ${mode === "admin" ? "active" : ""}`} onClick={() => setMode("admin")}>Админка</button>
            )}
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
