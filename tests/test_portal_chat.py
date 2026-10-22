import unittest,json
import test_agency_portal as base
import app


class ChatTest(unittest.TestCase):
 setUp=base.PortalTest.setUp
 tearDown=base.PortalTest.tearDown
 call=base.PortalTest.call
 portal=base.PortalTest.portal
 setup_review=base.PortalTest.setup_review

 def group(self,cid,name='Grupo do cliente'):
  status,result,_=self.call('/api/rooms','POST',{'kind':'group','name':name,'members':['alice']})
  self.assertEqual(status,200,result);rid=result['id']
  self.assertEqual(self.call('/api/rooms/'+rid+'/brand','PATCH',{'client_id':cid})[0],200)
  return rid

 def test_portal_and_collaborators_share_the_assigned_group(self):
  cid,_,_,token,_=self.setup_review();rid=self.group(cid)
  home=self.portal('home',token=token)[1]
  self.assertEqual([(room['id'],room['name']) for room in home['rooms']],[(rid,'Grupo do cliente')])
  self.assertEqual(self.portal('rooms/'+rid+'/messages','POST',{'text':'Olá NJA'},token)[0],200)
  internal=self.call('/api/rooms/'+rid+'/messages')[1]['messages'][0]
  self.assertEqual(internal['text'],'Olá NJA');self.assertEqual(internal['name'],'Contato');self.assertIsNone(internal['user_id'])
  self.assertEqual(self.call('/api/rooms/'+rid+'/messages','POST',{'text':'Olá cliente'})[0],200)
  messages=self.portal('rooms/'+rid+'/messages',token=token)[1]['messages']
  self.assertEqual([message['side'] for message in messages],['client','staff'])
  self.assertEqual([message['text'] for message in messages],['Olá NJA','Olá cliente'])
  self.assertEqual(self.call('/api/rooms/'+rid+'/messages',who='alice')[0],200)
  with app.connect() as c:self.assertTrue(c.execute('SELECT 1 FROM client_team WHERE client_id=? AND user_id=?',(cid,'alice')).fetchone())

 def test_client_cannot_open_another_clients_group(self):
  cid,_,_,token,_=self.setup_review();self.group(cid)
  other=self.call('/api/clients','POST',{'name':'Outro','entered':'2026-10-01','product':'Marketing'})[1]['id']
  other_room=self.group(other,'Grupo secreto')
  self.assertEqual(self.portal('rooms/'+other_room+'/messages',token=token)[0],404)
  self.assertEqual(self.call('/api/rooms/'+other_room+'/messages',who='bob')[0],403)
  self.assertEqual(self.portal('rooms/unknown/messages',token=token)[0],404)

 def test_pagination_empty_validation_and_persistence(self):
  cid,_,_,token,_=self.setup_review();rid=self.group(cid)
  path='rooms/'+rid+'/messages'
  self.assertEqual(self.portal(path,'POST',{'text':'  '},token)[0],400)
  with app.connect() as c:
   for i in range(105):
    c.execute('INSERT INTO messages(id,room_id,user_id,text,created) VALUES(?,?,?,?,?)',(app.uid(),rid,'master',str(i),app.now()))
  app.init()
  result=self.portal(path,token=token)[1];self.assertEqual(len(result['messages']),100);self.assertTrue(result['has_older'])
  older=self.portal(path+'?before='+str(result['messages'][0]['seq']),token=token)[1]
  self.assertEqual(len(older['messages']),5)
  self.assertEqual(self.portal(path+'?after='+str(result['messages'][-1]['seq']),token=token)[1]['messages'],[])
  self.assertEqual(self.portal(path+'?before=wrong',token=token)[0],400)

 def test_home_is_personalized_with_plan_and_group_members(self):
  cid,_,_,token,_=self.setup_review();rid=self.group(cid)
  with app.connect() as c:
   c.execute("UPDATE clients SET description=?,cover=? WHERE id=?",('Uma parceria feita para crescer',None,cid))
   c.execute('INSERT INTO service_plans(id,client_id,name,owner,items,start_month,end_month,active,created) VALUES(?,?,?,?,?,?,?,?,?)',('plan-portal',cid,'Plano Conteúdo Ninja','master',json.dumps([{'name':'Posts','quantity':8,'revision_limit':2}]),'2026-10',None,1,app.now()))
  home=self.portal('home',token=token)[1]
  self.assertEqual(home['client']['product'],'Marketing');self.assertEqual(home['client']['description'],'Uma parceria feita para crescer')
  self.assertEqual(home['plan']['name'],'Plano Conteúdo Ninja');self.assertEqual(home['plan']['items'][0]['quantity'],8)
  room=home['rooms'][0];self.assertEqual(room['id'],rid)
  self.assertIn('alice',[member['id'] for member in room['members']])
  self.assertIn('client',[member['kind'] for member in room['members']])

 def test_portal_contact_receives_group_video_call_and_signals(self):
  cid,_,_,token,_=self.setup_review();rid=self.group(cid)
  with app.connect() as c:account=c.execute('SELECT id FROM portal_accounts WHERE client_id=?',(cid,)).fetchone()[0]
  rooms=self.call('/api/rooms')[1];linked=next(room for room in rooms if room['id']==rid)
  self.assertEqual(linked['portal_contacts'][0]['id'],'portal:'+account)
  created=self.call('/api/meetings','POST',{'room_id':rid,'members':['portal:'+account],'mode':'video'})
  self.assertEqual(created[0],200,created[1]);meeting=created[1]['meeting'];mid=meeting['id']
  invitation=self.portal('meetings',token=token)
  self.assertEqual(invitation[0],200,invitation[1]);self.assertEqual(invitation[1]['meetings'][0]['my_status'],'invited')
  self.assertEqual(self.portal('meetings/'+mid+'/signals',token=token)[0],403)
  self.assertEqual(self.portal('meetings/'+mid+'/action','POST',{'action':'join'},token)[0],200)
  staff=self.call('/api/meetings/'+mid)[1]['meeting']
  external=next(member for member in staff['members'] if member['external'])
  self.assertEqual(external['user_id'],'portal:'+account);self.assertEqual(external['status'],'joined')
  offer={'recipient':'portal:'+account,'kind':'offer','payload':{'type':'offer','sdp':'staff-offer'}}
  self.assertEqual(self.call('/api/meetings/'+mid+'/signals','POST',offer)[0],200)
  received=self.portal('meetings/'+mid+'/signals',token=token)[1]['signals']
  self.assertEqual(received[0]['sender'],'master');self.assertEqual(received[0]['payload']['sdp'],'staff-offer')
  answer={'recipient':'master','kind':'answer','payload':{'type':'answer','sdp':'client-answer'}}
  self.assertEqual(self.portal('meetings/'+mid+'/signals','POST',answer,token)[0],200)
  staff_signals=self.call('/api/meetings/'+mid+'/signals')[1]['signals']
  self.assertEqual(staff_signals[-1]['sender'],'portal:'+account)
  self.assertEqual(self.portal('meetings/'+mid+'/action','POST',{'action':'end'},token)[0],400)


if __name__=='__main__':unittest.main()
