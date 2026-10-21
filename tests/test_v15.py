import unittest,os,json,time,re
from unittest.mock import patch
import test_system
app=test_system.app
class V15Test(unittest.TestCase):
 setUp=test_system.SystemTest.setUp
 tearDown=test_system.SystemTest.tearDown
 call=test_system.SystemTest.call
 make_task=test_system.SystemTest.make_task
 def client(self):return self.call('/api/clients','POST',{'name':'Cliente A','entered':'2026-01-01','product':'Marketing'})[1]['id']
 def meeting(self):
  st,r,_=self.call('/api/meetings','POST',{'room_id':'general','members':['alice','bob'],'mode':'video'});self.assertEqual(st,200,r);return r['meeting']['id']
 def test_task_client_link_rename_and_unlink(self):
  cid=self.client();self.call('/api/agency/access','POST',{'client_id':cid,'branch':'foz','members':['alice']});tid=self.call('/api/tasks','POST',{'title':'Arte','owner':'alice','client_id':cid})[1]['id']
  t=self.call('/api/tasks/'+tid,who='alice')[1];self.assertEqual(t['client_id'],cid);self.assertEqual(t['project'],'Cliente A')
  self.call('/api/clients/'+cid,'PATCH',{'name':'Cliente Renomeado'})
  self.assertEqual(self.call('/api/tasks/'+tid,who='alice')[1]['project'],'Cliente Renomeado')
  self.call('/api/tasks/'+tid,'PATCH',{'description':'Revisão'},who='alice');self.assertEqual(self.call('/api/tasks/'+tid,who='alice')[1]['client_id'],cid)
  self.assertEqual(self.call('/api/tasks/'+tid,'PATCH',{'client_id':'missing'},who='alice')[0],400)
  self.call('/api/tasks/'+tid,'PATCH',{'client_id':'','project':'Campanha interna'},who='alice');self.assertIsNone(self.call('/api/tasks/'+tid,who='alice')[1]['client_id'])
 def test_inactive_client_and_permissions(self):
  cid=self.client();self.call('/api/clients/'+cid+'/active','PATCH',{'active':False})
  self.assertEqual(self.call('/api/tasks','POST',{'title':'Nova','client_id':cid},who='alice')[0],400)
  with app.connect() as c:
   c.execute("INSERT INTO roles VALUES('limited','Limitado',?)",(json.dumps(['tasks','task_create','task_edit']),));c.execute("UPDATE users SET role_id='limited' WHERE id='alice'")
  self.assertEqual(self.call('/api/tasks','POST',{'title':'Sem acesso','client_id':cid},who='alice')[0],403)
 def test_group_call_invites_join_routing_and_host_transfer(self):
  mid=self.meeting();self.assertEqual(self.call('/api/meetings',who='alice')[1]['meetings'][0]['my_status'],'invited')
  self.assertEqual(self.call('/api/meetings/'+mid+'/signals',who='alice')[0],403)
  self.assertEqual(self.call('/api/meetings/'+mid+'/action','POST',{'action':'join'},who='alice')[0],200)
  self.call('/api/meetings/'+mid+'/action','POST',{'action':'join'},who='bob')
  payload={'recipient':'alice','kind':'offer','payload':{'type':'offer','sdp':'test'}}
  self.assertEqual(self.call('/api/meetings/'+mid+'/signals','POST',payload)[0],200)
  self.assertEqual(len(self.call('/api/meetings/'+mid+'/signals',who='alice')[1]['signals']),1)
  self.assertEqual(self.call('/api/meetings/'+mid+'/signals',who='bob')[1]['signals'],[])
  self.assertEqual(self.call('/api/meetings/'+mid+'/action','POST',{'action':'end'},who='alice')[0],403)
  self.call('/api/meetings/'+mid+'/action','POST',{'action':'leave'})
  self.assertEqual(self.call('/api/meetings/'+mid,who='alice')[1]['meeting']['host'],'alice')
  self.assertEqual(self.call('/api/meetings/'+mid+'/action','POST',{'action':'end'},who='alice')[0],200)
  self.assertEqual(self.call('/api/meetings',who='bob')[1]['meetings'],[])
 def test_group_limit_acl_busy_decline_and_rejoin(self):
  self.assertEqual(self.call('/api/meetings','POST',{'room_id':'general','members':[],'mode':'video'})[0],400)
  rid=self.call('/api/rooms','POST',{'kind':'group','name':'Reservado','members':['alice']})[1]['id']
  self.assertEqual(self.call('/api/meetings','POST',{'room_id':rid,'members':['bob'],'mode':'video'})[0],403)
  mid=self.meeting()
  self.assertEqual(self.call('/api/calls','POST',{'room_id':'general','callee':'alice','mode':'audio'},who='bob')[0],409)
  self.call('/api/meetings/'+mid+'/action','POST',{'action':'decline'},who='alice')
  self.assertEqual(self.call('/api/meetings',who='alice')[1]['meetings'],[])
  self.assertEqual(len(self.call('/api/meetings?room_id=general',who='alice')[1]['meetings']),1)
  self.call('/api/meetings/'+mid+'/action','POST',{'action':'join'},who='alice');self.call('/api/meetings/'+mid+'/action','POST',{'action':'leave'},who='alice')
  self.assertEqual(self.call('/api/meetings/'+mid+'/action','POST',{'action':'join'},who='alice')[0],200)
  with app.connect() as c:c.execute("DELETE FROM room_members WHERE room_id='general' AND user_id='alice'")
  self.assertEqual(self.call('/api/meetings/'+mid,who='alice')[0],403)
 def test_recovery_email_link_consumption_and_sessions(self):
  env={'SMTP_HOST':'smtp.example.test','SMTP_FROM':'NJA <acesso@nja.test>','SMTP_USER':'test','SMTP_PASSWORD':'test','SMTP_SECURITY':'starttls'}
  with patch.dict(os.environ,env),patch('mailer.smtplib.SMTP') as smtp:
   st,r,_=self.call('/api/recover','POST',{'email':'alice@nja.test'},login=False);self.assertEqual(st,200)
   obj=smtp.return_value.__enter__.return_value;obj.starttls.assert_called_once();obj.login.assert_called_once()
   msg=obj.send_message.call_args.args[0];self.assertEqual(msg['To'],'alice@nja.test');self.assertTrue(msg.is_multipart());token=re.search(r'reset=([A-Za-z0-9_-]+)',msg.get_body(preferencelist=('plain',)).get_content())[1]
   self.assertNotIn(token,self.call('/api/mail/status')[1].values())
  with app.connect() as c:self.assertEqual(c.execute('SELECT token FROM resets').fetchone()[0],app.digest(token))
  self.assertEqual(self.call('/api/reset','POST',{'token':token,'password':'Another-Strong-123','confirmation':'different'},login=False)[0],400)
  self.assertEqual(self.call('/api/reset','POST',{'token':token,'password':'Another-Strong-123','confirmation':'Another-Strong-123'},login=False)[0],200)
  self.assertEqual(self.call('/api/me',who='alice')[0],401)
  self.assertEqual(self.call('/api/reset','POST',{'token':token,'password':'Another-Strong-123'},login=False)[0],400)
  self.assertEqual(self.call('/api/login','POST',{'email':'alice@nja.test','password':'Another-Strong-123'},login=False)[0],200)
 def test_recovery_expiry_failure_generic_and_ssl(self):
  env={'SMTP_HOST':'smtp.example.test','SMTP_FROM':'acesso@nja.test','SMTP_USER':'u','SMTP_PASSWORD':'p','SMTP_SECURITY':'ssl','SMTP_PORT':'465'}
  with patch.dict(os.environ,env),patch('mailer.smtplib.SMTP_SSL') as smtp:
   known=self.call('/api/recover','POST',{'email':'alice@nja.test'},login=False)[1]
   unknown=self.call('/api/recover','POST',{'email':'unknown@nja.test'},login=False)[1];self.assertEqual(known,unknown)
   obj=smtp.return_value.__enter__.return_value;obj.starttls.assert_not_called();self.assertEqual(obj.send_message.call_count,1)
  with app.connect() as c:c.execute("INSERT OR REPLACE INTO resets VALUES(?,?,?)",(app.digest('expired'),'alice',time.time()-1))
  self.assertEqual(self.call('/api/reset','POST',{'token':'expired','password':'New-Strong-123'},login=False)[0],400)
  with patch.dict(os.environ,env),patch('mailer.smtplib.SMTP_SSL',side_effect=Exception('failure')):
   self.assertEqual(self.call('/api/recover','POST',{'email':'alice@nja.test'},login=False)[0],503)
  with app.connect() as c:self.assertIsNone(c.execute("SELECT 1 FROM resets WHERE user_id='alice'").fetchone())
