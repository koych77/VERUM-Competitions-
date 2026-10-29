"""Run with .venv/Scripts/python scripts/preview_v2.py. Local test database only."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloudflare_tests'))
from support import Database,make_app,seed
from fastapi import HTTPException,Request
import uvicorn

db_path=ROOT/'.wrangler'/'verum-preview.db'
db_path.parent.mkdir(exist_ok=True)
app=make_app(seed(Database(str(db_path))))

@app.post('/api/auth/dev')
async def development_login(request:Request):
    data=await request.json()
    user=app.state.db.connection.execute('SELECT * FROM users WHERE telegram_id=?',(data.get('telegram_id'),)).fetchone()
    if not user: raise HTTPException(401,'Choose one of the isolated preview identities')
    return {**dict(user),'access_token':f"test-{user['id']}"}

if __name__=='__main__':
    uvicorn.run(app,host='127.0.0.1',port=8788)
