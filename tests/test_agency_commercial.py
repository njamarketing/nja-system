import unittest
from datetime import datetime,timedelta
import test_system as base
import app,agency_commercial
class CommercialTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def lead(self):return self.call('/api/business/leads','POST',{'name':'Comprador','product':'Marketing'})[1]['id']
 def test_proposal_history_and_stale_acceptance(self):
  lead=self.lead();data={'lead_id':lead,'title':'Assessoria','valid_until':(datetime.now()+timedelta(days=30)).date().isoformat(),'items':[{'description':'Serviço','quantity':2,'price':'200.50'}],'terms':'Escopo acordado'}
  st,r,_=self.call('/api/agency/commercial/proposals','POST',data);self.assertEqual(st,200,r);pid=r['id'];p=self.call('/api/agency/commercial')[1]['proposals'][0];vid=p['current_version'];self.assertEqual(p['versions'][0]['total'],40100)
  self.assertEqual(self.call('/api/agency/commercial/proposals/'+pid+'/decision','POST',{'version_id':vid,'status':'sent'})[0],200)
  data['items'][0]['price']='300';self.call('/api/agency/commercial/proposals/'+pid+'/versions','POST',data)
  self.assertEqual(self.call('/api/agency/commercial/proposals/'+pid+'/decision','POST',{'version_id':vid,'status':'accepted','evidence':'E-mail do cliente'})[0],409)
  p=self.call('/api/agency/commercial')[1]['proposals'][0];self.assertEqual(len(p['versions']),2);self.assertEqual(p['versions'][1]['total'],40100)
 def test_receipts_commission_and_cancelled_sale(self):
  lead=self.lead();cid=self.call('/api/business/leads/'+lead+'/convert','POST',{})[1]['id'];self.assertTrue(cid)
  sale=self.call('/api/sales','POST',{'lead_id':lead,'amount':'1000','sold_on':datetime.now().date().isoformat()})[1]['id']
  rule=self.call('/api/agency/commercial/rules','POST',{'name':'Recebimento','branch':'foz','basis':'received','rate':'7.5','start':'2020-01-01'})[1]['id']
  result=self.call('/api/agency/commercial/commissions','POST',{'sale_id':sale,'rule_id':rule});self.assertEqual(result[0],200,result);id=result[1]['id']
  data={'reference':'PARC-1','amount':'400','received_on':datetime.now().date().isoformat()};self.assertEqual(self.call('/api/agency/commercial/commissions/'+id+'/receipts','POST',data)[0],200)
  self.assertEqual(self.call('/api/agency/commercial')[1]['commissions'][0]['commission'],3000)
  self.assertEqual(self.call('/api/agency/commercial/commissions/'+id+'/receipts','POST',data)[0],409)
  self.call('/api/sales/'+sale,'PATCH',{'status':'cancelled'});self.assertEqual(self.call('/api/agency/commercial')[1]['commissions'][0]['commission'],0)
 def test_followup_and_permissions(self):
  lead=self.lead();r=self.call('/api/agency/commercial/followups','POST',{'lead_id':lead,'due':'2020-01-01T12:00:00Z','note':'Retornar'});self.assertEqual(r[0],200,r)
  with app.connect() as c:agency_commercial.tick(app,c);agency_commercial.tick(app,c);self.assertEqual(c.execute("SELECT count(*) FROM reminder_log WHERE key LIKE 'followup:%'").fetchone()[0],1)
  self.assertEqual(self.call('/api/agency/commercial',who='bob')[0],403)
