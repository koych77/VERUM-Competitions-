"""Cloudflare Worker for VERUM Telegram registration."""
import hashlib, hmac, json, time
from urllib.parse import parse_qsl
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from js import fetch
from workers import asgi

app = FastAPI(title="VERUM Competitions")
Default = asgi.entrypoint(app)

async def setup(db):
    for sql in (
        "CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,telegram_id INTEGER UNIQUE NOT NULL,telegram_username TEXT,first_name TEXT,last_name TEXT)",
        "CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL,expires_at INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,event_date TEXT NOT NULL,place TEXT NOT NULL DEFAULT '',description TEXT NOT NULL DEFAULT '',image_url TEXT,registration_opens_at TEXT NOT NULL,registration_closes_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',is_republic_championship INTEGER DEFAULT 0,allow_full_registration INTEGER DEFAULT 1,allow_short_registration INTEGER DEFAULT 1,allow_coach_registration INTEGER DEFAULT 1)",
        "CREATE TABLE IF NOT EXISTS nominations(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id INTEGER NOT NULL,title TEXT NOT NULL,min_age INTEGER DEFAULT 0,max_age INTEGER DEFAULT 99,gender_rule TEXT DEFAULT 'any',battle_type TEXT DEFAULT 'solo',experience TEXT DEFAULT '',description TEXT DEFAULT '',is_active INTEGER DEFAULT 1,sort_order INTEGER DEFAULT 100)",
        "CREATE TABLE IF NOT EXISTS registrations(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id INTEGER NOT NULL,user_id INTEGER NOT NULL,registration_type TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_registration_owner_event ON registrations(event_id,user_id,registration_type)",
    ):
        await db.prepare(sql).run()

def e(request): return request.scope["env"]

def admins(raw):
    result=set()
    for value in (raw or "").replace(";",",").split(","):
        try: result.add(int(value.strip()))
        except ValueError: pass
    return result

def telegram_user(init_data, token, ttl):
    values=dict(parse_qsl(init_data,keep_blank_values=True)); supplied=values.pop("hash","")
    if not supplied or abs(int(time.time())-int(values.get("auth_date","0")))>ttl: raise ValueError("Сессия Telegram устарела")
    check="\n".join(f"{k}={values[k]}" for k in sorted(values))
    secret=hmac.new(b"WebAppData",token.encode(),hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(secret,check.encode(),hashlib.sha256).hexdigest(),supplied): raise ValueError("Подпись Telegram не подтверждена")
    return json.loads(values["user"])

async def auth(request):
    header=request.headers.get("authorization","")
    row=await e(request).DB.prepare("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires_at>?").bind(header.removeprefix("Bearer "),int(time.time())).first()
    if row is None: raise HTTPException(401,"Требуется авторизация")
    return row

@app.get("/api/health")
async def health(request:Request):
    await setup(e(request).DB); return {"status":"ok","database":"d1","query":1}

@app.post("/api/auth/telegram")
async def login(request:Request):
    await setup(e(request).DB); body=await request.json()
    try: user=telegram_user(body.get("init_data",""),e(request).BOT_TOKEN,int(getattr(e(request),"TELEGRAM_INIT_DATA_TTL_SECONDS","86400")))
    except Exception as exc: raise HTTPException(401,str(exc)) from exc
    tid=int(user["id"])
    await e(request).DB.prepare("INSERT INTO users(telegram_id,telegram_username,first_name,last_name) VALUES(?,?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET telegram_username=excluded.telegram_username,first_name=excluded.first_name,last_name=excluded.last_name").bind(tid,user.get("username"),user.get("first_name"),user.get("last_name")).run()
    saved=await e(request).DB.prepare("SELECT * FROM users WHERE telegram_id=?").bind(tid).first(); token=uuid4().hex+uuid4().hex; expires=int(time.time())+604800
    await e(request).DB.prepare("INSERT INTO sessions VALUES(?,?,?)").bind(token,saved.id,expires).run()
    return {"id":saved.id,"telegram_id":tid,"telegram_username":saved.telegram_username,"first_name":saved.first_name,"last_name":saved.last_name,"is_admin":tid in admins(getattr(e(request),"ADMIN_IDS","")),"access_token":token,"expires_at":expires}

@app.get("/api/events")
async def events(request:Request):
    await setup(e(request).DB); result=await e(request).DB.prepare("SELECT * FROM events WHERE status='open' AND registration_opens_at<=date('now') AND registration_closes_at>=date('now') ORDER BY event_date").all(); output=[]
    for row in result.results:
        item=dict(row); noms=await e(request).DB.prepare("SELECT * FROM nominations WHERE event_id=? AND is_active=1 ORDER BY sort_order,id").bind(row.id).all(); item["nominations"]=[dict(n) for n in noms.results]; output.append(item)
    return output

