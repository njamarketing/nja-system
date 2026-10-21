import unittest,os,json,time,base64
from unittest.mock import patch
import test_system
app=test_system.app

class EnterpriseTest(unittest.TestCase):
 setUp=test_system.SystemTest.setUp
 tearDown=test_system.SystemTest.tearDown
 call=test_system.SystemTest.call
 make_task=test_system.SystemTest.make_task
 def test_units_dashboard_and_permissions(self):
  self.assertEqual(self.call('/api/company','PATCH',{'manager_foz':'master','manager_teixeira':'bob'})[0],200)
  self.assertEqual(self.call('/api/users/alice/branch','PATCH',{'branch':'teixeira'})[0],200)
  self.assertEqual(self.call('/api/company','PATCH',{'manager_foz':'alice'},who='alice')[0],403)
  self.assertEqual(self.call('/api/users/alice/branch','PATCH',{'branch':'bad'})[0],400)
  o=self.call('/api/overview')[1];self.assertEqual(o['scope'],'company');self.assertEqual(o['tasks']['done'],0)
  tid=self.make_task();self.assertEqual(self.call('/api/overview')[1]['tasks']['pending'],1)
  self.assertEqual(self.call('/api/overview',who='bob')[1]['scope'],'accessible')
  self.assertEqual(self.call('/api/overview',who='bob')[1]['tasks']['pending'],0)
  self.call('/api/clients','POST',{'name':'Real','entered':'2026-01-01','product':'Marketing'})
  client=self.call('/api/clients')[1][0];self.assertEqual(self.call('/api/overview')[1]['clients_active'],1)
  self.call('/api/clients/'+client['id']+'/active','PATCH',{'active':False});self.assertEqual(self.call('/api/overview')[1]['clients_active'],0)
 def test_archive_personal_and_restore(self):
  self.assertEqual(self.call('/api/rooms/general/archive','POST',{'archived':True},who='alice')[0],200)
  self.assertTrue(self.call('/api/rooms',who='alice')[1][0]['archived']);self.assertFalse(self.call('/api/rooms',who='bob')[1][0]['archived'])
  self.call('/api/rooms/general/archive','POST',{'archived':False},who='alice');self.assertFalse(self.call('/api/rooms',who='alice')[1][0]['archived'])
  self.assertEqual(self.call('/api/rooms/unknown/archive','POST',{'archived':True},who='alice')[0],403)
 def test_google_oauth_state_tokens_and_isolation(self):
  import integrations
  with patch.dict(os.environ,{'GOOGLE_CLIENT_ID':'test-client','GOOGLE_CLIENT_SECRET':'test-secret','GOOGLE_WORKSPACE_DOMAIN':'nja.test'}):
   st,r,_=self.call('/api/drive/connect','POST',{},who='alice');self.assertEqual(st,200)
   from urllib.parse import urlparse,parse_qs,quote
   state=parse_qs(urlparse(r['url']).query)['state'][0]
   self.assertEqual(self.call('/api/drive/callback?state='+state+'&code=x',who='bob')[0],403)
   with patch.object(integrations,'external',side_effect=[{'access_token':'access','refresh_token':'refresh','expires_in':3600},{'user':{'emailAddress':'alice@nja.test'}}]):
    st,_,h=self.call('/api/drive/callback?state='+state+'&code=x',who='alice');self.assertEqual(st,303);self.assertEqual(dict(h)['Location'],'/#drive')
   self.assertEqual(self.call('/api/drive/callback?state='+state+'&code=x',who='alice')[0],403)
   with app.connect() as c:self.assertNotIn('refresh',c.execute('SELECT secret FROM drive_tokens').fetchone()[0])
   self.assertFalse(self.call('/api/integrations',who='bob')[1]['drive_connected'])
   self.assertEqual(self.call('/api/drive/files',who='bob')[0],409)
   with patch.object(integrations,'external',return_value={'files':[{'id':'file1','name':'Arquivo real'}]}) as ext:
    self.assertEqual(self.call('/api/drive/files?search=Projeto',who='alice')[1]['files'][0]['id'],'file1');self.assertIn('name+contains',ext.call_args.args[1])
   self.assertEqual(self.call('/api/drive/files?folder=%27bad',who='alice')[0],400)
 def test_ai_private_room_and_context(self):
  import integrations
  room=self.call('/api/ai/room','POST',{},who='alice')[1]['id']
  self.assertEqual(self.call('/api/rooms/'+room+'/messages',who='bob')[0],403)
  self.assertEqual(self.call('/api/rooms/'+room+'/ai','POST',{'prompt':'Olá'},who='alice')[0],503)
  with patch.dict(os.environ,{'OPENAI_API_KEY':'fake-test-key'}),patch.object(integrations,'external',return_value={'output':[{'type':'message','content':[{'type':'output_text','text':'Resposta do Ninja'}]}]}) as ext:
   st,r,_=self.call('/api/rooms/'+room+'/messages','POST',{'text':'Olá Ninja'},who='alice');self.assertEqual(st,200);self.assertIn('ai',r)
   messages=self.call('/api/rooms/'+room+'/messages',who='alice')[1]['messages'];self.assertEqual(messages[-1]['text'],'Resposta do Ninja');self.assertEqual(messages[-1]['name'],'Ninja IA')
   sent=ext.call_args.args[2];self.assertIn('Olá Ninja',sent['input']);self.assertFalse(sent['store'])
   self.call('/api/rooms/general/ai','PATCH',{'enabled':False})
   self.assertEqual(self.call('/api/rooms/general/ai','POST',{'prompt':'resuma'},who='alice')[0],409)
 def test_ai_failure_preserves_original_and_budget(self):
  import integrations
  room=self.call('/api/ai/room','POST',{},who='alice')[1]['id']
  with patch.dict(os.environ,{'OPENAI_API_KEY':'fake-test-key'}),patch.object(integrations,'external',side_effect=app.Error(503,'Teste de falha')):
   st,r,_=self.call('/api/rooms/'+room+'/messages','POST',{'text':'Mensagem preservada'},who='alice');self.assertEqual(st,200);self.assertEqual(r['ai_error'],'Teste de falha')
  self.assertEqual(self.call('/api/rooms/'+room+'/messages',who='alice')[1]['messages'][0]['text'],'Mensagem preservada')
  with patch.dict(os.environ,{'OPENAI_API_KEY':'fake-test-key','NJA_AI_USER_DAILY_LIMIT':'1'}):self.assertEqual(self.call('/api/rooms/'+room+'/ai','POST',{'prompt':'outro'},who='alice')[0],429)
 def test_audio_validation_and_acl(self):
  st,r,_=self.call('/api/rooms','POST',{'kind':'direct','members':['alice']});rid=r['id']
  # A small valid PCM WAV; browser test covers real MediaRecorder encoding.
  import wave
  out=__import__('io').BytesIO()
  with wave.open(out,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*1600)
  data=base64.b64encode(out.getvalue()).decode();payload={'room_id':rid,'data':data,'mime':'audio/wav'}
  self.assertEqual(self.call('/api/audio','POST',payload,who='bob')[0],403)
  st,r,_=self.call('/api/audio','POST',payload,who='alice');self.assertEqual(st,200);fid=r['id']
  self.assertEqual(self.call('/files/'+fid,who='bob')[0],403);self.assertEqual(self.call('/files/'+fid,who='master')[0],200)
  self.assertEqual(self.call('/api/audio','POST',payload|{'data':base64.b64encode(b'bad').decode()},who='alice')[0],400)
  self.assertEqual(self.call('/api/rooms/'+rid+'/messages',who='alice')[1]['files'][0]['mime'],'audio/wav')
  self.assertEqual(self.call('/api/audio/'+fid+'/transcribe','POST',{},who='alice')[0],503)
 def test_calls_signals_acl_busy_and_end(self):
  st,r,_=self.call('/api/calls','POST',{'room_id':'general','callee':'alice','mode':'video'});self.assertEqual(st,200);cid=r['call']['id']
  self.assertEqual(self.call('/api/calls/'+cid+'/signals',who='bob')[0],403)
  self.assertEqual(self.call('/api/calls','POST',{'room_id':'general','callee':'alice','mode':'audio'},who='bob')[0],409)
  self.assertEqual(self.call('/api/calls/'+cid+'/action','POST',{'action':'accept'})[0],409)
  self.assertEqual(self.call('/api/calls/'+cid+'/signals','POST',{'kind':'offer','payload':{'type':'offer','sdp':'test'}})[0],200)
  self.assertEqual(len(self.call('/api/calls/'+cid+'/signals',who='alice')[1]['signals']),1)
  self.assertEqual(self.call('/api/calls/'+cid+'/action','POST',{'action':'accept'},who='alice')[0],200)
  self.assertEqual(self.call('/api/calls/'+cid+'/signals','POST',{'kind':'answer','payload':{'type':'answer','sdp':'test'}},who='alice')[0],200)
  self.assertEqual(self.call('/api/calls/'+cid+'/signals','POST',{'kind':'candidate','payload':{'candidate':'candidate:x'}},who='alice')[0],200)
  signals=self.call('/api/calls/'+cid+'/signals')[1]['signals'];self.assertEqual(len(signals),2)
  self.assertEqual(self.call('/api/calls/'+cid+'/action','POST',{'action':'end'},who='alice')[0],200)
  self.assertEqual(self.call('/api/calls')[1]['calls'],[])
  self.assertEqual(self.call('/api/calls/'+cid+'/signals','POST',{'kind':'offer','payload':{}})[0],409)
 def test_call_expiry_and_removed_participant(self):
  cid=self.call('/api/calls','POST',{'room_id':'general','callee':'alice','mode':'audio'})[1]['call']['id']
  with app.connect() as c:c.execute('UPDATE calls SET expires=? WHERE id=?',(time.time()-1,cid))
  self.assertEqual(self.call('/api/calls/'+cid)[1]['call']['status'],'missed')
  cid=self.call('/api/calls','POST',{'room_id':'general','callee':'alice','mode':'audio'})[1]['call']['id']
  with app.connect() as c:c.execute("UPDATE users SET active=0 WHERE id='alice'")
  self.assertEqual(self.call('/api/calls/'+cid+'/signals')[0],403)
 def test_audio_transcription_and_ai_context(self):
  import integrations,io,wave
  out=io.BytesIO()
  with wave.open(out,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*160)
  fid=self.call('/api/audio','POST',{'room_id':'general','mime':'audio/wav','data':base64.b64encode(out.getvalue()).decode()},who='alice')[1]['id']
  with patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}),patch.object(integrations,'urlopen',return_value=io.BytesIO(b'{"text":"Entrega na sexta-feira"}')):
   self.assertEqual(self.call('/api/audio/'+fid+'/transcribe','POST',{},who='alice')[1]['text'],'Entrega na sexta-feira')
  self.assertEqual(self.call('/api/rooms/general/messages')[1]['files'][0]['transcript'],'Entrega na sexta-feira')
  with patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}),patch.object(integrations,'external',return_value={'output':[{'type':'message','content':[{'type':'output_text','text':'Combinado'}]}]}) as ext:
   self.assertEqual(self.call('/api/rooms/general/ai','POST',{'prompt':'Qual o prazo?'},who='alice')[0],200);self.assertIn('Entrega na sexta-feira',ext.call_args.args[2]['input'])
 def test_drive_refresh_disconnect_and_no_secret_exposure(self):
  import integrations
  with app.connect() as c:integrations.save_token(app,c,{'id':'alice'},{'access_token':'old','refresh_token':'secret-refresh','expires':0},'alice@nja.test')
  with patch.dict(os.environ,{'GOOGLE_CLIENT_ID':'test','GOOGLE_CLIENT_SECRET':'secret-client'}),patch.object(integrations,'external',side_effect=[{'access_token':'renewed','expires_in':3600},{'files':[]}]) as ext:
   self.assertEqual(self.call('/api/drive/files',who='alice')[0],200);self.assertEqual(ext.call_args.kwargs['headers']['Authorization'],'Bearer renewed')
  s=json.dumps(self.call('/api/integrations',who='alice')[1]);self.assertNotIn('secret-refresh',s);self.assertNotIn('secret-client',s);self.assertNotIn('renewed',s)
  with patch.object(integrations,'external',side_effect=app.Error(503,'Offline')):self.assertEqual(self.call('/api/drive/disconnect','POST',{},who='alice')[0],200)
  self.assertFalse(self.call('/api/integrations',who='alice')[1]['drive_connected'])
