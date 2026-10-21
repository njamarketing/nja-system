"""Workspace improvements: brand assets, master account controls and social replies."""
import base64,json,re,io
from urllib.parse import urlparse
import agency_access,social

def init(c):
 for table,col,kind in [('users','deleted','INTEGER NOT NULL DEFAULT 0'),('post_comments','parent_id','TEXT'),('posts','edited','TEXT')]:
  if col not in [r[1] for r in c.execute('PRAGMA table_info('+table+')')]:c.execute('ALTER TABLE '+table+' ADD COLUMN '+col+' '+kind)
 c.executescript('''CREATE TABLE IF NOT EXISTS client_brand(client_id TEXT PRIMARY KEY REFERENCES clients(id),colors TEXT NOT NULL DEFAULT '[]',drive_url TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS client_logos(id TEXT PRIMARY KEY,client_id TEXT NOT NULL REFERENCES clients(id),name TEXT NOT NULL,mime TEXT NOT NULL,payload BLOB NOT NULL,created TEXT NOT NULL);''')

def logo_list(c,cid):
 out=[]
 for r in c.execute('SELECT * FROM client_logos WHERE client_id=? ORDER BY created',(cid,)):
  item={'id':r['id'],'name':r['name'],'mime':r['mime'],'size':len(r['payload']),'created':r['created'],'thumbnail':''}
  if r['mime'].startswith('image/'):
   try:
    from PIL import Image
    im=Image.open(io.BytesIO(r['payload']));im.thumbnail((220,160));preview=io.BytesIO();im.save(preview,format='PNG');item['thumbnail']='data:image/png;base64,'+base64.b64encode(preview.getvalue()).decode()
   except Exception:pass
  out.append(item)
 return out

