import base64,io,json,os,tempfile,sys,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,scheduler

class SystemTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();app.DATA=Path(self.temp.name);app.DB=app.DATA/'nja.sqlite3';app.init();self.cookies={};self.csrf={}
  with app.connect() as c:
   for id,master in [('master',1),('alice',0),('bob',0)]:
    c.execute('INSERT INTO users(id,email,name,password,role_id,master,created) VALUES(?,?,?,?,?,?,?)',(id,id+'@nja.test',id.title(),app.hash_password('Testing-Strong-123'),'master' if master else 'member',master,app.now()));c.execute('INSERT INTO room_members(room_id,user_id) VALUES(?,?)',('general',id))
  for id in ['master','alice','bob']:
   status,r,h=self.call('/api/login','POST',{'email':id+'@nja.test','password':'Testing-Strong-123'},login=False)
   self.assertEqual(status,200);self.cookies[id]=dict(h)['Set-Cookie'].split(';')[0];self.csrf[id]=r['csrf']
 def tearDown(self):self.temp.cleanup()
 def call(self,path,method='GET',data=None,who='master',login=True,csrf=True,origin=None):
  body=json.dumps(data or {}).encode();env={'REQUEST_METHOD':method,'PATH_INFO':path.split('?')[0],'QUERY_STRING':path.partition('?')[2],'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body),'REMOTE_ADDR':'127.0.0.1'}
  if login:env['HTTP_COOKIE']=self.cookies.get(who,'');env['HTTP_X_CSRF_TOKEN']=self.csrf.get(who,'') if csrf else ''
  if origin:env['HTTP_ORIGIN']=origin
  capture={}
  def start(status,headers):capture.update(status=int(status.split()[0]),headers=headers)
  raw=b''.join(app.application(env,start));ctype=dict(capture['headers'])['Content-Type'];result=json.loads(raw) if 'application/json' in ctype else raw
  return capture['status'],result,capture['headers']
 def make_task(self,owner='alice',**kw):
  st,r,_=self.call('/api/tasks','POST',{'title':'Entrega cliente','owner':owner,**kw});self.assertEqual(st,200);return r['id']
 def test_group_identity_and_image_permissions(self):
  from PIL import Image
  st,r,_=self.call('/api/rooms','POST',{'kind':'group','name':'Cliente Teste','members':['alice'],'project':'Projeto Teste','description':'Entregas do cliente'})
  self.assertEqual(st,200);rid=r['id'];out=io.BytesIO();Image.new('RGB',(20,20),'blue').save(out,format='PNG')
  payload={'room_id':rid,'room_photo':True,'name':'logo.png','data':base64.b64encode(out.getvalue()).decode()}
  self.assertEqual(self.call('/api/upload','POST',payload,who='alice')[0],403)
  self.assertEqual(self.call('/api/upload','POST',payload,who='bob')[0],403)
  st,img,_=self.call('/api/upload','POST',payload);self.assertEqual(st,200)
  rooms=self.call('/api/rooms')[1];room=next(x for x in rooms if x['id']==rid)
  self.assertEqual(room['photo'],img['id']);self.assertEqual(room['project'],'Projeto Teste')
  self.assertEqual(self.call('/api/rooms/'+rid+'/messages')[1]['files'],[])
  self.assertEqual(self.call('/files/'+img['id'],who='alice')[0],200)
  self.assertEqual(self.call('/files/'+img['id'],who='bob')[0],403)
  self.assertEqual(self.call('/api/rooms/'+rid,'PATCH',{'description':'Nova descrição'})[0],200)
  self.assertEqual(self.call('/api/rooms/'+rid+'/messages',who='alice')[0],200)
 def test_profile_cover_owner_and_persistence(self):
  from PIL import Image
  out=io.BytesIO();Image.new('RGB',(20,20),'blue').save(out,format='PNG')
  st,img,_=self.call('/api/upload','POST',{'photo':True,'name':'capa.png','data':base64.b64encode(out.getvalue()).decode()},who='alice')
  self.assertEqual(st,200)
  self.assertEqual(self.call('/api/users/alice','PATCH',{'cover':img['id']},who='alice')[0],200)
  self.assertEqual(self.call('/api/users/bob','PATCH',{'cover':img['id']})[0],400)
  app.init();self.assertEqual(self.call('/api/me',who='alice')[1]['user']['cover'],img['id'])
 def test_login_and_hash(self):
  st,_,_=self.call('/api/login','POST',{'email':'alice@nja.test','password':'wrong'},login=False);self.assertEqual(st,401)
  with app.connect() as c:self.assertNotIn('Testing',c.execute('SELECT password FROM users LIMIT 1').fetchone()[0])
  self.assertEqual(self.call('/api/tasks',login=False)[0],401)
 def test_csrf_and_origin(self):
  self.assertEqual(self.call('/api/tasks','POST',{'title':'x'},csrf=False)[0],403)
  self.assertEqual(self.call('/api/login','POST',{'email':'x','password':'x'},login=False,origin='https://evil.test')[0],403)
 def test_task_visibility_and_permissions(self):
  id=self.make_task();self.assertEqual(self.call('/api/tasks/'+id,who='bob')[0],403)
  self.assertEqual(len(self.call('/api/tasks',who='bob')[1]),0)
  self.assertEqual(self.call('/api/tasks/'+id,'PATCH',{'owner':'bob'},who='alice')[0],403)
  self.assertEqual(self.call('/api/tasks/'+id,'PATCH',{'status':'done'},who='alice')[0],200)
  self.assertEqual(self.call('/api/tasks/'+id)[1]['status'],'done')
 def test_approval_and_checklist(self):
  id=self.make_task();self.call('/api/tasks/'+id,'PATCH',{'status':'approval','checklist':[{'text':'Revisar','done':False}]},who='alice')
  self.assertEqual(self.call('/api/tasks/'+id,'PATCH',{'status':'done'},who='alice')[0],403)
  self.assertEqual(self.call('/api/tasks/'+id,'PATCH',{'status':'done'})[0],200)
  self.assertTrue(self.call('/api/tasks/'+id)[1]['history'])
 def test_comments_and_subtasks(self):
  id=self.make_task();self.assertEqual(self.call('/api/tasks/'+id+'/comments','POST',{'text':'Revisado'},who='alice')[0],200)
  self.assertEqual(self.call('/api/tasks/'+id)[1]['comments'][0]['text'],'Revisado')
  sub=self.make_task(parent=id);self.assertEqual(self.call('/api/tasks/'+sub)[1]['parent'],id)
 def test_user_admin_and_deactivation(self):
  data={'name':'Carol','email':'carol@nja.test','password':'Testing-Strong-123','role_id':'member'}
  self.assertEqual(self.call('/api/users','POST',data,who='alice')[0],403)
  self.assertEqual(self.call('/api/users','POST',data)[0],200)
  self.assertEqual(self.call('/api/users/master','PATCH',{'active':False})[0],400)
  self.call('/api/users/alice','PATCH',{'active':False});self.assertEqual(self.call('/api/me',who='alice')[0],401)
 def test_custom_role_revocation(self):
  st,r,_=self.call('/api/roles','POST',{'name':'Consulta','permissions':['dashboard','team']});self.assertEqual(st,200)
  self.call('/api/users/alice','PATCH',{'role_id':r['id']});self.assertEqual(self.call('/api/tasks',who='alice')[0],403)
  self.assertEqual(self.call('/api/roles','POST',{'name':'Evil','permissions':['task_all']},who='alice')[0],403)
 def test_calendar_acl_dates_and_recurrence(self):
  start=datetime.now(timezone.utc)+timedelta(hours=1);end=start+timedelta(hours=1)
  data={'title':'Reunião','start':start.isoformat(),'end':end.isoformat(),'members':['alice'],'recurrence':'weekly','until_date':(start+timedelta(days=30)).isoformat()}
  st,r,_=self.call('/api/events','POST',data);self.assertEqual(st,200)
  self.assertEqual(len(self.call('/api/events',who='alice')[1]),1);self.assertEqual(len(self.call('/api/events',who='bob')[1]),0)
  self.assertEqual(self.call('/api/events/'+r['id'],'DELETE',{},who='alice')[0],403)
  self.assertEqual(self.call('/api/events','POST',{**data,'end':start.isoformat()})[0],400)
  e=self.call('/api/events')[1][0];self.assertEqual(len(list(scheduler.occurrences(e,start-timedelta(days=1),start+timedelta(days=30)))),5)
 def test_chats_isolation_and_membership(self):
  st,r,_=self.call('/api/rooms','POST',{'kind':'direct','members':['alice']});self.assertEqual(st,200);id=r['id']
  self.assertEqual(self.call('/api/rooms/'+id+'/messages',who='bob')[0],403)
  self.call('/api/rooms/'+id+'/messages','POST',{'text':'Olá'},who='alice');self.assertEqual(self.call('/api/rooms/'+id+'/messages')[1]['messages'][0]['text'],'Olá')
  st,g,_=self.call('/api/rooms','POST',{'kind':'group','name':'Projeto','members':['alice']});self.call('/api/rooms/'+g['id'],'PATCH',{'members':['bob']})
  self.assertEqual(self.call('/api/rooms/'+g['id']+'/messages',who='alice')[0],403)
 def test_upload_authorization_and_file_types(self):
  id=self.make_task();data={'task_id':id,'name':'documento.pdf','data':base64.b64encode(b'%PDF-1.4\nTest').decode()}
  self.assertEqual(self.call('/api/upload','POST',data,who='bob')[0],403)
  st,r,_=self.call('/api/upload','POST',data,who='alice');self.assertEqual(st,200)
  self.assertEqual(self.call('/files/'+r['id'],who='bob')[0],403)
  self.assertEqual(self.call('/files/'+r['id'],who='alice')[0],200)
  self.assertEqual(self.call('/api/upload','POST',{**data,'data':base64.b64encode(b'<script>evil</script>').decode()})[0],400)
 def test_metrics_actual_data(self):
  id=self.make_task();self.call('/api/tasks/'+id,'PATCH',{'status':'done'})
  r=self.call('/api/metrics',who='alice')[1];self.assertEqual(len(r['users']),1);self.assertEqual(r['users'][0]['percent'],100)
  self.assertEqual(self.call('/api/metrics?days=999')[0],400)
 def test_reminders_deduplicated(self):
  self.make_task(due=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat());scheduler.tick();scheduler.tick()
  with app.connect() as c:self.assertEqual(c.execute("SELECT count(*) FROM reminder_log WHERE key LIKE 'task:%'").fetchone()[0],2)
  self.assertEqual(len(self.call('/api/notifications',who='alice')[1]),2) # assignment + late
 def test_event_on_time_reminder(self):
  start=datetime.now(timezone.utc)-timedelta(seconds=10);end=start+timedelta(hours=1)
  self.call('/api/events','POST',{'title':'Agora','start':start.isoformat(),'end':end.isoformat(),'reminder':0,'members':['alice']});scheduler.tick()
  self.assertTrue(any(n['title']=='Compromisso se aproximando' for n in self.call('/api/notifications',who='alice')[1]))
 def test_password_invalidation_and_reset(self):
  self.call('/api/users/alice','PATCH',{'password':'New-Strong-12345'});self.assertEqual(self.call('/api/me',who='alice')[0],401)
  with app.connect() as c:c.execute('INSERT INTO resets VALUES(?,?,?)',(app.digest('reset-token'),'bob',__import__('time').time()+300))
  self.assertEqual(self.call('/api/reset','POST',{'token':'reset-token','password':'Other-Strong-12345'},login=False)[0],200)
  self.assertEqual(self.call('/api/reset','POST',{'token':'reset-token','password':'Other-Strong-12345'},login=False)[0],400)
  self.assertEqual(self.call('/api/me',who='bob')[0],401)
 def test_offline_shell_and_headers(self):
  for path in ['/','/manifest.webmanifest','/sw.js','/icon-192.png','/app.js']:
   st,r,h=self.call(path,login=False);self.assertEqual(st,200);self.assertEqual(dict(h)['X-Content-Type-Options'],'nosniff')
  manifest=json.loads(self.call('/manifest.webmanifest')[1]);self.assertEqual(manifest['display'],'standalone')
  sw=self.call('/sw.js')[1].decode();self.assertIn("url.pathname.startsWith('/api/')",sw);self.assertIn("url.pathname.startsWith('/files/')",sw)
 def test_sqlite_restart_persistence(self):
  id=self.make_task();app.init();self.assertEqual(self.call('/api/tasks/'+id)[1]['title'],'Entrega cliente')

if __name__=='__main__':unittest.main()
