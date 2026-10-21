"""NJA 1.10: group-level policies, onboarding and verified sales records."""
import json
from datetime import datetime,date
import business
BRANCHES={'foz':'Foz do Iguaçu/PR','teixeira':'Teixeira de Freitas/BA','cascavel':'Cascavel/PR'}
PERMISSIONS=['sales_ranking','sales_manage']

def init(c):
 for table,key,definition in [('rooms','send_policy',"TEXT NOT NULL DEFAULT 'all'"),('rooms','invite_policy',"TEXT NOT NULL DEFAULT 'managers'"),('rooms','send_members',"TEXT NOT NULL DEFAULT '[]'"),('rooms','invite_members',"TEXT NOT NULL DEFAULT '[]'"),('room_members','is_manager','INTEGER NOT NULL DEFAULT 0'),('users','tutorial_version','INTEGER NOT NULL DEFAULT 0')]:
  if key not in [r[1] for r in c.execute('PRAGMA table_info('+table+')')]:c.execute('ALTER TABLE '+table+' ADD COLUMN '+key+' '+definition)
 c.executescript('''CREATE TABLE IF NOT EXISTS sales(id TEXT PRIMARY KEY,lead_id TEXT NOT NULL UNIQUE REFERENCES leads(id),seller TEXT NOT NULL REFERENCES users(id),branch TEXT NOT NULL,amount INTEGER NOT NULL,sold_on TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'confirmed',created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS teamwork_schema(version INTEGER PRIMARY KEY);''')
 if not c.execute('SELECT 1 FROM teamwork_schema WHERE version=1').fetchone():
  r=c.execute("SELECT permissions FROM roles WHERE id='sales'").fetchone()
  if r:c.execute("UPDATE roles SET permissions=? WHERE id='sales'",(json.dumps(list(dict.fromkeys(json.loads(r[0])+['sales_ranking']))),))
  c.execute('INSERT INTO teamwork_schema VALUES(1)')

def manager(a,c,u,r):
 return bool(u['master'] or a.perm(u,'chat_manage') or r['creator']==u['id'] or c.execute('SELECT 1 FROM room_members WHERE room_id=? AND user_id=? AND is_manager=1',(r['id'],u['id'])).fetchone())

def allowed(a,c,u,r,action):
 if r['kind']=='direct':return True
 if manager(a,c,u,r):return True
 policy=r[action+'_policy']
 return policy=='all' or (policy=='selected' and u['id'] in json.loads(r[action+'_members']))

def need_action(a,c,u,id,action):
 a.room_access(c,u,id);r=c.execute('SELECT * FROM rooms WHERE id=?',(id,)).fetchone()
 if action=='manage':ok=manager(a,c,u,r)
 else:ok=allowed(a,c,u,r,action)
 if not ok:raise a.Error(403,'As permissões deste grupo não permitem esta ação.')
 return r

def serialize(a,c,u,r):
 return {'can_manage':manager(a,c,u,r),'can_send':allowed(a,c,u,r,'send'),'can_invite':allowed(a,c,u,r,'invite'),'managers':[m[0] for m in c.execute('SELECT user_id FROM room_members WHERE room_id=? AND (is_manager=1 OR user_id=?)',(r['id'],r['creator']))],'send_members':json.loads(r['send_members']),'invite_members':json.loads(r['invite_members'])}