@app.get("/api/directories/{kind}")
async def directories(kind:str): return []

@app.get("/api/registrations/me")
async def registrations(request:Request):
    user=await auth(request); rows=await e(request).DB.prepare("SELECT payload FROM registrations WHERE user_id=? ORDER BY id DESC").bind(user.id).all(); return [json.loads(r.payload) for r in rows.results]

@app.get("/api/profiles/participant/{telegram_id}")
async def profile(telegram_id:int,request:Request): await auth(request); return None

@app.get("/api/users/{telegram_id}/events/{event_id}/registration")
async def registration(telegram_id:int,event_id:int,request:Request):
    user=await auth(request); row=await e(request).DB.prepare("SELECT payload FROM registrations WHERE user_id=? AND event_id=? AND registration_type='full' ORDER BY id DESC LIMIT 1").bind(user.id,event_id).first(); return json.loads(row.payload) if row else None

@app.get("/api/users/{telegram_id}/events/{event_id}/registrations")
async def short_registrations(telegram_id:int,event_id:int,request:Request):
    user=await auth(request); rows=await e(request).DB.prepare("SELECT payload FROM registrations WHERE user_id=? AND event_id=? AND registration_type='short' ORDER BY id DESC").bind(user.id,event_id).all(); return [json.loads(r.payload) for r in rows.results]

@app.get("/api/events/{event_id}/available-nominations")
async def nominations(event_id:int,request:Request):
    rows=await e(request).DB.prepare("SELECT * FROM nominations WHERE event_id=? AND is_active=1 ORDER BY sort_order,id").bind(event_id).all(); return [dict(r) for r in rows.results]

@app.post("/api/events/{event_id}/register/{kind}")
async def register(event_id:int,kind:str,request:Request):
    user=await auth(request); body=await request.json(); profile=body.get("profile",body)
    existing=await e(request).DB.prepare("SELECT id FROM registrations WHERE event_id=? AND user_id=? AND registration_type=?").bind(event_id,user.id,kind).first()
    if existing: rid=existing.id
    else:
        inserted=await e(request).DB.prepare("INSERT INTO registrations(event_id,user_id,registration_type,payload) VALUES(?,?,?,?)").bind(event_id,user.id,kind,"{}").run(); rid=inserted.meta.last_row_id
    chosen=[]
    for nomination_id in body.get("nomination_ids",[]):
        row=await e(request).DB.prepare("SELECT * FROM nominations WHERE id=? AND event_id=? AND is_active=1").bind(nomination_id,event_id).first()
        if row: chosen.append(dict(row))
    saved={"id":rid,"event_id":event_id,"registration_type":kind,"full_name":profile.get("full_name",""),"nickname":profile.get("nickname",""),"birth_date":profile.get("birth_date"),"gender":profile.get("gender"),"phone":profile.get("phone"),"city":profile.get("city"),"club":profile.get("club"),"trainer":profile.get("trainer"),"team_name":body.get("team_name"),"team_members":body.get("team_members"),"nominations":chosen}
    await e(request).DB.prepare("UPDATE registrations SET payload=? WHERE id=?").bind(json.dumps(saved,ensure_ascii=False),rid).run(); return saved

@app.post("/api/bot/webhook/{secret}")
async def webhook(secret:str,request:Request):
    token=e(request).BOT_TOKEN
    if not hmac.compare_digest(secret,hashlib.sha256(token.encode()).hexdigest()[:32]): raise HTTPException(404,"Not found")
    update=await request.json(); message=update.get("message") or {}; chat=message.get("chat") or {}; command=(message.get("text") or "").split("@")[0]
    if chat.get("id") and command in {"/start","/form"}:
        payload={"chat_id":chat["id"],"text":"Привет! Нажмите кнопку ниже, чтобы открыть регистрацию на мероприятия VERUM.","reply_markup":{"inline_keyboard":[[{"text":"Открыть регистрацию VERUM","web_app":{"url":e(request).WEBAPP_URL}}]]}}
        response=await fetch(f"https://api.telegram.org/bot{token}/sendMessage",method="POST",headers={"content-type":"application/json"},body=json.dumps(payload))
        if not response.ok: raise HTTPException(502,"Telegram API error")
    return {"ok":True}

@app.get("/{path:path}")
async def frontend(path:str,request:Request):
    response=await e(request).ASSETS.fetch(f"https://assets.local/{path or 'index.html'}")
    if response.status==404 and "." not in path: response=await e(request).ASSETS.fetch("https://assets.local/index.html")
    return Response(content=await response.bytes(),status_code=response.status,headers=dict(response.headers))
