import unittest
import test_agency_portal as base
import app
class ChatTest(unittest.TestCase):
 setUp=base.PortalTest.setUp
 tearDown=base.PortalTest.tearDown
 call=base.PortalTest.call
 portal=base.PortalTest.portal
 setup_review=base.PortalTest.setup_review
 def test_both_directions_and_client_isolation(self):
  cid,_,_,token,_=self.setup_review()
  path='/api/agency/client-chats/'+cid
  self.assertEqual(self.portal('chat','POST',{'text':'Olá NJA','client_id':'forged'},token)[0],200)
  self.assertEqual(self.call(path)[1]['messages'][0]['text'],'Olá NJA')
  self.assertEqual(self.call(path,'POST',{'text':'Olá cliente'})[0],200)
  messages=self.portal('chat',token=token)[1]['messages']
  self.assertEqual([m['side'] for m in messages],['client','staff'])
  self.assertEqual(self.call(path,who='bob')[0],403)
  self.assertEqual(self.call(path,'POST',{'text':'Forbidden'},who='bob')[0],403)
  other=self.call('/api/clients','POST',{'name':'Outro','entered':'2026-10-01','product':'Marketing'})[1]['id']
  self.call('/api/agency/client-chats/'+other,'POST',{'text':'Segredo de outro cliente'})
  self.assertEqual(len(self.portal('chat',token=token)[1]['messages']),2)
  self.assertEqual(self.portal('chat',token='invalid')[0],401)
 def test_scope_revocation_and_deactivated_contact(self):
  cid,_,_,token,_=self.setup_review();path='/api/agency/client-chats/'+cid
  with app.connect() as c:c.execute('INSERT INTO client_team VALUES(?,?)',(cid,'alice'))
  self.assertEqual(self.call(path,'POST',{'text':'Responsável'},who='alice')[0],200)
  with app.connect() as c:c.execute('DELETE FROM client_team WHERE user_id=?',('alice',))
  self.assertEqual(self.call(path,who='alice')[0],403)
  account=self.call('/api/agency/reviews')[1]['accounts'][0]['id']
  self.call('/api/agency/portal/accounts/'+account,'PATCH',{'active':False})
  self.assertEqual(self.portal('chat','POST',{'text':'Bloqueado'},token)[0],401)
 def test_pagination_empty_and_persistence(self):
  cid,_,_,token,_=self.setup_review();path='/api/agency/client-chats/'+cid
  self.assertEqual(self.portal('chat','POST',{'text':'  '},token)[0],400)
  with app.connect() as c:
   for i in range(105):c.execute('INSERT INTO portal_chat_messages(client_id,actor,name,text,created) VALUES(?,?,?,?,?)',(cid,'staff:master','Master',str(i),app.now()))
  app.init()
  r=self.call(path)[1];self.assertEqual(len(r['messages']),100);self.assertTrue(r['has_older'])
  older=self.call(path+'?before='+str(r['messages'][0]['seq']))[1]
  self.assertEqual(len(older['messages']),5)
  self.assertEqual(self.call(path+'?after='+str(r['messages'][-1]['seq']))[1]['messages'],[])
  self.assertEqual(self.call(path+'?before=wrong')[0],400)
