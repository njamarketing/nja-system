import unittest,json,base64
from datetime import datetime
import test_system as base
import app
import test_attachments
class TeamworkTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 raw=test_attachments.AttachmentTest.raw
 send=test_attachments.AttachmentTest.send
 def group(self):
  r=self.call('/api/rooms','POST',{'kind':'group','name':'Equipe','members':['alice','bob']});self.assertEqual(r[0],200,r);return r[1]['id']
 def test_group_delegation_send_invite_and_revoke(self):
  rid=self.group();url='/api/rooms/'+rid
  r=self.call(url,'PATCH',{'managers':['alice'],'send_policy':'managers','invite_policy':'selected','invite_members':['bob']});self.assertEqual(r[0],200,r)
  self.assertEqual(self.call(url+'/messages','POST',{'text':'não'},who='bob')[0],403)
  self.assertEqual(self.call(url+'/messages','POST',{'text':'sim'},who='alice')[0],200)
  self.assertEqual(self.call(url,'PATCH',{'description':'Gestora local'},who='alice')[0],200)
  self.assertEqual(self.call(url,'PATCH',{'description':'Não permitido'},who='bob')[0],403)
  self.assertEqual(self.call(url+'/invite','POST',{'members':['master']},who='bob')[0],200)
  self.assertEqual(self.call(url,'PATCH',{'managers':['bob']},who='alice')[0],200)
  self.assertEqual(self.call(url,'PATCH',{'description':'Revogada'},who='alice')[0],403)
 def test_muted_upload_and_audio(self):
  rid=self.group();self.call('/api/rooms/'+rid,'PATCH',{'send_policy':'managers'})
  self.assertEqual(self.call('/api/upload','POST',{'room_id':rid,'name':'file.pdf','data':base64.b64encode(b'%PDF-1.4\ntest').decode()},who='bob')[0],403)
  self.assertEqual(self.send('pauta.txt',b'teste',{'room_id':rid},who='bob')[0],403)
  self.assertEqual(self.call('/api/audio','POST',{'room_id':rid,'data':'AA=='},who='bob')[0],403)
 def test_group_preserves_read_state_and_rejects_outsiders(self):
  rid=self.group()
  with app.connect() as c:c.execute('UPDATE room_members SET last_read=? WHERE room_id=? AND user_id=?',('2026-01-01',rid,'alice'))
  self.assertEqual(self.call('/api/rooms/'+rid,'PATCH',{'description':'Nova'})[0],200)
  with app.connect() as c:self.assertEqual(c.execute('SELECT last_read FROM room_members WHERE room_id=? AND user_id=?',(rid,'alice')).fetchone()[0],'2026-01-01')
  self.assertEqual(self.call('/api/rooms/'+rid,'PATCH',{'send_policy':'bad'})[0],400)
 def test_tutorial_per_user_and_cascavel(self):
  self.assertEqual(self.call('/api/tutorial','POST',{'version':1},who='alice')[0],200)
  self.assertEqual(self.call('/api/me',who='alice')[1]['user']['tutorial_version'],1)
  self.assertEqual(self.call('/api/me',who='bob')[1]['user']['tutorial_version'],0)
  self.assertIn('cascavel',[x['id'] for x in self.call('/api/company')[1]['branches']])
  self.assertEqual(self.call('/api/tutorial','POST',{'version':1},who='bob',csrf=False)[0],403)
 def test_real_sales_ranking_scope_and_cancellation(self):
  with app.connect() as c:c.execute("UPDATE users SET role_id='sales',branch='cascavel' WHERE id='alice'")
  lead=self.call('/api/business/leads','POST',{'name':'Cliente ABC','owner':'alice','budget':'99999','product':'Site'})[1]['id']
  self.assertEqual(self.call('/api/sales/ranking',who='alice')[1]['items'],[])
  self.assertEqual(self.call('/api/sales/ranking',who='bob')[0],403)
  self.assertEqual(self.call('/api/sales','POST',{'lead_id':lead,'amount':'200','sold_on':datetime.now(app.TZ).date().isoformat()},who='alice')[0],400)
  self.assertEqual(self.call('/api/business/leads/'+lead+'/convert','POST',{},who='alice')[0],200)
  r=self.call('/api/sales','POST',{'lead_id':lead,'amount':'200','sold_on':datetime.now(app.TZ).date().isoformat()},who='alice');self.assertEqual(r[0],200,r);sid=r[1]['id']
  self.assertEqual(self.call('/api/sales/ranking?branch=cascavel',who='alice')[1]['items'][0]['amount'],20000)
  self.assertEqual(self.call('/api/sales/ranking?branch=foz',who='alice')[1]['items'],[])
  with app.connect() as c:c.execute("UPDATE users SET branch='foz' WHERE id='alice'")
  self.assertEqual(len(self.call('/api/sales/ranking?branch=cascavel',who='alice')[1]['items']),1)
  self.assertEqual(self.call('/api/sales/'+sid,'PATCH',{'status':'cancelled'},who='alice')[0],403)
  self.assertEqual(self.call('/api/sales/'+sid,'PATCH',{'status':'cancelled'})[0],200)
  self.assertEqual(self.call('/api/sales/ranking',who='alice')[1]['items'],[])
