"""Authorized lead conversation history, approved text templates and media."""
import os,re,json,base64,time,hashlib,secrets,tempfile
from pathlib import Path
import attachments
from datetime import datetime,timedelta,timezone
from urllib.request import Request,build_opener,HTTPSHandler
from urllib.parse import urlparse
import business,business_connectors as bc

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS lead_media(message_id TEXT PRIMARY KEY REFERENCES lead_messages(id),media_id TEXT NOT NULL,kind TEXT NOT NULL,mime TEXT NOT NULL,name TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS lead_uploaded_media(media_id TEXT PRIMARY KEY,lead_id TEXT NOT NULL REFERENCES leads(id),user_id TEXT NOT NULL REFERENCES users(id),kind TEXT NOT NULL,created REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS lead_outbound_requests(nonce TEXT PRIMARY KEY,payload_hash TEXT NOT NULL);
 ''')
def history(c,id,before=None):
 params=[id];where='lead_id=?'
 if before:
  old=c.execute('SELECT rowid FROM lead_messages WHERE id=? AND lead_id=?',(before,id)).fetchone()
  if old:where+=' AND rowid<?';params.append(old[0])
  else:return {'items':[],'before':None}
 rows=c.execute('SELECT * FROM lead_messages WHERE '+where+' ORDER BY rowid DESC LIMIT 51',params).fetchall();more=len(rows)>50;rows=rows[:50];items=[]
 for r in reversed(rows):items.append(dict(r)|{'media':dict(m) if (m:=c.execute('SELECT * FROM lead_media WHERE message_id=?',(r['id'],)).fetchone()) else None})
 return {'items':items,'before':rows[-1]['id'] if more else None}
def incoming(c,id,m):
 kind=m.get('type');obj=m.get(kind,{})
 if kind in ['image','video','audio','document','sticker'] and re.fullmatch(r'\d+',str(obj.get('id',''))):c.execute('INSERT OR IGNORE INTO lead_media VALUES(?,?,?,?,?)',(id,str(obj['id']),kind,str(obj.get('mime_type','application/octet-stream'))[:120],str(obj.get('filename','arquivo-'+id))[:180]))
def templates(a):
 waba=os.getenv('WHATSAPP_BUSINESS_ID','')
 if not re.fullmatch(r'\d+',waba):raise a.Error(503,'Configure WHATSAPP_BUSINESS_ID para consultar os templates aprovados.')
 result=bc.graph(a,waba+'/message_templates',token_env='WHATSAPP_TOKEN',query={'fields':'name,status,language,components','limit':100})
 # Complex header/button/authentication templates need dedicated forms; never invent their parameters.
 return [x for x in result.get('data',[]) if x.get('status')=='APPROVED' and all(k.get('type') in ['BODY','FOOTER'] for k in x.get('components',[]))]
def media_bytes(a,id):
 result=bc.graph(a,id,token_env='WHATSAPP_TOKEN',query={'phone_number_id':os.getenv('WHATSAPP_PHONE_ID','')});url=result.get('url','');p=urlparse(url)
 if p.scheme!='https' or p.hostname!='lookaside.fbsbx.com' or p.username or p.password or p.port not in [None,443]:raise a.Error(503,'Endereço de mídia não autorizado.')
 try:
  with build_opener(bc.NoRedirect(),HTTPSHandler()).open(Request(url,headers={'Authorization':'Bearer '+os.getenv('WHATSAPP_TOKEN','')}),timeout=25) as response:
   raw=response.read(8*1024*1024+1)
   if len(raw)>8*1024*1024:raise a.Error(413,'Visualização de mídia limitada a 8 MB neste chat.')
 except a.Error:raise
 except Exception:raise a.Error(503,'A mídia expirou ou não está disponível na Meta.')
 return raw

def send(a,c,u,lead,payload,label,nonce):
 if not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',nonce):raise a.Error(400,'Identificador de envio inválido.')
 encoded=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
 if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
 old=c.execute('SELECT * FROM lead_messages WHERE id=?',(nonce,)).fetchone()
 if old:
  signature=c.execute('SELECT payload_hash FROM lead_outbound_requests WHERE nonce=?',(nonce,)).fetchone()
  if old['lead_id']!=lead['id'] or old['user_id']!=u['id'] or not signature or signature[0]!=encoded:raise a.Error(409,'Identificador de envio já utilizado.')
  return {'id':nonce,'status':old['status']}
 c.execute('INSERT INTO lead_outbound_requests VALUES(?,?)',(nonce,encoded));c.execute('INSERT INTO lead_messages VALUES(?,?,?,?,?,NULL,?,?)',(nonce,lead['id'],u['id'],'out',label,'sending',a.now()));c.commit()
 try:result=bc.graph(a,os.getenv('WHATSAPP_PHONE_ID','')+'/messages',{'messaging_product':'whatsapp','to':lead['phone'],**payload},'WHATSAPP_TOKEN');external=result['messages'][0]['id']
 except Exception:c.execute("UPDATE lead_messages SET status='unknown' WHERE id=?",(nonce,));c.commit();raise a.Error(503,'Envio sem confirmação. Confira a conversa antes de repetir.')
 c.execute("UPDATE lead_messages SET status='accepted',external_id=? WHERE id=?",(external,nonce));a.audit(c,u,'whatsapp_extended_send',lead['id']);return {'id':nonce,'status':'accepted'}

def api(a,c,u,method,path,d,q):
 if not path.startswith('/api/business/leads/'):return None
 parts=path.split('/');id=parts[4];action=parts[5] if len(parts)>5 else ''
 if action not in ['history','media','templates','template','send-media','upload-media']:return None
 lead=business.access(a,c,u,'leads',id)
 if action=='history' and method=='GET':return history(c,id,q.get('before',[''])[0])
 if action=='media' and method=='GET':
  r=c.execute('SELECT m.* FROM lead_media m JOIN lead_messages l ON l.id=m.message_id WHERE l.lead_id=? AND m.message_id=?',(id,q.get('message',[''])[0])).fetchone()
  if not r:raise a.Error(404,'Mídia não encontrada.')
  raw=media_bytes(a,r['media_id']);return {'name':r['name'],'mime':r['mime'],'data':base64.b64encode(raw).decode()}
 a.need(u,'crm_reply')
 if lead['owner']!=u['id']:raise a.Error(403,'Somente o responsável comercial pode enviar mensagens.')
 if not os.getenv('WHATSAPP_TOKEN') or not re.fullmatch(r'\d+',os.getenv('WHATSAPP_PHONE_ID','')):raise a.Error(503,'Configure WhatsApp no servidor.')
 if action=='upload-media' and method=='POST':
  name=Path(a.textfield(d,'name',True,180).replace('\\','/')).name
  try:raw=base64.b64decode(d.get('data',''),validate=True)
  except Exception:raise a.Error(400,'Arquivo inválido.')
  if not 0<len(raw)<=8*1024*1024:raise a.Error(413,'Envie até 8 MB.')
  with tempfile.NamedTemporaryFile() as f:f.write(raw);f.flush();mime=attachments.identify(a,Path(f.name),name)
  kind='image' if mime in ['image/jpeg','image/png'] else 'video' if mime=='video/mp4' else 'document' if mime=='application/pdf' else None
  if not kind:raise a.Error(400,'Envie JPEG, PNG, MP4 ou PDF.')
  if kind=='image' and len(raw)>5*1024*1024:raise a.Error(413,'Imagens devem ter até 5 MB.')
  a.throttle(c,'wa-media:'+u['id'],30);boundary='nja'+secrets.token_hex(18);safe_name='arquivo'+Path(name).suffix.lower()
  fields=[('messaging_product','whatsapp'),('type',mime)];body=b''
  for key,value in fields:body+=('--'+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n'+value+'\r\n').encode()
  body+=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="'+safe_name+'"\r\nContent-Type: '+mime+'\r\n\r\n').encode()+raw+('\r\n--'+boundary+'--\r\n').encode()
  version=os.getenv('META_GRAPH_VERSION','')
  if not re.fullmatch(r'v\d+\.0',version):raise a.Error(503,'Configure a versão Meta.')
  try:
   with build_opener(bc.NoRedirect(),HTTPSHandler()).open(Request('https://graph.facebook.com/'+version+'/'+os.getenv('WHATSAPP_PHONE_ID')+'/media',data=body,headers={'Authorization':'Bearer '+os.getenv('WHATSAPP_TOKEN'),'Content-Type':'multipart/form-data; boundary='+boundary}),timeout=25) as response:result=json.loads(response.read(1024*1024))
   media_id=str(result['id'])
   if not re.fullmatch(r'\d+',media_id):raise ValueError()
  except Exception:raise a.Error(503,'Upload não confirmado. A mensagem ainda não foi enviada.')
  c.execute('INSERT OR REPLACE INTO lead_uploaded_media VALUES(?,?,?,?,?)',(media_id,id,u['id'],kind,time.time()));a.audit(c,u,'whatsapp_media_upload',id);return {'media_id':media_id,'kind':kind,'filename':name}
 if action=='templates' and method=='GET':return {'items':templates(a)}
 if action=='template' and method=='POST':
  template=next((t for t in templates(a) if t['name']==d.get('name') and t['language']==d.get('language')),None)
  if not template:raise a.Error(400,'Template aprovado não encontrado nesta conta.')
  body=next((x.get('text','') for x in template['components'] if x['type']=='BODY'),'');slots=sorted(set(re.findall(r'\{\{(\d+)\}\}',body)),key=int);params=d.get('parameters',[])
  if not isinstance(params,list) or len(params)!=len(slots) or slots!=[str(i+1) for i in range(len(slots))] or re.search(r'\{\{[^0-9]',body):raise a.Error(400,'Confira os parâmetros numerados do template.')
  values=[a.textfield({'v':v},'v',True,1000) for v in params];payload={'type':'template','template':{'name':template['name'],'language':{'code':template['language']}}}
  if values:payload['template']['components']=[{'type':'body','parameters':[{'type':'text','text':v} for v in values]}]
  for n,value in enumerate(values,1):body=body.replace('{{'+str(n)+'}}',value)
  return send(a,c,u,lead,payload,'[Template '+template['name']+'] '+body,a.textfield(d,'nonce',True,100))
 if action=='send-media' and method=='POST':
  last=c.execute("SELECT MAX(created) FROM lead_messages WHERE lead_id=? AND direction='in'",(id,)).fetchone()[0]
  if not last or datetime.fromisoformat(last)<datetime.now(timezone.utc)-timedelta(hours=24):raise a.Error(409,'Mídia exige janela de atendimento aberta.')
  kind=d.get('kind');media_id=a.textfield(d,'media_id',True,100);caption=a.textfield(d,'caption',False,1024)
  if kind not in ['image','video','audio','document'] or not re.fullmatch(r'\d+',media_id):raise a.Error(400,'Tipo ou ID de mídia inválido.')
  if not c.execute('SELECT 1 FROM lead_uploaded_media WHERE media_id=? AND lead_id=? AND user_id=? AND kind=? AND created>?',(media_id,id,u['id'],kind,time.time()-86400)).fetchone():raise a.Error(403,'Envie o arquivo por este atendimento antes de usá-lo na mensagem.')
  # Provider confirms this media belongs to the configured business phone.
  info=bc.graph(a,media_id,token_env='WHATSAPP_TOKEN',query={'phone_number_id':os.getenv('WHATSAPP_PHONE_ID')})
  if str(info.get('id'))!=media_id:raise a.Error(403,'Mídia não confirmada nesta conta.')
  content={'id':media_id}
  if caption and kind!='audio':content['caption']=caption
  if kind=='document':content['filename']=a.textfield(d,'filename',True,180)
  return send(a,c,u,lead,{'type':kind,kind:content},'[Mídia '+kind+'] '+caption,a.textfield(d,'nonce',True,100))
 raise a.Error(404,'Ação de conversa não encontrada.')
