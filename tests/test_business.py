import unittest,json,io,os,hmac,hashlib,base64
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
import test_system as base
import app,business,business_connectors as bc

class BusinessTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def sales(self):
  with app.connect() as c:c.execute("UPDATE users SET role_id='sales' WHERE id IN ('alice','bob')")
 def lead(self,owner='alice',**kw):
  r=self.call('/api/business/leads','POST',{'name':'Lead Teste','owner':owner,'phone':kw.pop('phone','5545999990001'),'city':'Foz','product':'Site','budget':'1200.50',**kw});self.assertEqual(r[0],200,r);return r[1]['id']
 def grant(self,who,perms):
  with app.connect() as c:
   c.execute('INSERT OR REPLACE INTO roles VALUES(?,?,?)',('test-'+who,who,json.dumps(perms)));c.execute('UPDATE users SET role_id=? WHERE id=?',('test-'+who,who))
 def test_lead_scope_assignment_validation(self):
  self.sales();id=self.lead()
  self.assertEqual(self.call('/api/business/leads/'+id,who='bob')[0],403)
  self.assertEqual(len(self.call('/api/business/leads',who='alice')[1]['items']),1)
  self.assertEqual(self.call('/api/business/leads/'+id,'PATCH',{'owner':'bob'},who='alice')[0],403)
  self.assertEqual(self.call('/api/business/leads/'+id,'PATCH',{'budget':'NaN'},who='alice')[0],400)
  self.assertEqual(self.call('/api/business/leads/'+id,'PATCH',{'city':'Teixeira'},who='alice')[0],200)
  self.assertEqual(self.call('/api/business/leads/'+id,'PATCH',{'owner':'bob'})[0],200)
  self.assertEqual(self.call('/api/business/leads/'+id,who='alice')[0],403)
 def test_conversion_idempotent_and_duplicate_client(self):
  self.sales();id=self.lead()
  r=self.call('/api/business/leads/'+id+'/convert','POST',{},who='alice');self.assertEqual(r[0],200,r)
  self.assertEqual(self.call('/api/business/leads/'+id+'/convert','POST',{},who='alice')[1]['id'],r[1]['id'])
  id2=self.lead(phone='5545999990002')
  self.assertEqual(self.call('/api/business/leads/'+id2+'/convert','POST',{},who='alice')[0],409)
  self.assertEqual(self.call('/api/business/leads/'+id2+'/convert','POST',{'client_id':r[1]['id']},who='alice')[0],200)
 def test_lead_event_and_csrf(self):
  self.sales();id=self.lead();start=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat();end=(datetime.now(timezone.utc)+timedelta(hours=3)).isoformat()
  r=self.call('/api/business/leads/'+id+'/events','POST',{'title':'Meet','start':start,'end':end,'location':'https://meet.google.com/abc-defg-hij'},who='alice');self.assertEqual(r[0],200,r)
  self.assertIn(r[1]['id'],[e['id'] for e in self.call('/api/events',who='alice')[1]])
  self.assertEqual(self.call('/api/business/leads/'+id+'/notes','POST',{'text':'Teste'},who='alice',csrf=False)[0],403)
 def invoice(self,bank='itau'):
  r=self.call('/api/business/invoices','POST',{'bank':bank,'reference':'REF1','customer':'Cliente','amount':'1500.25','due':'2026-11-01'});self.assertEqual(r[0],200,r);return r[1]['id']
 def test_finance_bank_acl_and_document_acl(self):
  id=self.invoice();self.invoice('cora');self.grant('alice',['finance','bank_cora','finance_download'])
  rows=self.call('/api/business/invoices',who='alice')[1]['items'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['bank'],'cora')
  self.assertEqual(self.call('/api/business/invoices/'+id,who='alice')[0],403)
  doc={'name':'boleto.pdf','data':base64.b64encode(b'%PDF-1.4\ntest').decode()}
  r=self.call('/api/business/invoices/'+id+'/documents','POST',doc);self.assertEqual(r[0],200,r);fid=r[1]['id']
  self.assertEqual(self.call('/api/business/documents/'+fid,who='alice')[0],403)
  self.grant('alice',['finance','bank_itau'])
  self.assertEqual(self.call('/api/business/documents/'+fid,who='alice')[0],403)
  self.grant('alice',['finance','bank_itau','finance_download'])
  self.assertEqual(self.call('/api/business/documents/'+fid,who='alice')[0],200)
  self.assertEqual(self.call('/api/business/invoices/'+id+'/pay','POST',{})[0],404)
  self.assertEqual(self.call('/api/business/invoices/'+id+'/documents','POST',{'name':'bad.pdf','data':base64.b64encode(b'html').decode()})[0],400)
 def test_contract_scope_and_reminder_dedup(self):
  cid=self.call('/api/clients','POST',{'name':'Cliente contrato','entered':'2026-10-01','services':['Social media','Tráfego pago']})[1]['id']
  self.call('/api/agency/access','POST',{'client_id':cid,'branch':'foz','members':['alice','master']})
  self.grant('alice',['contracts','contract_manage','contract_download','clients']);self.grant('bob',['contracts','contract_manage'])
  today=datetime.now(app.TZ).date();expiry=(today+timedelta(days=7)).isoformat()
  data={'contract_number':'NJA-2026-001','title':'Contrato A','client_id':cid,'owner':'alice','start':today.isoformat(),'expires':expiry,'amount':'1000','services':['Social media','Tráfego pago']}
  r=self.call('/api/business/contracts','POST',data,who='alice');self.assertEqual(r[0],200,r);id=r[1]['id']
  item=self.call('/api/business/contracts',who='alice')[1]['items'][0]
  self.assertEqual(item['contract_number'],'NJA-2026-001');self.assertEqual(item['client_id'],cid);self.assertEqual(item['services'],data['services'])
  duplicate=self.call('/api/business/contracts','POST',data|{'title':'Duplicado'},who='alice');self.assertEqual(duplicate[0],409)
  self.assertEqual(self.call('/api/business/contracts/'+id,'PATCH',{},who='bob')[0],403)
  with app.connect() as c:
   business.reminders(app,c);business.reminders(app,c)
   self.assertEqual(c.execute("SELECT count(*) FROM notifications WHERE user_id='alice' AND category='contracts'").fetchone()[0],1)
   self.assertEqual(c.execute("SELECT count(*) FROM notifications WHERE user_id='bob' AND category='contracts'").fetchone()[0],0)
 def webhook(self,payload,valid=True):
  raw=json.dumps(payload).encode();env={'HTTP_X_HUB_SIGNATURE_256':'sha256='+hmac.new(b'secret',raw,hashlib.sha256).hexdigest() if valid else 'bad'}
  with app.connect() as c:return bc.webhook(app,c,'POST',env,{},raw)
 def payload(self,ref=True,mid='wamid.1',phone='5545999990001'):
  m={'id':mid,'from':phone,'timestamp':str(int(datetime.now().timestamp())),'type':'text','text':{'body':'Olá'}}
  if ref:m['referral']={'source_type':'ad','source_id':'123'}
  return {'object':'whatsapp_business_account','entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'12345'},'messages':[m]}}]}]}
 @patch.dict(os.environ,{'META_APP_SECRET':'secret','WHATSAPP_PHONE_ID':'12345','WHATSAPP_TOKEN':'token','META_GRAPH_VERSION':'v25.0'})
 def test_webhook_origin_signature_dedup_and_reply(self):
  self.sales()
  self.call('/api/business/connectors/whatsapp','POST',{'owner':'alice'})
  with self.assertRaises(app.Error):self.webhook(self.payload(),False)
  self.webhook(self.payload(False))
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM leads').fetchone()[0],0)
  self.webhook(self.payload());self.webhook(self.payload())
  with app.connect() as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM leads').fetchone()[0],1);self.assertEqual(c.execute('SELECT COUNT(*) FROM lead_messages').fetchone()[0],1);id=c.execute('SELECT id FROM leads').fetchone()[0]
  with patch.object(bc,'graph',return_value={'messages':[{'id':'out.1'}]}) as external:
   d={'text':'Olá, posso ajudar?','nonce':'abcdefgh1234567890'}
   self.assertEqual(self.call('/api/business/leads/'+id+'/messages','POST',d,who='bob')[0],403)
   self.assertEqual(self.call('/api/business/leads/'+id+'/messages','POST',d,who='alice')[0],200)
   self.assertEqual(self.call('/api/business/leads/'+id+'/messages','POST',d,who='alice')[0],200)
   self.assertEqual(external.call_count,1)
  with app.connect() as c:c.execute("UPDATE lead_messages SET created=? WHERE direction='in'",((datetime.now(timezone.utc)-timedelta(hours=25)).isoformat(),))
  self.assertEqual(self.call('/api/business/leads/'+id+'/messages','POST',{'text':'fora','nonce':'abcdefgh1234567891'},who='alice')[0],409)
 def test_connectors_no_secrets_and_unsupported_bank(self):
  self.assertEqual(self.call('/api/business/connectors',who='alice')[0],403)
  with patch.dict(os.environ,{'WHATSAPP_TOKEN':'SUPER_SECRET'}):self.assertNotIn('SUPER_SECRET',json.dumps(self.call('/api/business/connectors')[1]))
  self.assertEqual(self.call('/api/business/sync/itau','POST',{})[0],409)
 def test_cora_pagination_and_money(self):
  values=[{'access_token':'token'},{'items':[{'id':'inv_one'}],'totalItems':1},{'total_amount':12345,'payment_terms':{'due_date':'2026-12-01'},'customer':{'name':'Cliente'},'status':'OPEN'}]
  with patch.object(bc,'cora',side_effect=values):
   r=self.call('/api/business/sync/cora','POST',{'start':'2026-11-01','end':'2026-12-02'});self.assertEqual(r[0],200,r)
  row=self.call('/api/business/invoices')[1]['items'][0];self.assertEqual(row['amount'],12345);self.assertEqual(row['source'],'cora_api')
  self.assertEqual(self.call('/api/business/invoices/'+row['id'],'PATCH',{'amount':'1'})[0],409)
 def test_marketing_publish_once_and_acl(self):
  r=self.call('/api/business/marketing/posts','POST',{'platform':'facebook','text':'Olá'});self.assertEqual(r[0],200,r);id=r[1]['id']
  self.assertEqual(self.call('/api/business/marketing/posts',who='alice')[0],403)
  with patch.dict(os.environ,{'META_PAGE_ID':'123','META_PAGE_ACCESS_TOKEN':'secret'}),patch.object(bc,'graph',return_value={'id':'post123'}) as ex:
   self.assertEqual(self.call('/api/business/marketing/posts/'+id+'/publish','POST',{})[0],200)
   self.assertEqual(self.call('/api/business/marketing/posts/'+id+'/publish','POST',{})[0],409)
   self.assertEqual(ex.call_count,1)

 def test_pdf_provider_lookup_permission_and_no_payment(self):
  self.grant('alice',['finance','bank_cora'])
  with app.connect() as c:
   c.execute("INSERT INTO invoices(id,bank,reference,customer,amount,due,source,updated) VALUES('bank','cora','stage:inv_one','Customer',100,'2026-12-01','cora_api',?)",(app.now(),))
  with patch.object(bc,'cora',side_effect=[{'access_token':'token'},{'payment_options':{'bank_slip':{'url':'https://documents.cora.com.br/test.pdf'}}}]) as external:
   self.assertEqual(self.call('/api/business/invoices/bank/bank-pdf',who='alice')[0],403)
   self.assertEqual(external.call_count,0)
   self.assertEqual(self.call('/api/business/invoices/bank/bank-pdf')[0],200)
   self.assertTrue(all(call.args[1] in ['/token','/v2/invoices/inv_one'] for call in external.call_args_list))
 def test_publication_ambiguous_failure_blocks_retry(self):
  id=self.call('/api/business/marketing/posts','POST',{'platform':'facebook','text':'Teste'})[1]['id']
  with patch.dict(os.environ,{'META_PAGE_ID':'123','META_PAGE_ACCESS_TOKEN':'secret'}),patch.object(bc,'graph',side_effect=app.Error(503,'timeout')) as external:
   self.assertEqual(self.call('/api/business/marketing/posts/'+id+'/publish','POST',{})[0],503)
   self.assertEqual(self.call('/api/business/marketing/posts/'+id+'/publish','POST',{})[0],409)
   self.assertEqual(external.call_count,1)
  self.assertEqual(self.call('/api/business/marketing/posts')[1]['items'][0]['status'],'unknown')
