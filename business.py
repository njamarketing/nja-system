"""Business modules: scoped CRM, read-only receivables, contracts and marketing."""
import base64,json,re,os
import agency_access
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation

PERMISSIONS=['crm','crm_edit','crm_reply','crm_assign','crm_all','crm_convert','finance','finance_manage','finance_download','bank_itau','bank_cora','bank_infinitepay','contracts','contract_manage','contract_all','contract_download','marketing','marketing_manage','integrations_manage']
BANKS={'itau':'Itaú','cora':'Cora','infinitepay':'InfinitePay'}
STAGES=['new','contact','qualified','proposal','negotiation','won','lost']

def init(c):
 c.executescript('''
 CREATE TABLE IF NOT EXISTS leads(id TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL DEFAULT '',email TEXT NOT NULL DEFAULT '',company TEXT NOT NULL DEFAULT '',city TEXT NOT NULL DEFAULT '',industry TEXT NOT NULL DEFAULT '',product TEXT NOT NULL DEFAULT '',budget INTEGER NOT NULL DEFAULT 0,owner TEXT REFERENCES users(id),stage TEXT NOT NULL DEFAULT 'new',source TEXT NOT NULL DEFAULT 'manual',source_id TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',client_id TEXT REFERENCES clients(id),created TEXT NOT NULL,updated TEXT NOT NULL);
 CREATE UNIQUE INDEX IF NOT EXISTS lead_phone_unique ON leads(phone) WHERE phone<>'';
 CREATE TABLE IF NOT EXISTS lead_activity(id TEXT PRIMARY KEY,lead_id TEXT NOT NULL REFERENCES leads(id),user_id TEXT REFERENCES users(id),kind TEXT NOT NULL,text TEXT NOT NULL,event_id TEXT REFERENCES events(id) ON DELETE SET NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS lead_messages(id TEXT PRIMARY KEY,lead_id TEXT NOT NULL REFERENCES leads(id),user_id TEXT REFERENCES users(id),direction TEXT NOT NULL,text TEXT NOT NULL,external_id TEXT UNIQUE,status TEXT NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS invoices(id TEXT PRIMARY KEY,bank TEXT NOT NULL,reference TEXT NOT NULL,customer TEXT NOT NULL,client_id TEXT REFERENCES clients(id),description TEXT NOT NULL DEFAULT '',amount INTEGER NOT NULL,due TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',source TEXT NOT NULL DEFAULT 'manual',updated TEXT NOT NULL,UNIQUE(bank,reference));
 CREATE TABLE IF NOT EXISTS contracts(id TEXT PRIMARY KEY,title TEXT NOT NULL,client_id TEXT REFERENCES clients(id),owner TEXT NOT NULL REFERENCES users(id),start TEXT NOT NULL,expires TEXT NOT NULL,renewal TEXT,amount INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'active',notes TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 1,created TEXT NOT NULL,updated TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS business_documents(id TEXT PRIMARY KEY,scope TEXT NOT NULL,entity_id TEXT NOT NULL,name TEXT NOT NULL,payload BLOB NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS marketing_posts(id TEXT PRIMARY KEY,platform TEXT NOT NULL,text TEXT NOT NULL,image_url TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'draft',external_id TEXT NOT NULL DEFAULT '',container_id TEXT NOT NULL DEFAULT '',creator TEXT NOT NULL REFERENCES users(id),created TEXT NOT NULL,updated TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS connector_runs(provider TEXT PRIMARY KEY,updated TEXT NOT NULL,detail TEXT NOT NULL);
 ''')
 # Sales is opt-in; no existing user gains new business permissions on migration.
 c.execute('INSERT OR IGNORE INTO roles VALUES(?,?,?)',('sales','Comercial',json.dumps(['dashboard','tasks','calendar','chats','team','notifications','task_create','task_edit','task_complete','clients','client_manage','crm','crm_edit','crm_reply','crm_convert'])))

