-- Additive migration: legacy tables and rows are retained unchanged.
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,telegram_id INTEGER UNIQUE NOT NULL,telegram_username TEXT,first_name TEXT,last_name TEXT);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL,expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,event_date TEXT NOT NULL,place TEXT NOT NULL DEFAULT '',description TEXT NOT NULL DEFAULT '',image_url TEXT,registration_opens_at TEXT NOT NULL,registration_closes_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',is_republic_championship INTEGER DEFAULT 0,allow_full_registration INTEGER DEFAULT 1,allow_short_registration INTEGER DEFAULT 1,allow_coach_registration INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS nominations(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id INTEGER NOT NULL,title TEXT NOT NULL,min_age INTEGER DEFAULT 0,max_age INTEGER DEFAULT 99,gender_rule TEXT DEFAULT 'any',battle_type TEXT DEFAULT 'solo',experience TEXT DEFAULT '',description TEXT DEFAULT '',is_active INTEGER DEFAULT 1,sort_order INTEGER DEFAULT 100);
CREATE TABLE IF NOT EXISTS registrations(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id INTEGER NOT NULL,user_id INTEGER NOT NULL,registration_type TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE v2_people(id TEXT PRIMARY KEY,profile TEXT NOT NULL,fingerprint TEXT NOT NULL,created_by INTEGER NOT NULL REFERENCES users(id),version INTEGER NOT NULL DEFAULT 1,merged_into TEXT REFERENCES v2_people(id),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX v2_people_match ON v2_people(fingerprint);
CREATE TABLE v2_identity_keys(fingerprint TEXT PRIMARY KEY,person_id TEXT NOT NULL REFERENCES v2_people(id));
CREATE TABLE v2_links(user_id INTEGER NOT NULL REFERENCES users(id),person_id TEXT NOT NULL REFERENCES v2_people(id),role TEXT NOT NULL CHECK(role IN ('self','parent','coach')),status TEXT NOT NULL CHECK(status IN ('verified','pending','archived','revoked')),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,person_id,role));
CREATE UNIQUE INDEX v2_one_self ON v2_links(user_id) WHERE role='self' AND status='verified';
CREATE INDEX v2_links_person ON v2_links(person_id,status);
CREATE TABLE v2_event_settings(event_id INTEGER PRIMARY KEY REFERENCES events(id),rules TEXT NOT NULL DEFAULT '',rules_version INTEGER NOT NULL DEFAULT 1,minor_age INTEGER NOT NULL DEFAULT 18,require_parent INTEGER NOT NULL DEFAULT 1,edit_closes_at TEXT,timezone TEXT NOT NULL DEFAULT 'Europe/Minsk',version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE v2_nomination_settings(nomination_id INTEGER PRIMARY KEY REFERENCES nominations(id),capacity INTEGER,waitlist INTEGER NOT NULL DEFAULT 0,team_size INTEGER NOT NULL DEFAULT 1);
CREATE TABLE v2_event_access(user_id INTEGER NOT NULL REFERENCES users(id),event_id INTEGER NOT NULL REFERENCES events(id),PRIMARY KEY(user_id,event_id));
CREATE TABLE v2_registrations(id TEXT PRIMARY KEY,event_id INTEGER NOT NULL REFERENCES events(id),person_id TEXT NOT NULL REFERENCES v2_people(id),submitted_by INTEGER NOT NULL REFERENCES users(id),status TEXT NOT NULL CHECK(status IN ('awaiting_consent','submitted','needs_changes','confirmed','rejected','cancelled','waitlisted')),snapshot TEXT NOT NULL,comment TEXT NOT NULL DEFAULT '',rules_version INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(event_id,person_id));
CREATE INDEX v2_reg_event ON v2_registrations(event_id,status);
CREATE TABLE v2_entries(registration_id TEXT NOT NULL REFERENCES v2_registrations(id),nomination_id INTEGER NOT NULL REFERENCES nominations(id),status TEXT NOT NULL CHECK(status IN ('pending','confirmed','waitlisted','cancelled')),team_id TEXT,PRIMARY KEY(registration_id,nomination_id));
CREATE INDEX v2_entry_capacity ON v2_entries(nomination_id,status);
CREATE TABLE v2_consents(registration_id TEXT NOT NULL REFERENCES v2_registrations(id),user_id INTEGER NOT NULL REFERENCES users(id),kind TEXT NOT NULL CHECK(kind IN ('rules','parent')),rules_version INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(registration_id,user_id,kind,rules_version));
CREATE TABLE v2_drafts(user_id INTEGER NOT NULL REFERENCES users(id),person_id TEXT NOT NULL REFERENCES v2_people(id),event_id INTEGER NOT NULL REFERENCES events(id),payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,person_id,event_id));
CREATE TABLE v2_requests(user_id INTEGER NOT NULL REFERENCES users(id),request_key TEXT NOT NULL,digest TEXT NOT NULL,resource_id TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,request_key));
CREATE TABLE v2_invites(token_hash TEXT PRIMARY KEY,person_id TEXT NOT NULL REFERENCES v2_people(id),created_by INTEGER NOT NULL REFERENCES users(id),role TEXT NOT NULL CHECK(role IN ('parent','coach','self')),expires_at INTEGER NOT NULL,claimed_by INTEGER REFERENCES users(id),status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','claimed','accepted','rejected','revoked')));
CREATE TABLE v2_cases(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),kind TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',resolution TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE v2_audit(id TEXT PRIMARY KEY,actor_id INTEGER NOT NULL REFERENCES users(id),action TEXT NOT NULL,object_id TEXT NOT NULL,details TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE v2_notifications(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),title TEXT NOT NULL,body TEXT NOT NULL,registration_id TEXT,read_at TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX v2_notify_user ON v2_notifications(user_id,created_at);
CREATE TABLE v2_settings(user_id INTEGER PRIMARY KEY REFERENCES users(id),preferences TEXT NOT NULL DEFAULT '{}');
CREATE TABLE v2_legacy_map(legacy_id INTEGER PRIMARY KEY REFERENCES registrations(id),person_id TEXT REFERENCES v2_people(id),registration_id TEXT REFERENCES v2_registrations(id),status TEXT NOT NULL DEFAULT 'review');
CREATE TABLE v2_guard(value INTEGER NOT NULL CHECK(value=1));
-- Capacity is enforced inside each write transaction, not by a UI counter.
CREATE TRIGGER v2_capacity_insert BEFORE INSERT ON v2_entries WHEN NEW.status IN ('pending','confirmed') AND NEW.team_id IS NULL
BEGIN
 SELECT CASE WHEN (SELECT capacity FROM v2_nomination_settings WHERE nomination_id=NEW.nomination_id) IS NOT NULL
 AND (SELECT COUNT(*) FROM v2_entries WHERE nomination_id=NEW.nomination_id AND status IN ('pending','confirmed') AND team_id IS NULL)>=(SELECT capacity FROM v2_nomination_settings WHERE nomination_id=NEW.nomination_id)
 THEN RAISE(ABORT,'capacity_exceeded') END;
END;
CREATE TRIGGER v2_capacity_update BEFORE UPDATE OF status ON v2_entries WHEN NEW.status IN ('pending','confirmed') AND OLD.status NOT IN ('pending','confirmed') AND NEW.team_id IS NULL
BEGIN
 SELECT CASE WHEN (SELECT capacity FROM v2_nomination_settings WHERE nomination_id=NEW.nomination_id) IS NOT NULL
 AND (SELECT COUNT(*) FROM v2_entries WHERE nomination_id=NEW.nomination_id AND status IN ('pending','confirmed') AND team_id IS NULL)>=(SELECT capacity FROM v2_nomination_settings WHERE nomination_id=NEW.nomination_id)
 THEN RAISE(ABORT,'capacity_exceeded') END;
END;
