"""Versioned service plans, idempotent monthly projects and dependencies."""
import json,calendar,re
from datetime import datetime,date
import agency_access as scope,business

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS service_plans(id TEXT PRIMARY KEY,client_id TEXT NOT NULL REFERENCES clients(id),name TEXT NOT NULL,owner TEXT NOT NULL REFERENCES users(id),items TEXT NOT NULL,start_month TEXT NOT NULL,end_month TEXT,monthly_fee INTEGER NOT NULL DEFAULT 0,auto INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,revision INTEGER NOT NULL DEFAULT 1,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS agency_projects(id TEXT PRIMARY KEY,plan_id TEXT REFERENCES service_plans(id),client_id TEXT NOT NULL REFERENCES clients(id),month TEXT NOT NULL,title TEXT NOT NULL,snapshot TEXT NOT NULL,monthly_fee INTEGER NOT NULL,owner TEXT NOT NULL REFERENCES users(id),created TEXT NOT NULL,UNIQUE(plan_id,month));
 CREATE TABLE IF NOT EXISTS deliverables(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES agency_projects(id),task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id),service TEXT NOT NULL,estimated_minutes INTEGER NOT NULL,extra INTEGER NOT NULL DEFAULT 0,revision_limit INTEGER,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS task_dependencies(task_id TEXT NOT NULL REFERENCES tasks(id),depends_on TEXT NOT NULL REFERENCES tasks(id),PRIMARY KEY(task_id,depends_on),CHECK(task_id<>depends_on));''')
def month(a,value):
 if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}',value):raise a.Error(400,'Competência inválida.')
 try:date.fromisoformat(value+'-01')
 except ValueError:raise a.Error(400,'Competência inválida.')
 return value

def integer(a,value,lo,hi,label):
 try:
  if isinstance(value,bool) or str(int(value))!=str(value):raise ValueError()
  n=int(value)
  if not lo<=n<=hi:raise ValueError()
  return n
 except (ValueError,TypeError):raise a.Error(400,'Valor inválido: '+label)
def member(a,c,u,cid,id):
 person=business.person(a,c,id)
 a.need(person,'tasks')
 if not scope.allowed(c,person,cid):raise a.Error(400,'O responsável precisa fazer parte da carteira deste cliente.')
 return id

def items(a,c,u,cid,raw):
 if not isinstance(raw,list) or not 1<=len(raw)<=30:raise a.Error(400,'Cadastre de 1 a 30 serviços no pacote.')
 result=[]
 for x in raw:
  if not isinstance(x,dict):raise a.Error(400,'Serviço inválido.')
  result.append({'name':a.textfield(x,'name',True,120),'quantity':integer(a,x.get('quantity'),1,100,'quantidade'),'owner':member(a,c,u,cid,x.get('owner')),'estimated_minutes':integer(a,x.get('estimated_minutes',0),0,100000,'minutos'),'due_day':integer(a,x.get('due_day',28),1,31,'dia do prazo'),'due_time':delivery_time(a,x.get('due_time','18:00')),'revision_limit':integer(a,x['revision_limit'],0,100,'limite de revisões') if x.get('revision_limit') not in [None,''] else None})
 if sum(x['quantity'] for x in result)>300:raise a.Error(400,'Cada pacote pode gerar até 300 entregas por mês.')
 return result

def generate(a,c,u,plan,period):
 period=month(a,period)
 if not plan['active'] or period<plan['start_month'] or (plan['end_month'] and period>plan['end_month']):raise a.Error(400,'Competência fora da vigência ativa do pacote.')
 existing=c.execute('SELECT id FROM agency_projects WHERE plan_id=? AND month=?',(plan['id'],period)).fetchone()
 if existing:return {'id':existing[0],'existing':True}
 scope.need(a,c,u,plan['client_id']);it=json.loads(plan['items'])
 for x in it:member(a,c,u,plan['client_id'],x['owner'])
 id=a.uid();c.execute('INSERT INTO agency_projects VALUES(?,?,?,?,?,?,?,?,?)',(id,plan['id'],plan['client_id'],period,plan['name']+' · '+period,plan['items'],plan['monthly_fee'],plan['owner'],a.now()))
 client=c.execute('SELECT name FROM clients WHERE id=?',(plan['client_id'],)).fetchone()[0]
 for item in it:
  for n in range(item['quantity']):
   tid=a.uid();due=date.fromisoformat(period+'-01');due=due.replace(day=min(item['due_day'],calendar.monthrange(due.year,due.month)[1]));hour,minute=map(int,item.get('due_time','18:00').split(':'));stamp=datetime(due.year,due.month,due.day,hour,minute,tzinfo=a.TZ).isoformat();title=item['name']+' · '+str(n+1)+'/'+str(item['quantity'])
   c.execute('INSERT INTO tasks(id,title,description,project,client_id,owner,creator,due,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',(tid,title,'Entrega do pacote '+plan['name'],client,plan['client_id'],item['owner'],u['id'],stamp,a.now(),a.now()))
   c.execute('INSERT INTO deliverables VALUES(?,?,?,?,?,?,?,?)',(a.uid(),id,tid,item['name'],item['estimated_minutes'],0,item['revision_limit'],a.now()))
 a.audit(c,u,'production_generate',id,period);return {'id':id,'existing':False}

def dependency_guard(a,c,tid):
 if c.execute("SELECT 1 FROM task_dependencies d JOIN tasks t ON t.id=d.depends_on WHERE d.task_id=? AND t.status<>'done'",(tid,)).fetchone():raise a.Error(409,'Conclua as tarefas predecessoras antes de finalizar esta entrega.')

def api(a,c,u,method,path,d,q):
 if path.startswith('/api/tasks/') and path.endswith('/dependencies'):
  tid=path.split('/')[3];a.get_task(c,u,tid)
  if method=='GET':return {'items':[dict(r) for r in c.execute('SELECT t.* FROM task_dependencies d JOIN tasks t ON t.id=d.depends_on WHERE d.task_id=?',(tid,)) if a.task_access(c,u,r)]}
  if method=='POST':
   a.need(u,'task_edit');ids=d.get('ids',[])
   if not isinstance(ids,list) or len(ids)>50:raise a.Error(400,'Dependências inválidas.')
   for parent in ids:
    a.get_task(c,u,parent)
    if parent==tid or c.execute('WITH RECURSIVE chain(id) AS (SELECT depends_on FROM task_dependencies WHERE task_id=? UNION SELECT d.depends_on FROM task_dependencies d JOIN chain ON d.task_id=chain.id) SELECT 1 FROM chain WHERE id=?',(parent,tid)).fetchone():raise a.Error(400,'Dependência circular não permitida.')
   c.execute('DELETE FROM task_dependencies WHERE task_id=?',(tid,))
   for parent in set(ids):c.execute('INSERT INTO task_dependencies VALUES(?,?)',(tid,parent))
   a.audit(c,u,'task_dependencies',tid);return {'ok':True}
 if not path.startswith('/api/agency/production'):return None
 a.need(u,'production');parts=path.split('/')[4:]
 if method=='GET':
  plans=[dict(r)|{'items':json.loads(r['items'])} for r in c.execute('SELECT * FROM service_plans ORDER BY created DESC') if scope.allowed(c,u,r['client_id'])]
  projects=[dict(r) for r in c.execute('SELECT * FROM agency_projects ORDER BY month DESC,created DESC') if scope.allowed(c,u,r['client_id'])]
  if not a.perm(u,'agency_finance'):
   for row in plans+projects:row.pop('monthly_fee',None)
  for project in projects:
   project['deliverables']=[dict(r) for r in c.execute('SELECT d.*,t.title,t.owner,t.status,t.due FROM deliverables d JOIN tasks t ON t.id=d.task_id WHERE d.project_id=?',(project['id'],))]
   for delivery in project['deliverables']:
    delivery['revision_rounds']=c.execute("SELECT count(DISTINCT f.version_id) FROM creative_feedback f JOIN creative_reviews r ON r.id=f.review_id WHERE r.task_id=? AND f.decision='changes'",(delivery['task_id'],)).fetchone()[0]
  return {'plans':plans,'projects':projects,'teams':{r['id']:[x['id'] for x in c.execute('SELECT * FROM users WHERE active=1') if scope.allowed(c,a.user_public(c,x),r['id'])] for r in c.execute('SELECT * FROM clients') if scope.allowed(c,u,r['id'])}}
 a.need(u,'production_manage')
 if parts and parts[0]=='plans':
  id=parts[1] if len(parts)>1 else None;old=c.execute('SELECT * FROM service_plans WHERE id=?',(id,)).fetchone() if id else None
  if id and not old:raise a.Error(404,'Pacote não encontrado.')
  if old:scope.need(a,c,u,old['client_id'])
  if len(parts)>2 and parts[2]=='generate' and method=='POST':return generate(a,c,u,old,d.get('month'))
  if method in ['POST','PATCH']:
   cid=d.get('client_id',old['client_id'] if old else None);scope.need(a,c,u,cid)
   start=month(a,d.get('start_month'));end=month(a,d['end_month']) if d.get('end_month') else None
   if end and end<start:raise a.Error(400,'Fim anterior ao início.')
   fields={'client_id':cid,'name':a.textfield(d,'name',True,120),'owner':member(a,c,u,cid,d.get('owner')),'items':json.dumps(items(a,c,u,cid,d.get('items'))),'start_month':start,'end_month':end,'monthly_fee':business.money(a,d.get('monthly_fee',0)) if a.perm(u,'agency_finance_manage') else (old['monthly_fee'] if old else 0),'auto':int(d.get('auto') is True),'active':int(d.get('active',True) is True)}
   if old:fields['revision']=old['revision']+1;business.update(c,'service_plans',id,fields)
   else:
    id=a.uid();fields.update(id=id,created=a.now());c.execute('INSERT INTO service_plans('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',list(fields.values()))
   a.audit(c,u,'service_plan',id);return {'id':id}
 if parts and parts[0]=='extra' and method=='POST':
  project=c.execute('SELECT * FROM agency_projects WHERE id=?',(d.get('project_id'),)).fetchone()
  if not project:raise a.Error(404,'Projeto não encontrado.')
  scope.need(a,c,u,project['client_id']);owner=member(a,c,u,project['client_id'],d.get('owner'));tid=a.uid();title=a.textfield(d,'title',True,180);due=a.datefield(d.get('due'))
  c.execute('INSERT INTO tasks(id,title,description,client_id,owner,creator,due,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',(tid,title,'Entrega extra: '+project['title'],project['client_id'],owner,u['id'],due,a.now(),a.now()))
  c.execute('INSERT INTO deliverables VALUES(?,?,?,?,?,?,?,?)',(a.uid(),project['id'],tid,title,integer(a,d.get('estimated_minutes',0),0,100000,'minutos'),1,None,a.now()));a.audit(c,u,'production_extra',tid);return {'id':tid}
 raise a.Error(404,'Ação de produção não encontrada.')

def tick(a,c):
 period=datetime.now(a.TZ).strftime('%Y-%m')
 for plan in c.execute("SELECT * FROM service_plans WHERE active=1 AND auto=1 AND start_month<=? AND (end_month IS NULL OR end_month>=?)",(period,period)).fetchall():
  raw=c.execute('SELECT * FROM users WHERE id=? AND active=1',(plan['owner'],)).fetchone()
  if not raw:continue
  u=a.user_public(c,raw)
  if not a.perm(u,'production_manage') or not scope.allowed(c,u,plan['client_id']):continue
  c.execute('SAVEPOINT production_tick')
  try:generate(a,c,u,plan,period);c.execute('RELEASE production_tick')
  except a.Error:c.execute('ROLLBACK TO production_tick');c.execute('RELEASE production_tick')

def delivery_time(a,value):
 if not isinstance(value,str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value):raise a.Error(400,'Horário de entrega inválido.')
 return value
