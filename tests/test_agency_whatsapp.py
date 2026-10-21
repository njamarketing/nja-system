import unittest,os,json
from unittest.mock import patch
import test_system as base
import app,agency_whatsapp,business_connectors as bc
class WhatsAppExtendedTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def lead(self):return self.call('/api/business/leads','POST',{'name':'WhatsApp','phone':'5545999999999'})[1]['id']
 def test_history_pagination_and_inbound_media_scope(self):
  id=self.lead()
  with app.connect() as c:
   for i in range(61):c.execute('INSERT INTO lead_messages VALUES(?,?,NULL,?,?,?,?,?)',(str(i),id,'in','Mensagem '+str(i),'external'+str(i),'received',app.now()))
   agency_whatsapp.incoming(c,'60',{'type':'image','image':{'id':'999','mime_type':'image/jpeg'}})
  r=self.call('/api/business/leads/'+id+'/history')[1];self.assertEqual(len(r['items']),50);self.assertEqual(r['items'][-1]['media']['media_id'],'999')
  r2=self.call('/api/business/leads/'+id+'/history?before='+r['before'])[1];self.assertEqual(len(r2['items']),11);self.assertIsNone(r2['before'])
  self.assertFalse(set(x['id'] for x in r['items'])&set(x['id'] for x in r2['items']))
  self.assertEqual(self.call('/api/business/leads/'+id+'/history',who='bob')[0],403)
 def test_approved_template_idempotent_and_no_owner_bypass(self):
  id=self.lead();template={'name':'retorno','language':'pt_BR','status':'APPROVED','components':[{'type':'BODY','text':'Olá {{1}}'}]};d={'name':'retorno','language':'pt_BR','parameters':['Nelson'],'nonce':'nonce_12345678901234'}
  with patch.dict(os.environ,{'WHATSAPP_TOKEN':'token','WHATSAPP_PHONE_ID':'123'}),patch.object(agency_whatsapp,'templates',return_value=[template]),patch.object(bc,'graph',return_value={'messages':[{'id':'wamid.1'}]}) as graph:
   self.assertEqual(self.call('/api/business/leads/'+id+'/template','POST',d)[0],200)
   self.assertEqual(self.call('/api/business/leads/'+id+'/template','POST',d)[0],200);self.assertEqual(graph.call_count,1)
   d['parameters']=['Outra pessoa'];self.assertEqual(self.call('/api/business/leads/'+id+'/template','POST',d)[0],409)
   self.assertEqual(self.call('/api/business/leads/'+id+'/template','POST',d,who='bob')[0],403)
 def test_media_id_must_have_been_uploaded_for_this_lead(self):
  id=self.lead()
  with app.connect() as c:c.execute('INSERT INTO lead_messages VALUES(?,?,NULL,?,?,?,?,?)',('in',id,'in','Olá','external','received',app.now()))
  with patch.dict(os.environ,{'WHATSAPP_TOKEN':'token','WHATSAPP_PHONE_ID':'123'}):self.assertEqual(self.call('/api/business/leads/'+id+'/send-media','POST',{'kind':'image','media_id':'999','nonce':'abcdefgh123456789'})[0],403)