def money(a,value):
 try:
  d=Decimal(str(value));c=d*100
  if not d.is_finite() or d<0 or d>Decimal('1000000000') or c!=c.to_integral_value():raise ValueError()
  return int(c)
 except (ValueError,InvalidOperation,TypeError):raise a.Error(400,'Informe um valor válido, com até duas casas decimais.')

def day(a,s,optional=False):
 if optional and not s:return None
 try:return date.fromisoformat(s).isoformat()
 except (ValueError,TypeError):raise a.Error(400,'Informe uma data válida.')

def person(a,c,id,commercial=False):
 r=c.execute('SELECT * FROM users WHERE id=? AND active=1',(id,)).fetchone()
 if not r:raise a.Error(400,'Selecione um responsável ativo.')
 u=a.user_public(c,r)
 if commercial and not (a.perm(u,'crm') and a.perm(u,'crm_reply')):raise a.Error(400,'O responsável precisa de acesso comercial ao CRM e permissão de resposta.')
 return u

def access(a,c,u,kind,id):
 perm={'leads':'crm','invoices':'finance','contracts':'contracts'}[kind];a.need(u,perm)
 r=c.execute('SELECT * FROM '+kind+' WHERE id=?',(id,)).fetchone()
 if not r:raise a.Error(404,'Registro não encontrado.')
 if r['client_id']:agency_access.need(a,c,u,r['client_id'])
 if kind=='invoices':a.need(u,'bank_'+r['bank'])
 elif not a.perm(u,'crm_all' if kind=='leads' else 'contract_all') and r['owner']!=u['id']:raise a.Error(403,'Registro fora da sua carteira.')
 return dict(r)

def activity(a,c,u,id,kind,text,event=None):
 c.execute('INSERT INTO lead_activity VALUES(?,?,?,?,?,?,?)',(a.uid(),id,u['id'] if u else None,kind,text,event,a.now()))

def lead_fields(a,c,u,d,current=None):
 old=current or {};out={k:a.textfield(d,k,k=='name',500 if k=='notes' else 160) if k in d or not current else old[k] for k in ['name','email','company','city','industry','product','notes']}
 phone=d.get('phone',old.get('phone',''))
 if not isinstance(phone,str):raise a.Error(400,'Telefone inválido.')
 phone=re.sub(r'[\s()+.-]','',phone)
 if phone and not re.fullmatch(r'[1-9][0-9]{9,14}',phone):raise a.Error(400,'Use telefone com DDI e DDD, por exemplo 5545999999999.')
 out['phone']=phone;out['budget']=money(a,d['budget']) if 'budget' in d else old.get('budget',0)
 out['stage']=d.get('stage',old.get('stage','new'))
 if out['stage'] not in STAGES:raise a.Error(400,'Etapa inválida.')
 out['owner']=d.get('owner',old.get('owner',u['id'])) or None
 if out['owner']!=old.get('owner',u['id']):a.need(u,'crm_assign')
 if out['owner']:person(a,c,out['owner'],True)
 return out

def update(c,table,id,fields):
 c.execute('UPDATE '+table+' SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',list(fields.values())+[id])

def client(a,c,u,id):
 if not id:return None
 a.need(u,'clients');agency_access.need(a,c,u,id)
 if not c.execute('SELECT 1 FROM clients WHERE id=?',(id,)).fetchone():raise a.Error(400,'Cliente inválido.')
 return id

def docmeta(c,scope,id):return [dict(r) for r in c.execute('SELECT id,name,created FROM business_documents WHERE scope=? AND entity_id=? ORDER BY created DESC',(scope,id))]

