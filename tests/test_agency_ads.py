import unittest
from unittest.mock import patch
import test_system as base
import app,agency_editorial
class AdsTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def account(self):
  cid=self.call('/api/clients','POST',{'name':'Anunciante','entered':'2026-10-01','product':'Tráfego'})[1]['id']
  r=self.call('/api/agency/ads/accounts','POST',{'client_id':cid,'name':'Ads cliente','target':'act_123','token':'secret'});self.assertEqual(r[0],200,r);return r[1]['id']
 def test_paused_campaign_and_nonce(self):
  id=self.account();d={'name':'Campanha','objective':'OUTCOME_LEADS','categories':[],'daily_budget':'50','nonce':'campaign_nonce_12345678'};calls=[]
  def graph(a,acc,route,body=None,query=None):
   calls.append((route,body));return {'id':'789'} if body else {'id':'act_123','currency':'BRL'}
  with patch.object(agency_editorial,'graph',side_effect=graph):
   self.assertEqual(self.call('/api/agency/ads/accounts/'+id+'/campaigns','POST',d)[0],200);self.assertEqual(self.call('/api/agency/ads/accounts/'+id+'/campaigns','POST',d)[0],200)
  writes=[x for x in calls if x[1]];self.assertEqual(len(writes),1);self.assertEqual(writes[0][1]['status'],'PAUSED');self.assertEqual(writes[0][1]['daily_budget'],5000)
  self.assertEqual(self.call('/api/agency/ads',who='bob')[0],403)
 def test_cannot_update_other_accounts_campaign(self):
  id=self.account()
  with patch.object(agency_editorial,'graph',return_value={'account_id':'456'}) as graph:self.assertEqual(self.call('/api/agency/ads/accounts/'+id+'/campaigns/789','PATCH',{'status':'ACTIVE'})[0],403);self.assertEqual(graph.call_count,1)
 def test_other_currency_not_interpreted_as_brl(self):
  id=self.account()
  with patch.object(agency_editorial,'graph',return_value={'currency':'JPY'}):self.assertEqual(self.call('/api/agency/ads/accounts/'+id+'/campaigns','POST',{'name':'Campanha','objective':'OUTCOME_LEADS','daily_budget':'50','nonce':'campaign_nonce_12345678'})[0],409)
