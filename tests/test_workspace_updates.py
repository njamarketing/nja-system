import unittest,json,base64,io
import test_system as base
app=base.app
class WorkspaceTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def client(self):return self.call('/api/clients','POST',{'name':'Marca teste','entered':'2026-10-01','product':'Marketing'})[1]['id']
 def test_master_email_and_logical_deletion(self):
  self.assertEqual(self.call('/api/users/alice','PATCH',{'email':'new@example.test'},who='alice')[0],403)
  self.assertEqual(self.call('/api/users/alice','PATCH',{'email':'bob@nja.test'})[0],409)
  self.assertEqual(self.call('/api/users/alice','PATCH',{'email':'new@example.test'})[0],200)
  self.assertEqual(self.call('/api/me',who='alice')[0],401)
  self.assertEqual(self.call('/api/login','POST',{'email':'new@example.test','password':'Testing-Strong-123'},login=False)[0],200)
  self.assertEqual(self.call('/api/users/master','DELETE',{})[0],400)
  self.assertEqual(self.call('/api/users/bob','DELETE',{},who='bob')[0],403)
  self.assertEqual(self.call('/api/users/bob','DELETE',{})[0],200)
  self.assertEqual(self.call('/api/me',who='bob')[0],401)
  self.assertNotIn('bob',[r['id'] for r in self.call('/api/users')[1]])
  self.assertEqual(self.call('/api/users/bob','PATCH',{'active':True})[0],404)
  with app.connect() as c:self.assertIsNotNone(c.execute('SELECT id FROM users WHERE id=?',('bob',)).fetchone())
 def test_brand_permissions_original_file_and_palette(self):
  cid=self.client();path='/api/clients/'+cid+'/brand'
  self.assertEqual(self.call(path,who='bob')[0],403)
  self.assertEqual(self.call(path,'PATCH',{'colors':['red'],'drive_url':''})[0],400)
  self.assertEqual(self.call(path,'PATCH',{'colors':[],'drive_url':'https://evil.test'})[0],400)
  self.assertEqual(self.call(path,'PATCH',{'colors':['#12ABEF'],'drive_url':'https://drive.google.com/drive/folders/example'})[0],200)
  from PIL import Image
  out=io.BytesIO();Image.new('RGBA',(10,10),(0,0,0,0)).save(out,format='PNG');encoded=base64.b64encode(out.getvalue()).decode()
  st,r,_=self.call(path,'POST',{'name':'logo.png','data':encoded});self.assertEqual(st,200,r)
  self.assertEqual(self.call(path+'/'+r['id'])[1]['data'],encoded)
  other=self.client();self.assertEqual(self.call('/api/clients/'+other+'/brand/'+r['id'])[0],404)
  self.assertEqual(self.call(path+'/'+r['id'],'DELETE',{})[0],200)
 def test_edit_post_and_reply_parent_same_post(self):
  pid=self.call('/api/posts','POST',{'text':'Original'},who='alice')[1]['id']
  self.assertEqual(self.call('/api/posts/'+pid,'PATCH',{'text':'Forjado'},who='bob')[0],403)
  self.assertEqual(self.call('/api/posts/'+pid,'PATCH',{'text':'Editado'},who='alice')[0],200)
  self.call('/api/posts/'+pid+'/comments','POST',{'text':'Comentário'},who='bob')
  post=next(p for p in self.call('/api/posts')[1] if p['id']==pid);parent=post['comments'][0]['id']
  self.assertEqual(self.call('/api/posts/'+pid+'/comments','POST',{'text':'Resposta','parent_id':parent},who='alice')[0],200)
  other=self.call('/api/posts','POST',{'text':'Outro'})[1]['id']
  self.assertEqual(self.call('/api/posts/'+other+'/comments','POST',{'text':'Errado','parent_id':parent})[0],400)
  post=next(p for p in self.call('/api/posts')[1] if p['id']==pid);self.assertEqual(post['text'],'Editado');self.assertEqual(post['comments'][1]['parent_id'],parent)
 def test_story_reply_reuses_direct_room(self):
  sid=self.call('/api/stories','POST',{'text':'Meu story'},who='alice')[1]['id'];path='/api/stories/'+sid+'/reply'
  st,r,_=self.call(path,'POST',{'text':'Gostei'},who='bob');self.assertEqual(st,200,r);rid=r['room_id']
  self.assertEqual(self.call(path,'POST',{'text':'❤️'},who='bob')[1]['room_id'],rid)
  messages=self.call('/api/rooms/'+rid+'/messages',who='alice')[1]['messages'];self.assertEqual(len(messages),2);self.assertIn('Meu story',messages[0]['text'])
  self.assertEqual(self.call('/api/rooms/'+rid+'/messages')[0],403)
  with app.connect() as c:c.execute("UPDATE stories SET expires='2000-01-01T00:00:00+00:00' WHERE id=?",(sid,))
  self.assertEqual(self.call(path,'POST',{'text':'Expirou'},who='bob')[0],404)
