import unittest,io,base64,json,time
from datetime import datetime,timedelta,timezone
import test_system
app=test_system.app

class SocialTest(unittest.TestCase):
 setUp=test_system.SystemTest.setUp
 tearDown=test_system.SystemTest.tearDown
 call=test_system.SystemTest.call
 make_task=test_system.SystemTest.make_task
 def image(self,scope,who='alice'):
  from PIL import Image
  out=io.BytesIO();Image.new('RGB',(30,20),'blue').save(out,format='PNG')
  st,r,_=self.call('/api/media','POST',{'scope':scope,'data':base64.b64encode(out.getvalue()).decode()},who=who)
  self.assertEqual(st,200,r);return r['id']
 def test_profile_self_edit_and_isolation(self):
  data={'name':'Alice NJA','birthday':'1995-03-15','thought':'<script>inert</script>','corporate_email':'alice@nja.test','hired':'2024-02-10','career':[{'date':'2024-02-10','title':'Designer','description':'Início'},{'date':'2025-02-10','title':'Líder','description':'Promoção'}]}
  self.assertEqual(self.call('/api/users/alice','PATCH',data,who='alice')[0],200)
  self.assertEqual(self.call('/api/users/bob','PATCH',data,who='alice')[0],403)
  profile=self.call('/api/profiles/alice',who='bob')[1]
  self.assertEqual(profile['birthday'],'1995-03-15');self.assertEqual(len(profile['career']),2)
  self.assertNotIn('password',profile);self.assertNotIn('email',profile)
  self.assertEqual(self.call('/api/users/alice','PATCH',{'birthday':'2025-02-30'},who='alice')[0],400)
  self.assertEqual(self.call('/api/users/alice','PATCH',{'corporate_email':'bad'},who='alice')[0],400)
 def test_presence_heartbeat_expiry_and_logout(self):
  self.assertFalse(self.call('/api/profiles/alice')[1]['online'])
  self.assertEqual(self.call('/api/presence','POST',{},who='alice')[0],200)
  self.assertTrue(self.call('/api/profiles/alice')[1]['online'])
  with app.connect() as c:c.execute('UPDATE sessions SET last_seen=? WHERE user_id=?',(time.time()-100,'alice'))
  self.assertFalse(self.call('/api/profiles/alice')[1]['online'])
  self.call('/api/presence','POST',{},who='alice');self.call('/api/logout','POST',{},who='alice')
  p=self.call('/api/profiles/alice')[1];self.assertFalse(p['online']);self.assertTrue(p['last_seen_at'])
 def test_hours_only_completed_month_and_worker(self):
  tid=self.make_task();path='/api/tasks/'+tid+'/time'
  self.assertEqual(self.call(path,'POST',{'action':'manual','minutes':90},who='alice')[0],200)
  self.assertEqual(self.call(path,'POST',{'action':'manual','minutes':30})[0],200)
  self.assertEqual(self.call('/api/profiles/alice')[1]['work_month']['seconds'],0)
  self.call('/api/tasks/'+tid,'PATCH',{'status':'done'},who='alice')
  self.assertEqual(self.call('/api/profiles/alice')[1]['work_month']['seconds'],5400)
  self.assertEqual(self.call('/api/profiles/master')[1]['work_month']['seconds'],1800)
  self.call('/api/tasks/'+tid,'PATCH',{'status':'progress'},who='alice')
  self.assertEqual(self.call('/api/profiles/alice')[1]['work_month']['seconds'],0)
  self.call('/api/tasks/'+tid,'PATCH',{'status':'done'},who='alice')
  with app.connect() as c:c.execute('UPDATE tasks SET completed=? WHERE id=?',('2020-01-01T00:00:00+00:00',tid))
  self.assertEqual(self.call('/api/profiles/alice')[1]['work_month']['seconds'],0)
 def test_timer_single_running_and_completion_stop(self):
  first=self.make_task();second=self.make_task();path='/api/tasks/'+first+'/time'
  self.assertEqual(self.call(path,'POST',{'action':'start'},who='alice')[0],200)
  self.assertEqual(self.call('/api/tasks/'+second+'/time','POST',{'action':'start'},who='alice')[0],409)
  with app.connect() as c:c.execute('UPDATE running_timers SET started=started-120 WHERE user_id=?',('alice',))
  self.assertEqual(self.call('/api/tasks/'+first,'PATCH',{'status':'done'})[0],200)
  data=self.call(path,who='alice')[1];self.assertIsNone(data['timer']);self.assertGreaterEqual(data['entries'][0]['seconds'],120)
  self.assertEqual(self.call(path,'POST',{'action':'start'},who='alice')[0],400)
  self.assertEqual(self.call(path,'POST',{'action':'manual','minutes':-1},who='alice')[0],400)
  self.assertEqual(self.call(path,who='bob')[0],403)
 def test_clients_onboarding_permissions_and_brand(self):
  data={'name':'Cliente A','entered':'2026-10-14','product':'Assessoria','checklist':[{'text':'Briefing','done':False}]}
  self.assertEqual(self.call('/api/clients','POST',data,who='alice')[0],403)
  st,c,_=self.call('/api/clients','POST',data);self.assertEqual(st,200);cid=c['id']
  self.call('/api/agency/access','POST',{'client_id':cid,'branch':'foz','members':['alice']})
  logo=self.image('client','master');cover=self.image('client','master')
  self.assertEqual(self.call('/api/clients/'+cid,'PATCH',{'photo':logo,'cover':cover,'checklist':[{'text':'Briefing','done':True}]})[0],200)
  st,r,_=self.call('/api/rooms','POST',{'kind':'group','name':'Projeto A','members':['alice']});rid=r['id']
  self.assertEqual(self.call('/api/rooms/'+rid+'/brand','PATCH',{'client_id':cid})[0],200)
  room=next(r for r in self.call('/api/rooms',who='alice')[1] if r['id']==rid)
  self.assertEqual(room['cover'],cover);self.assertEqual(room['client_id'],cid)
  self.assertTrue(self.call('/api/clients',who='alice')[1][0]['checklist'][0]['done'])
  self.assertEqual(self.call('/api/clients/'+cid,'PATCH',{'product':'Outro'},who='alice')[0],403)
 def test_posts_images_likes_comments_delete_permissions(self):
  img=self.image('post')
  self.assertEqual(self.call('/files/'+img,who='bob')[0],403)
  st,p,_=self.call('/api/posts','POST',{'text':'Equipe!','image':img},who='alice');self.assertEqual(st,200);pid=p['id']
  self.assertEqual(self.call('/files/'+img,who='bob')[0],200)
  self.call('/api/posts/'+pid+'/like','POST',{},who='bob')
  self.call('/api/posts/'+pid+'/comments','POST',{'text':'Parabéns'},who='bob')
  posts=self.call('/api/posts?user=alice',who='alice')[1];self.assertEqual(posts[0]['likes'],1);self.assertEqual(posts[0]['comments'][0]['text'],'Parabéns')
  self.assertEqual(self.call('/api/posts/'+pid,'DELETE',{},who='bob')[0],403)
  self.assertEqual(self.call('/api/posts/'+pid,'DELETE',{},who='alice')[0],200)
  self.assertEqual(self.call('/files/'+img,who='alice')[0],404)
 def test_stories_exact_expiry_and_no_profile_reuse(self):
  image=self.image('story');st,s,_=self.call('/api/stories','POST',{'text':'Hoje','image':image},who='alice');self.assertEqual(st,200)
  delta=datetime.fromisoformat(s['expires'])-datetime.now(timezone.utc);self.assertTrue(86395<delta.total_seconds()<=86400)
  self.assertEqual(len(self.call('/api/stories',who='bob')[1]),1)
  self.assertEqual(self.call('/files/'+image,who='bob')[0],200)
  self.assertEqual(self.call('/api/users/alice','PATCH',{'photo':image},who='alice')[0],400)
  self.assertEqual(self.call('/api/posts','POST',{'image':image},who='alice')[0],400)
  with app.connect() as c:
   c.execute('UPDATE stories SET expires=?',('2020-01-01T00:00:00+00:00',));c.execute('UPDATE social_assets SET expires=? WHERE file_id=?',('2020-01-01T00:00:00+00:00',image))
  self.assertEqual(self.call('/api/stories',who='alice')[1],[])
  self.assertEqual(self.call('/files/'+image,who='alice')[0],404)
 def test_reactions_room_isolation(self):
  _,r,_=self.call('/api/rooms','POST',{'kind':'group','name':'Privado','members':['alice']});rid=r['id']
  _,m,_=self.call('/api/rooms/'+rid+'/messages','POST',{'text':'🎉'},who='alice');path='/api/rooms/'+rid+'/reactions'
  self.assertEqual(self.call(path,'POST',{'message_id':m['id'],'emoji':'❤️'},who='alice')[0],200)
  self.assertEqual(len(self.call(path,who='alice')[1]),1)
  self.assertEqual(self.call(path,who='bob')[0],403)
  self.call(path,'POST',{'message_id':m['id'],'emoji':'❤️'},who='alice');self.assertEqual(self.call(path)[1],[])
 def test_revoked_social_permission_blocks_media(self):
  img=self.image('post');self.call('/api/posts','POST',{'image':img},who='alice')
  self.call('/api/roles','POST',{'id':'restricted','name':'Restrito','permissions':['tasks']})
  self.call('/api/users/bob','PATCH',{'role_id':'restricted'})
  self.assertEqual(self.call('/api/posts',who='bob')[0],403)
  self.assertEqual(self.call('/api/stories',who='bob')[0],403)
  self.assertEqual(self.call('/files/'+img,who='bob')[0],403)
 def test_migrations_are_idempotent(self):
  self.call('/api/users/alice','PATCH',{'thought':'Persistente'},who='alice');app.init();app.init()
  self.assertEqual(self.call('/api/profiles/alice')[1]['thought'],'Persistente')
  self.assertTrue('social' in self.call('/api/me',who='alice')[1]['user']['permissions'])

if __name__=='__main__':unittest.main()
