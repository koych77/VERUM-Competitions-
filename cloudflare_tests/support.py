"""D1-compatible SQLite harness; never imported by the deployed Worker."""
import asyncio
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python_modules'))
from verum_service import install


class Statement:
    def __init__(self,db,sql,args=()): self.db,self.sql,self.args=db,sql,args
    def bind(self,*args): return Statement(self.db,self.sql,args)
    def execute(self):
        cursor=self.db.connection.execute(self.sql,self.args)
        rows=[dict(r) for r in cursor.fetchall()] if cursor.description else []
        return SimpleNamespace(results=rows,meta=SimpleNamespace(last_row_id=cursor.lastrowid,changes=cursor.rowcount))
    async def first(self):
        await asyncio.sleep(0)
        result=self.execute().results
        return result[0] if result else None
    async def all(self):
        await asyncio.sleep(0)
        return self.execute()
    async def run(self):
        await asyncio.sleep(0)
        return self.execute()


class Database:
    def __init__(self,path=':memory:'):
        self.connection=sqlite3.connect(path,check_same_thread=False,isolation_level=None)
        self.connection.row_factory=sqlite3.Row
        self.connection.execute('PRAGMA foreign_keys=ON')
        if not self.connection.execute("SELECT 1 FROM sqlite_master WHERE name='v2_people'").fetchone():
            self.connection.executescript((ROOT/'migrations'/'0001_people_and_roles.sql').read_text(encoding='utf-8'))
    def prepare(self,sql): return Statement(self,sql)
    async def batch(self,statements):
        await asyncio.sleep(0)
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            result=[s.execute() for s in statements]
            self.connection.execute('COMMIT')
            return result
        except Exception:
            self.connection.execute('ROLLBACK')
            raise


def make_app(db=None):
    db=db or Database()
    app=FastAPI()
    env=SimpleNamespace(DB=db,ADMIN_IDS='9001',WEBAPP_URL='http://127.0.0.1:5173')
    async def auth(request):
        token=request.headers.get('authorization','').removeprefix('Bearer ')
        if not token.startswith('test-') or token[5:] not in ('1','2','3','4','5'):
            raise HTTPException(401,'Требуется авторизация')
        row=db.connection.execute('SELECT * FROM users WHERE id=?',(int(token[5:]),)).fetchone()
        return dict(row)
    install(app,lambda r:env,auth)
    app.state.db=db
    return app


def seed(db):
    for ident,tid,name in [(1,9001,'Администратор'),(2,9002,'Мария'),(3,9003,'Тренер'),(4,9004,'Алексей'),(5,9005,'Другой')]:
        db.connection.execute('INSERT OR IGNORE INTO users(id,telegram_id,first_name) VALUES(?,?,?)',(ident,tid,name))
    if not db.connection.execute('SELECT 1 FROM events').fetchone():
        today=date.today()
        db.connection.execute("INSERT INTO events(id,title,event_date,place,description,registration_opens_at,registration_closes_at,status) VALUES(1,'VERUM OPEN · Тест',?,'Минск · Тестовая площадка','Изолированное тестовое событие',?,?,'open')",((today+timedelta(days=40)).isoformat(),(today-timedelta(days=1)).isoformat(),(today+timedelta(days=30)).isoformat()))
        db.connection.execute("INSERT INTO v2_event_settings(event_id,rules) VALUES(1,'Тестовый регламент. Проверяю правильность данных и правила участия.')")
        for nid,title,low,high in [(1,'Соло · Open',18,99),(2,'Соло · Kids 7–9',7,9),(3,'Соло · Juniors',10,17)]:
            db.connection.execute('INSERT INTO nominations(id,event_id,title,min_age,max_age) VALUES(?,1,?,?,?)',(nid,title,low,high))
            db.connection.execute('INSERT INTO v2_nomination_settings(nomination_id,capacity,waitlist) VALUES(?,32,1)',(nid,))
    return db
