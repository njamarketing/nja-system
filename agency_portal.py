"""Separate client identities; immutable versions and explicit sharing."""
import base64,hashlib,json,re,secrets,time,tempfile
from pathlib import Path
import agency_access as scope,attachments,agency_editorial

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS portal_accounts(id TEXT PRIMARY KEY,client_id TEXT NOT NULL REFERENCES clients(id),email TEXT NOT NULL,name TEXT NOT NULL,password TEXT,active INTEGER NOT NULL DEFAULT 1,can_approve INTEGER NOT NULL DEFAULT 1,UNIQUE(client_id,email));
 CREATE TABLE IF NOT EXISTS portal_invites(token TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES portal_accounts(id),expires REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS portal_sessions(token TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES portal_accounts(id),expires REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS creative_reviews(id TEXT PRIMARY KEY,client_id TEXT NOT NULL REFERENCES clients(id),task_id TEXT REFERENCES tasks(id),title TEXT NOT NULL,current_version TEXT,shared INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'draft',created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS creative_versions(id TEXT PRIMARY KEY,review_id TEXT NOT NULL REFERENCES creative_reviews(id),number INTEGER NOT NULL,file_id TEXT REFERENCES files(id),caption TEXT NOT NULL,sha256 TEXT NOT NULL,creator TEXT NOT NULL REFERENCES users(id),created TEXT NOT NULL,UNIQUE(review_id,number));
 CREATE TABLE IF NOT EXISTS creative_feedback(id TEXT PRIMARY KEY,review_id TEXT NOT NULL,version_id TEXT NOT NULL REFERENCES creative_versions(id),actor TEXT NOT NULL,name TEXT NOT NULL,decision TEXT NOT NULL,text TEXT NOT NULL,x REAL,y REAL,seconds REAL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS portal_uploads(id TEXT PRIMARY KEY,client_id TEXT NOT NULL,account_id TEXT NOT NULL,name TEXT NOT NULL,mime TEXT NOT NULL,payload BLOB NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS portal_chat_messages(seq INTEGER PRIMARY KEY AUTOINCREMENT,client_id TEXT NOT NULL REFERENCES clients(id),actor TEXT NOT NULL,name TEXT NOT NULL,text TEXT NOT NULL,created TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS portal_chat_client ON portal_chat_messages(client_id,seq);
 CREATE TABLE IF NOT EXISTS portal_shares(document_id TEXT PRIMARY KEY REFERENCES business_documents(id),client_id TEXT NOT NULL REFERENCES clients(id),created TEXT NOT NULL);''')

def review(a,c,u,id):
 r=c.execute('SELECT * FROM creative_reviews WHERE id=?',(id,)).fetchone()
 if not r:raise a.Error(404,'Material não encontrado.')
 scope.need(a,c,u,r['client_id']);return dict(r)
def serialize(c,r):
 d=dict(r);d['versions']=[]
 for v in c.execute('SELECT * FROM creative_versions WHERE review_id=? ORDER BY number DESC',(r['id'],)):
  files=[{k:f[k] for k in ['id','name','mime','size']} for f in agency_editorial.assets(c,v)]
  d['versions'].append(dict(v)|{'file':files[0] if files else None,'files':files})
 d['feedback']=[dict(v) for v in c.execute('SELECT * FROM creative_feedback WHERE review_id=? ORDER BY created',(r['id'],))];return d

def shared_file(a,c,p,fid):
 f=c.execute('SELECT f.* FROM files f WHERE f.id=? AND EXISTS(SELECT 1 FROM creative_reviews r JOIN creative_versions v ON v.review_id=r.id WHERE r.client_id=? AND r.shared=1 AND (v.file_id=f.id OR EXISTS(SELECT 1 FROM creative_assets x WHERE x.version_id=v.id AND x.file_id=f.id)))',(fid,p['client_id'])).fetchone()
 if not f:raise a.Error(404,'Arquivo não compartilhado.')
 return f

def feedback(a,c,r,actor,name,d,can_approve):
 if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
 r=dict(c.execute('SELECT * FROM creative_reviews WHERE id=?',(r['id'],)).fetchone())
 if actor.startswith('portal:'):
  person=c.execute('SELECT * FROM portal_accounts WHERE id=? AND active=1',(actor.split(':',1)[1],)).fetchone()
  if not person or person['client_id']!=r['client_id'] or not r['shared']:raise a.Error(403,'Material não compartilhado.')
  can_approve=person['can_approve']
 version=d.get('version_id');decision=d.get('decision','comment')
 if decision not in ['comment','approved','changes']:raise a.Error(400,'Decisão inválida.')
 v=c.execute('SELECT * FROM creative_versions WHERE id=? AND review_id=?',(version,r['id'])).fetchone()
 if not v:raise a.Error(404,'Versão não encontrada.')
 if decision!='comment' and (not can_approve or version!=r['current_version']):raise a.Error(409,'A decisão exige permissão e a versão atual do material.')
 if decision!='comment' and r['status'] not in ['waiting','changes']:raise a.Error(409,'Este material não está aguardando uma decisão. Solicite nova revisão.')
 tx=a.textfield(d,'text',decision=='changes',4000);coords={}
 for key,maximum in [('x',1),('y',1),('seconds',86400)]:
  value=d.get(key)
  if value in [None,'']:coords[key]=None;continue
  try:
   value=float(value)
   if not 0<=value<=maximum:raise ValueError()
  except (ValueError,TypeError):raise a.Error(400,'Posição de comentário inválida.')
  coords[key]=value
 id=a.uid();c.execute('INSERT INTO creative_feedback VALUES(?,?,?,?,?,?,?,?,?,?,?)',(id,r['id'],version,actor,name,decision,tx,coords['x'],coords['y'],coords['seconds'],a.now()))
 if decision!='comment':c.execute('UPDATE creative_reviews SET status=? WHERE id=?',(decision,r['id']))
 if r['task_id']:
  task=c.execute('SELECT owner FROM tasks WHERE id=?',(r['task_id'],)).fetchone()
  if task:a.notify(c,task[0],'Revisão de material',r['title']+': '+{'comment':'novo comentário','approved':'aprovado','changes':'alterações solicitadas'}[decision],'approvals:'+r['id'],'tasks')
 return {'id':id}

def chat(a,c,cid,actor,name,method,d,q):
 if method=='POST':
  tx=a.textfield(d,'text',True,5000)
  a.throttle(c,'portal-chat:'+actor,60)
  cur=c.execute('INSERT INTO portal_chat_messages(client_id,actor,name,text,created) VALUES(?,?,?,?,?)',(cid,actor,name,tx,a.now()))
  return {'id':cur.lastrowid}
 if method=='GET':
  try:
   before=int(q.get('before',['0'])[0]);after=int(q.get('after',['0'])[0])
   if before<0 or after<0 or (before and after):raise ValueError()
  except (ValueError,TypeError):raise a.Error(400,'Página inválida.')
  where='client_id=?';params=[cid]
  if before:where+=' AND seq<?';params.append(before)
  if after:where+=' AND seq>?';params.append(after)
  rows=[dict(r) for r in c.execute('SELECT seq,name,text,created,actor FROM portal_chat_messages WHERE '+where+' ORDER BY seq '+('ASC' if after else 'DESC')+' LIMIT 100',params)]
  if not after:rows.reverse()
  for r in rows:r['side']='client' if r.pop('actor').startswith('portal:') else 'staff'
  return {'messages':rows,'has_older':bool(rows and c.execute('SELECT 1 FROM portal_chat_messages WHERE client_id=? AND seq<? LIMIT 1',(cid,rows[0]['seq'])).fetchone())}
 raise a.Error(405,'Método não permitido.')

def api(a,c,u,method,path,d,q):
 if path=='/api/agency/client-chats' and method=='GET':
  a.need(u,'chats')
  return {'clients':[dict(r) for r in c.execute('SELECT id,name FROM clients WHERE active=1 ORDER BY name') if scope.allowed(c,u,r['id'])]}
 if path.startswith('/api/agency/client-chats/'):
  a.need(u,'chats');cid=path.split('/')[-1];client=scope.need(a,c,u,cid)
  if not client['active']:raise a.Error(403,'Cliente desativado.')
  result=chat(a,c,cid,'staff:'+u['id'],u['name'],method,d,q)
  if method=='POST':a.audit(c,u,'portal_chat_send',cid)
  return result
 if path=='/api/agency/reviews' and method=='GET':
  a.need(u,'approvals');return {'items':[serialize(c,r) for r in c.execute('SELECT * FROM creative_reviews ORDER BY created DESC') if scope.allowed(c,u,r['client_id'])],'accounts':[dict(r) for r in c.execute('SELECT id,client_id,email,name,active,can_approve FROM portal_accounts') if scope.allowed(c,u,r['client_id'])] if a.perm(u,'portal_manage') else [],'uploads':[{'id':r['id'],'name':r['name'],'client_id':r['client_id'],'created':r['created']} for r in c.execute('SELECT id,name,client_id,created FROM portal_uploads') if scope.allowed(c,u,r['client_id'])]}
 if path=='/api/agency/reviews' and method=='POST':
  a.need(u,'approvals');a.need(u,'approval_manage');cid=d.get('client_id');scope.need(a,c,u,cid);tid=d.get('task_id') or None
  if tid:
   t=a.get_task(c,u,tid)
   if t['client_id']!=cid:raise a.Error(400,'Tarefa de outro cliente.')
  id=a.uid();c.execute('INSERT INTO creative_reviews(id,client_id,task_id,title,created) VALUES(?,?,?,?,?)',(id,cid,tid,a.textfield(d,'title',True,180),a.now()));a.audit(c,u,'creative_create',id);return {'id':id}
 if path.startswith('/api/agency/reviews/'):
  parts=path.split('/');id=parts[4];r=review(a,c,u,id);a.need(u,'approvals')
  if len(parts)==5 and method=='GET':return serialize(c,r)
  action=parts[5] if len(parts)>5 else ''
  a.need(u,'approval_manage')
  if action=='versions' and method=='POST':
   if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
   fids=d.get('file_ids') if 'file_ids' in d else ([d['file_id']] if d.get('file_id') else [])
   if not isinstance(fids,list) or len(fids)>10 or len(set(fids))!=len(fids):raise a.Error(400,'Selecione até 10 arquivos sem repetições.')
   caption=a.textfield(d,'caption',False,10000);digest=hashlib.sha256()
   for fid in fids:
    f=c.execute('SELECT * FROM files WHERE id=?',(fid,)).fetchone()
    if not f or not f['task_id']:raise a.Error(400,'Selecione arquivos de tarefas deste cliente.')
    task=a.get_task(c,u,f['task_id'])
    if task['client_id']!=r['client_id']:raise a.Error(400,'Arquivo de outro cliente.')
    with open(a.DATA/'uploads'/fid,'rb') as stream:
     for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
   if not fids and not caption:raise a.Error(400,'Adicione um arquivo ou texto para revisão.')
   digest.update(b'\0'+caption.encode())
   idv=a.uid();number=c.execute('SELECT count(*)+1 FROM creative_versions WHERE review_id=?',(id,)).fetchone()[0];c.execute('INSERT INTO creative_versions VALUES(?,?,?,?,?,?,?,?)',(idv,id,number,fids[0] if fids else None,caption,digest.hexdigest(),u['id'],a.now()))
   for pos,fid in enumerate(fids):c.execute('INSERT INTO creative_assets VALUES(?,?,?)',(idv,fid,pos))
   c.execute("UPDATE creative_reviews SET current_version=?,status='waiting' WHERE id=?",(idv,id));a.audit(c,u,'creative_version',id,str(number));return {'id':idv,'number':number}
  if action=='sharing' and method=='POST':
   a.need(u,'portal_manage')
   if not isinstance(d.get('shared'),bool):raise a.Error(400,'Compartilhamento inválido.')
   c.execute('UPDATE creative_reviews SET shared=? WHERE id=?',(int(d['shared']),id));a.audit(c,u,'creative_sharing',id);return {'ok':True}
  if action=='feedback' and method=='POST':
   out=feedback(a,c,r,'staff:'+u['id'],u['name'],d,True);a.audit(c,u,'creative_decision',id,d.get('decision','comment'));return out
 if path=='/api/agency/portal/invite' and method=='POST':
  a.need(u,'portal_manage');cid=d.get('client_id');scope.need(a,c,u,cid);email=a.textfield(d,'email',True,254).lower();name=a.textfield(d,'name',True,120)
  if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise a.Error(400,'E-mail inválido.')
  account=c.execute('SELECT id FROM portal_accounts WHERE client_id=? AND email=?',(cid,email)).fetchone();id=account[0] if account else a.uid()
  if not account:c.execute('INSERT INTO portal_accounts(id,client_id,email,name,can_approve) VALUES(?,?,?,?,?)',(id,cid,email,name,int(d.get('can_approve') is True)))
  token=secrets.token_urlsafe(32);c.execute('DELETE FROM portal_invites WHERE account_id=?',(id,));c.execute('INSERT INTO portal_invites VALUES(?,?,?)',(a.digest(token),id,time.time()+172800));a.audit(c,u,'portal_invite',id);return {'url':a.ORIGIN+'/portal.html#invite='+token,'expires_hours':48}
 if path.startswith('/api/agency/portal/accounts/') and method=='PATCH':
  a.need(u,'portal_manage');id=path.split('/')[-1];r=c.execute('SELECT * FROM portal_accounts WHERE id=?',(id,)).fetchone()
  if not r:raise a.Error(404,'Contato não encontrado.')
  scope.need(a,c,u,r['client_id'])
  for key in ['active','can_approve']:
   if key in d:
    if not isinstance(d[key],bool):raise a.Error(400,'Configuração inválida.')
    c.execute('UPDATE portal_accounts SET '+key+'=? WHERE id=?',(int(d[key]),id))
  c.execute('DELETE FROM portal_sessions WHERE account_id=?',(id,));a.audit(c,u,'portal_account',id);return {'ok':True}
 if path=='/api/agency/portal/share-document' and method=='POST':
  a.need(u,'portal_manage');doc=c.execute('SELECT * FROM business_documents WHERE id=?',(d.get('document_id'),)).fetchone()
  if not doc:raise a.Error(404,'Documento não encontrado.')
  import business
  row=business.access(a,c,u,doc['scope'],doc['entity_id']);a.need(u,'finance_download' if doc['scope']=='invoices' else 'contract_download');cid=row['client_id']
  if not cid:raise a.Error(400,'Vincule o documento a um cliente antes de compartilhar.')
  if d.get('shared') is True:c.execute('INSERT OR REPLACE INTO portal_shares VALUES(?,?,?)',(doc['id'],cid,a.now()))
  else:c.execute('DELETE FROM portal_shares WHERE document_id=?',(doc['id'],))
  a.audit(c,u,'portal_document',doc['id']);return {'ok':True}
 if path.startswith('/api/agency/portal/uploads/') and method=='GET':
  a.need(u,'approvals');r=c.execute('SELECT * FROM portal_uploads WHERE id=?',(path.split('/')[-1],)).fetchone()
  if not r:raise a.Error(404,'Arquivo não encontrado.')
  scope.need(a,c,u,r['client_id']);return {'name':r['name'],'mime':r['mime'],'data':base64.b64encode(r['payload']).decode()}
 return None

def principal(a,c,environ):
 token=environ.get('HTTP_X_PORTAL_TOKEN','');r=c.execute('SELECT p.* FROM portal_accounts p JOIN portal_sessions s ON s.account_id=p.id JOIN clients cl ON cl.id=p.client_id WHERE s.token=? AND s.expires>? AND p.active=1 AND cl.active=1',(a.digest(token),time.time())).fetchone()
 if not r:raise a.Error(401,'Entre no portal do cliente.')
 return dict(r)

def portal_api(a,c,environ,method,path,d,q):
 action=path.removeprefix('/api/portal/')
 if action=='activate' and method=='POST':
  a.throttle(c,'portal-activate:'+environ.get('REMOTE_ADDR',''),20);token=a.digest(a.textfield(d,'token',True,256));p=a.textfield(d,'password',True,256)
  if len(p)<10:raise a.Error(400,'Use ao menos 10 caracteres na senha.')
  c.execute('BEGIN IMMEDIATE')
  r=c.execute('SELECT p.* FROM portal_accounts p JOIN portal_invites i ON i.account_id=p.id WHERE i.token=? AND i.expires>? AND p.active=1',(token,time.time())).fetchone()
  if not r:raise a.Error(400,'Convite inválido ou expirado.')
  # Reinvites reset only this client's independent account and revoke existing sessions.
  c.execute('UPDATE portal_accounts SET password=? WHERE id=?',(a.hash_password(p),r['id']));c.execute('DELETE FROM portal_invites WHERE account_id=?',(r['id'],));c.execute('DELETE FROM portal_sessions WHERE account_id=?',(r['id'],));return {'client_id':r['client_id'],'email':r['email']}
 if action=='login' and method=='POST':
  email=a.textfield(d,'email',True,254).lower();a.throttle(c,'portal-login:'+environ.get('REMOTE_ADDR',''),30);a.throttle(c,'portal-email:'+email)
  r=c.execute('SELECT p.* FROM portal_accounts p JOIN clients cl ON cl.id=p.client_id WHERE p.client_id=? AND email=? AND p.active=1 AND cl.active=1',(d.get('client_id'),email)).fetchone()
  if not r or not r['password'] or not a.verify_password(a.textfield(d,'password',True,256),r['password']):raise a.Error(401,'Cliente, e-mail ou senha incorretos.')
  token=secrets.token_urlsafe(32);c.execute('INSERT INTO portal_sessions VALUES(?,?,?)',(a.digest(token),r['id'],time.time()+28800));return {'token':token,'name':r['name']}
 p=principal(a,c,environ);cid=p['client_id']
 if action=='chat':return chat(a,c,cid,'portal:'+p['id'],p['name'],method,d,q)
 if action=='logout' and method=='POST':c.execute('DELETE FROM portal_sessions WHERE token=?',(a.digest(environ.get('HTTP_X_PORTAL_TOKEN','')),));return {'ok':True}
 if action=='home' and method=='GET':
  client=c.execute('SELECT id,name,photo FROM clients WHERE id=?',(cid,)).fetchone()
  return {'client':dict(client),'person':{'name':p['name'],'can_approve':bool(p['can_approve'])},'reviews':[serialize(c,r) for r in c.execute('SELECT * FROM creative_reviews WHERE client_id=? AND shared=1 ORDER BY created DESC',(cid,))],'projects':[{'id':r['id'],'title':r['title'],'month':r['month'],'total':c.execute('SELECT count(*) FROM deliverables WHERE project_id=?',(r['id'],)).fetchone()[0],'done':c.execute("SELECT count(*) FROM deliverables d JOIN tasks t ON t.id=d.task_id WHERE d.project_id=? AND t.status='done'",(r['id'],)).fetchone()[0]} for r in c.execute('SELECT * FROM agency_projects WHERE client_id=? ORDER BY month DESC',(cid,))],'documents':[dict(r) for r in c.execute('SELECT b.id,b.name,b.created FROM business_documents b JOIN portal_shares s ON s.document_id=b.id WHERE s.client_id=?',(cid,))]}
 if action.startswith('reviews/'):
  id=action.split('/')[1];r=c.execute('SELECT * FROM creative_reviews WHERE id=? AND client_id=? AND shared=1',(id,cid)).fetchone()
  if not r:raise a.Error(404,'Material não compartilhado.')
  if method=='POST':return feedback(a,c,dict(r),'portal:'+p['id'],p['name'],d,p['can_approve'])
 if action.startswith('files/') and method=='GET':
  fid=action.split('/')[-1];f=shared_file(a,c,p,fid)
  return {'name':f['name'],'mime':f['mime'],'data':base64.b64encode((a.DATA/'uploads'/fid).read_bytes()).decode()}
 if action.startswith('documents/') and method=='GET':
  r=c.execute('SELECT b.* FROM business_documents b JOIN portal_shares s ON s.document_id=b.id WHERE b.id=? AND s.client_id=?',(action.split('/')[-1],cid)).fetchone()
  if not r:raise a.Error(404,'Documento não compartilhado.')
  return {'name':r['name'],'mime':'application/pdf','data':base64.b64encode(r['payload']).decode()}
 if action=='uploads' and method=='POST':
  name=Path(a.textfield(d,'name',True,180).replace('\\','/')).name
  try:raw=base64.b64decode(d.get('data',''),validate=True)
  except Exception:raise a.Error(400,'Arquivo inválido.')
  if not 0<len(raw)<=8*1024*1024:raise a.Error(413,'Envie até 8 MB por arquivo.')
  with tempfile.NamedTemporaryFile() as f:f.write(raw);f.flush();mime=attachments.identify(a,Path(f.name),name)
  id=a.uid();c.execute('INSERT INTO portal_uploads VALUES(?,?,?,?,?,?,?)',(id,cid,p['id'],name,mime,raw,a.now()));return {'id':id}
 raise a.Error(404,'Recurso não encontrado no portal.')
