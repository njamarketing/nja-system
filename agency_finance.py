"""Management ledger and operational reporting; never initiates bank payments."""
from datetime import datetime,date,timezone
from decimal import Decimal,ROUND_HALF_UP
import agency_access as scope,agency_production as production,business

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS agency_ledger(id TEXT PRIMARY KEY,client_id TEXT REFERENCES clients(id),project_id TEXT REFERENCES agency_projects(id),branch TEXT NOT NULL,kind TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,amount INTEGER NOT NULL,competence TEXT NOT NULL,cash_date TEXT,reference TEXT NOT NULL,void INTEGER NOT NULL DEFAULT 0,creator TEXT NOT NULL REFERENCES users(id),created TEXT NOT NULL,UNIQUE(branch,reference));
 CREATE TABLE IF NOT EXISTS agency_hour_rates(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),effective TEXT NOT NULL,rate INTEGER NOT NULL,created TEXT NOT NULL,UNIQUE(user_id,effective));
 CREATE TABLE IF NOT EXISTS agency_capacity(user_id TEXT NOT NULL REFERENCES users(id),month TEXT NOT NULL,minutes INTEGER NOT NULL,PRIMARY KEY(user_id,month));''')

def ledger_allowed(c,u,r):return scope.allowed(c,u,r['client_id']) if r['client_id'] else scope.branch_allowed(u,r['branch'])
def filters(a,c,u,q):
 month=production.month(a,q.get('month',[datetime.now(a.TZ).strftime('%Y-%m')])[0]);cid=q.get('client',[''])[0];branch=q.get('branch',[''])[0]
 if cid:scope.need(a,c,u,cid)
 if branch and (branch not in scope.BRANCHES or not scope.branch_allowed(u,branch)):raise a.Error(403,'Unidade não autorizada.')
 return month,cid,branch

def report(a,c,u,q):
 month,cid,branch=filters(a,c,u,q)
 clients=[dict(r) for r in c.execute('SELECT id,name,branch FROM clients') if scope.allowed(c,u,r['id']) and (not cid or r['id']==cid) and (not branch or r['branch']==branch)];ids={x['id'] for x in clients}
 projects=[dict(r) for r in c.execute('SELECT * FROM agency_projects WHERE month=?',(month,)) if r['client_id'] in ids]
 tasks=[dict(r) for r in c.execute('SELECT t.*,d.project_id,d.estimated_minutes,d.extra FROM deliverables d JOIN tasks t ON t.id=d.task_id JOIN agency_projects p ON p.id=d.project_id WHERE p.month=?',(month,)) if r['client_id'] in ids]
 entries=[dict(r) for r in c.execute('SELECT e.*,t.client_id FROM time_entries e JOIN tasks t ON t.id=e.task_id') if r['client_id'] in ids and datetime.fromisoformat(r['created']).astimezone(a.TZ).strftime('%Y-%m')==month]
 result={'month':month,'clients':clients,'production':{'projects':len(projects),'deliverables':len(tasks),'done':sum(t['status']=='done' for t in tasks),'late':sum(t['status']!='done' and bool(t['due']) and t['due']<a.now() for t in tasks),'extra':sum(t['extra'] for t in tasks),'estimated_minutes':sum(t['estimated_minutes'] for t in tasks),'logged_seconds':sum(e['seconds'] for e in entries)},'capacity':[],'financial':None}
 for r in c.execute('SELECT cap.*,u.name,u.branch FROM agency_capacity cap JOIN users u ON u.id=cap.user_id WHERE month=?',(month,)):
  if not scope.branch_allowed(u,r['branch']) or (branch and r['branch']!=branch):continue
  assigned=sum(t['estimated_minutes'] for t in tasks if t['owner']==r['user_id']);logged=sum(e['seconds'] for e in entries if e['user_id']==r['user_id']);result['capacity'].append(dict(r)|{'assigned_minutes':assigned,'logged_seconds':logged})
 if not a.perm(u,'agency_finance'):return result
 ledger=[dict(r) for r in c.execute('SELECT * FROM agency_ledger WHERE void=0') if ledger_allowed(c,u,r) and (not cid or r['client_id']==cid) and (not branch or r['branch']==branch)]
 monthledger=[r for r in ledger if r['competence']==month];buckets={x['id']:{'id':x['id'],'name':x['name'],'revenue':0,'expenses':0,'labor':0,'unpriced_seconds':0,'logged_seconds':0} for x in clients}
 overhead=0
 for r in monthledger:
  if r['client_id'] in buckets:buckets[r['client_id']]['revenue' if r['kind']=='revenue' else 'expenses']+=r['amount']
  elif not r['client_id'] and r['kind']=='expense':overhead+=r['amount']
 for e in entries:
  bucket=buckets[e['client_id']];bucket['logged_seconds']+=e['seconds'];rate=c.execute('SELECT rate FROM agency_hour_rates WHERE user_id=? AND effective<=? ORDER BY effective DESC LIMIT 1',(e['user_id'],e['created'][:10])).fetchone()
  if not rate:bucket['unpriced_seconds']+=e['seconds'];continue
  bucket['labor']+=int((Decimal(rate[0])*Decimal(e['seconds'])/3600).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
 for x in buckets.values():
  x['margin']=x['revenue']-x['expenses']-x['labor'];x['margin_percent']=round(x['margin']/x['revenue']*100,2) if x['revenue'] else None
 result['financial']={'clients':list(buckets.values()),'revenue':sum(r['amount'] for r in monthledger if r['kind']=='revenue'),'expenses':sum(r['amount'] for r in monthledger if r['kind']=='expense'),'labor':sum(x['labor'] for x in buckets.values()),'unallocated_expenses':overhead,'unpriced_seconds':sum(x['unpriced_seconds'] for x in buckets.values()),'cash_in':sum(r['amount'] for r in ledger if r['kind']=='revenue' and r['cash_date'] and r['cash_date'][:7]==month),'cash_out':sum(r['amount'] for r in ledger if r['kind']=='expense' and r['cash_date'] and r['cash_date'][:7]==month),'planned_fees':sum(p['monthly_fee'] for p in projects),'note':'Margem gerencial parcial: receitas menos despesas registradas e custo das horas apontadas. Custos de equipe já contabilizados no custo-hora não devem ser lançados novamente como despesa. Sem rateio automático. Não substitui apuração contábil.'}
 return result

def api(a,c,u,method,path,d,q):
 if path=='/api/agency/reports' and method=='GET':a.need(u,'agency_reports');return report(a,c,u,q)
 if not path.startswith('/api/agency/finance'):return None
 a.need(u,'agency_finance');parts=path.split('/')[4:]
 if not parts and method=='GET':
  return {'items':[dict(r) for r in c.execute('SELECT * FROM agency_ledger ORDER BY competence DESC,created DESC') if ledger_allowed(c,u,r)],'rates':[dict(r) for r in c.execute('SELECT h.*,u.name,u.branch FROM agency_hour_rates h JOIN users u ON u.id=h.user_id ORDER BY effective DESC') if scope.branch_allowed(u,r['branch'])],'capacity':[dict(r) for r in c.execute('SELECT cap.*,u.name,u.branch FROM agency_capacity cap JOIN users u ON u.id=cap.user_id') if scope.branch_allowed(u,r['branch'])],'projects':[dict(r) for r in c.execute('SELECT id,title,client_id FROM agency_projects') if scope.allowed(c,u,r['client_id'])]}
 a.need(u,'agency_finance_manage')
 if parts==['entries'] and method=='POST':
  cid=d.get('client_id') or None;project=d.get('project_id') or None;branch=d.get('branch');kind=d.get('kind');competence=production.month(a,d.get('competence'));cash=business.day(a,d.get('cash_date'),True)
  if cid:client=scope.need(a,c,u,cid);branch=client['branch']
  if branch not in scope.BRANCHES or (not cid and not scope.branch_allowed(u,branch)):raise a.Error(403,'Defina uma unidade autorizada para o lançamento.')
  if kind not in ['revenue','expense']:raise a.Error(400,'Natureza inválida.')
  if project:
   p=c.execute('SELECT * FROM agency_projects WHERE id=?',(project,)).fetchone()
   if not p or p['client_id']!=cid:raise a.Error(400,'Projeto de outro cliente.')
  amount=business.money(a,d.get('amount'))
  if amount<=0 or (cash and cash>datetime.now(a.TZ).date().isoformat()):raise a.Error(400,'Valor deve ser positivo e a data de caixa não pode ser futura.')
  id=a.uid();c.execute('INSERT INTO agency_ledger(id,client_id,project_id,branch,kind,category,description,amount,competence,cash_date,reference,creator,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(id,cid,project,branch,kind,a.textfield(d,'category',True,100),a.textfield(d,'description',True,500),amount,competence,cash,a.textfield(d,'reference',True,160),u['id'],a.now()));a.audit(c,u,'ledger_create',id);return {'id':id}
 if len(parts)==2 and parts[0]=='entries' and method=='PATCH':
  r=c.execute('SELECT * FROM agency_ledger WHERE id=?',(parts[1],)).fetchone()
  if not r:raise a.Error(404,'Lançamento não encontrado.')
  if not ledger_allowed(c,u,r):raise a.Error(403,'Lançamento fora da carteira.')
  if d.get('void') is not True:raise a.Error(400,'Para corrigir, anule e registre um novo lançamento.')
  reason=a.textfield(d,'reason',True,500);c.execute('UPDATE agency_ledger SET void=1 WHERE id=?',(r['id'],));a.audit(c,u,'ledger_void',r['id'],reason);return {'ok':True}
 if parts==['rates'] and method=='POST':
  person=business.person(a,c,d.get('user_id'))
  if not scope.branch_allowed(u,person['branch']):raise a.Error(403,'Pessoa de outra unidade.')
  id=a.uid();c.execute('INSERT INTO agency_hour_rates VALUES(?,?,?,?,?)',(id,person['id'],business.day(a,d.get('effective')),business.money(a,d.get('rate')),a.now()));a.audit(c,u,'hour_rate',id);return {'id':id}
 if parts==['capacity'] and method=='POST':
  person=business.person(a,c,d.get('user_id'))
  if not scope.branch_allowed(u,person['branch']):raise a.Error(403,'Pessoa de outra unidade.')
  month=production.month(a,d.get('month'));minutes=production.integer(a,d.get('minutes'),0,44640,'minutos disponíveis')
  c.execute('INSERT INTO agency_capacity VALUES(?,?,?) ON CONFLICT(user_id,month) DO UPDATE SET minutes=excluded.minutes',(person['id'],month,minutes));a.audit(c,u,'capacity',person['id'],month);return {'ok':True}
 raise a.Error(404,'Ação financeira não encontrada.')