def api(a,c,u,method,path,d,q):
 if not path.startswith('/api/business/'):return None
 parts=path.split('/')[3:];resource=parts[0];id=parts[1] if len(parts)>1 else None;action=parts[2] if len(parts)>2 else None
 if resource=='connectors':
  a.need(u,'integrations_manage')
  import business_connectors as bc
  if method=='GET':return bc.status(a,c)
  if method=='POST' and id=='whatsapp':
   owner=d.get('owner');person(a,c,owner,True)
   c.execute('INSERT OR REPLACE INTO company_settings VALUES(?,?)',('whatsapp_owner',owner));a.audit(c,u,'whatsapp_owner','config');return {'ok':True}
 if resource=='documents' and id:
  r=c.execute('SELECT * FROM business_documents WHERE id=?',(id,)).fetchone()
  if not r:raise a.Error(404,'Documento não encontrado.')
  access(a,c,u,r['scope'],r['entity_id']);a.need(u,'finance_download' if r['scope']=='invoices' else 'contract_download')
  if method=='GET':
   a.audit(c,u,'document_download',id);return {'name':r['name'],'data':base64.b64encode(r['payload']).decode(),'mime':'application/pdf'}
 if resource in ['leads','invoices','contracts']:
  a.need(u,{'leads':'crm','invoices':'finance','contracts':'contracts'}[resource])
  if resource=='leads' and action=='convert' and method=='POST':c.execute('BEGIN IMMEDIATE')
  row=access(a,c,u,resource,id) if id else None
  if action=='documents':
   if resource=='leads':raise a.Error(404,'Recurso inválido.')
   if method=='POST':
    a.need(u,'finance_manage' if resource=='invoices' else 'contract_manage')
    try:raw=base64.b64decode(d.get('data',''),validate=True)
    except Exception:raise a.Error(400,'Arquivo inválido.')
    if len(raw)>8*1024*1024:raise a.Error(413,'PDF deve ter até 8 MB.')
    if not raw.startswith(b'%PDF-'):raise a.Error(400,'Envie um documento PDF.')
    name=a.textfield(d,'name',True,180)
    if not name.lower().endswith('.pdf'):raise a.Error(400,'Use extensão PDF.')
    fid=a.uid();c.execute('INSERT INTO business_documents VALUES(?,?,?,?,?,?)',(fid,resource,id,name,raw,a.now()));a.audit(c,u,'document_upload',id);return {'id':fid}
  if resource=='leads':
   if not id and method=='GET':
    rows=[dict(r) for r in c.execute('SELECT * FROM leads ORDER BY updated DESC') if (a.perm(u,'crm_all') or r['owner']==u['id']) and agency_access.allowed(c,u,r['client_id'])]
    return {'items':rows,'salespeople':[{'id':r['id'],'name':r['name']} for r in c.execute('SELECT * FROM users WHERE active=1') if a.perm(a.user_public(c,r),'crm') and a.perm(a.user_public(c,r),'crm_reply')]}
   if not id and method=='POST':
    a.need(u,'crm_edit');fields=lead_fields(a,c,u,d);id=a.uid();fields.update(id=id,source='manual',created=a.now(),updated=a.now())
    c.execute('INSERT INTO leads('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',list(fields.values()));activity(a,c,u,id,'created','Lead cadastrado manualmente.');a.audit(c,u,'lead_create',id);return {'id':id}
   if id and not action and method=='GET':return {'lead':row,'activity':[dict(r) for r in c.execute('SELECT * FROM lead_activity WHERE lead_id=? ORDER BY created DESC',(id,))],'messages':[dict(r) for r in c.execute('SELECT * FROM (SELECT * FROM lead_messages WHERE lead_id=? ORDER BY created DESC LIMIT 200) ORDER BY created',(id,))]}
   if id and not action and method=='PATCH':
    a.need(u,'crm_edit');fields=lead_fields(a,c,u,d,row);fields['updated']=a.now();update(c,'leads',id,fields);activity(a,c,u,id,'updated','Cadastro comercial atualizado.');a.audit(c,u,'lead_update',id);return {'ok':True}
   if action=='notes' and method=='POST':
    a.need(u,'crm_edit');activity(a,c,u,id,'note',a.textfield(d,'text',True,4000));a.notify_mentions(c,u,d,a.textfield(d,'text',True,4000),'crm:'+id,'messages');a.audit(c,u,'lead_note',id);return {'ok':True}
   if action=='convert' and method=='POST':
    a.need(u,'crm_convert');a.need(u,'clients');a.need(u,'client_manage')
    if row['client_id']:return {'id':row['client_id'],'existing':True}
    target=d.get('client_id')
    if target:target=client(a,c,u,target)
    else:
     name=row['company'] or row['name']
     if c.execute('SELECT 1 FROM clients WHERE lower(trim(name))=lower(trim(?))',(name,)).fetchone():raise a.Error(409,'Já existe cliente com esse nome. Selecione o cadastro existente para vincular.')
     if not row['product']:raise a.Error(400,'Preencha o produto antes de converter.')
     target=a.uid();description='\n'.join([f'{k}: {row[k]}' for k in ['name','phone','email','city','industry','notes']])+f'\nOrçamento: R$ {row["budget"]/100:.2f}\nLead: {id}'
     c.execute('INSERT INTO clients(id,name,entered,product,description,created) VALUES(?,?,?,?,?,?)',(target,name,datetime.now(a.TZ).date().isoformat(),row['product'],description,a.now()))
    agency_access.created(c,u,target)
    c.execute("UPDATE leads SET client_id=?,stage='won',updated=? WHERE id=?",(target,a.now(),id));activity(a,c,u,id,'converted','Convertido/vinculado ao cadastro de cliente.');a.audit(c,u,'lead_convert',id);return {'id':target}
   if action=='events' and method=='POST':
    a.need(u,'crm_edit');a.need(u,'calendar');start=a.datefield(d.get('start'));end=a.datefield(d.get('end'))
    if not start or not end or end<=start:raise a.Error(400,'Término deve ser após início.')
    eid=a.uid();location=a.textfield(d,'location',False,500);title=a.textfield(d,'title',True,160)
    c.execute('INSERT INTO events(id,title,description,creator,start,end,location,created) VALUES(?,?,?,?,?,?,?,?)',(eid,title,'CRM: '+row['name']+' · '+id,u['id'],start,end,location,a.now()))
    for who in {u['id'],row['owner']} - {None}:c.execute('INSERT INTO event_members VALUES(?,?)',(eid,who))
    activity(a,c,u,id,'meeting',title,eid);a.audit(c,u,'lead_meeting',id);return {'id':eid}
   if action=='messages' and method=='POST':
    a.need(u,'crm_reply')
    if row['owner']!=u['id']:raise a.Error(403,'Somente o responsável comercial pode responder. Reatribua o lead antes de enviar.')
    import business_connectors as bc
    return bc.send_whatsapp(a,c,u,row,d)
  if resource=='invoices':
   if action=='bank-pdf' and method=='GET':
    a.need(u,'finance_download')
    if row['source']!='cora_api':raise a.Error(409,'Use o PDF anexado ao cadastro manual.')
    import business_connectors as bc
    return bc.cora_pdf(a,c,u,row)
   if not id and method=='GET':
    rows=[dict(r) for r in c.execute('SELECT * FROM invoices ORDER BY due') if a.perm(u,'bank_'+r['bank']) and agency_access.allowed(c,u,r['client_id'])]
    for r in rows:r['documents']=docmeta(c,resource,r['id'])
    return {'items':rows,'banks':{k:v for k,v in BANKS.items() if a.perm(u,'bank_'+k)}}
   if method in ['POST','PATCH'] and not action:
    a.need(u,'finance_manage');old=row or {};bank=d.get('bank',old.get('bank'))
    if bank not in BANKS:raise a.Error(400,'Banco inválido.')
    a.need(u,'bank_'+bank)
    if old.get('source')=='cora_api':raise a.Error(409,'Dados bancários sincronizados são atualizados somente pela consulta ao banco.')
    fields={k:a.textfield(d,k,k in ['reference','customer'],500) for k in ['reference','customer','description']};fields.update(bank=bank,client_id=client(a,c,u,d.get('client_id')),amount=money(a,d.get('amount')),due=day(a,d.get('due')),status=d.get('status','open'),updated=a.now())
    if fields['status'] not in ['open','paid','cancelled']:raise a.Error(400,'Status inválido.')
    if id:update(c,resource,id,fields)
    else:
     id=a.uid();fields['id']=id;c.execute('INSERT INTO invoices('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',list(fields.values()))
    a.audit(c,u,'invoice_record',id);return {'id':id}
  if resource=='contracts':
   if not id and method=='GET':
    rows=[dict(r) for r in c.execute('SELECT * FROM contracts ORDER BY expires') if (a.perm(u,'contract_all') or r['owner']==u['id']) and agency_access.allowed(c,u,r['client_id'])]
    for r in rows:r['documents']=docmeta(c,resource,r['id'])
    return {'items':rows}
   if method in ['POST','PATCH'] and not action:
    a.need(u,'contract_manage');old=row or {};owner=d.get('owner',old.get('owner',u['id']));person(a,c,owner)
    if owner!=u['id']:a.need(u,'contract_all')
    fields={k:a.textfield(d,k,k=='title',4000 if k=='notes' else 200) for k in ['title','notes']};fields.update(client_id=client(a,c,u,d.get('client_id')),owner=owner,start=day(a,d.get('start')),expires=day(a,d.get('expires')),renewal=day(a,d.get('renewal'),True),amount=money(a,d.get('amount',0)),status=d.get('status','active'),updated=a.now())
    if fields['expires']<fields['start']:raise a.Error(400,'Vencimento anterior ao início.')
    if fields['status'] not in ['active','closed','cancelled']:raise a.Error(400,'Status inválido.')
    if id:
     fields['revision']=old['revision']+1;update(c,resource,id,fields)
    else:
     id=a.uid();fields.update(id=id,created=a.now());c.execute('INSERT INTO contracts('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',list(fields.values()))
    a.audit(c,u,'contract_update',id);return {'id':id}
 if resource=='sync' and method=='POST':
  a.need(u,'integrations_manage');a.need(u,'finance');a.need(u,'finance_manage')
  if id not in BANKS:raise a.Error(404,'Banco inválido.')
  a.need(u,'bank_'+id)
  import business_connectors as bc
  return bc.sync_bank(a,c,u,id,d)
 if resource=='marketing':
  a.need(u,'marketing');a.need(u,'client_company_all')
  import business_connectors as bc
  return bc.marketing(a,c,u,method,parts[1:],d)
 raise a.Error(404,'Recurso não encontrado.')

def reminders(a,c,current=None):
 today=(current or datetime.now(a.TZ)).astimezone(a.TZ).date()
 for r in c.execute("SELECT * FROM contracts WHERE status='active'").fetchall():
  for field,label in [('expires','Vencimento'),('renewal','Renovação')]:
   if not r[field]:continue
   days=(date.fromisoformat(r[field])-today).days
   if days>30:continue
   stage=30 if days>15 else 15 if days>7 else 7 if days>1 else 1 if days>0 else 0
   for raw in c.execute('SELECT * FROM users WHERE active=1').fetchall():
    u=a.user_public(c,raw)
    if not agency_access.allowed(c,u,r['client_id']) or not a.perm(u,'contracts') or (u['id']!=r['owner'] and not a.perm(u,'contract_all')):continue
    key=f'contract:{r["id"]}:{field}:{r[field]}:{stage}:{u["id"]}'
    if c.execute('INSERT OR IGNORE INTO reminder_log VALUES(?,?)',(key,a.now())).rowcount:a.notify(c,u['id'],label+' de contrato',r['title']+' · '+r[field], 'contracts:'+r['id'],'contracts')
