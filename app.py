"""NJA System — WSGI API, SQLite, sessions and authorization."""
import social
import business
import teamwork
import agency_access
import agency_production
import workspace_updates
import interaction_updates
import agency_portal
import agency_editorial
import agency_commercial
import agency_finance
import agency_calendar
import agency_whatsapp
import agency_ads
import companion
import enterprise
import integrations
import calls
import attachments
import mailer
import meetings
import base64, hashlib, hmac, io, json, mimetypes, os, re, secrets, sqlite3, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
DATA=Path(os.getenv('NJA_DATA', str(ROOT/'data')))
DB=DATA/'nja.sqlite3'
TZ=ZoneInfo('America/Sao_Paulo')
ORIGIN=os.getenv('NJA_ORIGIN','http://localhost:8000').rstrip('/')
SECURE=ORIGIN.startswith('https://')
MAX_FILE=8*1024*1024
PERMS=['dashboard','tasks','calendar','chats','team','notifications','task_create','task_edit','task_assign','task_approve','task_complete','task_all','calendar_all','user_manage','role_manage','chat_manage','audit','social','clients','client_manage','drive','ai']
PERMS += business.PERMISSIONS + teamwork.PERMISSIONS + agency_access.PERMISSIONS
STATES=['pending','progress','approval','done']

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def uid(): return secrets.token_hex(12)
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def hash_password(p):
    salt=secrets.token_bytes(16)
    return salt.hex()+':'+hashlib.scrypt(p.encode(),salt=salt,n=16384,r=8,p=1).hex()
