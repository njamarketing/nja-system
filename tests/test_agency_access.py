import unittest,json,tempfile,os,sqlite3
from unittest.mock import patch
import test_system as base
import app,agency_access
class AccessTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def client(self):return self.call('/api/clients','POST',{'name':'Cliente privado','entered':'2026-10-01','product':'Marketing'})[1]['id']
 def test_revocation_covers_directory_task_room(self):
  cid=self.client();self.assertEqual(self.call('/api/clients',who='alice')[1],[])
  self.assertEqual(self.call('/api/clients/'+cid,'PATCH',{'name':'Intruso'},who='alice')[0],403)
  self.call('/api/agency/access','POST',{'client_id':cid,'branch':'foz','members':['alice']})
  tid=self.call('/api/tasks','POST',{'title':'Privada','owner':'alice','client_id':cid})[1]['id'];self.assertEqual(self.call('/api/tasks/'+tid,who='alice')[0],200)
  rid=self.call('/api/rooms','POST',{'name':'Cliente','kind':'group','members':['alice']})[1]['id'];self.call('/api/rooms/'+rid+'/brand','PATCH',{'client_id':cid})
  self.call('/api/agency/access','POST',{'client_id':cid,'branch':'foz','members':[]})
  self.assertEqual(self.call('/api/tasks/'+tid,who='alice')[0],403)
  self.assertEqual(self.call('/api/rooms/'+rid+'/messages',who='alice')[0],403)
  self.assertNotIn(rid,[r['id'] for r in self.call('/api/rooms',who='alice')[1]])
 def test_unit_permission_does_not_cross_units(self):
  cid=self.client()
  with app.connect() as c:
   c.execute('INSERT INTO roles VALUES(?,?,?)',('local','Local',json.dumps(['clients','client_unit_all'])));c.execute("UPDATE users SET role_id='local',branch='cascavel' WHERE id='alice'")
  self.assertEqual(self.call('/api/clients',who='alice')[1],[])
  self.call('/api/agency/access','POST',{'client_id':cid,'branch':'cascavel','members':[]})
  self.assertEqual(len(self.call('/api/clients',who='alice')[1]),1)
 def test_backup_integrity_and_operational_acl(self):
  self.assertEqual(self.call('/api/agency/operations',who='alice')[0],403)
  with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'NJA_BACKUP_DIR':root}):
   r=self.call('/api/agency/operations','POST',{'action':'backup'});self.assertEqual(r[0],200,r)
   with sqlite3.connect(os.path.join(root,r[1]['name'],'nja.sqlite3')) as c:self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertGreater(c.execute('SELECT count(*) FROM users').fetchone()[0],0)
