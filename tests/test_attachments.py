import unittest,io,json,zipfile
from urllib.parse import urlencode
import test_system
app=test_system.app
class AttachmentTest(unittest.TestCase):
 setUp=test_system.SystemTest.setUp
 tearDown=test_system.SystemTest.tearDown
 call=test_system.SystemTest.call
 make_task=test_system.SystemTest.make_task
 def raw(self,path,method='GET',body=b'',who='alice',headers=None,length=None):
  env={'REQUEST_METHOD':method,'PATH_INFO':path.split('?')[0],'QUERY_STRING':path.partition('?')[2],'CONTENT_TYPE':'application/octet-stream','CONTENT_LENGTH':str(len(body) if length is None else length),'wsgi.input':io.BytesIO(body),'REMOTE_ADDR':'127.0.0.1','HTTP_COOKIE':self.cookies.get(who,''),'HTTP_X_CSRF_TOKEN':self.csrf.get(who,'')}
  env.update(headers or {});capture={}
  def response(status,hs):capture.update(status=int(status.split()[0]),headers=dict(hs))
  raw=b''.join(app.application(env,response));return capture['status'],raw,capture['headers']
 def send(self,name,raw,destination,who='alice',**kw):
  st,out,h=self.raw('/api/upload-binary?'+urlencode({'name':name,**destination}),'POST',raw,who=who,**kw);return st,json.loads(out),h
 def test_task_materials_and_chat_video_acl(self):
  tid=self.make_task();video=b'\0\0\0\x18ftypisom\0\0\0\0isommp42'
  st,v,_=self.send('entrega.mp4',video,{'task_id':tid});self.assertEqual(st,200);self.assertEqual(v['mime'],'video/mp4')
  self.assertEqual(self.call('/tasks/'+tid)[0],404)
  task=self.call('/api/tasks/'+tid,who='alice')[1];self.assertEqual(task['files'][0]['name'],'entrega.mp4')
  self.assertEqual(self.raw('/files/'+v['id'],who='bob')[0],403)
  rid=self.call('/api/rooms','POST',{'kind':'direct','members':['alice']})[1]['id']
  st,v,_=self.send('video.mp4',video,{'room_id':rid});self.assertEqual(st,200)
  self.assertEqual(self.raw('/files/'+v['id'],who='bob')[0],403)
  st,raw,h=self.raw('/files/'+v['id']);self.assertEqual(st,200);self.assertEqual(raw,video);self.assertIn('inline',h['Content-Disposition'])
 def test_document_formats_and_download_disposition(self):
  tid=self.make_task()
  for ext,main in [('docx','word/document.xml'),('xlsx','xl/workbook.xml'),('pptx','ppt/presentation.xml')]:
   out=io.BytesIO()
   with zipfile.ZipFile(out,'w') as z:z.writestr('[Content_Types].xml','<Types/>');z.writestr(main,'<document/>')
   st,r,_=self.send('material.'+ext,out.getvalue(),{'task_id':tid});self.assertEqual(st,200,r)
   st,_,h=self.raw('/files/'+r['id']);self.assertEqual(st,200);self.assertIn('attachment',h['Content-Disposition'])
  for name,raw in [('briefing.pdf',b'%PDF-1.4\n%%EOF'),('pauta.txt','Conteúdo da pauta'.encode()),('dados.csv',b'nome,valor\nA,10')]:self.assertEqual(self.send(name,raw,{'task_id':tid})[0],200)
 def test_reject_spoofed_document_macro_and_cleanup(self):
  tid=self.make_task()
  for name,raw in [('bad.docx',b'not-a-zip'),('bad.mp4',b'%PDF-1.4'),('bad.exe',b'MZ executable'),('bad.txt',b'MZ\0\0')]:self.assertEqual(self.send(name,raw,{'task_id':tid})[0],400)
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:z.writestr('[Content_Types].xml','types');z.writestr('word/document.xml','doc');z.writestr('word/vbaProject.bin','macro')
  self.assertEqual(self.send('macro.docx',out.getvalue(),{'task_id':tid})[0],400)
  self.assertEqual(list((app.DATA/'uploads').iterdir()),[])
 def test_upload_limits_csrf_origin_and_short_body(self):
  tid=self.make_task();dest={'task_id':tid}
  self.assertEqual(self.send('pauta.txt',b'abc',dest,headers={'HTTP_X_CSRF_TOKEN':''})[0],403)
  self.assertEqual(self.send('pauta.txt',b'abc',dest,headers={'HTTP_ORIGIN':'https://evil.test'})[0],403)
  self.assertEqual(self.send('pauta.txt',b'abc',dest,who='bob')[0],403)
  self.assertEqual(self.send('pauta.txt',b'abc',dest,length=101*1024*1024)[0],413)
  self.assertEqual(self.send('pauta.txt',b'abc',dest,length=10)[0],400)
  self.assertEqual(list((app.DATA/'uploads').iterdir()),[])
 def test_large_upload_range_seek_head_and_download(self):
  tid=self.make_task();raw=b'%PDF-1.4\n'+b'a'*(9*1024*1024)
  st,r,_=self.send('material-grande.pdf',raw,{'task_id':tid});self.assertEqual(st,200);fid=r['id']
  st,part,h=self.raw('/files/'+fid,headers={'HTTP_RANGE':'bytes=2-9'});self.assertEqual(st,206);self.assertEqual(part,raw[2:10]);self.assertEqual(h['Content-Range'],'bytes 2-9/'+str(len(raw)))
  st,part,h=self.raw('/files/'+fid,headers={'HTTP_RANGE':'bytes=-5'});self.assertEqual(st,206);self.assertEqual(part,raw[-5:])
  self.assertEqual(self.raw('/files/'+fid,headers={'HTTP_RANGE':'bytes=999999999-1000000000'})[0],416)
  self.assertEqual(self.raw('/files/'+fid,headers={'HTTP_RANGE':'bytes=100-2'})[0],416)
  st,part,h=self.raw('/files/'+fid,'HEAD');self.assertEqual(st,200);self.assertEqual(part,b'');self.assertEqual(int(h['Content-Length']),len(raw))
  self.assertEqual(self.raw('/files/'+fid,who='bob',headers={'HTTP_RANGE':'bytes=0-2'})[0],403)
