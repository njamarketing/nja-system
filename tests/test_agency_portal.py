import unittest,json,io,base64
import test_system as base
import app
class PortalTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def portal(self,path,method='GET',data=None,token=''):
  route,_,query=path.partition('?');raw=json.dumps(data or {}).encode();env={'REQUEST_METHOD':method,'PATH_INFO':'/api/portal/'+route,'QUERY_STRING':query,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw),'REMOTE_ADDR':'portal-test','HTTP_X_PORTAL_TOKEN':token};capture={}
  def response(status,headers):capture['status']=int(status.split()[0])
  result=json.loads(b''.join(app.application(env,response)));return capture['status'],result
 def invite_token(self,url):return url.rsplit('/',1)[-1] if '/c/' in url else url.split('#invite=')[1]
 def setup_review(self):
  cid=self.call('/api/clients','POST',{'name':'Portal cliente','entered':'2026-10-01','product':'Marketing'})[1]['id']
  rid=self.call('/api/agency/reviews','POST',{'client_id':cid,'title':'Campanha'})[1]['id']
  vid=self.call('/api/agency/reviews/'+rid+'/versions','POST',{'caption':'Versão 1'})[1]['id']
  invite=self.invite_token(self.call('/api/agency/portal/invite','POST',{'client_id':cid,'name':'Contato','email':'cliente@test.com','can_approve':True})[1]['url'])
  st,r=self.portal('activate','POST',{'token':invite,'password':'Cliente-Seguro-123'});self.assertEqual(st,200,r)
  st,r=self.portal('login','POST',{'client_id':cid,'email':'cliente@test.com','password':'Cliente-Seguro-123'});self.assertEqual(st,200,r)
  return cid,rid,vid,r['token'],invite
 def test_explicit_sharing_and_version_bound_approval(self):
  cid,rid,vid,token,invite=self.setup_review();self.assertEqual(self.portal('home',token=token)[1]['reviews'],[])
  self.assertEqual(self.portal('reviews/'+rid,'POST',{'version_id':vid,'decision':'approved'},token)[0],404)
  self.call('/api/agency/reviews/'+rid+'/sharing','POST',{'shared':True})
  self.assertEqual(self.portal('reviews/'+rid,'POST',{'version_id':vid,'decision':'approved'},token)[0],200)
  new=self.call('/api/agency/reviews/'+rid+'/versions','POST',{'caption':'Versão 2'})[1]['id']
  r=self.portal('home',token=token)[1]['reviews'][0];self.assertEqual(r['status'],'waiting');self.assertEqual(len(r['feedback']),1)
  self.assertEqual(self.portal('reviews/'+rid,'POST',{'version_id':vid,'decision':'approved'},token)[0],409)
  self.assertEqual(self.portal('reviews/'+rid,'POST',{'version_id':new,'decision':'changes','text':'Ajustar título','x':.2,'y':.4},token)[0],200)
 def test_invitation_single_use_revoke_and_isolated_auth(self):
  cid,rid,vid,token,invite=self.setup_review();self.assertEqual(self.portal('activate','POST',{'token':invite,'password':'Cliente-Seguro-456'})[0],400)
  self.assertEqual(self.portal('home',token='wrong')[0],401)
  account=self.call('/api/agency/reviews')[1]['accounts'][0]['id'];self.call('/api/agency/portal/accounts/'+account,'PATCH',{'active':False});self.assertEqual(self.portal('home',token=token)[0],401)
  self.assertEqual(self.call('/api/agency/reviews',who='bob')[0],403)
 def test_short_invite_friendly_code_and_password_management(self):
  cid,rid,vid,token,_=self.setup_review();accounts=self.call('/api/agency/reviews')[1]['accounts'];account=accounts[0]
  self.assertEqual(account['client_code'],'portal-cliente')
  generated=self.call('/api/agency/portal/accounts/'+account['id']+'/reset','POST',{'mode':'link'})
  self.assertEqual(generated[0],200,generated[1]);self.assertIn('/c/portal-cliente-',generated[1]['url'])
  short=self.invite_token(generated[1]['url']);capture={}
  env={'REQUEST_METHOD':'GET','PATH_INFO':'/c/'+short,'QUERY_STRING':'','wsgi.input':io.BytesIO(b''),'REMOTE_ADDR':'portal-test'}
  body=b''.join(app.application(env,lambda status,headers:capture.update(status=int(status.split()[0]),headers=dict(headers))))
  self.assertEqual(capture['status'],303);self.assertEqual(capture['headers']['Location'],'/portal.html#invite='+short);self.assertEqual(body,b'')
  self.assertEqual(self.portal('activate','POST',{'token':short,'password':'Nova-Senha-Segura'})[0],200)
  login=self.portal('login','POST',{'client_id':'portal-cliente','email':'cliente@test.com','password':'Nova-Senha-Segura'});self.assertEqual(login[0],200,login[1])
  changed=self.call('/api/agency/portal/accounts/'+account['id']+'/reset','POST',{'mode':'password','password':'Senha-Direta-123','confirmation':'Senha-Direta-123'});self.assertEqual(changed[0],200,changed[1])
  self.assertEqual(self.portal('home',token=login[1]['token'])[0],401)
  self.assertEqual(self.portal('login','POST',{'client_id':'portal-cliente','email':'cliente@test.com','password':'Senha-Direta-123'})[0],200)
  self.assertEqual(self.call('/api/agency/portal/accounts/'+account['id']+'/reset','POST',{'mode':'password','password':'curta','confirmation':'curta'})[0],400)
 def test_portal_material_upload_and_cross_client_block(self):
  cid,rid,vid,token,invite=self.setup_review();r=self.portal('uploads','POST',{'name':'briefing.txt','data':base64.b64encode(b'Briefing teste').decode()},token);self.assertEqual(r[0],200,r)
  self.assertEqual(self.call('/api/agency/portal/uploads/'+r[1]['id'])[0],200)
  self.assertEqual(self.call('/api/agency/portal/uploads/'+r[1]['id'],who='bob')[0],403)
  self.assertEqual(self.portal('files/unknown',token=token)[0],404)
 def test_carousel_keeps_order_and_individual_captions(self):
  from PIL import Image
  cid=self.call('/api/clients','POST',{'name':'Cliente carrossel','entered':'2026-10-01','product':'Marketing'})[1]['id']
  tid=self.call('/api/tasks','POST',{'title':'Carrossel','owner':'master','client_id':cid})[1]['id']
  file_ids=[]
  for color in ['red','blue']:
   payload=io.BytesIO();Image.new('RGB',(20,20),color).save(payload,format='PNG')
   upload=self.call('/api/upload','POST',{'task_id':tid,'name':color+'.png','data':base64.b64encode(payload.getvalue()).decode()})
   self.assertEqual(upload[0],200,upload[1]);file_ids.append(upload[1]['id'])
  created=self.call('/api/agency/reviews','POST',{'client_id':cid,'task_id':tid,'title':'Sequência','format':'carousel'})
  self.assertEqual(created[0],200,created[1]);rid=created[1]['id']
  self.assertEqual(self.call('/api/agency/reviews/'+rid+'/versions','POST',{'file_ids':file_ids,'captions':['Primeiro card','Segundo card'],'caption':'Legenda geral'})[0],200)
  review=self.call('/api/agency/reviews/'+rid)[1]
  self.assertEqual(review['format'],'carousel')
  self.assertEqual([item['id'] for item in review['versions'][0]['files']],file_ids)
  self.assertEqual([item['caption'] for item in review['versions'][0]['files']],['Primeiro card','Segundo card'])
  self.assertEqual(self.call('/api/agency/reviews/'+rid+'/versions','POST',{'file_ids':file_ids,'captions':['Só uma']})[0],400)
  image=self.call('/api/agency/reviews','POST',{'client_id':cid,'task_id':tid,'title':'Imagem única','format':'image'})[1]['id']
  self.assertEqual(self.call('/api/agency/reviews/'+image+'/versions','POST',{'file_ids':file_ids,'captions':['A','B']})[0],400)
