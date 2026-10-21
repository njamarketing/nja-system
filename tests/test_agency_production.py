import unittest
import test_system as base
import app,agency_production
class ProductionTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def plan(self):
  cid=self.call('/api/clients','POST',{'name':'Produção','entered':'2026-10-01','product':'Marketing'})[1]['id'];self.call('/api/agency/access','POST',{'client_id':cid,'branch':'foz','members':['alice','master']})
  data={'client_id':cid,'name':'Mensal','owner':'master','start_month':'2026-01','end_month':'2027-12','monthly_fee':'2500','auto':True,'items':[{'name':'Criativo','quantity':2,'owner':'alice','estimated_minutes':60,'due_day':31}]}
  r=self.call('/api/agency/production/plans','POST',data);self.assertEqual(r[0],200,r);return r[1]['id'],data
 def test_idempotent_generation_snapshot_and_short_month(self):
  id,d=self.plan();url='/api/agency/production/plans/'+id+'/generate';r=self.call(url,'POST',{'month':'2026-02'});self.assertEqual(r[0],200,r)
  self.assertEqual(self.call(url,'POST',{'month':'2026-02'})[1]['id'],r[1]['id'])
  projects=self.call('/api/agency/production')[1]['projects'];self.assertEqual(len(projects),1);self.assertEqual(len(projects[0]['deliverables']),2);self.assertIn('2026-02-28',projects[0]['deliverables'][0]['due'])
  d['items'][0]['quantity']=3;self.call('/api/agency/production/plans/'+id,'PATCH',d);self.assertEqual(len(self.call('/api/agency/production')[1]['projects'][0]['deliverables']),2)
 def test_dependencies_cycle_and_completion_gate(self):
  id,d=self.plan();self.call('/api/agency/production/plans/'+id+'/generate','POST',{'month':'2026-10'});rows=self.call('/api/agency/production')[1]['projects'][0]['deliverables'];a,b=[x['task_id'] for x in rows]
  self.assertEqual(self.call('/api/tasks/'+a+'/dependencies','POST',{'ids':[b]})[0],200)
  self.assertEqual(self.call('/api/tasks/'+b+'/dependencies','POST',{'ids':[a]})[0],400)
  self.assertEqual(self.call('/api/tasks/'+a,'PATCH',{'status':'done'})[0],409)
  self.call('/api/tasks/'+b,'PATCH',{'status':'done'});self.assertEqual(self.call('/api/tasks/'+a,'PATCH',{'status':'done'})[0],200)
 def test_access_and_invalid_plan(self):
  id,d=self.plan();self.assertEqual(self.call('/api/agency/production',who='bob')[0],403)
  d['items'][0]['owner']='bob';self.assertEqual(self.call('/api/agency/production/plans','POST',d)[0],400)
  self.assertEqual(self.call('/api/agency/production/plans/'+id+'/generate','POST',{'month':'2028-01'})[0],400)
