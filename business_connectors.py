"""Fixed-host provider adapters. No payment operations exist in this module."""
import os,json,re,hmac,hashlib,ssl,time
from datetime import datetime,timezone,timedelta
from urllib.request import Request,build_opener,HTTPSHandler,HTTPRedirectHandler
from urllib.parse import urlencode
import business as b

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args):return None

def http(a,url,body=None,token=None,context=None,form=False):
 headers={'Accept':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 raw=None
 if body is not None:
  raw=(urlencode(body) if form else json.dumps(body)).encode();headers['Content-Type']='application/x-www-form-urlencoded' if form else 'application/json'
 try:
  with build_opener(NoRedirect(),HTTPSHandler(context=context)).open(Request(url,data=raw,headers=headers),timeout=25) as r:
   data=r.read(4*1024*1024+1)
   if len(data)>4*1024*1024:raise ValueError()
   return json.loads(data)
 except Exception:raise a.Error(503,'Não foi possível confirmar a resposta do provedor. Confira credenciais, permissões e conexão; não repita envios sem verificar o destino.')

def graph(a,route,body=None,token_env='META_ACCESS_TOKEN',query=None):
 version=os.getenv('META_GRAPH_VERSION','')
 if not re.fullmatch(r'v\d+\.0',version):raise a.Error(503,'Configure META_GRAPH_VERSION com a versão habilitada no aplicativo Meta.')
 token=os.getenv(token_env,'')
 if not token:raise a.Error(503,'Integração não configurada no servidor.')
 if not re.fullmatch(r'[A-Za-z0-9_/-]+',route):raise a.Error(400,'Identificador inválido.')
 return http(a,'https://graph.facebook.com/'+version+'/'+route+('?' + urlencode(query) if query else ''),body,token)

def status(a,c):
 import enterprise
 return {'items':[
 {'id':'cora','name':'Cora','ready':all(os.getenv(k) for k in ['CORA_CLIENT_ID','CORA_CERT_PATH','CORA_KEY_PATH']),'detail':'Consulta paginada de boletos emitidos na conta autorizada, por vencimento. Certificado mTLS necessário. Ambiente: '+os.getenv('CORA_ENV','stage')},
 {'id':'itau','name':'Itaú','ready':False,'detail':'Controle manual e PDFs disponíveis. Sincronização aguarda contratação/habilitação e documentação da API específica da conta.'},
 {'id':'infinitepay','name':'InfinitePay','ready':False,'detail':'Controle manual e PDFs disponíveis. API pública de checkout não equivale à consulta geral de faturas; sincronização geral ainda indisponível.'},
 {'id':'whatsapp','name':'WhatsApp Business','ready':all(os.getenv(k) for k in ['WHATSAPP_TOKEN','WHATSAPP_PHONE_ID','META_APP_SECRET','WHATSAPP_VERIFY_TOKEN','META_GRAPH_VERSION']),'detail':'Webhook com assinatura, origem de anúncio e chat de texto com janela de atendimento.'},
 {'id':'meta','name':'Facebook e Instagram','ready':bool(os.getenv('META_GRAPH_VERSION') and os.getenv('META_ACCESS_TOKEN')),'detail':'Publicação em página/Instagram configurados; consulta e pausa/ativação de campanhas da conta configurada.'}], 'whatsapp_owner':enterprise.setting(c,'whatsapp_owner'), 'runs':[dict(r) for r in c.execute('SELECT * FROM connector_runs')], 'webhook':a.ORIGIN+'/webhooks/whatsapp'}

def cora(a,path,token=None,body=None):
 if os.getenv('CORA_ENV','stage') not in ['stage','production']:raise a.Error(503,'CORA_ENV inválido.')
 if not all(os.getenv(k) for k in ['CORA_CLIENT_ID','CORA_CERT_PATH','CORA_KEY_PATH']):raise a.Error(503,'Configure credenciais e certificado Cora no servidor.')
 try:
  context=ssl.create_default_context();context.load_cert_chain(os.environ['CORA_CERT_PATH'],os.environ['CORA_KEY_PATH'])
 except (OSError,ssl.SSLError):raise a.Error(503,'Certificado Cora indisponível ou inválido.')
 host='https://matls-clients.api.'+('stage.' if os.getenv('CORA_ENV','stage')=='stage' else '')+'cora.com.br'
 return http(a,host+path,body,token,context,form=body is not None)

def sync_bank(a,c,u,bank,d):
 if bank!='cora':raise a.Error(409,'Sincronização deste banco depende da API habilitada para a conta. Use o cadastro manual e anexe os PDFs por enquanto.')
 start=b.day(a,d.get('start'));end=b.day(a,d.get('end'))
 if end<=start:raise a.Error(400,'Data final deve ser posterior à inicial.')
 try:page=int(d.get('page',1))
 except Exception:raise a.Error(400,'Página inválida.')
 if page<1 or page>10000:raise a.Error(400,'Página inválida.')
 a.throttle(c,'cora-sync:'+u['id'],30)
 token=cora(a,'/token',body={'grant_type':'client_credentials','client_id':os.getenv('CORA_CLIENT_ID')}).get('access_token')
 if not token:raise a.Error(503,'Cora não retornou token.')
 result=cora(a,'/v2/invoices/?'+urlencode({'start':start,'end':end,'page':page,'perPage':20}),token)
 items=result.get('items')
 if not isinstance(items,list):raise a.Error(503,'Formato inesperado da resposta Cora.')
 prepared=[]
 for item in items:
  ref=item.get('id','')
  if not re.fullmatch(r'[A-Za-z0-9_-]{1,150}',ref):raise a.Error(503,'Identificador inválido recebido da Cora.')
  r=cora(a,'/v2/invoices/'+ref,token)
  amount=r.get('total_amount');due=(r.get('payment_terms') or {}).get('due_date');customer=(r.get('customer') or {}).get('name')
  if not isinstance(amount,int) or amount<0 or not customer:raise a.Error(503,'Dados incompletos recebidos da Cora.')
  due=b.day(a,due);status={'PAID':'paid','CANCELLED':'cancelled','OPEN':'open','LATE':'open'}.get(r.get('status'),'pending')
  # Distinguish sandbox data and avoid collisions with production references.
  source='cora_api';ref=('stage:' if os.getenv('CORA_ENV','stage')=='stage' else '')+ref
  prepared.append((ref,customer,amount,due,status,source))
 for ref,customer,amount,due,status,source in prepared:
  old=c.execute("SELECT * FROM invoices WHERE bank='cora' AND reference=?",(ref,)).fetchone()
  if old and old['source']!='cora_api':raise a.Error(409,'Referência já cadastrada manualmente. Revise antes de sincronizar.')
  c.execute("INSERT INTO invoices(id,bank,reference,customer,amount,due,status,source,updated) VALUES(?,'cora',?,?,?,?,?,?,?) ON CONFLICT(bank,reference) DO UPDATE SET customer=excluded.customer,amount=excluded.amount,due=excluded.due,status=excluded.status,updated=excluded.updated",(a.uid(),ref,customer,amount,due,status,source,a.now()))
 c.execute('INSERT OR REPLACE INTO connector_runs VALUES(?,?,?)',('cora',a.now(),f'Página {page}: {len(prepared)} registros. Período {start} a {end}. Ambiente '+os.getenv('CORA_ENV','stage')));a.audit(c,u,'cora_sync','cora')
 return {'count':len(prepared),'page':page,'has_more':len(items)==20,'total':result.get('totalItems'),'environment':os.getenv('CORA_ENV','stage')}

def webhook(a,c,method,environ,q,raw):
 if method=='GET':
  verify=os.getenv('WHATSAPP_VERIFY_TOKEN','')
  if not verify or q.get('hub.mode',[''])[0]!='subscribe' or not hmac.compare_digest(q.get('hub.verify_token',[''])[0],verify):raise a.Error(403,'Verificação inválida.')
  challenge=q.get('hub.challenge',[''])[0]
  if not re.fullmatch(r'\d{1,100}',challenge):raise a.Error(400,'Desafio inválido.')
  return challenge.encode()
 if method!='POST':raise a.Error(400,'Método inválido.')
 secret=os.getenv('META_APP_SECRET','');signature=environ.get('HTTP_X_HUB_SIGNATURE_256','')
 if not secret or not hmac.compare_digest(signature,'sha256='+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()):raise a.Error(403,'Assinatura inválida.')
 try:payload=json.loads(raw)
 except Exception:raise a.Error(400,'JSON inválido.')
 if not isinstance(payload,dict):raise a.Error(400,'Objeto JSON esperado.')
 if payload.get('object')!='whatsapp_business_account':return b'OK'
 import enterprise
 for entry in payload.get('entry',[]):
  for change in entry.get('changes',[]):
   value=change.get('value',{})
   if not os.getenv('WHATSAPP_PHONE_ID') or value.get('metadata',{}).get('phone_number_id')!=os.getenv('WHATSAPP_PHONE_ID'):continue
   for s in value.get('statuses',[]):
    if s.get('status') in ['sent','delivered','read','failed']:
     old=c.execute('SELECT status FROM lead_messages WHERE external_id=?',(s.get('id'),)).fetchone();rank={'sending':0,'unknown':0,'accepted':1,'sent':2,'delivered':3,'read':4,'failed':5}
     if old and rank.get(s['status'],0)>rank.get(old[0],0):c.execute('UPDATE lead_messages SET status=? WHERE external_id=?',(s['status'],s.get('id')))
   for m in value.get('messages',[]):
    mid=m.get('id');phone=m.get('from','')
    if not isinstance(mid,str) or len(mid)>300 or not re.fullmatch(r'[1-9][0-9]{9,14}',phone):continue
    if c.execute('SELECT 1 FROM lead_messages WHERE external_id=?',(mid,)).fetchone():continue
    row=c.execute('SELECT * FROM leads WHERE phone=?',(phone,)).fetchone()
    referral=m.get('referral') or {}
    if not row:
     if referral.get('source_type')!='ad' or not str(referral.get('source_id','')).isdigit():continue
     owner=enterprise.setting(c,'whatsapp_owner') or None
     try:
      if owner:b.person(a,c,owner,True)
     except a.Error:owner=None
     name=next((x.get('profile',{}).get('name') for x in value.get('contacts',[]) if x.get('wa_id')==phone),None) or phone
     id=a.uid();c.execute("INSERT INTO leads(id,name,phone,owner,source,source_id,created,updated) VALUES(?,?,?,?,'meta_ad',?,?,?)",(id,str(name)[:160],phone,owner,str(referral['source_id']),a.now(),a.now()));b.activity(a,c,None,id,'imported','Contato recebido de anúncio Meta.');row=c.execute('SELECT * FROM leads WHERE id=?',(id,)).fetchone()
    body=m.get('text',{}).get('body','') if m.get('type')=='text' else '[Mensagem '+str(m.get('type','desconhecida'))+'] '+str(m.get(m.get('type'),{}).get('caption',''))
    try:ts=datetime.fromtimestamp(min(float(m['timestamp']),time.time()),timezone.utc).isoformat(timespec='seconds')
    except Exception:continue
    message_id=a.uid();c.execute('INSERT INTO lead_messages VALUES(?,?,NULL,?,?,?,?,?)',(message_id,row['id'],'in',str(body)[:4000],mid,'received',ts));
    import agency_whatsapp
    agency_whatsapp.incoming(c,message_id,m)
    c.execute('UPDATE leads SET updated=? WHERE id=?',(a.now(),row['id']))
    if row['owner']:
     try:
      b.person(a,c,row['owner'],True);a.notify(c,row['owner'],'Mensagem de lead',row['name'],'crm:'+row['id'],'messages')
     except a.Error:pass
    a.audit(c,{'id':None},'whatsapp_received',row['id'])
 return b'OK'

def send_whatsapp(a,c,u,row,d):
 text=a.textfield(d,'text',True,4000);nonce=a.textfield(d,'nonce',True,100)
 if not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',nonce):raise a.Error(400,'Identificador de envio inválido.')
 old=c.execute('SELECT * FROM lead_messages WHERE id=?',(nonce,)).fetchone()
 if old:
  if old['lead_id']!=row['id'] or old['user_id']!=u['id'] or old['text']!=text:raise a.Error(409,'Identificador de envio já utilizado.')
  return {'id':nonce,'status':old['status']}
 last=c.execute("SELECT MAX(created) FROM lead_messages WHERE lead_id=? AND direction='in'",(row['id'],)).fetchone()[0]
 if not last or datetime.fromisoformat(last)<datetime.now(timezone.utc)-timedelta(hours=24):raise a.Error(409,'Janela de atendimento encerrada. Aguarde nova mensagem do contato; envio de templates ainda não está disponível.')
 phone_id=os.getenv('WHATSAPP_PHONE_ID','')
 if not phone_id or not os.getenv('WHATSAPP_TOKEN'):raise a.Error(503,'WhatsApp não configurado.')
 a.throttle(c,'wa-send:'+u['id'],40)
 c.execute('INSERT INTO lead_messages VALUES(?,?,?,?,?,NULL,?,?)',(nonce,row['id'],u['id'],'out',text,'sending',a.now()));c.commit()
 try:
  result=graph(a,phone_id+'/messages',{'messaging_product':'whatsapp','to':row['phone'],'type':'text','text':{'body':text}},'WHATSAPP_TOKEN');external=result['messages'][0]['id']
 except Exception:
  c.execute("UPDATE lead_messages SET status='unknown' WHERE id=?",(nonce,));c.commit();raise a.Error(503,'Envio sem confirmação. Confira a conversa antes de repetir; o registro foi preservado.')
 c.execute("UPDATE lead_messages SET status='accepted',external_id=? WHERE id=?",(external,nonce));a.audit(c,u,'whatsapp_sent',row['id']);return {'id':nonce,'status':'accepted'}

def marketing(a,c,u,method,parts,d):
 kind=parts[0] if parts else 'posts';id=parts[1] if len(parts)>1 else None;action=parts[2] if len(parts)>2 else None
 if kind=='campaigns':
  account=os.getenv('META_AD_ACCOUNT_ID','')
  if not re.fullmatch(r'act_\d+',account):raise a.Error(503,'Configure a conta de anúncios no servidor.')
  result=graph(a,account+'/campaigns',query={'fields':'id,name,status,effective_status,objective','limit':100})
  if method=='GET':return {'items':result.get('data',[]),'has_more':bool(result.get('paging',{}).get('next'))}
  a.need(u,'marketing_manage')
  if method=='POST' and id and any(x.get('id')==id for x in result.get('data',[])) and d.get('status') in ['ACTIVE','PAUSED']:
   graph(a,id,{'status':d['status']});a.audit(c,u,'campaign_status',id,d['status']);return {'ok':True}
  raise a.Error(400,'Campanha ou ação inválida.')
 if kind!='posts':raise a.Error(404,'Recurso inválido.')
 if method=='GET':return {'items':[dict(r) for r in c.execute('SELECT * FROM marketing_posts ORDER BY created DESC')]}
 a.need(u,'marketing_manage')
 if method=='POST' and not id:
  platform=d.get('platform');text=a.textfield(d,'text',True,2200);url=a.textfield(d,'image_url',False,2000)
  if platform not in ['facebook','instagram']:raise a.Error(400,'Plataforma inválida.')
  if url and (not url.startswith('https://') or any(x in url for x in ['\r','\n'])):raise a.Error(400,'Use URL pública HTTPS para imagem.')
  if platform=='instagram' and not url:raise a.Error(400,'Instagram requer URL pública de imagem.')
  id=a.uid();c.execute('INSERT INTO marketing_posts(id,platform,text,image_url,creator,created,updated) VALUES(?,?,?,?,?,?,?)',(id,platform,text,url,u['id'],a.now(),a.now()));a.audit(c,u,'marketing_draft',id);return {'id':id}
 r=c.execute('SELECT * FROM marketing_posts WHERE id=?',(id,)).fetchone()
 if not r:raise a.Error(404,'Publicação não encontrada.')
 if method=='DELETE' and r['status']=='draft':c.execute('DELETE FROM marketing_posts WHERE id=?',(id,));a.audit(c,u,'marketing_delete',id);return {'ok':True}
 if method=='POST' and action=='publish':
  env='META_PAGE_ID' if r['platform']=='facebook' else 'META_INSTAGRAM_ID';target=os.getenv(env,'')
  token_env='META_PAGE_ACCESS_TOKEN' if r['platform']=='facebook' else 'META_ACCESS_TOKEN'
  if not target or not os.getenv(token_env):raise a.Error(503,'Configure a conta e o token de publicação no servidor.')
  if c.execute("UPDATE marketing_posts SET status='publishing',updated=? WHERE id=? AND status='draft'",(a.now(),id)).rowcount!=1:raise a.Error(409,'Publicação já enviada ou aguardando conferência; não será reenviada automaticamente.')
  c.commit()
  try:
   if r['platform']=='facebook':
    result=graph(a,target+('/photos' if r['image_url'] else '/feed'),{'url':r['image_url'],'caption':r['text']} if r['image_url'] else {'message':r['text']},token_env=token_env);external=result.get('post_id') or result['id']
   else:
    container=graph(a,target+'/media',{'image_url':r['image_url'],'caption':r['text']})['id'];c.execute('UPDATE marketing_posts SET container_id=? WHERE id=?',(container,id));c.commit();external=graph(a,target+'/media_publish',{'creation_id':container})['id']
  except Exception:
   c.execute("UPDATE marketing_posts SET status='unknown',updated=? WHERE id=?",(a.now(),id));c.commit();raise a.Error(503,'Publicação sem confirmação. Confira no Meta antes de criar outra; não repetimos automaticamente.')
  c.execute("UPDATE marketing_posts SET status='published',external_id=?,updated=? WHERE id=?",(external,a.now(),id));a.audit(c,u,'marketing_publish',id);return {'id':external}
 raise a.Error(400,'Ação inválida.')


def cora_pdf(a,c,u,row):
 from urllib.parse import urlsplit
 stage=row['reference'].startswith('stage:')
 if stage!=(os.getenv('CORA_ENV','stage')=='stage'):raise a.Error(409,'O registro pertence a outro ambiente Cora.')
 ref=row['reference'].removeprefix('stage:')
 if not re.fullmatch(r'[A-Za-z0-9_-]{1,150}',ref):raise a.Error(400,'Referência inválida.')
 token=cora(a,'/token',body={'grant_type':'client_credentials','client_id':os.getenv('CORA_CLIENT_ID')}).get('access_token')
 if not token:raise a.Error(503,'Cora não retornou token.')
 r=cora(a,'/v2/invoices/'+ref,token)
 url=(r.get('payment_options') or {}).get('bank_slip',{}).get('url','')
 try:
  p=urlsplit(url)
  if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in [None,443] or any(x in url for x in ['\r','\n']):raise ValueError()
 except Exception:raise a.Error(503,'PDF ainda não disponível na resposta do banco.')
 a.audit(c,u,'bank_pdf',row['id']);return {'url':url}
