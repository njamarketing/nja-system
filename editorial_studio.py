"""Direct editorial publishing, with immutable snapshots and client-scoped uploads."""
import hashlib,json,re
from datetime import datetime,timezone
import agency_access as scope
import agency_editorial as editorial


def file_access(a,c,u,fid):
 row=c.execute('SELECT client_id FROM editorial_uploads WHERE file_id=?',(fid,)).fetchone()
 if not row:return False
 a.need(u,'editorial');scope.need(a,c,u,row['client_id']);return True


def detail(a,c,u,id):
 p=c.execute('SELECT p.*,s.name AS account_name,s.platform AS platform FROM editorial_posts p JOIN social_accounts s ON s.id=p.account_id WHERE p.id=?',(id,)).fetchone()
 if not p:raise a.Error(404,'Publicação não encontrada.')
 scope.need(a,c,u,p['client_id'])
 v=c.execute('SELECT * FROM creative_versions WHERE id=?',(p['version_id'],)).fetchone()
 return dict(p)|{'caption':v['caption'],'files':[{k:f[k] for k in ['id','name','mime','size']} for f in editorial.assets(c,v)]}


def api(a,c,u,method,parts,d):
 if parts[0]=='posts' and method=='GET':return detail(a,c,u,parts[1])
 a.need(u,'editorial_manage')
 if not ((parts==['direct'] and method=='POST') or (parts[0]=='posts' and method=='PATCH')):raise a.Error(404,'Ação não encontrada.')
 if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
 old=None
 if method=='PATCH':
  old=detail(a,c,u,parts[1])
  if old['source']!='direct' or old['status'] not in ['draft','scheduled','blocked']:raise a.Error(409,'Esta publicação não pode ser editada. O fluxo de aprovação é mantido para materiais de tarefas.')
 cid=d.get('client_id');client=scope.need(a,c,u,cid)
 if not client['active']:raise a.Error(409,'O cliente está desativado.')
 if old and old['client_id']!=cid:raise a.Error(400,'A publicação deve permanecer no mesmo cliente.')
 acc=editorial.account(a,c,u,d.get('account_id'))
 if acc['client_id']!=cid:raise a.Error(400,'Escolha uma conta deste cliente.')
 options=['text','image','video'] if acc['platform']=='facebook' else ['image','reel','carousel'] if acc['platform']=='instagram' else []
 fmt=d.get('format')
 if fmt not in options:raise a.Error(400,'Formato indisponível para esta conta.')
 title=a.textfield(d,'title',True,180);caption=a.textfield(d,'caption',False,2200)
 fids=d.get('file_ids',[])
 if not isinstance(fids,list) or len(fids)>10 or any(not isinstance(fid,str) for fid in fids) or len(set(fids))!=len(fids):raise a.Error(400,'Selecione até 10 mídias sem repetições.')
 files=[];digest=hashlib.sha256()
 for fid in fids:
  f=c.execute('SELECT f.* FROM files f JOIN editorial_uploads e ON e.file_id=f.id WHERE f.id=? AND e.client_id=?',(fid,cid)).fetchone()
  if not f or not (a.DATA/'uploads'/fid).is_file():raise a.Error(400,'Mídia indisponível ou de outro cliente.')
  files.append(f)
  with open(a.DATA/'uploads'/fid,'rb') as stream:
   for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
 if fmt=='text' and (files or not caption):raise a.Error(400,'Texto exige legenda e não permite mídia.')
 if fmt=='image' and (len(files)!=1 or files[0]['mime']!='image/jpeg'):raise a.Error(400,'Selecione uma imagem JPEG.')
 if fmt in ['video','reel'] and (len(files)!=1 or files[0]['mime']!='video/mp4'):raise a.Error(400,'Selecione um vídeo MP4.')
 if fmt=='carousel' and (not 2<=len(files)<=10 or any(f['mime']!='image/jpeg' for f in files)):raise a.Error(400,'O carrossel precisa de 2 a 10 imagens JPEG.')
 mode=d.get('mode','draft')
 if mode not in ['draft','schedule','now']:raise a.Error(400,'Escolha rascunho, agendamento ou publicar agora.')
 scheduled=editorial.required_schedule(a,d.get('scheduled')) if mode=='schedule' or (mode=='draft' and d.get('scheduled')) else a.now()
 if mode=='schedule' and datetime.fromisoformat(scheduled)<=datetime.now(timezone.utc):raise a.Error(400,'Escolha um horário futuro.')
 # A nonce makes a lost HTTP response safe to retry without a second publication.
 nonce=d.get('nonce','');payload=json.dumps(d,sort_keys=True)
 if not isinstance(nonce,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',nonce):raise a.Error(400,'Identificador de envio inválido. Reabra o editor.')
 previous=c.execute('SELECT * FROM editorial_submissions WHERE nonce=?',(nonce,)).fetchone()
 if previous:
  if previous['user_id']!=u['id'] or previous['payload']!=payload:raise a.Error(409,'Este envio já foi utilizado. Reabra a publicação para editar.')
  return {'id':previous['post_id'],'reused':True}
 if mode!='draft':
  if not acc['active'] or not acc['verified']:raise a.Error(409,'Ative e verifique a conta antes de publicar.')
  if fmt!='text' and not a.ORIGIN.startswith('https://'):raise a.Error(409,'A publicação de mídia precisa do endereço HTTPS público do servidor.')
 digest.update(b'\0'+caption.encode());vid=a.uid();now=a.now()
 if old:
  rid=c.execute('SELECT review_id FROM creative_versions WHERE id=?',(old['version_id'],)).fetchone()[0]
  number=c.execute('SELECT count(*)+1 FROM creative_versions WHERE review_id=?',(rid,)).fetchone()[0]
 else:
  rid=a.uid();number=1
  c.execute("INSERT INTO creative_reviews(id,client_id,title,status,created) VALUES(?,?,?,'direct',?)",(rid,cid,title,now))
 c.execute('INSERT INTO creative_versions VALUES(?,?,?,?,?,?,?,?)',(vid,rid,number,fids[0] if fids else None,caption,digest.hexdigest(),u['id'],now))
 for pos,fid in enumerate(fids):c.execute('INSERT INTO creative_assets VALUES(?,?,?)',(vid,fid,pos))
 c.execute('UPDATE creative_reviews SET current_version=?,title=? WHERE id=?',(vid,title,rid))
 status='draft' if mode=='draft' else 'scheduled'
 id=old['id'] if old else a.uid()
 if old:
  c.execute('DELETE FROM editorial_media WHERE post_id=?',(id,))
  c.execute("UPDATE editorial_posts SET account_id=?,version_id=?,title=?,format=?,scheduled=?,status=?,creator=?,container=NULL,external_id=NULL,error='',updated=? WHERE id=?",(acc['id'],vid,title,fmt,scheduled,status,u['id'],now,id))
 else:c.execute("INSERT INTO editorial_posts(id,client_id,account_id,version_id,title,format,scheduled,status,creator,updated,created,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'direct')",(id,cid,acc['id'],vid,title,fmt,scheduled,status,u['id'],now,now))
 c.execute('INSERT INTO editorial_submissions VALUES(?,?,?,?)',(nonce,u['id'],payload,id))
 a.audit(c,u,'editorial_direct_'+mode,id);return {'id':id,'status':status}
