"""Versioned proposals, explicit follow-ups and configurable sales incentives."""
import json
from datetime import datetime,date,timezone
from decimal import Decimal,ROUND_HALF_UP
import agency_access as scope,agency_production as production,business

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY,lead_id TEXT NOT NULL REFERENCES leads(id),owner TEXT NOT NULL REFERENCES users(id),title TEXT NOT NULL,current_version TEXT,status TEXT NOT NULL DEFAULT 'draft',created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS proposal_versions(id TEXT PRIMARY KEY,proposal_id TEXT NOT NULL REFERENCES proposals(id),number INTEGER NOT NULL,items TEXT NOT NULL,terms TEXT NOT NULL,valid_until TEXT NOT NULL,total INTEGER NOT NULL,created TEXT NOT NULL,UNIQUE(proposal_id,number));
 CREATE TABLE IF NOT EXISTS proposal_decisions(id TEXT PRIMARY KEY,proposal_id TEXT NOT NULL REFERENCES proposals(id),version_id TEXT NOT NULL REFERENCES proposal_versions(id),status TEXT NOT NULL,evidence TEXT NOT NULL,actor TEXT NOT NULL REFERENCES users(id),created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS lead_followups(id TEXT PRIMARY KEY,lead_id TEXT NOT NULL REFERENCES leads(id),owner TEXT NOT NULL REFERENCES users(id),due TEXT NOT NULL,note TEXT NOT NULL,done INTEGER NOT NULL DEFAULT 0,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS sales_goals(id TEXT PRIMARY KEY,month TEXT NOT NULL,branch TEXT NOT NULL,seller TEXT REFERENCES users(id),metric TEXT NOT NULL,target INTEGER NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS commission_rules(id TEXT PRIMARY KEY,name TEXT NOT NULL,branch TEXT NOT NULL,basis TEXT NOT NULL,rate INTEGER NOT NULL,start TEXT NOT NULL,end TEXT,active INTEGER NOT NULL DEFAULT 1,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS sale_commissions(id TEXT PRIMARY KEY,sale_id TEXT NOT NULL UNIQUE REFERENCES sales(id),rule_id TEXT NOT NULL REFERENCES commission_rules(id),rule_name TEXT NOT NULL,basis TEXT NOT NULL,rate INTEGER NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS commission_receipts(id TEXT PRIMARY KEY,commission_id TEXT NOT NULL REFERENCES sale_commissions(id),reference TEXT NOT NULL,amount INTEGER NOT NULL,received_on TEXT NOT NULL,creator TEXT NOT NULL REFERENCES users(id),UNIQUE(commission_id,reference));''')

def visible(a,c,u,lead):
 try:business.access(a,c,u,'leads',lead);return True
 except a.Error:return False

def proposal(a,c,u,id):
 r=c.execute('SELECT * FROM proposals WHERE id=?',(id,)).fetchone()
 if not r:raise a.Error(404,'Proposta não encontrada.')
 business.access(a,c,u,'leads',r['lead_id']);return r

def version(a,c,r,d):
 if r['status'] in ['accepted','rejected']:raise a.Error(409,'Proposta encerrada. Crie uma nova proposta para negociar outra condição.')
 values=d.get('items')
 if not isinstance(values,list) or not 1<=len(values)<=50:raise a.Error(400,'Cadastre de 1 a 50 itens.')
 items=[];total=0
 for x in values:
  if not isinstance(x,dict):raise a.Error(400,'Item inválido.')
  qty=production.integer(a,x.get('quantity'),1,1000,'quantidade');price=business.money(a,x.get('price'));total+=qty*price
  items.append({'description':a.textfield(x,'description',True,500),'quantity':qty,'price':price})
 if total>100000000000:raise a.Error(400,'Valor da proposta acima do limite.')
 until=business.day(a,d.get('valid_until'))
 if until<datetime.now(a.TZ).date().isoformat():raise a.Error(400,'A validade não pode estar no passado.')
 id=a.uid();n=c.execute('SELECT count(*)+1 FROM proposal_versions WHERE proposal_id=?',(r['id'],)).fetchone()[0]
 c.execute('INSERT INTO proposal_versions VALUES(?,?,?,?,?,?,?,?)',(id,r['id'],n,json.dumps(items),a.textfield(d,'terms',False,10000),until,total,a.now()));c.execute("UPDATE proposals SET current_version=?,status='draft' WHERE id=?",(id,r['id']));return {'id':id,'number':n}

def commissions(a,c,u):
 result=[]
 for r in c.execute('SELECT sc.*,s.seller,s.branch,s.amount AS sale_amount,s.status AS sale_status,s.sold_on,s.lead_id,l.name AS lead_name FROM sale_commissions sc JOIN sales s ON s.id=sc.sale_id JOIN leads l ON l.id=s.lead_id'):
  if not visible(a,c,u,r['lead_id']) or (r['seller']!=u['id'] and not a.perm(u,'commercial_manage')):continue
  amount=r['sale_amount'] if r['basis']=='sale' else min(r['sale_amount'],c.execute('SELECT COALESCE(sum(amount),0) FROM commission_receipts WHERE commission_id=?',(r['id'],)).fetchone()[0])
  computed=int((Decimal(amount)*Decimal(r['rate'])/10000).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if r['sale_status']=='confirmed' else 0
  result.append(dict(r)|{'base_amount':amount,'commission':computed,'receipts':[dict(x) for x in c.execute('SELECT id,reference,amount,received_on FROM commission_receipts WHERE commission_id=?',(r['id'],))]})
 return result

def api(a,c,u,method,path,d,q):
 if not path.startswith('/api/agency/commercial'):return None
 a.need(u,'commercial_ops');a.need(u,'crm');parts=path.split('/')[4:]
 if not parts and method=='GET':
  proposals=[]
  for r in c.execute('SELECT * FROM proposals ORDER BY created DESC'):
   if visible(a,c,u,r['lead_id']):proposals.append(dict(r)|{'versions':[dict(v)|{'items':json.loads(v['items'])} for v in c.execute('SELECT * FROM proposal_versions WHERE proposal_id=? ORDER BY number DESC',(r['id'],))],'decisions':[dict(v) for v in c.execute('SELECT * FROM proposal_decisions WHERE proposal_id=? ORDER BY created',(r['id'],))]})
  goals=[]
  for r in c.execute('SELECT * FROM sales_goals ORDER BY month DESC'):
   if not scope.branch_allowed(u,r['branch']) or (r['seller'] and r['seller']!=u['id'] and not a.perm(u,'commercial_manage')):continue
   rows=[x for x in c.execute("SELECT s.* FROM sales s WHERE status='confirmed' AND branch=? AND substr(sold_on,1,7)=? AND (? IS NULL OR seller=?)",(r['branch'],r['month'],r['seller'],r['seller'])) if visible(a,c,u,x['lead_id'])]
   actual=sum(x['amount'] for x in rows) if r['metric']=='revenue' else len(rows)
   goals.append(dict(r)|{'actual':actual})
  return {'proposals':proposals,'leads':[dict(r) for r in c.execute('SELECT id,name,owner,client_id FROM leads') if visible(a,c,u,r['id'])],'followups':[dict(r) for r in c.execute('SELECT * FROM lead_followups ORDER BY due') if visible(a,c,u,r['lead_id'])],'goals':goals,'rules':[dict(r) for r in c.execute('SELECT * FROM commission_rules ORDER BY start DESC') if scope.branch_allowed(u,r['branch'])],'commissions':commissions(a,c,u),'sales':[dict(r) for r in c.execute("SELECT s.*,l.name FROM sales s JOIN leads l ON l.id=s.lead_id WHERE s.status='confirmed'") if visible(a,c,u,r['lead_id'])]}
 if not parts:raise a.Error(404,'Ação inválida.')
 kind=parts[0];id=parts[1] if len(parts)>1 else None;action=parts[2] if len(parts)>2 else None
 if kind=='proposals':
  a.need(u,'crm_edit')
  if not id and method=='POST':
   lead=business.access(a,c,u,'leads',d.get('lead_id'));id=a.uid();c.execute('INSERT INTO proposals(id,lead_id,owner,title,created) VALUES(?,?,?,?,?)',(id,lead['id'],lead['owner'] or u['id'],a.textfield(d,'title',True,180),a.now()));r=proposal(a,c,u,id);version(a,c,r,d);a.audit(c,u,'proposal_create',id);return {'id':id}
  r=proposal(a,c,u,id)
  if action=='versions' and method=='POST':
   if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
   out=version(a,c,proposal(a,c,u,id),d);a.audit(c,u,'proposal_version',id);return out
  if action=='decision' and method=='POST':
   if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
   r=proposal(a,c,u,id);status=d.get('status');allowed={'draft':['sent'],'sent':['accepted','rejected','expired']}
   if status not in allowed.get(r['status'],[]):raise a.Error(409,'Transição inválida para esta proposta.')
   if d.get('version_id')!=r['current_version']:raise a.Error(409,'A proposta mudou. Confira a versão atual.')
   v=c.execute('SELECT * FROM proposal_versions WHERE id=?',(r['current_version'],)).fetchone()
   if status in ['sent','accepted'] and v['valid_until']<datetime.now(a.TZ).date().isoformat():raise a.Error(409,'A proposta venceu. Revise a validade em uma nova versão.')
   evidence=a.textfield(d,'evidence',status in ['accepted','rejected'],4000)
   c.execute('INSERT INTO proposal_decisions VALUES(?,?,?,?,?,?,?)',(a.uid(),id,r['current_version'],status,evidence,u['id'],a.now()));c.execute('UPDATE proposals SET status=? WHERE id=?',(status,id));business.activity(a,c,u,r['lead_id'],'proposal','Proposta '+r['title']+': '+status);a.audit(c,u,'proposal_decision',id,status);return {'ok':True}
 if kind=='followups':
  a.need(u,'crm_edit')
  if not id and method=='POST':
   lead=business.access(a,c,u,'leads',d.get('lead_id'));owner=lead['owner'] or u['id'];due=a.datefield(d.get('due'))
   if not due:raise a.Error(400,'Informe data e horário do próximo contato.')
   id=a.uid();c.execute('INSERT INTO lead_followups(id,lead_id,owner,due,note,created) VALUES(?,?,?,?,?,?)',(id,lead['id'],owner,due,a.textfield(d,'note',True,2000),a.now()));a.audit(c,u,'followup_create',id);return {'id':id}
  if id and method=='PATCH':
   r=c.execute('SELECT * FROM lead_followups WHERE id=?',(id,)).fetchone()
   if not r:raise a.Error(404,'Próximo contato não encontrado.')
   business.access(a,c,u,'leads',r['lead_id'])
   if not isinstance(d.get('done'),bool):raise a.Error(400,'Estado inválido.')
   c.execute('UPDATE lead_followups SET done=? WHERE id=?',(int(d['done']),id));a.audit(c,u,'followup_update',id);return {'ok':True}
 a.need(u,'commercial_manage')
 if kind=='goals' and method=='POST':
  period=production.month(a,d.get('month'));branch=d.get('branch');seller=d.get('seller') or None;metric=d.get('metric')
  if branch not in scope.BRANCHES or not scope.branch_allowed(u,branch):raise a.Error(403,'Unidade não autorizada.')
  if seller:
   person=business.person(a,c,seller,True)
   if person['branch']!=branch:raise a.Error(400,'Vendedor de outra unidade.')
  if metric not in ['revenue','deals']:raise a.Error(400,'Indicador inválido.')
  target=business.money(a,d.get('target')) if metric=='revenue' else production.integer(a,d.get('target'),1,100000,'meta')
  if target<=0:raise a.Error(400,'A meta deve ser positiva.')
  existing=c.execute('SELECT id FROM sales_goals WHERE month=? AND branch=? AND seller IS ? AND metric=?',(period,branch,seller,metric)).fetchone()
  if existing:id=existing[0];c.execute('UPDATE sales_goals SET target=? WHERE id=?',(target,id))
  else:id=a.uid();c.execute('INSERT INTO sales_goals VALUES(?,?,?,?,?,?,?)',(id,period,branch,seller,metric,target,a.now()))
  a.audit(c,u,'sales_goal',id);return {'id':id}
 if kind=='rules' and method=='POST':
  branch=d.get('branch');basis=d.get('basis');rate=business.money(a,d.get('rate'));start=business.day(a,d.get('start'));end=business.day(a,d.get('end'),True)
  if branch not in scope.BRANCHES or not scope.branch_allowed(u,branch):raise a.Error(403,'Unidade não autorizada.')
  if basis not in ['sale','received'] or rate>10000 or (end and end<start):raise a.Error(400,'Confira base, percentual e vigência.')
  id=a.uid();c.execute('INSERT INTO commission_rules(id,name,branch,basis,rate,start,end,created) VALUES(?,?,?,?,?,?,?,?)',(id,a.textfield(d,'name',True,120),branch,basis,rate,start,end,a.now()));a.audit(c,u,'commission_rule',id);return {'id':id}
 if kind=='commissions' and not id and method=='POST':
  s=c.execute('SELECT * FROM sales WHERE id=?',(d.get('sale_id'),)).fetchone();rule=c.execute('SELECT * FROM commission_rules WHERE id=?',(d.get('rule_id'),)).fetchone()
  if not s or not rule:raise a.Error(404,'Venda ou regra não encontrada.')
  business.access(a,c,u,'leads',s['lead_id'])
  if not scope.branch_allowed(u,s['branch']) or rule['branch']!=s['branch']:raise a.Error(403,'Regra de outra unidade.')
  if not rule['active'] or s['status']!='confirmed' or s['sold_on']<rule['start'] or (rule['end'] and s['sold_on']>rule['end']):raise a.Error(409,'Regra fora da vigência ou venda não confirmada.')
  id=a.uid();c.execute('INSERT INTO sale_commissions VALUES(?,?,?,?,?,?,?)',(id,s['id'],rule['id'],rule['name'],rule['basis'],rule['rate'],a.now()));a.audit(c,u,'commission_assign',id);return {'id':id}
 if kind=='commissions' and action=='receipts' and method=='POST':
  a.need(u,'agency_finance_manage');a.need(u,'agency_finance')
  if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
  r=next((r for r in commissions(a,c,u) if r['id']==id),None)
  if not r or r['basis']!='received':raise a.Error(404,'Comissão por recebimento não encontrada.')
  amount=business.money(a,d.get('amount'));day=business.day(a,d.get('received_on'));total=sum(x['amount'] for x in r['receipts'])
  if amount<=0 or total+amount>r['sale_amount'] or day>datetime.now(a.TZ).date().isoformat():raise a.Error(400,'Recebimento inválido ou acima do valor da venda.')
  ref=a.textfield(d,'reference',True,160);c.execute('INSERT INTO commission_receipts VALUES(?,?,?,?,?,?)',(a.uid(),id,ref,amount,day,u['id']));a.audit(c,u,'commission_receipt',id);return {'ok':True}
 raise a.Error(404,'Ação comercial não encontrada.')

def tick(a,c):
 for r in c.execute('SELECT * FROM lead_followups WHERE done=0 AND due<=?',(a.now(),)).fetchall():
  lead=c.execute('SELECT * FROM leads WHERE id=?',(r['lead_id'],)).fetchone();owner=lead['owner'] or r['owner'];raw=c.execute('SELECT * FROM users WHERE id=? AND active=1',(owner,)).fetchone()
  if not raw:continue
  u=a.user_public(c,raw)
  if not a.perm(u,'commercial_ops') or not visible(a,c,u,r['lead_id']):continue
  if c.execute('INSERT OR IGNORE INTO reminder_log VALUES(?,?)',('followup:'+r['id']+':'+owner,a.now())).rowcount:a.notify(c,owner,'Próximo contato comercial',lead['name']+' · '+r['note'][:150],'commercial_ops:'+r['lead_id'],'tasks')
