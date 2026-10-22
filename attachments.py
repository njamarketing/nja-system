"""Streamed task/chat materials, container checks and protected range downloads."""
import os,re,tempfile,zipfile
from pathlib import Path
from urllib.parse import quote

MAX_ATTACHMENT=100*1024*1024
OFFICE={'docx':('word/document.xml','application/vnd.openxmlformats-officedocument.wordprocessingml.document'),'xlsx':('xl/workbook.xml','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),'pptx':('ppt/presentation.xml','application/vnd.openxmlformats-officedocument.presentationml.presentation')}
ODF={'odt':'application/vnd.oasis.opendocument.text','ods':'application/vnd.oasis.opendocument.spreadsheet','odp':'application/vnd.oasis.opendocument.presentation'}

def identify(a,path,name):
    ext=Path(name).suffix.lower().lstrip('.')
    with open(path,'rb') as f:head=f.read(8192)
    if ext in ['png','jpg','jpeg','webp','gif']:
        signatures={'png':head.startswith(b'\x89PNG\r\n\x1a\n'),'jpg':head.startswith(b'\xff\xd8\xff'),'jpeg':head.startswith(b'\xff\xd8\xff'),'webp':head.startswith(b'RIFF') and head[8:12]==b'WEBP','gif':head.startswith((b'GIF87a',b'GIF89a'))}
        if signatures[ext]:return {'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','gif':'image/gif','webp':'image/webp'}[ext]
    elif ext=='pdf' and head.startswith(b'%PDF-'):return 'application/pdf'
    elif ext in ['mp4','m4v','mov'] and len(head)>12 and head[4:8]==b'ftyp':return 'video/quicktime' if ext=='mov' else 'video/mp4'
    elif ext=='webm' and head.startswith(b'\x1aE\xdf\xa3') and b'webm' in head[:128]:return 'video/webm'
    elif ext in OFFICE or ext in ODF:
        try:
            with zipfile.ZipFile(path) as z:
                items=z.infolist();names={x.filename for x in items}
                if len(items)>10000 or sum(x.file_size for x in items)>250*1024*1024 or any(x.flag_bits&1 for x in items):raise ValueError()
                if ext in OFFICE and '[Content_Types].xml' in names and OFFICE[ext][0] in names and not any(x.lower().endswith('vbaproject.bin') for x in names):return OFFICE[ext][1]
                if ext in ODF and 'mimetype' in names and z.getinfo('mimetype').file_size<200 and z.read('mimetype').decode()==ODF[ext]:return ODF[ext]
        except (zipfile.BadZipFile,ValueError,UnicodeDecodeError,RuntimeError):pass
    elif ext in ['doc','xls','ppt'] and head.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):return {'doc':'application/msword','xls':'application/vnd.ms-excel','ppt':'application/vnd.ms-powerpoint'}[ext]
    elif ext in ['txt','csv']:
        try:
            text=head.decode('utf-8-sig')
            if '\0' not in text and not any(ord(x)<32 and x not in '\r\n\t' for x in text):return 'text/plain' if ext=='txt' else 'text/csv'
        except UnicodeDecodeError:pass
    raise a.Error(400,'Formato inválido. Envie imagem, PDF, documento Office/OpenDocument, TXT/CSV ou vídeo MP4, WebM ou MOV.')

def upload(a,c,u,q,stream,length):
    tid=q.get('task_id',[''])[0] or None;rid=q.get('room_id',[''])[0] or None
    cid=q.get('editorial_client_id',[''])[0] or None;review_id=q.get('review_id',[''])[0] or None
    if sum(bool(x) for x in [tid,rid,cid,review_id])!=1:raise a.Error(400,'Selecione uma tarefa, conversa, cliente editorial ou revisão para o arquivo.')
    if review_id:
        import agency_portal
        a.need(u,'approvals');a.need(u,'approval_manage');review=agency_portal.review(a,c,u,review_id)
    if cid:
        import agency_access
        a.need(u,'editorial');a.need(u,'editorial_manage');client=agency_access.need(a,c,u,cid)
        if not client['active']:raise a.Error(409,'Cliente desativado.')
    if tid:a.get_task(c,u,tid);a.need(u,'task_edit')
    if rid:
        import teamwork
        teamwork.need_action(a,c,u,rid,'send')
    name=a.textfield({'name':q.get('name',[''])[0]},'name',True,180)
    if any(ord(x)<32 for x in name):raise a.Error(400,'Nome de arquivo inválido.')
    name=Path(name.replace('\\','/')).name
    if not name or not 0<length<=MAX_ATTACHMENT:raise a.Error(413,'Cada material pode ter até 100 MB.')
    file_id=a.uid();dest=a.DATA/'uploads'/file_id;temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=a.DATA/'uploads',prefix='.incoming-',delete=False) as f:
            temporary=Path(f.name);remaining=length
            while remaining:
                block=stream.read(min(64*1024,remaining))
                if not block:raise a.Error(400,'O envio foi interrompido. Selecione o arquivo novamente.')
                f.write(block);remaining-=len(block)
        mime=identify(a,temporary,name)
        if cid or review_id:
            if mime not in ['image/jpeg','image/png','image/webp','video/mp4']:raise a.Error(400,'Envie uma imagem JPG, PNG, WebP ou vídeo MP4.')
            if mime.startswith('image/'):
                from PIL import Image,ImageOps
                try:
                    with Image.open(temporary) as image:
                        if image.width*image.height>40_000_000:raise ValueError()
                        image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((1440,1440));image.save(temporary,format='JPEG',quality=94)
                    mime='image/jpeg';name=Path(name).stem+'.jpg';length=temporary.stat().st_size
                except Exception:raise a.Error(400,'Imagem inválida ou grande demais. Use até 40 megapixels.')
        os.replace(temporary,dest);temporary=None
        c.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?)',(file_id,name,mime,length,u['id'],tid,rid,a.now()))
        if cid:c.execute('INSERT INTO editorial_uploads VALUES(?,?)',(file_id,cid))
        if review_id:c.execute('INSERT INTO review_uploads VALUES(?,?)',(file_id,review_id))
        if rid:
            for member in c.execute('SELECT user_id FROM room_members WHERE room_id=? AND user_id<>?',(rid,u['id'])):a.notify(c,member[0],u['name'],'Enviou um material: '+name,'chats:'+rid,'messages')
        a.audit(c,u,'file_upload',file_id,name)
        return {'id':file_id,'name':name,'mime':mime,'size':length}
    except Exception:
        if dest.exists():dest.unlink()
        raise
    finally:
        if temporary and temporary.exists():temporary.unlink()