def verify_password(p,h):
    try:
        salt,want=h.split(':'); return hmac.compare_digest(hashlib.scrypt(p.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex(),want)
    except (ValueError,TypeError): return False

class ClosingConnection(sqlite3.Connection):
    def __exit__(self,exc_type,exc_value,traceback):
        try:return super().__exit__(exc_type,exc_value,traceback)
        finally:self.close()

def connect():
    c=sqlite3.connect(DB,timeout=20,factory=ClosingConnection); c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA busy_timeout=20000')
    return c

def init():
    DATA.mkdir(parents=True,exist_ok=True); (DATA/'uploads').mkdir(exist_ok=True)
    with connect() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
CREATE TABLE IF NOT EXISTS roles(id TEXT PRIMARY KEY,name TEXT NOT NULL,permissions TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role_id TEXT NOT NULL REFERENCES roles(id),master INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,title TEXT NOT NULL DEFAULT '',area TEXT NOT NULL DEFAULT '',bio TEXT NOT NULL DEFAULT '',photo TEXT,preferences TEXT NOT NULL DEFAULT '{"tasks":true,"events":true,"messages":true}',created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),csrf TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS resets(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS rate_limits(key TEXT PRIMARY KEY,count INTEGER NOT NULL,until REAL NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',project TEXT NOT NULL DEFAULT '',owner TEXT NOT NULL REFERENCES users(id),creator TEXT NOT NULL REFERENCES users(id),priority TEXT NOT NULL DEFAULT 'normal',status TEXT NOT NULL DEFAULT 'pending',start TEXT,due TEXT,checklist TEXT NOT NULL DEFAULT '[]',parent TEXT REFERENCES tasks(id),created TEXT NOT NULL,updated TEXT NOT NULL,completed TEXT);
CREATE TABLE IF NOT EXISTS task_members(task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id),PRIMARY KEY(task_id,user_id));
CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY,task_id TEXT NOT NULL REFERENCES tasks(id),user_id TEXT NOT NULL REFERENCES users(id),text TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',creator TEXT NOT NULL REFERENCES users(id),start TEXT NOT NULL,end TEXT NOT NULL,location TEXT NOT NULL DEFAULT '',shared INTEGER NOT NULL DEFAULT 0,recurrence TEXT NOT NULL DEFAULT 'none',until_date TEXT,reminder INTEGER NOT NULL DEFAULT 30,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS event_members(event_id TEXT REFERENCES events(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id),PRIMARY KEY(event_id,user_id));
CREATE TABLE IF NOT EXISTS rooms(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL DEFAULT 'group',creator TEXT REFERENCES users(id),created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS room_members(room_id TEXT REFERENCES rooms(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id),last_read TEXT NOT NULL DEFAULT '',PRIMARY KEY(room_id,user_id));
CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,room_id TEXT REFERENCES rooms(id),user_id TEXT REFERENCES users(id),text TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,name TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,user_id TEXT REFERENCES users(id),task_id TEXT REFERENCES tasks(id),room_id TEXT REFERENCES rooms(id),created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),title TEXT NOT NULL,body TEXT NOT NULL,link TEXT NOT NULL,category TEXT NOT NULL,seen INTEGER NOT NULL DEFAULT 0,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,action TEXT NOT NULL,entity TEXT NOT NULL,detail TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS subscriptions(endpoint TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),subscription TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS push_outbox(id TEXT PRIMARY KEY,notification_id TEXT REFERENCES notifications(id),attempts INTEGER NOT NULL DEFAULT 0,next_attempt REAL NOT NULL DEFAULT 0,last_error TEXT);
CREATE TABLE IF NOT EXISTS reminder_log(key TEXT PRIMARY KEY,created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_tasks_owner ON tasks(owner);
CREATE INDEX IF NOT EXISTS ix_messages_room ON messages(room_id,created);
CREATE INDEX IF NOT EXISTS ix_notifications_user ON notifications(user_id,created);
''')
        for table, column, definition in [('rooms','photo','TEXT'),('rooms','project',"TEXT NOT NULL DEFAULT ''"),('rooms','description',"TEXT NOT NULL DEFAULT ''"),('users','cover','TEXT')]:
            if column not in [r[1] for r in c.execute('PRAGMA table_info('+table+')')]:
                c.execute('ALTER TABLE '+table+' ADD COLUMN '+column+' '+definition)
        c.execute('INSERT OR IGNORE INTO roles VALUES(?,?,?)',('master','Administrador master',json.dumps(PERMS)))
        c.execute('INSERT OR IGNORE INTO roles VALUES(?,?,?)',('member','Colaborador',json.dumps(['dashboard','tasks','calendar','chats','team','notifications','task_create','task_edit','task_complete'])))
        c.execute('INSERT OR IGNORE INTO rooms(id,name,kind,creator,created) VALUES(?,?,?,?,?)',('general','Equipe NJA','general',None,now()))
        social.init(c)
        enterprise.init(c)
        integrations.init(c)
        calls.init(c)
        meetings.init(c)
        companion.init(c)
        business.init(c)
        teamwork.init(c)
        agency_access.init(c)
        agency_production.init(c)
        agency_portal.init(c)
        agency_editorial.init(c)
        agency_commercial.init(c)
        agency_finance.init(c)
        agency_calendar.init(c)
        agency_whatsapp.init(c)
        agency_ads.init(c)
        workspace_updates.init(c)
        interaction_updates.init(c)

def user_public(c,u):
    d=dict(u); d.pop('password',None); d['permissions']=PERMS if d['master'] else json.loads(c.execute('SELECT permissions FROM roles WHERE id=?',(d['role_id'],)).fetchone()[0]); d['preferences']=json.loads(d['preferences']); return d

def perm(u,p): return bool(u['master'] or p in u['permissions'])
def need(u,p):
    if not perm(u,p): raise Error(403,'Você não tem permissão para esta ação.')
class Error(Exception):
    def __init__(self,status,message): self.status=status; self.message=message

def audit(c,u,action,entity,detail=''):
    c.execute('INSERT INTO audit(user_id,action,entity,detail,created) VALUES(?,?,?,?,?)',(u['id'],action,entity,str(detail)[:2000],now()))
def notify(c,user,title,body,link,category):
    active=c.execute('SELECT active,preferences FROM users WHERE id=?',(user,)).fetchone()
    if not active or not active['active']: return
    raw=c.execute('SELECT * FROM users WHERE id=?',(user,)).fetchone()
    if not agency_access.notification_allowed(sys.modules[__name__],c,user_public(c,raw),link):return
    n=uid(); c.execute('INSERT INTO notifications(id,user_id,title,body,link,category,created) VALUES(?,?,?,?,?,?,?)',(n,user,title,body[:500],link,category,now()))
    if json.loads(active['preferences']).get(category,True): c.execute('INSERT INTO push_outbox(id,notification_id) VALUES(?,?)',(uid(),n))

def notify_mentions(c,u,d,body,link,category,skip=()):
    ids=d.get('mentions',[])
    if not isinstance(ids,list):return
    for id in set(x for x in ids[:50] if isinstance(x,str)) - set(skip) - {u['id']}:
        raw=c.execute('SELECT * FROM users WHERE id=? AND active=1',(id,)).fetchone()
        if not raw or '@'+raw['name'] not in body:continue
        target=user_public(c,raw)
        if link=='feed' and not perm(target,'social'):continue
        notify(c,id,u['name']+' mencionou você',body,link,category)

def textfield(d,k,required=False,limit=2000):
    s=d.get(k,'')
    if not isinstance(s,str): raise Error(400,f'Campo inválido: {k}')
    s=s.strip()
    if (required and not s) or len(s)>limit: raise Error(400,f'Preencha {k} (máximo {limit} caracteres).')
    return s

def datefield(s):
    if not s: return None
    try:
        d=datetime.fromisoformat(s.replace('Z','+00:00'))
        if d.tzinfo is None: d=d.replace(tzinfo=TZ)
        return d.astimezone(timezone.utc).isoformat(timespec='seconds')
    except (ValueError,AttributeError): raise Error(400,'Data ou horário inválido.')

def active_ids(c,ids):
    if not isinstance(ids,list) or len(ids)>200: raise Error(400,'Participantes inválidos.')
    ids=list(dict.fromkeys(ids))
    for i in ids:
        if not isinstance(i,str) or not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(i,)).fetchone(): raise Error(400,'Usuário inexistente ou inativo.')
    return ids

def task_access(c,u,t):
    if t['client_id'] and not agency_access.allowed(c,u,t['client_id']):return False
    return perm(u,'task_all') or t['owner']==u['id'] or t['creator']==u['id'] or bool(c.execute('SELECT 1 FROM task_members WHERE task_id=? AND user_id=?',(t['id'],u['id'])).fetchone())
def get_task(c,u,id):
    need(u,'tasks'); t=c.execute('SELECT * FROM tasks WHERE id=?',(id,)).fetchone()
    if not t: raise Error(404,'Tarefa não encontrada.')
    if not task_access(c,u,t): raise Error(403,'Sem acesso à tarefa.')
    return t

def event_access(c,u,e):
    return perm(u,'calendar_all') or e['creator']==u['id'] or e['shared'] or bool(c.execute('SELECT 1 FROM event_members WHERE event_id=? AND user_id=?',(e['id'],u['id'])).fetchone())
def room_access(c,u,id):
    need(u,'chats')
    room=c.execute('SELECT client_id FROM rooms WHERE id=?',(id,)).fetchone()
    if room and room[0]:agency_access.need(sys.modules[__name__],c,u,room[0])
    if not c.execute('SELECT 1 FROM room_members WHERE room_id=? AND user_id=?',(id,u['id'])).fetchone(): raise Error(403,'Sem acesso à conversa.')
def task_json(c,t):
    d=dict(t)
    if d.get('client_id'):
        client=c.execute('SELECT name FROM clients WHERE id=?',(d['client_id'],)).fetchone()
        if client:d['project']=client['name']
    d['checklist']=json.loads(d['checklist']);d['members']=[r[0] for r in c.execute('SELECT user_id FROM task_members WHERE task_id=?',(t['id'],))];return d

def throttle(c,key,limit=10):
    row=c.execute('SELECT * FROM rate_limits WHERE key=?',(key,)).fetchone()
    if row and row['until']>time.time():
        if row['count']>=limit: raise Error(429,'Muitas tentativas. Aguarde 15 minutos.')
        c.execute('UPDATE rate_limits SET count=count+1 WHERE key=?',(key,))
    else: c.execute('INSERT OR REPLACE INTO rate_limits VALUES(?,?,?)',(key,1,time.time()+900))
    c.commit()

def authenticate(c,environ):
    cookies={x.strip().split('=',1)[0]:x.strip().split('=',1)[1] for x in environ.get('HTTP_COOKIE','').split(';') if '=' in x}
    token=cookies.get('nja_session','')
    row=c.execute('SELECT users.*,sessions.csrf FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>? AND active=1',(digest(token),time.time())).fetchone()
    if not row: raise Error(401,'Entre na sua conta para continuar.')
    u=user_public(c,row);csrf=u.pop('csrf');return u,csrf,token

def send_reset(email,token):
    mailer.send_reset(ORIGIN,email,token)

def api(c,environ,method,path,d,q):
    headers=[]
    if path.startswith('/api/portal/'):
        return agency_portal.portal_api(sys.modules[__name__],c,environ,method,path,d,q),headers
    if path=='/api/login' and method=='POST':
        email=textfield(d,'email',True,254).lower();p=textfield(d,'password',True,256)
        throttle(c,'login-ip:'+environ.get('REMOTE_ADDR',''),40);throttle(c,'login:'+email)
        row=c.execute('SELECT * FROM users WHERE email=? AND active=1',(email,)).fetchone()
        valid=verify_password(p,row['password'] if row else '00'*16+':'+'00'*64)
        if not row or not valid: raise Error(401,'E-mail ou senha incorretos.')
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
        c.execute('INSERT INTO sessions(token,user_id,csrf,expires) VALUES(?,?,?,?)',(digest(token),row['id'],csrf,time.time()+86400))
        c.execute('DELETE FROM rate_limits WHERE key=?',('login:'+email,));audit(c,row,'login',row['id'])
        headers.append(('Set-Cookie',f'nja_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=86400'+('; Secure' if SECURE else '')))
        return {'user':user_public(c,row),'csrf':csrf},headers
    if path=='/api/recover' and method=='POST':
        email=textfield(d,'email',True,254).lower();throttle(c,'reset-ip:'+environ.get('REMOTE_ADDR',''),8)
        if not mailer.config()['ready']: raise Error(503,'Recuperação por e-mail ainda não configurada. Solicite ao administrador uma redefinição de senha.')
        row=c.execute('SELECT * FROM users WHERE email=? AND active=1',(email,)).fetchone();c.commit()
        if row:
            token=secrets.token_urlsafe(32);c.execute('DELETE FROM resets WHERE user_id=?',(row['id'],));c.execute('INSERT INTO resets VALUES(?,?,?)',(digest(token),row['id'],time.time()+1800));c.commit()
            try:send_reset(email,token)
            except Exception:
                c.execute('DELETE FROM resets WHERE token=?',(digest(token),));c.commit()
                raise Error(503,'Não foi possível enviar o e-mail. Tente novamente mais tarde.')
        return {'message':'Se a conta estiver ativa, enviaremos as instruções.'},headers
    if path=='/api/reset' and method=='POST':
        token=textfield(d,'token',True,256);p=textfield(d,'password',True,256)
        if len(p)<10:raise Error(400,'Use uma senha com pelo menos 10 caracteres.')
        if d.get('confirmation',p)!=p:raise Error(400,'As senhas não coincidem.')
        c.execute('BEGIN IMMEDIATE')
        r=c.execute('SELECT resets.* FROM resets JOIN users ON users.id=resets.user_id WHERE resets.token=? AND resets.expires>? AND users.active=1',(digest(token),time.time())).fetchone()
        if not r:raise Error(400,'Link inválido ou expirado.')
        c.execute('UPDATE users SET password=? WHERE id=?',(hash_password(p),r['user_id']));c.execute('DELETE FROM resets WHERE user_id=?',(r['user_id'],));c.execute('DELETE FROM sessions WHERE user_id=?',(r['user_id'],))
        return {'message':'Senha redefinida. Entre novamente.'},headers
    u,csrf,token=authenticate(c,environ)
    if method!='GET' and not hmac.compare_digest(environ.get('HTTP_X_CSRF_TOKEN',''),csrf):raise Error(403,'Sessão inválida. Atualize a página.')
    if path=='/api/presence' and method=='POST':
        c.execute('UPDATE users SET last_seen=? WHERE id=?',(time.time(),u['id']))
        c.execute('UPDATE sessions SET last_seen=? WHERE token=?',(time.time(),digest(token)))
    extra=interaction_updates.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=workspace_updates.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=agency_ads.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=agency_whatsapp.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=agency_calendar.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=agency_finance.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=agency_commercial.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=agency_editorial.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=agency_portal.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=agency_production.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=agency_access.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=teamwork.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=business.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=companion.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=mailer.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=meetings.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=calls.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=integrations.audio_api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=integrations.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=enterprise.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    extra=social.api(sys.modules[__name__],c,u,method,path,d,q)
    if extra is not None:return extra,headers
    if path=='/api/me' and method=='GET':return {'user':u,'csrf':csrf,'push_key':os.getenv('VAPID_PUBLIC_KEY',''),'smtp_ready':mailer.config()['ready']},headers
    if path=='/api/logout' and method=='POST':
        c.execute('DELETE FROM sessions WHERE token=?',(digest(token),));headers.append(('Set-Cookie','nja_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'+('; Secure' if SECURE else '')));return {'ok':True},headers
    if path=='/api/password' and method=='POST':
        r=c.execute('SELECT password FROM users WHERE id=?',(u['id'],)).fetchone()
        if not verify_password(textfield(d,'current',True,256),r[0]):raise Error(400,'Senha atual incorreta.')
        p=textfield(d,'password',True,256)
        if len(p)<10:raise Error(400,'Use pelo menos 10 caracteres.')
        c.execute('UPDATE users SET password=? WHERE id=?',(hash_password(p),u['id']));c.execute('DELETE FROM sessions WHERE user_id=? AND token<>?',(u['id'],digest(token)));audit(c,u,'password_change',u['id']);return {'ok':True},headers
    if path=='/api/preferences' and method=='POST':
        prefs={k:bool(d.get(k,True)) for k in ['tasks','events','messages']};c.execute('UPDATE users SET preferences=? WHERE id=?',(json.dumps(prefs),u['id']));return {'ok':True},headers
    if path=='/api/users' and method=='GET':
        if not any(perm(u,p) for p in ['team','tasks','calendar','chats']):return [user_public(c,c.execute('SELECT * FROM users WHERE id=?',(u['id'],)).fetchone())],headers
        rows=c.execute('SELECT * FROM users'+(' WHERE deleted=0' if perm(u,'user_manage') else ' WHERE active=1 AND deleted=0')+' ORDER BY name').fetchall()
        result=[]
        for r in rows:
            v=user_public(c,r);v.update(social.presence(c,r['id']))
            if not perm(u,'user_manage'):
                for k in ['email','permissions','preferences','master']:v.pop(k,None)
            result.append(v)
        return result,headers
    if path=='/api/roles' and method=='GET':
        need(u,'user_manage');return [dict(r)|{'permissions':json.loads(r['permissions'])} for r in c.execute('SELECT * FROM roles')],headers
    if path=='/api/roles' and method=='POST':
        need(u,'role_manage');id=d.get('id') or uid();name=textfield(d,'name',True,80);ps=d.get('permissions',[])
        if not isinstance(ps,list) or any(p not in PERMS for p in ps) or id=='master':raise Error(400,'Permissões inválidas.')
        c.execute('INSERT INTO roles VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,permissions=excluded.permissions',(id,name,json.dumps(ps)));audit(c,u,'role_save',id);return {'id':id},headers
    if path=='/api/users' and method=='POST':
        need(u,'user_manage');name=textfield(d,'name',True,120);email=textfield(d,'email',True,254).lower();p=textfield(d,'password',True,256)
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(p)<10:raise Error(400,'Informe um e-mail válido e senha com 10 caracteres ou mais.')
        role=d.get('role_id','member')
        if not c.execute('SELECT 1 FROM roles WHERE id=? AND id<>?',(role,'master')).fetchone():raise Error(400,'Perfil de acesso inválido.')
        id=uid();c.execute('INSERT INTO users(id,email,name,password,role_id,title,area,bio,created) VALUES(?,?,?,?,?,?,?,?,?)',(id,email,name,hash_password(p),role,textfield(d,'title',False,100),textfield(d,'area',False,100),textfield(d,'bio',False,2000),now()))
        c.execute('INSERT INTO room_members(room_id,user_id) VALUES(?,?)',('general',id));audit(c,u,'user_create',id,name);return {'id':id},headers
    if path.startswith('/api/users/') and path.endswith('/activity') and method=='GET':
        id=path.split('/')[3]
        if id!=u['id']:need(u,'audit')
        return [dict(r) for r in c.execute('SELECT * FROM audit WHERE user_id=? ORDER BY id DESC LIMIT 100',(id,))],headers
    if path.startswith('/api/users/') and method=='PATCH':
        id=path.split('/')[-1];r=c.execute('SELECT * FROM users WHERE id=?',(id,)).fetchone()
        if not r:raise Error(404,'Usuário não encontrado.')
        if r['deleted']:raise Error(404,'Perfil excluído.')
        if id!=u['id']:need(u,'user_manage')
        admin=perm(u,'user_manage');fields=social.profile_fields(sys.modules[__name__],d)
        if 'email' in d:
            if not u['master']:raise Error(403,'Somente o master pode alterar o e-mail de login.')
            email=textfield(d,'email',True,254).lower()
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise Error(400,'E-mail inválido.')
            if c.execute('SELECT 1 FROM users WHERE lower(email)=? AND id<>?',(email,id)).fetchone():raise Error(409,'Este e-mail já está em uso.')
            fields['email']=email
            if email!=r['email']:
                c.execute('DELETE FROM sessions WHERE user_id=?',(id,));c.execute('DELETE FROM resets WHERE user_id=?',(id,))
        for k in ['name','title','area','bio']:
            if k in d:fields[k]=textfield(d,k,k=='name',2000 if k=='bio' else 120)
        for image_field in ['photo','cover']:
            if image_field not in d:continue
            f=c.execute('SELECT * FROM files WHERE id=?',(d[image_field],)).fetchone()
            if not f or c.execute('SELECT 1 FROM social_assets WHERE file_id=?',(f['id'],)).fetchone() or c.execute('SELECT 1 FROM editorial_uploads WHERE file_id=?',(f['id'],)).fetchone() or f['user_id']!=id or f['task_id'] or f['room_id'] or not f['mime'].startswith('image/'):raise Error(400,'Foto inválida.')
            fields[image_field]=f['id']
        if admin:
            if 'role_id' in d:
                if r['master'] or d['role_id']=='master' or not c.execute('SELECT 1 FROM roles WHERE id=?',(d['role_id'],)).fetchone():raise Error(400,'Perfil inválido.')
                fields['role_id']=d['role_id']
            if 'active' in d:
                if r['master']:raise Error(400,'O master não pode ser desativado.')
                fields['active']=int(bool(d['active']))
            if d.get('password'):
                p=textfield(d,'password',True,256)
                if len(p)<10:raise Error(400,'Use pelo menos 10 caracteres.')
                fields['password']=hash_password(p);c.execute('DELETE FROM sessions WHERE user_id=?',(id,));c.execute('DELETE FROM resets WHERE user_id=?',(id,))
        elif any(k in d for k in ['active','role_id','password']):raise Error(403,'Somente o administrador pode alterar esses campos.')
        if fields:c.execute('UPDATE users SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',list(fields.values())+[id])
        audit(c,u,'user_update',id,','.join(fields));return {'ok':True},headers
    if path=='/api/tasks' and method=='GET':
        need(u,'tasks');return [task_json(c,t) for t in c.execute('SELECT * FROM tasks ORDER BY created DESC') if task_access(c,u,t)],headers
    if path=='/api/tasks' and method=='POST':
        need(u,'tasks');need(u,'task_create');owner=d.get('owner') or u['id'];active_ids(c,[owner]);members=active_ids(c,d.get('members',[]))
        if owner!=u['id'] or members:need(u,'task_assign')
        title=textfield(d,'title',True,180);start=datefield(d.get('start'));due=datefield(d.get('due'))
        if start and due and due<start:raise Error(400,'O prazo deve ser posterior ao início.')
        priority=d.get('priority','normal')
        if priority not in ['low','normal','high','urgent']:raise Error(400,'Prioridade inválida.')
        parent=d.get('parent') or None
        if parent:get_task(c,u,parent)
        id=uid();c.execute('INSERT INTO tasks(id,title,description,project,owner,creator,priority,start,due,parent,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(id,title,textfield(d,'description',False,10000),textfield(d,'project',False,120),owner,u['id'],priority,start,due,parent,now(),now()))
        linked=enterprise.task_client(sys.modules[__name__],c,u,d)
        agency_access.task_members(sys.modules[__name__],c,linked.get('client_id'),[owner]+members)
        if linked:c.execute('UPDATE tasks SET '+','.join(k+'=?' for k in linked)+' WHERE id=?',list(linked.values())+[id])
        for m in members:c.execute('INSERT INTO task_members VALUES(?,?)',(id,m))
        audit(c,u,'task_create',id,title)
        for m in set([owner]+members)-{u['id']}:notify(c,m,'Nova tarefa',title,'tasks:'+id,'tasks')
        return {'id':id},headers
    if path.startswith('/api/tasks/'):
        parts=path.split('/');id=parts[3];t=get_task(c,u,id)
        if len(parts)==4 and method=='GET':
            return task_json(c,t)|{'comments':[dict(r) for r in c.execute('SELECT comments.*,users.name FROM comments JOIN users ON users.id=comments.user_id WHERE task_id=? ORDER BY comments.created',(id,))],'files':[dict(r) for r in c.execute('SELECT id,name,mime,size FROM files WHERE task_id=?',(id,))],'history':[dict(r) for r in c.execute('SELECT audit.*,users.name FROM audit LEFT JOIN users ON users.id=audit.user_id WHERE entity=? ORDER BY audit.id DESC LIMIT 50',(id,))]},headers
        if len(parts)==5 and parts[4]=='comments' and method=='POST':
            tx=textfield(d,'text',True,5000);c.execute('INSERT INTO comments VALUES(?,?,?,?,?)',(uid(),id,u['id'],tx,now()));audit(c,u,'task_comment',id)
            for m in set([t['owner'],t['creator']]+[r[0] for r in c.execute('SELECT user_id FROM task_members WHERE task_id=?',(id,))])-{u['id']}:notify(c,m,'Comentário em '+t['title'],tx,'tasks:'+id,'tasks')
            notify_mentions(c,u,d,tx,'tasks:'+id,'tasks',set([t['owner'],t['creator']]+[r[0] for r in c.execute('SELECT user_id FROM task_members WHERE task_id=?',(id,))]))
            return {'ok':True},headers
        if len(parts)==4 and method=='PATCH':
            fields={}
            if any(k in d for k in ['title','description','project','client_id','start','due','priority','checklist']):need(u,'task_edit')
            for k in ['title','description','project']:
                if k in d:fields[k]=textfield(d,k,k=='title',10000 if k=='description' else 180)
            fields.update(enterprise.task_client(sys.modules[__name__],c,u,d,t))
            for k in ['start','due']:
                if k in d:fields[k]=datefield(d[k])
            if fields.get('start',t['start']) and fields.get('due',t['due']) and fields.get('due',t['due'])<fields.get('start',t['start']):raise Error(400,'Prazo anterior ao início.')
            if 'priority' in d:
                if d['priority'] not in ['low','normal','high','urgent']:raise Error(400,'Prioridade inválida.')
                fields['priority']=d['priority']
            if 'checklist' in d:
                if not isinstance(d['checklist'],list) or len(d['checklist'])>100:raise Error(400,'Checklist inválido.')
                items=[]
                for item in d['checklist']:
                    if not isinstance(item,dict):raise Error(400,'Checklist inválido.')
                    items.append({'text':textfield(item,'text',True,300),'done':bool(item.get('done'))})
                fields['checklist']=json.dumps(items)
            if 'owner' in d:need(u,'task_assign');active_ids(c,[d['owner']]);fields['owner']=d['owner']
            if 'members' in d:
                need(u,'task_assign');ms=active_ids(c,d['members']);c.execute('DELETE FROM task_members WHERE task_id=?',(id,))
                for m in ms:c.execute('INSERT INTO task_members VALUES(?,?)',(id,m))
            if any(k in d for k in ['client_id','owner','members']):agency_access.task_members(sys.modules[__name__],c,fields.get('client_id',t['client_id']),[fields.get('owner',t['owner'])]+[r[0] for r in c.execute('SELECT user_id FROM task_members WHERE task_id=?',(id,))])
            if 'status' in d:
                status=d['status']
                if status not in STATES:raise Error(400,'Estado inválido.')
                if status=='done':agency_production.dependency_guard(sys.modules[__name__],c,id)
                if status=='done':need(u,'task_approve' if t['status']=='approval' else 'task_complete')
                else:need(u,'task_edit')
                fields['status']=status;fields['completed']=(t['completed'] if t['status']=='done' else now()) if status=='done' else None
                if status=='done':
                    for timer in c.execute('SELECT * FROM running_timers WHERE task_id=?',(id,)).fetchall():social.finish_timer(sys.modules[__name__],c,timer)
            fields['updated']=now();c.execute('UPDATE tasks SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',list(fields.values())+[id]);audit(c,u,'task_update',id,','.join(fields))
            for m in set([fields.get('owner',t['owner']),t['creator']]+[r[0] for r in c.execute('SELECT user_id FROM task_members WHERE task_id=?',(id,))])-{u['id']}:notify(c,m,'Tarefa atualizada',t['title'],'tasks:'+id,'tasks')
            return {'ok':True},headers
    if path=='/api/events' and method=='GET':
        need(u,'calendar');result=[]
        for e in c.execute('SELECT * FROM events ORDER BY start'):
            if event_access(c,u,e):result.append(dict(e)|{'members':[r[0] for r in c.execute('SELECT user_id FROM event_members WHERE event_id=?',(e['id'],))]})
        return result,headers
    if path=='/api/events' and method=='POST':
        need(u,'calendar');start=datefield(d.get('start'));end=datefield(d.get('end'));rec=d.get('recurrence','none')
        if not start or not end or end<=start:raise Error(400,'Informe início e término válidos.')
        if rec not in ['none','daily','weekly','monthly']:raise Error(400,'Recorrência inválida.')
        try:rem=int(d.get('reminder',30))
        except (TypeError,ValueError):raise Error(400,'Lembrete inválido.')
        if rem not in [0,5,15,30,60,1440]:raise Error(400,'Lembrete inválido.')
        until=datefield(d.get('until_date'))
        if rec!='none' and (not until or until<start):raise Error(400,'Defina o término da recorrência após o início.')
        members=active_ids(c,d.get('members',[]));shared=bool(d.get('shared'))
        if shared:need(u,'calendar_all')
        id=uid();title=textfield(d,'title',True,180)
        c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(id,title,textfield(d,'description',False,5000),u['id'],start,end,textfield(d,'location',False,500),int(shared),rec,until,rem,now()))
        for m in set(members+[u['id']]):c.execute('INSERT INTO event_members VALUES(?,?)',(id,m))
        for m in set(members)-{u['id']}:notify(c,m,'Novo compromisso',title,'calendar','events')
        audit(c,u,'event_create',id,title);return {'id':id},headers
    if path.startswith('/api/events/') and method in ['DELETE','PATCH']:
        need(u,'calendar');id=path.split('/')[-1];e=c.execute('SELECT * FROM events WHERE id=?',(id,)).fetchone()
        if not e:raise Error(404,'Compromisso não encontrado.')
        if e['creator']!=u['id']:need(u,'calendar_all')
        if method=='DELETE':
            for m in c.execute('SELECT user_id FROM event_members WHERE event_id=?',(id,)):
                if m[0]!=u['id']:notify(c,m[0],'Compromisso cancelado',e['title'],'calendar','events')
            c.execute('DELETE FROM events WHERE id=?',(id,));audit(c,u,'event_delete',id);return {'ok':True},headers
        fields={}
        for k in ['title','description','location']:
            if k in d:fields[k]=textfield(d,k,k=='title',5000 if k=='description' else 500)
        for k in ['start','end','until_date']:
            if k in d:fields[k]=datefield(d[k])
        if not fields.get('start',e['start']) or not fields.get('end',e['end']) or fields.get('end',e['end'])<=fields.get('start',e['start']):raise Error(400,'Intervalo inválido.')
        if fields:c.execute('UPDATE events SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',list(fields.values())+[id])
        audit(c,u,'event_update',id);return {'ok':True},headers
    if path=='/api/rooms' and method=='GET':
        need(u,'chats');result=[]
        for r in c.execute('''SELECT rooms.*,room_members.last_read FROM rooms
          JOIN room_members ON rooms.id=room_members.room_id
          WHERE room_members.user_id=? AND NOT EXISTS(
            SELECT 1 FROM room_deletions d WHERE d.user_id=? AND d.room_id=rooms.id)
          ORDER BY rooms.created''',(u['id'],u['id'])):
            if r['client_id'] and not agency_access.allowed(c,u,r['client_id']):continue
            x=dict(r);x.update(teamwork.serialize(sys.modules[__name__],c,u,r));x['archived']=bool(c.execute('SELECT 1 FROM room_archives WHERE user_id=? AND room_id=?',(u['id'],r['id'])).fetchone());x['members']=[v[0] for v in c.execute('SELECT user_id FROM room_members WHERE room_id=?',(r['id'],))]
            x['portal_contacts']=[{'id':'portal:'+v['id'],'name':v['name'],'photo':v['photo'],'external':True} for v in c.execute('''SELECT p.id,p.name,cl.photo FROM portal_accounts p JOIN clients cl ON cl.id=p.client_id WHERE p.client_id=? AND p.active=1 ORDER BY p.name''',(r['client_id'],))] if r['kind']=='group' and r['client_id'] else []
            x['unread']=c.execute("SELECT count(*) FROM messages WHERE room_id=? AND created>? AND COALESCE(user_id,'')<>?",(r['id'],r['last_read'],u['id'])).fetchone()[0];last=c.execute('SELECT text,created FROM messages WHERE room_id=? ORDER BY created DESC,rowid DESC LIMIT 1',(r['id'],)).fetchone();x['last']=dict(last) if last else None;result.append(x)
        return result,headers
    if path=='/api/rooms' and method=='POST':
        need(u,'chats');kind=d.get('kind','group');members=active_ids(c,d.get('members',[]))
        if kind=='direct':
            if len(members)!=1 or members[0]==u['id']:raise Error(400,'Escolha outro usuário.')
            for r in c.execute("SELECT rooms.id FROM rooms JOIN room_members ON room_members.room_id=rooms.id WHERE rooms.kind='direct' AND room_members.user_id=?",(u['id'],)):
                existing={v[0] for v in c.execute('SELECT user_id FROM room_members WHERE room_id=?',(r[0],))}
                if existing=={u['id'],members[0]}:
                    c.execute('DELETE FROM room_deletions WHERE user_id=? AND room_id=?',(u['id'],r[0]))
                    return {'id':r[0]},headers
            name='Conversa direta'
        elif kind=='group':need(u,'chat_manage');name=textfield(d,'name',True,120)
        else:raise Error(400,'Tipo inválido.')
        if kind!='group' and d.get('external') is not None:raise Error(400,'Convites externos exigem uma conversa em grupo.')
        id=uid();c.execute('INSERT INTO rooms(id,name,kind,creator,created) VALUES(?,?,?,?,?)',(id,name,kind,u['id'],now()))
        if kind=='group':
            c.execute('UPDATE rooms SET project=?,description=? WHERE id=?',(textfield(d,'project',False,120),textfield(d,'description',False,2000),id))
        for m in set(members+[u['id']]):c.execute('INSERT INTO room_members(room_id,user_id) VALUES(?,?)',(id,m))
        result={'id':id}
        if kind=='group' and d.get('external') is not None:result['invitation']=agency_portal.invite_room_external(sys.modules[__name__],c,u,id,d['external'])
        audit(c,u,'room_create',id,name);return result,headers
    if path.startswith('/api/rooms/'):
        parts=path.split('/');id=parts[3];room_access(c,u,id)
        if len(parts)==4 and method=='DELETE':
            r=c.execute('SELECT kind FROM rooms WHERE id=?',(id,)).fetchone()
            if r['kind']=='general':raise Error(400,'A conversa geral da equipe não pode ser excluída.')
            c.execute('INSERT OR REPLACE INTO room_deletions(user_id,room_id,deleted) VALUES(?,?,?)',(u['id'],id,now()))
            audit(c,u,'room_delete_for_user',id);return {'ok':True},headers
        if len(parts)==4 and method=='PATCH':
            need(u,'chat_manage');r=c.execute('SELECT * FROM rooms WHERE id=?',(id,)).fetchone()
            if r['kind']!='group':raise Error(400,'Participantes deste tipo de conversa não podem ser alterados.')
            members=active_ids(c,d.get('members',[m[0] for m in c.execute('SELECT user_id FROM room_members WHERE room_id=?',(id,))]));members=list(set(members+[u['id']]))
            c.execute('DELETE FROM room_members WHERE room_id=?',(id,))
            for m in members:c.execute('INSERT INTO room_members(room_id,user_id) VALUES(?,?)',(id,m))
            if r['client_id']:c.execute('INSERT OR IGNORE INTO client_team SELECT ?,user_id FROM room_members WHERE room_id=?',(r['client_id'],id))
            if 'name' in d:c.execute('UPDATE rooms SET name=? WHERE id=?',(textfield(d,'name',True,120),id))
            for field in ['project','description']:
                if field in d:c.execute('UPDATE rooms SET '+field+'=? WHERE id=?',(textfield(d,field,False,2000 if field=='description' else 120),id))
            audit(c,u,'room_update',id);return {'ok':True},headers
        if len(parts)==5 and parts[4]=='messages':
            if method=='GET':
                rows=[dict(r) for r in c.execute("SELECT messages.*,COALESCE(users.name,messages.portal_name,'Cliente') AS name,users.photo FROM messages LEFT JOIN users ON users.id=messages.user_id WHERE room_id=? ORDER BY messages.rowid DESC LIMIT 200",(id,))];rows.reverse()
                interaction_updates.mark_delivered(c,id,u['id'],now())
                interaction_updates.add_quotes(sys.modules[__name__],c,id,rows)
                interaction_updates.add_receipts(c,rows)
                return {'messages':rows,'files':[dict(r) for r in c.execute('SELECT f.id,f.name,f.mime,f.size,f.user_id,f.created,t.text AS transcript,t.status AS transcript_status FROM files f LEFT JOIN audio_transcripts t ON t.file_id=f.id WHERE room_id=? AND id NOT IN (SELECT photo FROM rooms WHERE photo IS NOT NULL) ORDER BY f.created',(id,))]},headers
            if method=='POST':
                reply=interaction_updates.validate_reply(sys.modules[__name__],c,id,d)
                tx=textfield(d,'text',True,5000);mid=uid();c.execute('INSERT INTO messages(id,room_id,user_id,text,created) VALUES(?,?,?,?,?)',(mid,id,u['id'],tx,now()))
                interaction_updates.prepare_receipts(c,id,mid,u['id'])
                c.execute('DELETE FROM room_deletions WHERE room_id=?',(id,))
                if reply:c.execute('INSERT INTO message_replies VALUES(?,?,?)',(mid,*reply))
                for m in c.execute('SELECT user_id FROM room_members WHERE room_id=? AND user_id<>?',(id,u['id'])):notify(c,m[0],u['name'],tx,'chats:'+id,'messages')
                notify_mentions(c,u,d,tx,'chats:'+id,'messages',[r[0] for r in c.execute('SELECT user_id FROM room_members WHERE room_id=?',(id,))])
                if d.get('defer_ai') is True and integrations.wants_response(sys.modules[__name__],c,u,id,tx):
                    return {'id':mid,'ai_pending':True},headers
                return {'id':mid}|integrations.maybe_respond(sys.modules[__name__],c,u,id,tx),headers
        if len(parts)==5 and parts[4]=='read' and method=='POST':
            stamp=now();c.execute('UPDATE room_members SET last_read=? WHERE room_id=? AND user_id=?',(stamp,id,u['id']))
            interaction_updates.mark_read(c,id,u['id'],stamp);return {'ok':True},headers
    if path=='/api/notifications' and method=='GET':
        need(u,'notifications');return [dict(r) for r in c.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY rowid DESC LIMIT 100',(u['id'],)) if agency_access.notification_allowed(sys.modules[__name__],c,u,r['link'])],headers
    if path=='/api/notifications/read' and method=='POST':
        need(u,'notifications')
        if d.get('id'):c.execute('UPDATE notifications SET seen=1 WHERE id=? AND user_id=?',(d['id'],u['id']))
        else:c.execute('UPDATE notifications SET seen=1 WHERE user_id=?',(u['id'],))
        return {'ok':True},headers
    if path=='/api/audit' and method=='GET':
        need(u,'audit');return [dict(r) for r in c.execute('SELECT audit.*,users.name FROM audit LEFT JOIN users ON users.id=audit.user_id ORDER BY audit.id DESC LIMIT 200')],headers
    if path=='/api/metrics' and method=='GET':
        need(u,'dashboard');days=int(q.get('days',['30'])[0])
        if days not in [7,30,90]:raise Error(400,'Período inválido.')
        since=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat();result=[]
        users=c.execute('SELECT id,name,area FROM users WHERE active=1'+('' if u['master'] else ' AND id=?'),() if u['master'] else (u['id'],)).fetchall()
        for v in users:
            tasks=[r for r in c.execute('SELECT * FROM tasks WHERE owner=? AND created>=?',(v['id'],since)) if task_access(c,u,r)];done=sum(t['status']=='done' for t in tasks);result.append(dict(v)|{'total':len(tasks),'done':done,'percent':round(100*done/len(tasks)) if tasks else 0,'pending':sum(t['status']=='pending' for t in tasks),'progress':sum(t['status']=='progress' for t in tasks),'approval':sum(t['status']=='approval' for t in tasks),'late':sum(t['status']!='done' and bool(t['due']) and t['due']<now() for t in tasks)})
        return {'days':days,'since':since,'criterion':'Tarefas criadas no período e atribuídas atualmente ao usuário; conclusão = estado atual concluída.','users':result},headers
    if path=='/api/push' and method=='POST':
        if not os.getenv('VAPID_PUBLIC_KEY'):raise Error(503,'Push ainda não configurado no servidor.')
        sub=d.get('subscription');endpoint=sub.get('endpoint','') if isinstance(sub,dict) else ''
        host=urlparse(endpoint).hostname or ''
        allowed=(host=='fcm.googleapis.com' or host.endswith('.push.services.mozilla.com') or host=='updates.push.services.mozilla.com' or host.endswith('.push.apple.com') or host.endswith('.notify.windows.com'))
        if not allowed or not endpoint.startswith('https://') or not isinstance(sub.get('keys'),dict) or not sub['keys'].get('auth') or not sub['keys'].get('p256dh'):raise Error(400,'Assinatura push inválida ou provedor não permitido.')
        c.execute('INSERT INTO subscriptions VALUES(?,?,?) ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id,subscription=excluded.subscription',(endpoint,u['id'],json.dumps(sub)));return {'ok':True},headers
    if path=='/api/push' and method=='DELETE':
        c.execute('DELETE FROM subscriptions WHERE user_id=?',(u['id'],));return {'ok':True},headers
    if path=='/api/upload' and method=='POST':
        name=textfield(d,'name',True,180);tid=d.get('task_id');rid=d.get('room_id');photo=bool(d.get('photo'));room_photo=bool(d.get('room_photo'))
        if sum(bool(x) for x in [tid,rid,photo])!=1:raise Error(400,'Selecione um destino para o arquivo.')
        if tid:get_task(c,u,tid);need(u,'task_edit')
        if rid:room_access(c,u,rid)
        if rid and not room_photo:teamwork.need_action(sys.modules[__name__],c,u,rid,'send')
        if room_photo:
            if not rid:raise Error(400,'Selecione o grupo.')
            teamwork.need_action(sys.modules[__name__],c,u,rid,'manage')
            if c.execute('SELECT kind FROM rooms WHERE id=?',(rid,)).fetchone()[0]=='direct':raise Error(400,'Altere a foto pelo perfil.')
        try:raw=base64.b64decode(d.get('data',''),validate=True)
        except Exception:raise Error(400,'Arquivo inválido.')
        if not raw or len(raw)>MAX_FILE:raise Error(400,'Limite de arquivo: 8 MB.')
        mime=None
        if raw.startswith(b'\x89PNG\r\n\x1a\n'):mime='image/png'
        elif raw.startswith(b'\xff\xd8\xff'):mime='image/jpeg'
        elif raw.startswith(b'RIFF') and raw[8:12]==b'WEBP':mime='image/webp'
        elif raw.startswith(b'%PDF-'):mime='application/pdf'
        if not mime or ((photo or room_photo) and not mime.startswith('image/')):raise Error(400,'Aceitamos PNG, JPG, WebP e PDF; fotos devem ser imagens.')
        if photo or room_photo:
            # Decode and re-encode avatars: strip metadata and reject malformed/decompression bombs.
            try:
                from PIL import Image
                Image.MAX_IMAGE_PIXELS=20_000_000
                im=Image.open(io.BytesIO(raw));im.load();im.thumbnail((512,512));out=io.BytesIO();im.convert('RGB').save(out,format='JPEG',quality=88);raw=out.getvalue();mime='image/jpeg'
            except Exception:raise Error(400,'Imagem inválida ou grande demais para foto de perfil.')
        id=uid();(DATA/'uploads'/id).write_bytes(raw);c.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?)',(id,Path(name).name,mime,len(raw),u['id'],tid,rid,now()))
        if room_photo:
            c.execute('UPDATE rooms SET photo=? WHERE id=?',(id,rid))
        if rid and not room_photo:
            for m in c.execute('SELECT user_id FROM room_members WHERE room_id=? AND user_id<>?',(rid,u['id'])):notify(c,m[0],u['name'],'Enviou um arquivo: '+name,'chats:'+rid,'messages')
        audit(c,u,'file_upload',id,name);return {'id':id},headers
    raise Error(404,'Recurso não encontrado.')

SECURITY=[('X-Content-Type-Options','nosniff'),('X-Frame-Options','DENY'),('Referrer-Policy','same-origin'),('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; media-src 'self' blob:; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")]
if SECURE:SECURITY.append(('Strict-Transport-Security','max-age=31536000'))

def application(environ,start_response):
    method=environ['REQUEST_METHOD'];path=environ.get('PATH_INFO','/');q=parse_qs(environ.get('QUERY_STRING',''));headers=list(SECURITY)
    def response(status,data,mime='application/json; charset=utf-8',extra=None):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
        start_response(f'{status} '+{200:'OK',201:'Created',303:'See Other',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',413:'Payload Too Large',429:'Too Many Requests',500:'Internal Server Error',503:'Service Unavailable'}.get(status,'Error'),headers+[('Content-Type',mime),('Content-Length',str(len(data)))]+(extra or []));return [data]
    try:
        if path=='/webhooks/whatsapp':
            import business_connectors
            length=int(environ.get('CONTENT_LENGTH') or 0)
            if length<0 or length>1024*1024:raise Error(413,'Webhook grande demais.')
            raw=environ['wsgi.input'].read(length)
            with connect() as c:
                result=business_connectors.webhook(sys.modules[__name__],c,method,environ,q,raw)
            return response(200,result,'text/plain; charset=utf-8',[('Cache-Control','no-store')])
        if path=='/api/upload-binary':
            if method!='POST':raise Error(400,'Use POST para enviar um material.')
            headers.append(('Cache-Control','no-store'))
            origin=environ.get('HTTP_ORIGIN')
            if origin and origin!=ORIGIN:raise Error(403,'Origem não autorizada.')
            with connect() as c:
                u,csrf,_=authenticate(c,environ)
                if not hmac.compare_digest(environ.get('HTTP_X_CSRF_TOKEN',''),csrf):raise Error(403,'Sessão inválida. Atualize a página.')
                try:length=int(environ.get('CONTENT_LENGTH') or 0)
                except ValueError:raise Error(400,'Tamanho de arquivo inválido.')
                result=attachments.upload(sys.modules[__name__],c,u,q,environ['wsgi.input'],length)
            return response(200,result)
        if path.startswith('/api/'):
            headers.append(('Cache-Control','no-store'))
            if method not in ['GET','POST','PATCH','DELETE']:raise Error(400,'Método inválido.')
            if method!='GET':
                origin=environ.get('HTTP_ORIGIN')
                if origin and origin!=ORIGIN:raise Error(403,'Origem não autorizada.')
                if 'application/json' not in environ.get('CONTENT_TYPE',''):raise Error(400,'Envie JSON.')
            try:length=int(environ.get('CONTENT_LENGTH') or 0)
            except ValueError:raise Error(400,'Conteúdo inválido.')
            if length>12*1024*1024:raise Error(413,'Arquivo ou formulário grande demais.')
            try:d=json.loads(environ['wsgi.input'].read(length)) if length else {}
            except (ValueError,UnicodeDecodeError):raise Error(400,'JSON inválido.')
            if not isinstance(d,dict):raise Error(400,'Objeto JSON esperado.')
            with connect() as c:
                if path=='/api/stream' and method=='GET':
                    u,_,_=authenticate(c,environ)
                    start_response('200 OK',headers+[('Content-Type','text/event-stream'),('X-Accel-Buffering','no')])
                    return stream(u['id'],digest(authenticate(c,environ)[2]))
                result,extra=api(c,environ,method,path,d,q)
            if path=='/api/agency/calendar/callback':return response(303,b'',mime='text/html; charset=utf-8',extra=[('Location','/#calendar')])
            if path=='/api/drive/callback':return response(303,b'',mime='text/html; charset=utf-8',extra=[('Location','/#drive')])
            return response(200,result,extra=extra)
        if path.startswith('/publish-media/'):
            if method not in ['GET','HEAD']:raise Error(404,'Arquivo indisponível.')
            with connect() as c:
                f=agency_editorial.media(sys.modules[__name__],c,path.split('/')[-1])
                return attachments.download(sys.modules[__name__],f,environ,start_response,headers)
        if path.startswith('/portal-files/'):
            if method not in ['GET','HEAD']:raise Error(404,'Arquivo indisponível.')
            with connect() as c:
                person=agency_portal.principal(sys.modules[__name__],c,environ)
                f=agency_portal.shared_file(sys.modules[__name__],c,person,path.split('/')[-1])
                return attachments.download(sys.modules[__name__],f,environ,start_response,headers)
        if path.startswith('/portal-brand/'):
            if method not in ['GET','HEAD']:raise Error(404,'Imagem indisponível.')
            with connect() as c:
                person=agency_portal.principal(sys.modules[__name__],c,environ)
                f=agency_portal.brand_file(sys.modules[__name__],c,person,path.split('/')[-1])
                return attachments.download(sys.modules[__name__],f,environ,start_response,headers)
        if path.startswith('/files/'):
            if method not in ['GET','HEAD']:raise Error(404,'Arquivo não encontrado.')
            with connect() as c:
                u,_,_=authenticate(c,environ);f=c.execute('SELECT * FROM files WHERE id=?',(path.split('/')[-1],)).fetchone()
                if not f:raise Error(404,'Arquivo não encontrado.')
                import editorial_studio
                if editorial_studio.file_access(sys.modules[__name__],c,u,f['id']):pass
                elif social.file_access(sys.modules[__name__],c,u,f['id']):pass
                elif f['task_id']:get_task(c,u,f['task_id'])
                elif f['room_id']:room_access(c,u,f['room_id'])
                elif f['user_id']!=u['id'] and not any(perm(u,p) for p in ['team','tasks','calendar','chats']):raise Error(403,'Sem acesso à foto.')
                return attachments.download(sys.modules[__name__],f,environ,start_response,headers)
        if method!='GET':raise Error(404,'Página não encontrada.')
        p=ROOT/'static'/('index.html' if path=='/' else path.lstrip('/'))
        if not p.resolve().is_relative_to((ROOT/'static').resolve()) or not p.is_file():raise Error(404,'Página não encontrada.')
        mime=mimetypes.guess_type(str(p))[0] or 'application/octet-stream'
        return response(200,p.read_bytes(),mime,[('Cache-Control','no-cache')])
    except Error as e:return response(e.status,{'error':e.message})
    except sqlite3.IntegrityError:return response(409,{'error':'Dados duplicados ou referência inválida. Verifique o cadastro.'})
    except (ValueError,TypeError,OverflowError):return response(400,{'error':'Verifique os dados informados.'})
    except Exception:
        import traceback;traceback.print_exc(file=sys.stderr);return response(500,{'error':'Erro interno. Tente novamente e consulte o administrador.'})

def stream(user_id,session_token):
    # SSE emits invalidation only, never data. Every reload reapplies current ACLs.
    last=-1
    for _ in range(12):
        with connect() as c:
            if not c.execute('SELECT 1 FROM users JOIN sessions ON users.id=sessions.user_id WHERE users.id=? AND users.active=1 AND sessions.token=? AND sessions.expires>?',(user_id,session_token,time.time())).fetchone():return
            v=(c.execute('SELECT COALESCE(MAX(id),0) FROM audit').fetchone()[0]
               +c.execute('SELECT count(*) FROM messages').fetchone()[0]
               +c.execute('SELECT count(*) FROM notifications WHERE user_id=?',(user_id,)).fetchone()[0]
               +c.execute('SELECT count(*) FROM message_receipts WHERE delivered IS NOT NULL').fetchone()[0]
               +c.execute('SELECT count(*) FROM message_receipts WHERE read IS NOT NULL').fetchone()[0])
        if v!=last:yield ('event: refresh\ndata: {}\n\n').encode();last=v
        else:yield b': heartbeat\n\n'
        time.sleep(5)

if __name__=='__main__':
    init()
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIServer,make_server
    class ThreadedServer(ThreadingMixIn,WSGIServer):daemon_threads=True
    print('NJA System: '+ORIGIN+' (servidor de desenvolvimento)')
    make_server('127.0.0.1',int(os.getenv('PORT','8000')),application,server_class=ThreadedServer).serve_forever()