def api(a,c,u,method,path,d,q):
 if path=='/api/tutorial' and method=='POST':
  if d.get('version')!=1:raise a.Error(400,'Versão de tutorial inválida.')
  c.execute('UPDATE users SET tutorial_version=1 WHERE id=?',(u['id'],));return {'ok':True}
 if path.startswith('/api/rooms/'):
  parts=path.split('/');id=parts[3]
  if len(parts)==4 and method=='PATCH':
   r=need_action(a,c,u,id,'manage')
   if r['kind'] not in ['group','general']:raise a.Error(400,'Este tipo de conversa não possui administração de grupo.')
   current={m[0] for m in c.execute('SELECT user_id FROM room_members WHERE room_id=?',(id,))}
   members=set(a.active_ids(c,d['members'])) if 'members' in d else current
   members.add(u['id'])
   if r['kind']=='general' and members!=current:raise a.Error(400,'Integrantes do grupo geral são definidos pelo cadastro da equipe.')
   managers=set(a.active_ids(c,d['managers'])) if 'managers' in d else {m[0] for m in c.execute('SELECT user_id FROM room_members WHERE room_id=? AND is_manager=1',(id,))}|({r['creator']} if r['creator'] else set())
   managers&=members
   if not managers:managers.add(u['id'])
   # The creator is a legacy administrator; transfer creation authority to a selected manager.
   if r['creator'] not in managers:c.execute('UPDATE rooms SET creator=? WHERE id=?',(sorted(managers)[0],id))
   for action in ['send','invite']:
    policy=d.get(action+'_policy',r[action+'_policy'])
    if policy not in ['all','managers','selected']:raise a.Error(400,'Política de grupo inválida.')
    selected=set(a.active_ids(c,d[action+'_members'])) if action+'_members' in d else set(json.loads(r[action+'_members']))&members
    if not selected<=members:raise a.Error(400,'Selecione somente integrantes do grupo.')
    c.execute('UPDATE rooms SET '+action+'_policy=?,'+action+'_members=? WHERE id=?',(policy,json.dumps(sorted(selected)),id))
   for member in current-members:c.execute('DELETE FROM room_members WHERE room_id=? AND user_id=?',(id,member))
   for member in members:
    c.execute('INSERT OR IGNORE INTO room_members(room_id,user_id) VALUES(?,?)',(id,member));c.execute('UPDATE room_members SET is_manager=? WHERE room_id=? AND user_id=?',(int(member in managers),id,member))
   for key in ['name','description','project']:
    if key in d:c.execute('UPDATE rooms SET '+key+'=? WHERE id=?',(a.textfield(d,key,key=='name',2000 if key=='description' else 120),id))
   a.audit(c,u,'group_settings',id);return {'ok':True}
  if len(parts)==5 and parts[4]=='invite' and method=='POST':
   r=need_action(a,c,u,id,'invite')
   if r['kind']!='group':raise a.Error(400,'Convites disponíveis apenas em grupos personalizados.')
   for member in a.active_ids(c,d.get('members',[])):c.execute('INSERT OR IGNORE INTO room_members(room_id,user_id) VALUES(?,?)',(id,member))
   a.audit(c,u,'group_invite',id);return {'ok':True}
  if len(parts)==5 and parts[4]=='messages' and method=='POST':need_action(a,c,u,id,'send')
 if path=='/api/sales' and method=='POST':
  import interaction_updates
  if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
  a.need(u,'crm_convert');lead=business.access(a,c,u,'leads',d.get('lead_id'))
  if not lead['client_id']:raise a.Error(400,'Converta o lead em cliente antes de registrar a venda.')
  seller=lead['owner']
  if not seller:raise a.Error(400,'Atribua o responsável comercial.')
  if seller!=u['id'] and not a.perm(u,'sales_manage'):raise a.Error(403,'Somente o vendedor ou gestor de vendas pode registrar a venda.')
  person=business.person(a,c,seller,True);amount=business.money(a,d.get('amount'));sold_on=business.day(a,d.get('sold_on'))
  if amount<=0 or sold_on>datetime.now(a.TZ).date().isoformat():raise a.Error(400,'Informe valor positivo e uma data não futura.')
  previous=interaction_updates.ranking(c,sold_on[:7])
  id=a.uid();c.execute('INSERT INTO sales(id,lead_id,seller,branch,amount,sold_on,created) VALUES(?,?,?,?,?,?,?)',(id,lead['id'],seller,person['branch'],amount,sold_on,a.now()));a.audit(c,u,'sale_confirmed',id);interaction_updates.celebrate_sale(a,c,id,seller,sold_on,previous);return {'id':id}
 if path=='/api/sales' and method=='GET':
  a.need(u,'sales_ranking')
  return {'items':[dict(r) for r in c.execute('SELECT sales.*,leads.name FROM sales JOIN leads ON leads.id=sales.lead_id WHERE seller=? OR ? ORDER BY sold_on DESC',(u['id'],int(a.perm(u,'sales_manage'))))]}
 if path.startswith('/api/sales/') and method=='PATCH':
  a.need(u,'sales_manage')
  if d.get('status') not in ['confirmed','cancelled']:raise a.Error(400,'Status inválido.')
  if not c.execute('UPDATE sales SET status=? WHERE id=?',(d['status'],path.split('/')[-1])).rowcount:raise a.Error(404,'Venda não encontrada.')
  a.audit(c,u,'sale_status',path.split('/')[-1],d['status']);return {'ok':True}
 if path=='/api/sales/ranking' and method=='GET':
  a.need(u,'sales_ranking');a.need(u,'dashboard')
  month=q.get('month',[datetime.now(a.TZ).strftime('%Y-%m')])[0]
  try:date.fromisoformat(month+'-01')
  except (ValueError,TypeError):raise a.Error(400,'Mês inválido.')
  branch=q.get('branch',['national'])[0]
  if branch not in ['national',*BRANCHES]:raise a.Error(400,'Unidade inválida.')
  rows=[dict(r) for r in c.execute("SELECT s.seller AS id,u.name,u.photo,SUM(s.amount) AS amount,COUNT(*) AS deals FROM sales s JOIN users u ON u.id=s.seller WHERE s.status='confirmed' AND substr(s.sold_on,1,7)=? AND (?='national' OR s.branch=?) GROUP BY s.seller ORDER BY amount DESC,deals DESC,u.name,s.seller",(month,branch,branch))]
  return {'items':rows,'month':month,'branch':branch,'criterion':'Vendas confirmadas no mês, por valor. Desempate: quantidade, nome e identificador. Unidade registrada na data de cadastro da venda.'}
 return None
