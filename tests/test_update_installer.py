import unittest,tempfile,subprocess,os,tarfile
from pathlib import Path

class UpdateInstallerTest(unittest.TestCase):
 def run_installer(self,fail=False):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'release';target=root/'live';binpath=root/'bin'
   source.mkdir();target.mkdir();binpath.mkdir();(source/'static').mkdir();(target/'static').mkdir()
   for name in ['app.py','interaction_updates.py','drive_gallery.py','requirements.txt']:(source/name).write_text('updated')
   for name in ['index.html','interaction-updates.js','interaction-updates.css','celebrations.js']:(source/'static'/name).write_text('updated')
   (source/'note.md').write_text('guide');(source/'ATUALIZAR-NJA.sh').write_text((Path(__file__).parents[1]/'ATUALIZAR-NJA.sh').read_text())
   originals={'.env':'DUMMY_SECRET=preserved','compose.yaml':'DNS CUSTOM','compose.override.yaml':'CUSTOM VOLUME','Dockerfile':'CUSTOM IMAGE','app.py':'old code'}
   for name,text in originals.items():(target/name).write_text(text)
   mock=binpath/'docker';mock.write_text('''#!/usr/bin/env python3
import sys,os,pathlib
args=sys.argv[1:]
if args[:4]==['compose','ps','-q','web']:print('mock-web')
if '--output' in args and os.getenv('MOCK_BACKUP_FAIL')=='1':sys.exit(1)
if args and args[0]=='cp':
 p=pathlib.Path(args[-1]);p.mkdir();(p/'nja.sqlite3').write_bytes(b'existing-database');(p/'uploads').mkdir();(p/'uploads'/'original.png').write_bytes(b'original-upload');(p/'integration.key').write_bytes(b'original-key')
''');mock.chmod(0o755)
   env=os.environ|{'PATH':str(binpath)+os.pathsep+os.environ['PATH'],'MOCK_BACKUP_FAIL':'1' if fail else '0'}
   result=subprocess.run(['bash',str(source/'ATUALIZAR-NJA.sh'),str(target)],capture_output=True,text=True,env=env)
   for name in ['.env','compose.yaml','compose.override.yaml','Dockerfile']:self.assertEqual((target/name).read_text(),originals[name])
   if fail:self.assertNotEqual(result.returncode,0);self.assertEqual((target/'app.py').read_text(),'old code')
   else:
    self.assertEqual(result.returncode,0,result.stderr);self.assertEqual((target/'app.py').read_text(),'updated')
    backup=next(root.glob('nja-backup-v117-*'));self.assertEqual((backup/'dados/nja.sqlite3').read_bytes(),b'existing-database')
    self.assertEqual((backup/'dados/uploads/original.png').read_bytes(),b'original-upload')
    with tarfile.open(backup/'codigo-e-configuracoes.tar.gz') as tar:self.assertEqual(tar.extractfile('./app.py').read(),b'old code')
 def test_installer_preserves_config_and_saves_backup(self):self.run_installer()
 def test_backup_failure_stops_before_copy(self):self.run_installer(True)
