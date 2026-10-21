import unittest,json
import test_system as base
import app
class FinanceTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def test_margin_from_logged_time_and_explicit_ledger(self):
  cid=self.call('/api/clients','POST',{'name':'Margem','entered':'2026-10-01','product':'Marketing'})[1]['id'];tid=self.call('/api/tasks','POST',{'title':'Entrega','owner':'master','client_id':cid})[1]['id']
  with app.connect() as c:c.execute('INSERT INTO time_entries VALUES(?,?,?,?,?,?)',('t1',tid,'master',3600,'Trabalho','2026-10-15T12:00:00+00:00'))
  self.call('/api/agency/finance/rates','POST',{'user_id':'master','effective':'2026-01-01','rate':'100'})
  for kind,amount in [('revenue','1000'),('expense','200')]:
   r=self.call('/api/agency/finance/entries','POST',{'client_id':cid,'kind':kind,'category':'Serviços','description':'Registro','amount':amount,'competence':'2026-10','reference':kind});self.assertEqual(r[0],200,r)
  f=self.call('/api/agency/reports?month=2026-10')[1]['financial'];self.assertEqual(f['clients'][0]['margin'],70000);self.assertEqual(f['cash_in'],0);self.assertEqual(f['labor'],10000)
  with app.connect() as c:c.execute('INSERT INTO time_entries VALUES(?,?,?,?,?,?)',('t2',tid,'alice',1800,'Sem taxa','2026-10-15T12:00:00+00:00'))
  self.assertEqual(self.call('/api/agency/reports?month=2026-10')[1]['financial']['unpriced_seconds'],1800)
 def test_idempotent_reference_and_void_audit(self):
  data={'branch':'foz','kind':'expense','category':'Estrutura','description':'Servidor','amount':'50','competence':'2026-10','reference':'DOC1'}
  st,r,_=self.call('/api/agency/finance/entries','POST',data);self.assertEqual(st,200,r)
  self.assertEqual(self.call('/api/agency/finance/entries','POST',data)[0],409)
  self.assertEqual(self.call('/api/agency/finance/entries/'+r['id'],'PATCH',{'void':True,'reason':'Duplicidade externa'})[0],200)
  self.assertEqual(self.call('/api/agency/reports?month=2026-10')[1]['financial']['expenses'],0)
  with app.connect() as c:self.assertEqual(c.execute("SELECT count(*) FROM audit WHERE action='ledger_void'").fetchone()[0],1)
 def test_reports_do_not_leak_financial_without_permission(self):
  role=self.call('/api/roles','POST',{'name':'Operacional','permissions':['agency_reports']})[1]['id'];self.call('/api/users/bob','PATCH',{'role_id':role})
  st,r,_=self.call('/api/agency/reports?month=2026-10',who='bob');self.assertEqual(st,200,r);self.assertIsNone(r['financial']);self.assertEqual(r['clients'],[])
  self.assertEqual(self.call('/api/agency/finance',who='bob')[0],403)
