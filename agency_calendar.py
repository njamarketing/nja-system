"""Separate Google Calendar consent and idempotent Meet creation per event."""
import os,json,time,secrets,hashlib
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
import integrations
SCOPE='https://www.googleapis.com/auth/calendar.events.owned'

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS calendar_states(state TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),expires REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS calendar_tokens(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,email TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS calendar_links(event_id TEXT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,user_id TEXT NOT NULL REFERENCES users(id),google_id TEXT NOT NULL,status TEXT NOT NULL,meet TEXT NOT NULL DEFAULT '',updated TEXT NOT NULL);''')
 if 'account_email' not in [r[1] for r in c.execute('PRAGMA table_info(calendar_links)')]:c.execute("ALTER TABLE calendar_links ADD COLUMN account_email TEXT NOT NULL DEFAULT ''")
def save(a,c,u,token,email):c.execute('INSERT OR REPLACE INTO calendar_tokens VALUES(?,?,?)',(u['id'],integrations.cipher(a).encrypt(json.dumps(token).encode()).decode(),email))
def token(a,c,u):
 r=c.execute('SELECT * FROM calendar_tokens WHERE user_id=?',(u['id'],)).fetchone()
 if not r:raise a.Error(409,'Conecte sua conta Google Calendar primeiro.')
 try:t=json.loads(integrations.cipher(a).decrypt(r['secret'].encode()))
 except Exception:raise a.Error(503,'Reconecte a conta Google Calendar.')
 if t['expires']<time.time()+60:
  new=integrations.external(a,'https://oauth2.googleapis.com/token',{'client_id':os.getenv('GOOGLE_CLIENT_ID'),'client_secret':os.getenv('GOOGLE_CLIENT_SECRET'),'refresh_token':t['refresh_token'],'grant_type':'refresh_token'},form=True);t.update(new);t['expires']=time.time()+new.get('expires_in',3600);save(a,c,u,t,r['email']);c.commit()
 return t['access_token']
def remote(a,access,id,body=None):
 url='https://www.googleapis.com/calendar/v3/calendars/primary/events'+('/'+id if body is None else '?conferenceDataVersion=1&sendUpdates=none')
 try:
  with urlopen(Request(url,data=json.dumps(body).encode() if body else None,headers={'Authorization':'Bearer '+access,'Content-Type':'application/json'}),timeout=25) as r:return json.loads(r.read(1024*1024))
 except HTTPError as e:
  if e.code==409 and body is not None:return remote(a,access,id)
  raise a.Error(503,'O Google não confirmou o compromisso. Verifique as permissões e consulte o estado antes de tentar novamente.')
 except (URLError,TimeoutError,ValueError):raise a.Error(503,'Resposta do Google não confirmada. Consulte o estado do mesmo compromisso para evitar duplicidade.')
def api(a,c,u,method,path,d,q):
 if not path.startswith('/api/agency/calendar'):return None
 a.need(u,'calendar');action=path.removeprefix('/api/agency/calendar').strip('/')
 if not action and method=='GET':
  r=c.execute('SELECT email FROM calendar_tokens WHERE user_id=?',(u['id'],)).fetchone();return {'connected':bool(r),'email':r[0] if r else '', 'configured':bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET')),'links':[dict(r) for r in c.execute('SELECT * FROM calendar_links WHERE user_id=?',(u['id'],))]}
 if action=='connect' and method=='POST':
  if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):raise a.Error(503,'Configure o aplicativo Google OAuth e a URL de retorno no servidor.')
  state=secrets.token_urlsafe(32);c.execute('INSERT INTO calendar_states VALUES(?,?,?)',(a.digest(state),u['id'],time.time()+600));params={'client_id':os.getenv('GOOGLE_CLIENT_ID'),'redirect_uri':a.ORIGIN+'/api/agency/calendar/callback','response_type':'code','scope':SCOPE+' https://www.googleapis.com/auth/userinfo.email','access_type':'offline','prompt':'consent','state':state}
  if os.getenv('GOOGLE_WORKSPACE_DOMAIN'):params['hd']=os.getenv('GOOGLE_WORKSPACE_DOMAIN')
  return {'url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(params)}
 if action=='callback' and method=='GET':
  key=a.digest(q.get('state',[''])[0]);r=c.execute('SELECT * FROM calendar_states WHERE state=? AND user_id=? AND expires>?',(key,u['id'],time.time())).fetchone()
  if not r:raise a.Error(403,'Autorização expirada ou inválida.')
  c.execute('DELETE FROM calendar_states WHERE state=?',(key,));c.commit()
  if q.get('error'):raise a.Error(400,'Autorização cancelada. Volte à agenda.')
  t=integrations.external(a,'https://oauth2.googleapis.com/token',{'client_id':os.getenv('GOOGLE_CLIENT_ID'),'client_secret':os.getenv('GOOGLE_CLIENT_SECRET'),'code':q.get('code',[''])[0],'grant_type':'authorization_code','redirect_uri':a.ORIGIN+'/api/agency/calendar/callback'},form=True)
  if SCOPE not in t.get('scope','').split() or not t.get('refresh_token'):raise a.Error(403,'O Google não concedeu o acesso necessário à agenda.')
  info=integrations.external(a,'https://www.googleapis.com/oauth2/v2/userinfo',headers={'Authorization':'Bearer '+t['access_token']});email=info.get('email','');domain=os.getenv('GOOGLE_WORKSPACE_DOMAIN','').lower()
  if not info.get('verified_email') or (domain and email.lower().split('@')[-1]!=domain):raise a.Error(403,'Use uma conta verificada do domínio corporativo.')
  old=c.execute('SELECT email FROM calendar_tokens WHERE user_id=?',(u['id'],)).fetchone()
  if c.execute('SELECT 1 FROM calendar_links WHERE user_id=? AND account_email<>? AND account_email<>?',(u['id'],email,'')).fetchone():raise a.Error(409,'Há compromissos vinculados à conta anterior. Reconecte a mesma conta para consultar esses compromissos.')
  t['expires']=time.time()+t.get('expires_in',3600);save(a,c,u,t,email);a.audit(c,u,'calendar_connect',u['id']);return {'ok':True}
 if action=='disconnect' and method=='POST':
  c.execute('DELETE FROM calendar_tokens WHERE user_id=?',(u['id'],));c.execute('DELETE FROM calendar_states WHERE user_id=?',(u['id'],));a.audit(c,u,'calendar_disconnect',u['id']);return {'ok':True}
 if action.startswith('events/') and method=='POST':
  eid=action.split('/')[1];e=c.execute('SELECT * FROM events WHERE id=?',(eid,)).fetchone()
  if not e:raise a.Error(404,'Compromisso não encontrado.')
  if e['creator']!=u['id']:raise a.Error(403,'Somente quem criou o compromisso pode vinculá-lo à própria conta Google.')
  if e['recurrence']!='none':raise a.Error(400,'Crie o Meet em um compromisso sem recorrência.')
  access=token(a,c,u);link=c.execute('SELECT * FROM calendar_links WHERE event_id=?',(eid,)).fetchone();gid=hashlib.sha256((a.ORIGIN+':'+eid).encode()).hexdigest()
  if link and link['user_id']!=u['id']:raise a.Error(403,'Vínculo de outra conta.')
  if not link:
   c.execute("INSERT INTO calendar_links(event_id,user_id,google_id,status,updated,account_email) VALUES(?,?,?,'pending',?,?)",(eid,u['id'],gid,a.now(),c.execute('SELECT email FROM calendar_tokens WHERE user_id=?',(u['id'],)).fetchone()[0]));c.commit()
  payload={'id':gid,'summary':e['title'],'description':e['description'],'start':{'dateTime':e['start']},'end':{'dateTime':e['end']},'conferenceData':{'createRequest':{'requestId':gid,'conferenceSolutionKey':{'type':'hangoutsMeet'}}}}
  # Same deterministic event ID for every retry, including ambiguous network responses.
  result=remote(a,access,gid,None if link and link['status']=='pending_conference' else payload)
  status=result.get('conferenceData',{}).get('createRequest',{}).get('status',{}).get('statusCode');meet=result.get('hangoutLink','')
  if meet and not meet.startswith('https://meet.google.com/'):raise a.Error(503,'Link de reunião inesperado.')
  state='ready' if meet else 'failed' if status=='failure' else 'pending_conference'
  c.execute('UPDATE calendar_links SET status=?,meet=?,updated=? WHERE event_id=?',(state,meet,a.now(),eid))
  if meet:c.execute('UPDATE events SET location=? WHERE id=?',(meet,eid))
  a.audit(c,u,'calendar_meet',eid,state);return {'status':state,'meet':meet}
 raise a.Error(404,'Ação de agenda não encontrada.')
