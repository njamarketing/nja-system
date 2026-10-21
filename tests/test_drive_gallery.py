import unittest,os,io,base64
from unittest.mock import patch,MagicMock
import test_system,integrations,drive_gallery
from PIL import Image
app=test_system.app
class DriveGalleryTest(unittest.TestCase):
 setUp=test_system.SystemTest.setUp
 tearDown=test_system.SystemTest.tearDown
 call=test_system.SystemTest.call
 def connect_drive(self):
  with app.connect() as c:integrations.save_token(app,c,{'id':'alice'},{'access_token':'private-alice','expires':9999999999},'alice@test.com')
 def test_empty_root_and_fields(self):
  self.connect_drive()
  with patch.dict(os.environ,{'GOOGLE_DRIVE_ROOT_ID':''}),patch.object(integrations,'external',return_value={'files':[]}) as ext:
   self.assertEqual(self.call('/api/drive/files',who='alice')[0],200)
   from urllib.parse import parse_qs,urlsplit
   q=parse_qs(urlsplit(ext.call_args.args[1]).query)
   self.assertIn("'root' in parents",q['q'][0]);self.assertIn('hasThumbnail',q['fields'][0])
  self.assertEqual(self.call('/api/drive/files?folder=%27bad',who='alice')[0],400)
 def test_user_permission_and_no_store(self):
  self.connect_drive()
  self.assertEqual(self.call('/api/drive/thumbnail/file1',login=False)[0],401)
  self.assertEqual(self.call('/api/drive/thumbnail/file1',who='bob')[0],409)
  with patch.object(integrations,'external',return_value={'thumbnailLink':'https://lh3.googleusercontent.com/a'}) as ext,patch.object(drive_gallery,'fetch_thumbnail',return_value='data') as fetch:
   st,data,h=self.call('/api/drive/thumbnail/file1',who='alice');self.assertEqual(st,200);self.assertEqual(data['data'],'data');self.assertEqual(dict(h)['Cache-Control'],'no-store')
   self.assertEqual(ext.call_args.kwargs['headers']['Authorization'],'Bearer private-alice');fetch.assert_called_once_with('https://lh3.googleusercontent.com/a','private-alice')
  with patch.object(integrations,'external',side_effect=app.Error(403,'Sem acesso')),patch.object(drive_gallery,'fetch_thumbnail') as fetch:
   self.assertEqual(self.call('/api/drive/thumbnail/other',who='alice')[0],403);fetch.assert_not_called()
 def test_safe_proxy_and_thumbnail(self):
  for url in ['http://lh3.googleusercontent.com/a','https://googleusercontent.com.evil.test/a','https://127.0.0.1/a','https://user:pass@lh3.googleusercontent.com/a','https://lh3.googleusercontent.com:999/a']:
   self.assertFalse(drive_gallery.google_thumbnail_url(url));self.assertIsNone(drive_gallery.fetch_thumbnail(url,'private'))
  raw=io.BytesIO();Image.new('RGBA',(800,600),(20,40,80,0)).save(raw,format='PNG')
  response=MagicMock();response.__enter__.return_value.read.return_value=raw.getvalue();opener=MagicMock();opener.open.return_value=response
  with patch.object(drive_gallery,'build_opener',return_value=opener):
   data=drive_gallery.fetch_thumbnail('https://lh3.googleusercontent.com/a','private')
   with Image.open(io.BytesIO(base64.b64decode(data))) as im:self.assertEqual(im.size,(480,360));self.assertEqual(im.getpixel((0,0))[3],0)
   response.__enter__.return_value.read.return_value=b'<html>login</html>';self.assertIsNone(drive_gallery.fetch_thumbnail('https://lh3.googleusercontent.com/a','private'))
 def test_redirect_does_not_leak_token(self):
  from urllib.error import HTTPError
  opener=MagicMock();opener.open.side_effect=HTTPError('x',302,'Found',{'Location':'https://evil.test/a'},None)
  with patch.object(drive_gallery,'build_opener',return_value=opener):
   self.assertIsNone(drive_gallery.fetch_thumbnail('https://lh3.googleusercontent.com/a','private'));self.assertEqual(opener.open.call_count,1)
