"""Client/team and branch boundaries shared by every agency module."""
import json,time,os,sqlite3,shutil,secrets
from contextlib import closing
from pathlib import Path
from datetime import datetime,timezone
PERMISSIONS=['client_scope_manage','client_unit_all','client_company_all','operations','production','production_manage','approvals','approval_manage','portal_manage','editorial','editorial_manage','commercial_ops','commercial_manage','agency_reports','agency_finance','agency_finance_manage']
BRANCHES=['foz','teixeira','cascavel']
def init(c):
 if 'branch' not in [r[1] for r in c.execute('PRAGMA table_info(clients)')]:c.execute("ALTER TABLE clients ADD COLUMN branch TEXT")
 c.executescript('''CREATE TABLE IF NOT EXISTS client_team(client_id TEXT REFERENCES clients(id),user_id TEXT REFERENCES users(id),PRIMARY KEY(client_id,user_id));
 CREATE TABLE IF NOT EXISTS agency_schema(version INTEGER PRIMARY KEY);
 CREATE TABLE IF NOT EXISTS operation_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
 if not c.execute('SELECT 1 FROM agency_schema WHERE version=1').fetchone():
  # Preserve explicit legacy relationships, never grant the entire client directory.
  c.execute('INSERT OR IGNORE INTO client_team SELECT client_id,owner FROM tasks WHERE client_id IS NOT NULL')
  c.execute('INSERT OR IGNORE INTO client_team SELECT t.client_id,m.user_id FROM tasks t JOIN task_members m ON m.task_id=t.id WHERE t.client_id IS NOT NULL')
  c.execute('INSERT OR IGNORE INTO client_team SELECT r.client_id,m.user_id FROM rooms r JOIN room_members m ON m.room_id=r.id WHERE r.client_id IS NOT NULL')
  c.execute('INSERT OR IGNORE INTO client_team SELECT client_id,owner FROM leads WHERE client_id IS NOT NULL AND owner IS NOT NULL')
  c.execute('INSERT INTO agency_schema VALUES(1)')
def has(u,p):return bool(u['master'] or p in u['permissions'])
def allowed(c,u,id):
 if not id:return True
 if has(u,'client_company_all'):return True
 r=c.execute('SELECT branch FROM clients WHERE id=?',(id,)).fetchone()
 return bool(r and ((has(u,'client_unit_all') and r['branch'] and r['branch']==u.get('branch')) or c.execute('SELECT 1 FROM client_team WHERE client_id=? AND user_id=?',(id,u['id'])).fetchone()))
def need(a,c,u,id):
 r=c.execute('SELECT * FROM clients WHERE id=?',(id,)).fetchone()
 if not r:raise a.Error(404,'Cliente não encontrado.')
 if not allowed(c,u,id):raise a.Error(403,'Cliente fora da sua carteira ou unidade.')
 return dict(r)
def created(c,u,id):
 c.execute('UPDATE clients SET branch=? WHERE id=? AND branch IS NULL',(u.get('branch') or 'foz',id));c.execute('INSERT OR IGNORE INTO client_team VALUES(?,?)',(id,u['id']))
def filter_clients(c,u,rows):return [r for r in rows if allowed(c,u,r['id'])]
def branch_allowed(u,branch):return has(u,'client_company_all') or branch==u.get('branch')
def api(a,c,u,method,path,d,q):
 if path=='/api/agency/access':
  a.need(u,'client_scope_manage')
  if method=='GET':return {'items':[dict(r)|{'members':[m[0] for m in c.execute('SELECT user_id FROM client_team WHERE client_id=?',(r['id'],))]} for r in c.execute('SELECT id,name,branch FROM clients ORDER BY name') if allowed(c,u,r['id'])]}
  if method=='POST':
   id=d.get('client_id');need(a,c,u,id);branch=d.get('branch')
   if branch not in BRANCHES:raise a.Error(400,'Selecione a unidade.')
   if not branch_allowed(u,branch):raise a.Error(403,'Sem acesso à unidade de destino.')
   members=a.active_ids(c,d.get('members',[]));c.execute('UPDATE clients SET branch=? WHERE id=?',(branch,id));c.execute('DELETE FROM client_team WHERE client_id=?',(id,))
   for who in members:c.execute('INSERT INTO client_team VALUES(?,?)',(id,who))
   a.audit(c,u,'client_scope',id,json.dumps({'branch':branch,'members':members}));return {'ok':True}
 if path=='/api/agency/operations':
  a.need(u,'operations')
  if method=='GET':return {'state':dict(c.execute('SELECT key,value FROM operation_state')),'backup_configured':bool(os.getenv('NJA_BACKUP_DIR')),'secure_cookies':a.SECURE,'sessions':[dict(r) for r in c.execute('SELECT s.token AS id,s.user_id,u.name,s.expires,s.last_seen FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.expires>?',(time.time(),))],'unassigned_clients':c.execute('SELECT count(*) FROM clients WHERE branch IS NULL').fetchone()[0]}
  if method=='POST':
   if d.get('action')=='revoke':c.execute('DELETE FROM sessions WHERE token=?',(d.get('id'),));a.audit(c,u,'session_revoke',d.get('id'));return {'ok':True}
   if d.get('action')=='backup':c.commit();result=backup(a);a.audit(c,u,'backup','operations');return result
 return None

def backup(a):
 root=os.getenv('NJA_BACKUP_DIR','')
 if not root:raise a.Error(409,'Configure NJA_BACKUP_DIR com um destino de backup separado da instalação.')
 folder=Path(root).expanduser().resolve()/('nja-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3));folder.mkdir(parents=True,mode=0o700)
 try:
  with a.connect() as source,closing(sqlite3.connect(folder/'nja.sqlite3')) as target:source.backup(target)
  with closing(sqlite3.connect(folder/'nja.sqlite3')) as check:
   if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Integrity check failed')
  shutil.copytree(a.DATA/'uploads',folder/'uploads',ignore=shutil.ignore_patterns('.incoming-*'))
  if (a.DATA/'integration.key').exists():shutil.copy2(a.DATA/'integration.key',folder/'integration.key')
  (folder/'RESTORE.txt').write_text('Pare web e scheduler. Preserve os arquivos atuais. Restaure nja.sqlite3, uploads e integration.key para NJA_DATA. Restaure separadamente as variáveis de ambiente. Reinicie e confira os acessos.\n')
  with a.connect() as c:c.execute('INSERT OR REPLACE INTO operation_state VALUES(?,?)',('last_backup',a.now()))
  return {'ok':True,'name':folder.name}
 except Exception:
  with a.connect() as c:c.execute('INSERT OR REPLACE INTO operation_state VALUES(?,?)',('backup_error',a.now()))
  raise a.Error(503,'Falha no backup. Verifique espaço e permissões do destino.')

def notification_allowed(a,c,u,link):
 kind,sep,id=link.partition(':')
 try:
  if sep and kind=='tasks':a.get_task(c,u,id)
  elif sep and kind=='chats':a.need(u,'chats');a.room_access(c,u,id)
  elif sep and kind in ['contracts','crm']:
   import business
   business.access(a,c,u,'contracts' if kind=='contracts' else 'leads',id)
  elif sep and kind=='approvals':
   a.need(u,'approvals');r=c.execute('SELECT client_id FROM creative_reviews WHERE id=?',(id,)).fetchone()
   if not r:return False
   need(a,c,u,r[0])
  elif sep and kind=='commercial_ops':
   import business
   a.need(u,'commercial_ops');business.access(a,c,u,'leads',id)
  return True
 except a.Error:return False

def task_members(a,c,cid,ids):
 if not cid:return
 for id in ids:
  raw=c.execute('SELECT * FROM users WHERE id=? AND active=1',(id,)).fetchone()
  if not raw or not allowed(c,a.user_public(c,raw),cid):raise a.Error(400,'Todos os responsáveis e participantes precisam de acesso ao cliente. Ajuste a carteira antes de atribuir a tarefa.')
