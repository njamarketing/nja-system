import unittest,os
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
import test_system as base
import app,agency_editorial
class EditorialTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
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