def download(a,f,environ,start_response,headers):
    path=a.DATA/'uploads'/f['id']
    if not path.is_file():raise a.Error(404,'Arquivo não encontrado no armazenamento.')
    size=path.stat().st_size;start=0;end=size-1;code='200 OK';extra=[]
    # Ignore multipart/unknown ranges; support one byte range for media seeking.
    requested=environ.get('HTTP_RANGE','')
    if requested and ',' not in requested:
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
        invalid=not match or not any(match.groups()) or size==0
        if not invalid:
            left,right=match.groups()
            if left:start=int(left);end=min(int(right),size-1) if right else size-1
            else:
                suffix=int(right);invalid=suffix<=0;start=max(0,size-suffix)
            invalid=invalid or start>=size or end<start
        if invalid:
            start_response('416 Range Not Satisfiable',headers+[('Content-Range',f'bytes */{size}'),('Content-Length','0'),('Cache-Control','no-store'),('Accept-Ranges','bytes')]);return []
        code='206 Partial Content';extra=[('Content-Range',f'bytes {start}-{end}/{size}')]
    name=''.join(x for x in f['name'] if 32<=ord(x)<127 and x not in ['"','\\']) or 'arquivo'
    inline=f['mime'].startswith(('image/','audio/','video/')) and not environ.get('QUERY_STRING','').startswith('download=1')
    disposition=('inline' if inline else 'attachment')+f'; filename="{name}"; filename*=UTF-8\'\''+quote(f['name'],safe='')
    count=max(0,end-start+1)
    start_response(code,headers+[('Content-Type',f['mime']),('Content-Length',str(count)),('Content-Disposition',disposition),('Cache-Control','no-store'),('Accept-Ranges','bytes')]+extra)
    if environ['REQUEST_METHOD']=='HEAD':return []
    def chunks():
        with path.open('rb') as stream:
            stream.seek(start);remaining=count
            while remaining:
                chunk=stream.read(min(64*1024,remaining))
                if not chunk:break
                remaining-=len(chunk);yield chunk
    return chunks()
