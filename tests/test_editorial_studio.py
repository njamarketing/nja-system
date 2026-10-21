import gc,io,json,secrets,unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from PIL import Image
import test_system as base
import test_attachments
import app,agency_editorial


class EditorialStudioTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 call=base.SystemTest.call
 raw=test_attachments.AttachmentTest.raw
 send=test_attachments.AttachmentTest.send
 def tearDown(self):
  gc.collect();base.SystemTest.tearDown(self)
 def account(self,platform='facebook'):
  cid=self.call('/api/clients','POST',{'name':'Cliente Studio','entered':'2026-10-01','product':'Marketing'})[1]['id']
  aid=self.call('/api/agency/editorial/accounts','POST',{'client_id':cid,'name':'Conta Studio','platform':platform,'target':'123','token':'test-secret'})[1]['id']
  with app.connect() as c:c.execute('UPDATE social_accounts SET verified=? WHERE id=?',(app.now(),aid))
  return cid,aid
 def payload(self,cid,aid,**changes):
  return {'client_id':cid,'account_id':aid,'title':'Ideia direta','caption':'Uma legenda','format':'text','file_ids':[],'mode':'draft','nonce':secrets.token_hex(16),**changes}
 def image(self,cid,color='red'):
  out=io.BytesIO();Image.new('RGB',(50,50),color).save(out,format='PNG')
  status,result,_=self.send('imagem.png',out.getvalue(),{'editorial_client_id':cid},who='master')
  self.assertEqual(status,200,result);self.assertEqual(result['mime'],'image/jpeg');return result['id']
 def test_direct_text_needs_no_task_or_approval_and_is_idempotent(self):
  cid,aid=self.account();payload=self.payload(cid,aid,mode='now')
  status,result,_=self.call('/api/agency/editorial/direct','POST',payload);self.assertEqual(status,200,result)
  status,retry,_=self.call('/api/agency/editorial/direct','POST',payload);self.assertEqual(status,200,retry);self.assertEqual(result['id'],retry['id'])
  with patch.object(agency_editorial,'graph',return_value={'id':'published'}) as graph:
   agency_editorial.tick(app);agency_editorial.tick(app);self.assertEqual(graph.call_count,1)
   self.assertEqual(graph.call_args.args[2],'123/feed');self.assertEqual(graph.call_args.args[3],{'message':'Uma legenda'})
  post=self.call('/api/agency/editorial/posts/'+result['id'])[1];self.assertEqual(post['status'],'published');self.assertEqual(post['source'],'direct')
  with app.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM tasks').fetchone()[0],0)
  self.assertEqual(self.call('/api/agency/editorial')[1]['reviews'],[])
  self.assertEqual(self.call('/api/agency/reviews')[1]['items'],[])
 def test_upload_client_scope_and_image_conversion(self):
  cid,aid=self.account();fid=self.image(cid)
  self.assertEqual(self.raw('/files/'+fid,who='master')[0],200)
  self.assertEqual(self.raw('/files/'+fid,who='bob')[0],403)
  self.assertEqual(self.send('bad.png',b'bad',{'editorial_client_id':cid},who='master')[0],400)
  self.assertEqual(self.send('bad.pdf',b'%PDF-1.7',{'editorial_client_id':cid},who='master')[0],400)
  self.assertEqual(self.send('bad.mp4',b'\0\0\0\x18ftypisom',{'editorial_client_id':cid},who='bob')[0],403)
  self.assertEqual(self.call('/api/users/master','PATCH',{'photo':fid})[0],400)
  data=self.call('/api/agency/editorial')[1];self.assertEqual(data['uploads'][0]['client_id'],cid)
  other,otheraid=self.account()
  self.assertEqual(self.call('/api/agency/editorial/direct','POST',self.payload(other,otheraid,format='image',file_ids=[fid]))[0],400)
  self.assertEqual(self.call('/api/agency/editorial/direct','POST',self.payload(other,aid))[0],400)
 def test_schedule_media_edit_snapshot_and_preview(self):
  cid,aid=self.account();fid=self.image(cid);schedule=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
  payload=self.payload(cid,aid,format='image',file_ids=[fid],mode='schedule',scheduled=schedule)
  with patch.object(app,'ORIGIN','https://studio.example'):
   status,result,_=self.call('/api/agency/editorial/direct','POST',payload)
  self.assertEqual(status,200,result);url='/api/agency/editorial/posts/'+result['id']
  old=self.call(url)[1];self.assertEqual(old['files'][0]['id'],fid)
  status,result,_=self.call(url,'PATCH',self.payload(cid,aid,format='image',file_ids=[fid],caption='Legenda revisada'))
  self.assertEqual(status,200,result);updated=self.call(url)[1]
  self.assertEqual(updated['caption'],'Legenda revisada');self.assertEqual(updated['status'],'draft');self.assertNotEqual(old['version_id'],updated['version_id'])
  with app.connect() as c:self.assertEqual(c.execute('SELECT caption FROM creative_versions WHERE id=?',(old['version_id'],)).fetchone()[0],'Uma legenda')
  with patch.object(agency_editorial,'graph') as graph:agency_editorial.tick(app);graph.assert_not_called()
 def test_carousel_order_and_integrity(self):
  cid,aid=self.account('instagram');first=self.image(cid);second=self.image(cid,'blue')
  status,result,_=self.call('/api/agency/editorial/direct','POST',self.payload(cid,aid,format='carousel',file_ids=[second,first]))
  self.assertEqual(status,200,result);p=self.call('/api/agency/editorial/posts/'+result['id'])[1];self.assertEqual([f['id'] for f in p['files']],[second,first])
  with app.connect() as c:
   row=c.execute('SELECT * FROM editorial_posts WHERE id=?',(p['id'],)).fetchone();agency_editorial.approved(app,c,row)
   (app.DATA/'uploads'/first).write_bytes(b'changed')
   with self.assertRaises(app.Error):agency_editorial.approved(app,c,row)
 def test_facebook_video_payload_and_protected_range(self):
  cid,aid=self.account();video=b'\0\0\0\x18ftypisom\0\0\0\0isommp42'
  status,f,_=self.send('video.mp4',video,{'editorial_client_id':cid},who='master');self.assertEqual(status,200,f)
  status,body,headers=self.raw('/files/'+f['id'],who='master',headers={'HTTP_RANGE':'bytes=0-7'});self.assertEqual(status,206);self.assertEqual(body,video[:8])
  with patch.object(app,'ORIGIN','https://studio.example'):
   status,result,_=self.call('/api/agency/editorial/direct','POST',self.payload(cid,aid,format='video',file_ids=[f['id']],mode='now'))
  self.assertEqual(status,200,result)
  with patch.object(agency_editorial,'graph',return_value={'id':'v123'}) as graph:
   agency_editorial.tick(app);self.assertEqual(graph.call_args.args[2],'123/videos');self.assertIn('file_url',graph.call_args.args[3]);self.assertEqual(graph.call_args.args[3]['description'],'Uma legenda')
 def test_validation_permissions_and_unverified_account(self):
  cid,aid=self.account()
  for fields in [{'format':'reel'},{'caption':''},{'file_ids':['missing']},{'caption':'x'*2201},{'mode':'bad'},{'mode':'schedule','scheduled':app.now()},{'file_ids':[{}]},{'nonce':'bad'}]:
   self.assertEqual(self.call('/api/agency/editorial/direct','POST',self.payload(cid,aid,**fields))[0],400,fields)
  self.assertEqual(self.call('/api/agency/editorial/direct','POST',self.payload(cid,aid),who='bob')[0],403)
  with app.connect() as c:c.execute('UPDATE social_accounts SET verified=NULL WHERE id=?',(aid,))
  self.assertEqual(self.call('/api/agency/editorial/direct','POST',self.payload(cid,aid,mode='now'))[0],409)
  self.assertEqual(self.call('/api/agency/editorial/direct','POST',self.payload(cid,aid))[0],200)
 def test_instagram_reel_uses_two_phase_publishing(self):
  cid,aid=self.account('instagram');video=b'\0\0\0\x18ftypisom\0\0\0\0isommp42'
  status,f,_=self.send('reel.mp4',video,{'editorial_client_id':cid},who='master');self.assertEqual(status,200)
  with patch.object(app,'ORIGIN','https://studio.example'):
   status,result,_=self.call('/api/agency/editorial/direct','POST',self.payload(cid,aid,format='reel',file_ids=[f['id']],mode='now'))
  self.assertEqual(status,200,result)
  with patch.object(agency_editorial,'graph',return_value={'id':'container'}) as graph:
   agency_editorial.tick(app);self.assertEqual(graph.call_args.args[2],'123/media');self.assertEqual(graph.call_args.args[3]['media_type'],'REELS')
  p=self.call('/api/agency/editorial/posts/'+result['id'])[1];self.assertEqual(p['status'],'processing')
  self.assertEqual(self.call('/api/agency/editorial/posts/'+p['id'],'PATCH',self.payload(cid,aid,format='reel',file_ids=[f['id']]))[0],409)
  with app.connect() as c:c.execute('UPDATE editorial_posts SET updated=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat(),p['id']))
  with patch.object(agency_editorial,'graph',side_effect=[{'status_code':'FINISHED'},{'id':'published-reel'}]) as graph:
   agency_editorial.tick(app);self.assertEqual(graph.call_count,2);self.assertEqual(graph.call_args.args[2],'123/media_publish')
  self.assertEqual(self.call('/api/agency/editorial/posts/'+p['id'])[1]['status'],'published')
 def test_direct_editor_without_task_or_approval_permissions(self):
  cid,aid=self.account();role=self.call('/api/roles','POST',{'name':'Editor Studio','permissions':['editorial','editorial_manage']})[1]['id']
  self.call('/api/users/alice','PATCH',{'role_id':role})
  self.call('/api/agency/access','POST',{'client_id':cid,'branch':'foz','members':['alice']})
  status,result,_=self.call('/api/agency/editorial/direct','POST',self.payload(cid,aid),who='alice');self.assertEqual(status,200,result)
  self.assertEqual(self.call('/api/agency/editorial/posts/'+result['id'],who='alice')[0],200)
  self.assertEqual(self.call('/api/agency/editorial/posts/'+result['id'],who='bob')[0],403)
  self.assertEqual(self.call('/api/tasks',who='alice')[0],403)
  self.assertEqual(self.call('/api/agency/reviews',who='alice')[0],403)
