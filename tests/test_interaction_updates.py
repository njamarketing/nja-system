import unittest,io,base64
from datetime import datetime
from unittest.mock import patch
import test_system as base
import app

class InteractionTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def room(self):return self.call('/api/rooms','POST',{'kind':'direct','members':['alice']})[1]['id']
 def story(self,who='alice'):return self.call('/api/stories','POST',{'text':'Minha história'},who=who)[1]['id']
 def test_reply_scoped_to_room_and_original(self):
  rid=self.room();target=self.call('/api/rooms/'+rid+'/messages','POST',{'text':'Mensagem original'},who='alice')[1]['id']
  other=self.call('/api/rooms/general/messages','POST',{'text':'Outro grupo'})[1]['id']
  self.assertEqual(self.call('/api/rooms/'+rid+'/messages','POST',{'text':'Resposta','reply_to':other})[0],404)
  r=self.call('/api/rooms/'+rid+'/messages','POST',{'text':'Resposta','reply_to':target});self.assertEqual(r[0],200)
  rows=self.call('/api/rooms/'+rid+'/messages',who='alice')[1]['messages'];self.assertEqual(rows[-1]['reply']['text'],'Mensagem original');self.assertEqual(rows[-1]['reply']['name'],'Alice')
  self.assertEqual(self.call('/api/rooms/'+rid+'/messages',who='bob')[0],403)
  self.assertEqual(self.call('/api/rooms/'+rid+'/messages','POST',{'text':'Resposta','reply_to':[]})[0],400)
 def test_reactions_toggle_file_reply_and_outsiders(self):
  rid=self.room();url='/api/rooms/'+rid
  mid=self.call(url+'/messages','POST',{'text':'Olá'})[1]['id']
  payload={'target_id':mid,'emoji':'❤️','kind':'message'}
  self.assertEqual(self.call(url+'/interactions','POST',payload,who='alice')[0],200)
  self.assertEqual(self.call(url+'/interactions',who='alice')[1]['reactions'][0]['emoji'],'❤️')
  self.call(url+'/interactions','POST',payload,who='alice');self.assertEqual(self.call(url+'/interactions')[1]['reactions'],[])
  self.assertEqual(self.call(url+'/interactions','POST',payload,who='bob')[0],403)
  with app.connect() as c:c.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?)',('attachment1','Pauta.pdf','application/pdf',10,'master',None,rid,app.now()))
  payload={'target_id':'attachment1','emoji':'👍','kind':'file'}
  self.assertEqual(self.call(url+'/interactions','POST',payload,who='alice')[0],200)
  self.assertEqual(self.call(url+'/messages','POST',{'text':'Sobre a pauta','reply_to':'attachment1','reply_kind':'file'},who='alice')[0],200)
  self.assertEqual(self.call(url+'/messages')[1]['messages'][-1]['reply']['text'],'Pauta.pdf')
  self.assertEqual(self.call(url+'/interactions')[1]['reactions'][0]['kind'],'file')
 def test_group_readonly_cannot_reply_or_react(self):
  rid=self.call('/api/rooms','POST',{'kind':'group','name':'Grupo','members':['alice']})[1]['id'];url='/api/rooms/'+rid
  mid=self.call(url+'/messages','POST',{'text':'Pauta'})[1]['id']
  self.call(url,'PATCH',{'send_policy':'managers'})
  self.assertEqual(self.call(url+'/interactions','POST',{'target_id':mid,'emoji':'👍'},who='alice')[0],403)
  self.assertEqual(self.call(url+'/reactions','POST',{'message_id':mid,'emoji':'👍'},who='alice')[0],403)
  self.assertEqual(self.call(url+'/messages','POST',{'text':'Oi','reply_to':mid},who='alice')[0],403)
 def test_message_receipts_delivery_read_and_personal_chat_deletion(self):
  rid=self.room();url='/api/rooms/'+rid
  mid=self.call(url+'/messages','POST',{'text':'Você recebeu?'})[1]['id']
  before=self.call(url+'/messages')[1]['messages'][-1]
  self.assertIsNone(before['receipts'][0]['delivered_at']);self.assertIsNone(before['receipts'][0]['read_at'])
  self.call(url+'/messages',who='alice')
  delivered=self.call(url+'/messages')[1]['messages'][-1]['receipts'][0]
  self.assertIsNotNone(delivered['delivered_at']);self.assertIsNone(delivered['read_at'])
  self.call(url+'/read','POST',{},who='alice')
  viewed=self.call(url+'/messages')[1]['messages'][-1]['receipts'][0]
  self.assertIsNotNone(viewed['read_at']);self.assertEqual(viewed['user_id'],'alice')
  self.assertEqual(self.call(url,'DELETE',{})[0],200)
  self.assertNotIn(rid,[r['id'] for r in self.call('/api/rooms')[1]])
  self.assertIn(rid,[r['id'] for r in self.call('/api/rooms',who='alice')[1]])
  self.call(url+'/messages','POST',{'text':'A conversa voltou'},who='alice')
  self.assertIn(rid,[r['id'] for r in self.call('/api/rooms')[1]])
  self.assertEqual(self.call('/api/rooms/general','DELETE',{})[0],400)
 def test_deferred_ai_marks_pending_without_waiting_for_provider(self):
  rid=self.call('/api/ai/room','POST',{})[1]['id']
  result=self.call('/api/rooms/'+rid+'/messages','POST',{'text':'Crie uma ideia','defer_ai':True})
  self.assertEqual(result[0],200);self.assertTrue(result[1]['ai_pending'])
  self.assertEqual(len(self.call('/api/rooms/'+rid+'/messages')[1]['messages']),1)
 def test_story_viewers_are_private_even_from_master(self):
  sid=self.story();url='/api/stories/'+sid
  self.call(url+'/view','POST',{},who='alice');self.call(url+'/view','POST',{},who='bob');self.call(url+'/view','POST',{},who='bob')
  st,data,_=self.call(url+'/viewers',who='alice');self.assertEqual(st,200);self.assertEqual(data['count'],1);self.assertEqual(data['viewers'][0]['user_id'],'bob')
  self.assertEqual(self.call(url+'/viewers',who='master')[0],403);self.assertEqual(self.call(url+'/viewers',who='bob')[0],403)
  self.assertNotIn('viewers',self.call('/api/stories',who='bob')[1][0])
  with app.connect() as c:c.execute("UPDATE stories SET expires='2000-01-01T00:00:00+00:00' WHERE id=?",(sid,))
  self.assertEqual(self.call(url+'/view','POST',{},who='bob')[0],410)
  self.assertEqual(self.call(url, 'DELETE',{},who='alice')[0],200)
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM story_views').fetchone()[0],0)
 def sale(self,seller,amount):
  with app.connect() as c:c.execute("UPDATE users SET role_id='sales' WHERE id=?",(seller,))
  lead=self.call('/api/business/leads','POST',{'name':'Cliente '+seller+' '+app.uid(),'owner':seller,'product':'Site'})[1]['id']
  self.assertEqual(self.call('/api/business/leads/'+lead+'/convert','POST',{},who=seller)[0],200)
  r=self.call('/api/sales','POST',{'lead_id':lead,'amount':amount,'sold_on':datetime.now(app.TZ).date().isoformat()},who=seller);self.assertEqual(r[0],200,r);return r[1]['id']
 def test_sale_events_all_staff_minimal_data_and_new_leader(self):
  baseline=self.call('/api/celebrations',who='bob')[1];self.assertEqual(baseline,{'cursor':0,'items':[]})
  sale1=self.sale('alice','100');sale2=self.sale('bob','200')
  with app.connect() as c:c.execute("UPDATE users SET role_id='member' WHERE id='bob'")
  self.assertEqual(self.call('/api/sales/ranking',who='bob')[0],403)
  events=self.call('/api/celebrations?after=0',who='bob')[1];self.assertEqual(len(events['items']),2)
  self.assertTrue(events['items'][0]['assumed_first']);self.assertTrue(events['items'][1]['assumed_first']);self.assertEqual(events['items'][1]['position'],1)
  for row in events['items']:
   for key in ['amount','lead_id','client_id','sale_id']:self.assertNotIn(key,row)
  self.assertEqual(self.call('/api/celebrations?after='+str(events['cursor']))[1]['items'],[])
  self.call('/api/sales/'+sale2,'PATCH',{'status':'cancelled'})
  self.assertEqual(len(self.call('/api/celebrations?after=0')[1]['items']),1)
  self.assertEqual(self.call('/api/celebrations?after=bad')[0],400)
  self.assertEqual(self.call('/api/celebrations',login=False)[0],401)
 def test_second_sale_by_leader_does_not_announce_new_podium(self):
  self.sale('alice','100');self.sale('alice','50')
  items=self.call('/api/celebrations?after=0')[1]['items'];self.assertFalse(items[-1]['assumed_first']);self.assertEqual(items[-1]['position'],1)
