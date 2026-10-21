"""Client-scoped editorial queue. Approved immutable assets; no blind retries."""
import json,os,re,secrets,time,hashlib
from datetime import datetime,timezone,timedelta
from urllib.parse import urlencode
import agency_access as scope,integrations,business_connectors as bc

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS social_accounts(id TEXT PRIMARY KEY,client_id TEXT NOT NULL REFERENCES clients(id),name TEXT NOT NULL,platform TEXT NOT NULL,target TEXT NOT NULL,secret TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,verified TEXT,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS editorial_posts(id TEXT PRIMARY KEY,client_id TEXT NOT NULL REFERENCES clients(id),account_id TEXT NOT NULL REFERENCES social_accounts(id),version_id TEXT NOT NULL REFERENCES creative_versions(id),title TEXT NOT NULL,format TEXT NOT NULL,scheduled TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',creator TEXT NOT NULL REFERENCES users(id),container TEXT,external_id TEXT,error TEXT NOT NULL DEFAULT '',updated TEXT NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS editorial_media(token TEXT PRIMARY KEY,post_id TEXT NOT NULL REFERENCES editorial_posts(id),file_id TEXT NOT NULL REFERENCES files(id),expires REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS creative_assets(version_id TEXT NOT NULL REFERENCES creative_versions(id),file_id TEXT NOT NULL REFERENCES files(id),position INTEGER NOT NULL,PRIMARY KEY(version_id,file_id));''')

 if 'deleted' not in [r[1] for r in c.execute('PRAGMA table_info(social_accounts)')]:c.execute('ALTER TABLE social_accounts ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0')

def assets(c,v):
 rows=c.execute('SELECT f.* FROM creative_assets x JOIN files f ON f.id=x.file_id WHERE x.version_id=? ORDER BY x.position',(v['id'],)).fetchall()
 return rows or ([c.execute('SELECT * FROM files WHERE id=?',(v['file_id'],)).fetchone()] if v['file_id'] else [])
def approved(a,c,p):
 v=c.execute('SELECT * FROM creative_versions WHERE id=?',(p['version_id'],)).fetchone();r=c.execute('SELECT * FROM creative_reviews WHERE id=?',(v['review_id'],)).fetchone()
 if r['client_id']!=p['client_id'] or r['current_version']!=v['id'] or r['status']!='approved':raise a.Error(409,'A publicação exige a versão atual aprovada. Uma nova revisão bloqueia o agendamento anterior.')
 fs=assets(c,v)
 if any(not f or not (a.DATA/'uploads'/f['id']).is_file() for f in fs):raise a.Error(409,'Um arquivo aprovado não está disponível.')
 digest=hashlib.sha256()
 for f in fs:
  with open(a.DATA/'uploads'/f['id'],'rb') as stream:
   for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
 digest.update(b'\0'+v['caption'].encode())
 if digest.hexdigest()!=v['sha256']:raise a.Error(409,'O conteúdo aprovado foi alterado. Envie uma nova versão.')
 if len(v['caption'])>2200:raise a.Error(400,'A legenda deve ter até 2.200 caracteres para publicação.')
 fmt=p['format']
 if fmt=='text' and fs:raise a.Error(400,'Texto não pode descartar arquivos aprovados.')
 if fmt=='image' and (len(fs)!=1 or fs[0]['mime']!='image/jpeg'):raise a.Error(400,'A publicação de imagem usa uma imagem JPEG aprovada.')
 if fmt=='reel' and (len(fs)!=1 or fs[0]['mime']!='video/mp4'):raise a.Error(400,'Reel exige um vídeo MP4 aprovado.')
 if fmt=='carousel' and (not 2<=len(fs)<=10 or any(f['mime']!='image/jpeg' for f in fs)):raise a.Error(400,'Carrossel exige de 2 a 10 imagens JPEG aprovadas, na ordem da versão.')
 return v,fs

def account(a,c,u,id):
 r=c.execute('SELECT * FROM social_accounts WHERE id=?',(id,)).fetchone()
 if not r or r['deleted']:raise a.Error(404,'Conta não encontrada.')
 scope.need(a,c,u,r['client_id']);return r

def graph(a,acc,route,body=None,query=None):
 version=os.getenv('META_GRAPH_VERSION','')
 if not re.fullmatch(r'v\d+\.0',version):raise a.Error(503,'Configure META_GRAPH_VERSION no servidor.')
 if not re.fullmatch(r'[A-Za-z0-9_/-]+',route):raise a.Error(400,'Identificador Meta inválido.')
 try:token=integrations.cipher(a).decrypt(acc['secret'].encode()).decode()
 except Exception:raise a.Error(503,'Reconecte a conta: chave de credenciais indisponível.')
 return bc.http(a,'https://graph.facebook.com/'+version+'/'+route+('?' + urlencode(query) if query else ''),body,token,form=body is not None)

def api(a,c,u,method,path,d,q):
 if not path.startswith('/api/agency/editorial'):return None
 a.need(u,'editorial');parts=path.split('/')[4:]
 if not parts and method=='GET':
  return {'accounts':[dict(r) for r in c.execute("SELECT id,client_id,name,platform,target,active,verified FROM social_accounts WHERE platform<>'ads' AND deleted=0") if scope.allowed(c,u,r['client_id'])],'posts':[dict(r) for r in c.execute('SELECT p.*,s.name AS account_name FROM editorial_posts p JOIN social_accounts s ON s.id=p.account_id ORDER BY p.scheduled') if scope.allowed(c,u,r['client_id'])],'reviews':[{'id':r['id'],'client_id':r['client_id'],'title':r['title'],'version_id':r['current_version'],'status':r['status']} for r in c.execute('SELECT * FROM creative_reviews') if scope.allowed(c,u,r['client_id'])]}
 a.need(u,'editorial_manage')
 if parts and parts[0]=='accounts':
  a.need(u,'integrations_manage')
  if len(parts)==1 and method=='POST':
   cid=d.get('client_id');scope.need(a,c,u,cid);platform=d.get('platform');target=a.textfield(d,'target',True,100);token=a.textfield(d,'token',True,4000)
   if platform not in ['instagram','facebook'] or not re.fullmatch(r'\d+',target):raise a.Error(400,'Plataforma ou ID inválido.')
   id=a.uid();c.execute('INSERT INTO social_accounts(id,client_id,name,platform,target,secret,created) VALUES(?,?,?,?,?,?,?)',(id,cid,a.textfield(d,'name',True,120),platform,target,integrations.cipher(a).encrypt(token.encode()).decode(),a.now()));a.audit(c,u,'social_account',id);return {'id':id}
  if len(parts)<2:raise a.Error(404,'Ação editorial não encontrada.')
  if method in ['PATCH','DELETE'] and len(parts)==2 and not c.in_transaction:c.execute('BEGIN IMMEDIATE')
  acc=account(a,c,u,parts[1]);id=acc['id']
  if acc['platform'] not in ['instagram','facebook']:raise a.Error(404,'Conta editorial não encontrada.')
  if len(parts)==3 and parts[2]=='verify' and method=='POST':
   result=graph(a,acc,acc['target'],query={'fields':'id'} )
   if str(result.get('id'))!=acc['target']:raise a.Error(409,'A credencial não confirmou a conta selecionada.')
   c.execute('UPDATE social_accounts SET verified=? WHERE id=?',(a.now(),id));a.audit(c,u,'social_verified',id);return {'ok':True}
  if len(parts)==2 and method=='DELETE':
   if c.execute("SELECT 1 FROM editorial_posts WHERE account_id=? AND status IN ('processing','sending','unknown')",(id,)).fetchone():raise a.Error(409,'Há uma publicação em processamento ou sem confirmação. Confira seu estado na Meta antes de apagar a conta.')
   c.execute("DELETE FROM editorial_media WHERE post_id IN (SELECT id FROM editorial_posts WHERE account_id=? AND status IN ('draft','scheduled','blocked'))",(id,))
   c.execute("UPDATE editorial_posts SET status='cancelled',updated=? WHERE account_id=? AND status IN ('draft','scheduled','blocked')",(a.now(),id))
   c.execute("UPDATE social_accounts SET deleted=1,active=0,secret='',verified=NULL WHERE id=?",(id,));a.audit(c,u,'social_account_delete',id);return {'ok':True}
  if len(parts)==2 and method=='PATCH':
   cid=d.get('client_id',acc['client_id']);scope.need(a,c,u,cid)
   name=a.textfield(d,'name',True,120) if 'name' in d else acc['name']
   platform=d.get('platform',acc['platform']);target=a.textfield(d,'target',True,100) if 'target' in d else acc['target']
   if platform not in ['instagram','facebook'] or not re.fullmatch(r'\d+',target):raise a.Error(400,'Plataforma ou ID inválido.')
   active=d.get('active',bool(acc['active']))
   if not isinstance(active,bool):raise a.Error(400,'Estado inválido.')
   changed=cid!=acc['client_id'] or platform!=acc['platform'] or target!=acc['target']
   if cid!=acc['client_id'] and c.execute('SELECT 1 FROM editorial_posts WHERE account_id=?',(id,)).fetchone():raise a.Error(409,'Esta conta possui publicações vinculadas. Cadastre outra conta para o novo cliente para preservar o histórico.')
   if (changed or 'token' in d or not active) and c.execute("SELECT 1 FROM editorial_posts WHERE account_id=? AND status IN ('processing','sending','unknown')",(id,)).fetchone():raise a.Error(409,'Confira a publicação em processamento ou sem confirmação na Meta antes de alterar a conexão da conta.')
   secret=integrations.cipher(a).encrypt(a.textfield(d,'token',True,4000).encode()).decode() if 'token' in d else acc['secret']
   if changed:
    c.execute("UPDATE editorial_posts SET status='cancelled',updated=? WHERE account_id=? AND status IN ('draft','scheduled','blocked')",(a.now(),id))
   c.execute('UPDATE social_accounts SET client_id=?,name=?,platform=?,target=?,secret=?,active=?,verified=? WHERE id=?',(cid,name,platform,target,secret,int(active),None if changed or 'token' in d else acc['verified'],id))
   a.audit(c,u,'social_account_update',id);return {'ok':True}
 if parts and parts[0]=='posts':
  if len(parts)==1 and method=='POST':
   acc=account(a,c,u,d.get('account_id'));v=c.execute('SELECT v.*,r.client_id FROM creative_versions v JOIN creative_reviews r ON r.id=v.review_id WHERE v.id=?',(d.get('version_id'),)).fetchone()
   if not v or v['client_id']!=acc['client_id']:raise a.Error(400,'Selecione uma versão deste cliente.')
   fmt=d.get('format');options=['text','image'] if acc['platform']=='facebook' else ['image','reel','carousel'] if acc['platform']=='instagram' else []
   if fmt not in options:raise a.Error(400,'Formato não disponível nesta plataforma.')
   id=a.uid();c.execute('INSERT INTO editorial_posts(id,client_id,account_id,version_id,title,format,scheduled,creator,updated,created) VALUES(?,?,?,?,?,?,?,?,?,?)',(id,acc['client_id'],acc['id'],v['id'],a.textfield(d,'title',True,180),fmt,required_schedule(a,d.get('scheduled')),u['id'],a.now(),a.now()));a.audit(c,u,'editorial_draft',id);return {'id':id}
  p=c.execute('SELECT * FROM editorial_posts WHERE id=?',(parts[1],)).fetchone()
  if not p:raise a.Error(404,'Publicação não encontrada.')
  scope.need(a,c,u,p['client_id']);action=parts[2] if len(parts)>2 else ''
  if method=='POST' and action=='schedule':
   if p['status']!='draft':raise a.Error(409,'Somente um rascunho pode ser agendado.')
   approved(a,c,p);acc=account(a,c,u,p['account_id'])
   if not acc['active'] or not acc['verified']:raise a.Error(409,'Verifique e ative a conta antes de agendar.')
   if datetime.fromisoformat(p['scheduled'])<=datetime.now(timezone.utc):raise a.Error(400,'Escolha uma data futura.')
   if p['format']!='text' and not a.ORIGIN.startswith('https://'):raise a.Error(409,'Configure o endereço HTTPS público para a Meta buscar os arquivos aprovados.')
   c.execute("UPDATE editorial_posts SET status='scheduled',creator=?,updated=? WHERE id=?",(u['id'],a.now(),p['id']));a.audit(c,u,'editorial_schedule',p['id']);return {'ok':True}
  if method=='POST' and action=='cancel':
   if c.execute("UPDATE editorial_posts SET status='cancelled',updated=? WHERE id=? AND status IN ('draft','scheduled','blocked')",(a.now(),p['id'])).rowcount!=1:raise a.Error(409,'Publicação em processamento ou já enviada. Confira na plataforma.')
   c.execute('DELETE FROM editorial_media WHERE post_id=?',(p['id'],));a.audit(c,u,'editorial_cancel',p['id']);return {'ok':True}
 raise a.Error(404,'Ação editorial não encontrada.')

def media(a,c,token):
 r=c.execute("SELECT f.* FROM editorial_media m JOIN files f ON f.id=m.file_id JOIN editorial_posts p ON p.id=m.post_id WHERE m.token=? AND m.expires>? AND p.status IN ('processing','sending','published','unknown')",(a.digest(token),time.time())).fetchone()
 if not r:raise a.Error(404,'Arquivo indisponível.')
 return r

def tick(a):
 # One atomic claim per post. Network calls occur after committing the claim.
 with a.connect() as c:
  c.execute("UPDATE editorial_posts SET status='unknown',error='Processamento interrompido. Confira na Meta antes de reenviar.' WHERE status='sending' AND updated<?",((datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(),))
  rows=c.execute("SELECT id FROM editorial_posts WHERE (status='scheduled' AND scheduled<=?) OR (status='processing' AND updated<=?) ORDER BY scheduled LIMIT 10",(a.now(),(datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat())).fetchall()
 for item in rows:
  with a.connect() as c:
   c.execute('BEGIN IMMEDIATE');p=c.execute('SELECT * FROM editorial_posts WHERE id=?',(item['id'],)).fetchone()
   if p['status'] not in ['scheduled','processing']:continue
   prior=p['status']
   try:
    raw=c.execute('SELECT * FROM users WHERE id=? AND active=1',(p['creator'],)).fetchone()
    if not raw:raise a.Error(403,'Responsável inativo.')
    u=a.user_public(c,raw);a.need(u,'editorial');a.need(u,'editorial_manage');scope.need(a,c,u,p['client_id']);v,fs=approved(a,c,p);acc=account(a,c,u,p['account_id'])
    if not acc['active'] or not acc['verified']:raise a.Error(409,'Conta desativada ou aguardando verificação.')
   except a.Error as e:
    c.execute("UPDATE editorial_posts SET status='blocked',error=?,updated=? WHERE id=?",(e.message,a.now(),p['id']));continue
   c.execute("UPDATE editorial_posts SET status='sending',updated=? WHERE id=?",(a.now(),p['id']));urls=[]
   for f in fs:
    token=secrets.token_urlsafe(32);c.execute('INSERT INTO editorial_media VALUES(?,?,?,?)',(a.digest(token),p['id'],f['id'],time.time()+172800));urls.append(a.ORIGIN+'/publish-media/'+token)
   c.commit()
   try:
    if acc['platform']=='facebook':
     result=graph(a,acc,acc['target']+('/photos' if fs else '/feed'),{'url':urls[0],'caption':v['caption']} if fs else {'message':v['caption']});external=result.get('post_id') or result['id']
    else:
     container=p['container']
     if not container:
      payload={'caption':v['caption']}
      if p['format']=='carousel':
       children=[graph(a,acc,acc['target']+'/media',{'image_url':url,'is_carousel_item':'true'})['id'] for url in urls];payload.update(media_type='CAROUSEL',children=','.join(children))
      elif p['format']=='reel':payload.update(media_type='REELS',video_url=urls[0])
      else:payload['image_url']=urls[0]
      container=graph(a,acc,acc['target']+'/media',payload)['id'];c.execute("UPDATE editorial_posts SET container=?,status='processing',updated=? WHERE id=?",(container,a.now(),p['id']));c.commit();continue
     result=graph(a,acc,container,query={'fields':'status_code,status'});status=result.get('status_code')
     if status=='IN_PROGRESS':
      c.execute("UPDATE editorial_posts SET status='processing',updated=? WHERE id=?",(a.now(),p['id']));continue
     if status in ['ERROR','EXPIRED']:
      c.execute("UPDATE editorial_posts SET status='blocked',error='A Meta não processou o arquivo. Confira o formato e crie um novo agendamento.',updated=? WHERE id=?",(a.now(),p['id']));continue
     if status!='FINISHED':raise a.Error(503,'Estado de publicação precisa ser conferido na Meta.')
     external=graph(a,acc,acc['target']+'/media_publish',{'creation_id':container})['id']
    c.execute("UPDATE editorial_posts SET status='published',external_id=?,error='',updated=? WHERE id=?",(external,a.now(),p['id']));a.audit(c,u,'editorial_published',p['id'],str(external))
   except Exception:
    c.execute("UPDATE editorial_posts SET status='unknown',error='Resposta não confirmada. Confira a conta Meta antes de criar outro envio.',updated=? WHERE id=?",(a.now(),p['id']))

def required_schedule(a,value):
 result=a.datefield(value)
 if not result:raise a.Error(400,'Informe data e horário da publicação.')
 return result