def api(a,c,u,method,path,d,q):
 parts=path.strip('/').split('/')
 if len(parts)==3 and parts[1]=='users' and method=='DELETE':
  if not u['master']:raise a.Error(403,'Somente o master pode excluir perfis.')
  target=c.execute('SELECT * FROM users WHERE id=?',(parts[2],)).fetchone()
  if not target:raise a.Error(404,'Usuário não encontrado.')
  if target['master'] or target['id']==u['id']:raise a.Error(400,'Não é possível excluir o master ou o próprio acesso.')
  c.execute('UPDATE users SET active=0,deleted=1 WHERE id=?',(target['id'],))
  for table in ['sessions','resets','subscriptions','running_timers']:c.execute('DELETE FROM '+table+' WHERE user_id=?',(target['id'],))
  a.audit(c,u,'user_delete',target['id'],'Perfil excluído; autoria histórica preservada.');return {'ok':True}
 if len(parts)>=4 and parts[1]=='clients' and parts[3]=='brand':
  cid=parts[2];a.need(u,'clients');agency_access.need(a,c,u,cid)
  if method!='GET':a.need(u,'client_manage')
  if len(parts)==4:
   if method=='GET':
    r=c.execute('SELECT * FROM client_brand WHERE client_id=?',(cid,)).fetchone()
    return {'colors':json.loads(r['colors']) if r else [],'drive_url':r['drive_url'] if r else '', 'logos':logo_list(c,cid)}
   if method=='PATCH':
    colors=d.get('colors',[]);url=a.textfield(d,'drive_url',False,2000)
    if not isinstance(colors,list) or len(colors)>30 or any(not isinstance(x,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',x) for x in colors):raise a.Error(400,'Use até 30 cores em formato #RRGGBB.')
    try:
     parsed=urlparse(url)
     if url and (parsed.scheme!='https' or parsed.hostname not in ['drive.google.com','docs.google.com'] or parsed.username or parsed.password or parsed.port not in [None,443]):raise ValueError()
    except ValueError:raise a.Error(400,'Use um link HTTPS do Google Drive.')
    c.execute('INSERT INTO client_brand VALUES(?,?,?) ON CONFLICT(client_id) DO UPDATE SET colors=excluded.colors,drive_url=excluded.drive_url',(cid,json.dumps(colors),url));a.audit(c,u,'client_brand',cid);return {'ok':True}
   if method=='POST':
    name=a.textfield(d,'name',True,180)
    try:raw=base64.b64decode(d.get('data',''),validate=True)
    except Exception:raise a.Error(400,'Arquivo inválido.')
    if not 0<len(raw)<=8*1024*1024:raise a.Error(413,'Limite de 8 MB por logo.')
    ext=name.rsplit('.',1)[-1].lower()
    if ext in ['png','jpg','jpeg','webp']:
     try:
      from PIL import Image
      im=Image.open(io.BytesIO(raw))
      if im.width*im.height>20_000_000:raise ValueError()
      im.verify();mime=Image.MIME[im.format]
      if mime not in ['image/png','image/jpeg','image/webp']:raise ValueError()
     except Exception:raise a.Error(400,'Imagem inválida.')
    elif ext=='svg':
     try:
      import xml.etree.ElementTree as ET
      if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError()
      if ET.fromstring(raw).tag.split('}')[-1]!='svg':raise ValueError()
     except Exception:raise a.Error(400,'SVG inválido.')
     mime='application/octet-stream' # Download only; never render active SVG in the application.
    elif ext=='pdf' and raw.startswith(b'%PDF-'):mime='application/pdf'
    else:raise a.Error(400,'Envie PNG, JPG, WebP, SVG ou PDF.')
    id=a.uid();c.execute('INSERT INTO client_logos VALUES(?,?,?,?,?,?)',(id,cid,name,mime,raw,a.now()));a.audit(c,u,'client_logo_add',cid);return {'id':id}
  if len(parts)==5:
   r=c.execute('SELECT * FROM client_logos WHERE id=? AND client_id=?',(parts[4],cid)).fetchone()
   if not r:raise a.Error(404,'Logo não encontrada.')
   if method=='GET':return {'name':r['name'],'mime':r['mime'],'data':base64.b64encode(r['payload']).decode()}
   if method=='DELETE':c.execute('DELETE FROM client_logos WHERE id=?',(r['id'],));a.audit(c,u,'client_logo_delete',cid);return {'ok':True}
 if len(parts)==3 and parts[1]=='posts' and method=='PATCH':
  a.need(u,'social');r=c.execute('SELECT * FROM posts WHERE id=?',(parts[2],)).fetchone()
  if not r:raise a.Error(404,'Publicação não encontrada.')
  if r['user_id']!=u['id']:raise a.Error(403,'Somente o autor pode editar a publicação.')
  tx=a.textfield(d,'text',False,5000);image=r['image']
  if 'image' in d and d['image']!=image:image=social.asset(a,c,u,d['image'],'post')
  if not tx and not image:raise a.Error(400,'Adicione texto ou imagem.')
  c.execute('UPDATE posts SET text=?,image=?,edited=? WHERE id=?',(tx,image,a.now(),r['id']))
  if r['image'] and r['image']!=image:c.execute('UPDATE social_assets SET entity_id=NULL WHERE file_id=?',(r['image'],))
  if image:c.execute('UPDATE social_assets SET entity_id=? WHERE file_id=?',(r['id'],image))
  a.audit(c,u,'post_edit',r['id']);return {'ok':True}
 if len(parts)==4 and parts[1]=='stories' and parts[3]=='reply' and method=='POST':
  a.need(u,'social');a.need(u,'chats');s=c.execute('SELECT * FROM stories WHERE id=? AND expires>?',(parts[2],a.now())).fetchone()
  if not s:raise a.Error(404,'História expirada ou indisponível.')
  target=c.execute('SELECT * FROM users WHERE id=? AND active=1',(s['user_id'],)).fetchone()
  if not target or target['id']==u['id'] or not a.perm(a.user_public(c,target),'chats'):raise a.Error(400,'Este autor não está disponível para receber mensagens.')
  tx=a.textfield(d,'text',True,2000)
  rid=None
  for row in c.execute("SELECT id FROM rooms WHERE kind='direct'"):
   members={m[0] for m in c.execute('SELECT user_id FROM room_members WHERE room_id=?',(row['id'],))}
   if members=={u['id'],target['id']}:rid=row['id'];break
  if not rid:
   rid=a.uid();c.execute('INSERT INTO rooms(id,name,kind,creator,created) VALUES(?,?,?,?,?)',(rid,'Conversa direta','direct',u['id'],a.now()))
   for who in [u['id'],target['id']]:c.execute('INSERT INTO room_members(room_id,user_id) VALUES(?,?)',(rid,who))
  a.room_access(c,u,rid)
  c.execute('DELETE FROM room_archives WHERE room_id=? AND user_id IN (?,?)',(rid,u['id'],target['id']))
  text='Resposta à história de '+target['name']+' ('+s['created']+')'+('\n'+s['text'][:500] if s['text'] else '')+'\n\n'+tx
  c.execute('INSERT INTO messages VALUES(?,?,?,?,?)',(a.uid(),rid,u['id'],text,a.now()));a.notify(c,target['id'],u['name']+' respondeu sua história',tx,'chats:'+rid,'messages');a.audit(c,u,'story_reply',s['id']);return {'room_id':rid}
 return None
