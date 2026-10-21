import unittest,os,gc
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
import test_system as base
import app,agency_editorial
class EditorialTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 def tearDown(self):
  gc.collect()  # Release SQLite connections before removing the database on Windows.
  base.SystemTest.tearDown(self)
 call=base.SystemTest.call
 def draft(self):
  cid=self.call('/api/clients','POST',{'name':'Editorial','entered':'2026-10-01','product':'Marketing'})[1]['id']
  aid=self.call('/api/agency/editorial/accounts','POST',{'client_id':cid,'name':'Página','platform':'facebook','target':'123','token':'secret-test'})[1]['id']
  rid=self.call('/api/agency/reviews','POST',{'client_id':cid,'title':'Texto'})[1]['id']
  vid=self.call('/api/agency/reviews/'+rid+'/versions','POST',{'caption':'Legenda aprovada'})[1]['id']
  pid=self.call('/api/agency/editorial/posts','POST',{'account_id':aid,'version_id':vid,'title':'Post','format':'text','scheduled':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()})[1]['id']
  return cid,aid,rid,vid,pid
 def test_approval_and_verification_required(self):
  cid,aid,rid,vid,pid=self.draft();url='/api/agency/editorial/posts/'+pid+'/schedule'
  self.assertEqual(self.call(url,'POST')[0],409)
  self.call('/api/agency/reviews/'+rid+'/feedback','POST',{'version_id':vid,'decision':'approved'})
  self.assertEqual(self.call(url,'POST')[0],409)
  with patch.object(agency_editorial,'graph',return_value={'id':'123'}):self.assertEqual(self.call('/api/agency/editorial/accounts/'+aid+'/verify','POST')[0],200)
  self.assertEqual(self.call(url,'POST')[0],200)
  self.call('/api/agency/reviews/'+rid+'/versions','POST',{'caption':'Alterada'})
  with app.connect() as c:c.execute("UPDATE editorial_posts SET scheduled=? WHERE id=?",(app.now(),pid))
  with patch.object(agency_editorial,'graph') as graph:agency_editorial.tick(app);graph.assert_not_called()
  self.assertEqual(self.call('/api/agency/editorial')[1]['posts'][0]['status'],'blocked')
 def test_publish_once_and_credentials_not_exposed(self):
  cid,aid,rid,vid,pid=self.draft()
  self.call('/api/agency/reviews/'+rid+'/feedback','POST',{'version_id':vid,'decision':'approved'})
  with app.connect() as c:c.execute('UPDATE social_accounts SET verified=?',(app.now(),));c.execute("UPDATE editorial_posts SET status='scheduled',scheduled=?",(app.now(),));secret=c.execute('SELECT secret FROM social_accounts').fetchone()[0]
  self.assertNotIn('secret-test',secret)
  with patch.object(agency_editorial,'graph',return_value={'id':'post123'}) as graph:agency_editorial.tick(app);agency_editorial.tick(app);self.assertEqual(graph.call_count,1)
  data=self.call('/api/agency/editorial')[1];self.assertNotIn('secret',data['accounts'][0]);self.assertEqual(data['posts'][0]['status'],'published')
  self.assertEqual(self.call('/api/agency/editorial',who='bob')[0],403)
 def test_ambiguous_response_no_retry(self):
  *_,pid=self.draft()
  with app.connect() as c:c.execute("UPDATE creative_reviews SET status='approved'");c.execute('UPDATE social_accounts SET verified=?',(app.now(),));c.execute("UPDATE editorial_posts SET status='scheduled',scheduled=?",(app.now(),))
  with patch.object(agency_editorial,'graph',side_effect=TimeoutError()) as graph:agency_editorial.tick(app);agency_editorial.tick(app);self.assertEqual(graph.call_count,1)
  self.assertEqual(self.call('/api/agency/editorial')[1]['posts'][0]['status'],'unknown')
 def test_edit_account_fields_and_preserve_token(self):
  cid,aid,*_=self.draft();url='/api/agency/editorial/accounts/'+aid
  with app.connect() as c:
   before=c.execute('SELECT secret FROM social_accounts WHERE id=?',(aid,)).fetchone()[0]
   c.execute('UPDATE social_accounts SET verified=? WHERE id=?',(app.now(),aid))
  self.assertEqual(self.call(url,'PATCH',{'name':'Nova conta','platform':'instagram','target':'456','active':False,'client_id':cid})[0],200)
  data=self.call('/api/agency/editorial')[1];acc=data['accounts'][0]
  self.assertEqual((acc['name'],acc['platform'],acc['target'],acc['active']),('Nova conta','instagram','456',0))
  self.assertIsNone(acc['verified']);self.assertEqual(data['posts'][0]['status'],'cancelled')
  with app.connect() as c:self.assertEqual(c.execute('SELECT secret FROM social_accounts WHERE id=?',(aid,)).fetchone()[0],before)
  self.assertEqual(self.call(url,'PATCH',{'token':'new-secret','active':True})[0],200)
  with app.connect() as c:self.assertNotEqual(c.execute('SELECT secret FROM social_accounts WHERE id=?',(aid,)).fetchone()[0],before)
 def test_delete_account_cancels_queue_preserves_history(self):
  cid,aid,*_,pid=self.draft();url='/api/agency/editorial/accounts/'+aid
  self.assertEqual(self.call(url,'DELETE',who='bob')[0],403)
  with app.connect() as c:c.execute("UPDATE editorial_posts SET status='scheduled' WHERE id=?",(pid,))
  self.assertEqual(self.call(url,'DELETE')[0],200)
  data=self.call('/api/agency/editorial')[1];self.assertEqual(data['accounts'],[])
  self.assertEqual(data['posts'][0]['status'],'cancelled');self.assertTrue(data['posts'][0]['account_name'])
  with app.connect() as c:
   acc=c.execute('SELECT * FROM social_accounts WHERE id=?',(aid,)).fetchone()
   self.assertEqual(acc['secret'],'');self.assertEqual(acc['active'],0)
  self.assertEqual(self.call(url,'PATCH',{'active':True})[0],404)
  self.assertEqual(self.call(url+'/verify','POST')[0],404)
  with patch.object(agency_editorial,'graph') as graph:agency_editorial.tick(app);graph.assert_not_called()
 def test_invalid_edits_and_inflight_delete_are_rejected(self):
  cid,aid,*_,pid=self.draft();url='/api/agency/editorial/accounts/'+aid
  for payload in [{'name':''},{'target':'abc'},{'platform':'ads'},{'active':'yes'},{'token':''}]:
   self.assertEqual(self.call(url,'PATCH',payload)[0],400)
  self.assertEqual(self.call(url,'PATCH',{'name':'Forbidden'},who='bob')[0],403)
  for status in ['processing','sending','unknown']:
   with app.connect() as c:c.execute('UPDATE editorial_posts SET status=? WHERE id=?',(status,pid))
   self.assertEqual(self.call(url,'DELETE')[0],409)
   self.assertEqual(self.call(url,'PATCH',{'target':'789'})[0],409)
  with app.connect() as c:c.execute("UPDATE editorial_posts SET status='published',external_id='published123' WHERE id=?",(pid,))
  self.assertEqual(self.call(url,'DELETE')[0],200)
  self.assertEqual(self.call('/api/agency/editorial')[1]['posts'][0]['status'],'published')
 def test_change_client_requires_access_and_no_history(self):
  cid,aid,*_=self.draft();url='/api/agency/editorial/accounts/'+aid
  other=self.call('/api/clients','POST',{'name':'Outro','entered':'2026-10-01','product':'Marketing'})[1]['id']
  self.assertEqual(self.call(url,'PATCH',{'client_id':'missing'})[0],404)
  self.assertEqual(self.call(url,'PATCH',{'client_id':other})[0],409)
  fresh=self.call('/api/agency/editorial/accounts','POST',{'client_id':cid,'name':'Nova','platform':'facebook','target':'555','token':'secret'})[1]['id']
  self.assertEqual(self.call('/api/agency/editorial/accounts/'+fresh,'PATCH',{'client_id':other})[0],200)
