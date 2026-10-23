"""NJA 1.2: profiles, time tracking, customers and internal social content."""
import base64,io,json,re,time
import agency_access
from datetime import datetime,timedelta,timezone,date

def init(c):
    columns=[('users','birthday',"TEXT NOT NULL DEFAULT ''"),('users','thought',"TEXT NOT NULL DEFAULT ''"),('users','hired',"TEXT NOT NULL DEFAULT ''"),('users','corporate_email',"TEXT NOT NULL DEFAULT ''"),('users','career',"TEXT NOT NULL DEFAULT '[]'"),('users','last_seen','REAL NOT NULL DEFAULT 0'),('sessions','last_seen','REAL NOT NULL DEFAULT 0'),('rooms','client_id','TEXT'),('rooms','cover','TEXT')]
    for table,col,definition in columns:
        if col not in [r[1] for r in c.execute('PRAGMA table_info('+table+')')]:c.execute('ALTER TABLE '+table+' ADD COLUMN '+col+' '+definition)
    c.executescript('''
CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY,name TEXT NOT NULL,entered TEXT NOT NULL,product TEXT NOT NULL,checklist TEXT NOT NULL DEFAULT '[]',description TEXT NOT NULL DEFAULT '',photo TEXT,cover TEXT,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS time_entries(id TEXT PRIMARY KEY,task_id TEXT NOT NULL REFERENCES tasks(id),user_id TEXT NOT NULL REFERENCES users(id),seconds INTEGER NOT NULL CHECK(seconds>0),note TEXT NOT NULL DEFAULT '',created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS running_timers(user_id TEXT PRIMARY KEY REFERENCES users(id),task_id TEXT NOT NULL REFERENCES tasks(id),started REAL NOT NULL);
CREATE TABLE IF NOT EXISTS posts(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),text TEXT NOT NULL,kind TEXT NOT NULL DEFAULT 'text',image TEXT,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS post_likes(post_id TEXT REFERENCES posts(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id),PRIMARY KEY(post_id,user_id));
CREATE TABLE IF NOT EXISTS post_comments(id TEXT PRIMARY KEY,post_id TEXT REFERENCES posts(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id),text TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stories(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),text TEXT NOT NULL,image TEXT,created TEXT NOT NULL,expires TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_assets(file_id TEXT PRIMARY KEY REFERENCES files(id),scope TEXT NOT NULL,entity_id TEXT,expires TEXT);
CREATE TABLE IF NOT EXISTS message_reactions(message_id TEXT REFERENCES messages(id),user_id TEXT REFERENCES users(id),emoji TEXT NOT NULL,PRIMARY KEY(message_id,user_id));
CREATE TABLE IF NOT EXISTS social_schema(version INTEGER PRIMARY KEY);
''')
    if not c.execute('SELECT 1 FROM social_schema WHERE version=1').fetchone():
        for r in c.execute('SELECT * FROM roles').fetchall():
            ps=json.loads(r['permissions'])
            if r['id']=='member':ps+=['social','clients']
            if r['id']=='master':ps+=['social','clients','client_manage']
            c.execute('UPDATE roles SET permissions=? WHERE id=?',(json.dumps(list(dict.fromkeys(ps))),r['id']))
        c.execute('INSERT INTO social_schema VALUES(1)')

def day(a,d,key):
    s=a.textfield(d,key,False,10)
    if s:
        try:date.fromisoformat(s)
        except ValueError:raise a.Error(400,'Data inválida: '+key)
    return s

def profile_fields(a,d):
    fields={}
    for key,limit in [('thought',240),('corporate_email',254)]:
        if key in d:fields[key]=a.textfield(d,key,False,limit)
    if fields.get('corporate_email') and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',fields['corporate_email']):raise a.Error(400,'E-mail corporativo inválido.')
    for key in ['birthday','hired']:
        if key in d:fields[key]=day(a,d,key)
    for key in ['cover_x','cover_y','cover_zoom']:
        if key in d:
            try:value=int(d[key])
            except (TypeError,ValueError):raise a.Error(400,'Ajuste de capa inválido.')
            low,high=(100,220) if key=='cover_zoom' else (0,100)
            if not low<=value<=high:raise a.Error(400,'Ajuste de capa fora do limite.')
            fields[key]=value
    if 'career' in d:
        if not isinstance(d['career'],list) or len(d['career'])>60:raise a.Error(400,'Histórico inválido.')
        rows=[]
        for item in d['career']:
            if not isinstance(item,dict):raise a.Error(400,'Histórico inválido.')
            dt=day(a,item,'date')
            if not dt:raise a.Error(400,'Informe a data da função ou promoção.')
            rows.append({'date':dt,'title':a.textfield(item,'title',True,120),'description':a.textfield(item,'description',False,500)})
        fields['career']=json.dumps(sorted(rows,key=lambda x:x['date']))
    return fields

def presence(c,id):
    last=c.execute('SELECT last_seen FROM users WHERE id=?',(id,)).fetchone()[0]
    online=bool(c.execute('SELECT 1 FROM sessions WHERE user_id=? AND expires>? AND last_seen>?',(id,time.time(),time.time()-75)).fetchone())
    return {'online':online,'last_seen_at':datetime.fromtimestamp(last,timezone.utc).isoformat() if last else None}

def month_seconds(a,c,id):
    local=datetime.now(a.TZ);start=local.replace(day=1,hour=0,minute=0,second=0,microsecond=0);end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
    total=c.execute("SELECT COALESCE(SUM(e.seconds),0) FROM time_entries e JOIN tasks t ON t.id=e.task_id WHERE e.user_id=? AND t.status='done' AND t.completed>=? AND t.completed<?",(id,start.astimezone(timezone.utc).isoformat(timespec='seconds'),end.astimezone(timezone.utc).isoformat(timespec='seconds'))).fetchone()[0]
    return {'seconds':total,'month':local.strftime('%Y-%m'),'criterion':'Tempo registrado pelo usuário em tarefas atualmente concluídas, cuja conclusão ocorreu neste mês (São Paulo).'}

def finish_timer(a,c,row):
    secs=max(1,int(time.time()-row['started']))
    c.execute('INSERT INTO time_entries VALUES(?,?,?,?,?,?)',(a.uid(),row['task_id'],row['user_id'],secs,'Cronômetro',a.now()))
    c.execute('DELETE FROM running_timers WHERE user_id=?',(row['user_id'],))

def asset(a,c,u,id,scope):
    if not id:return None
    r=c.execute('SELECT f.*,s.scope,s.entity_id FROM files f JOIN social_assets s ON s.file_id=f.id WHERE f.id=?',(id,)).fetchone()
    if not r or r['user_id']!=u['id'] or r['scope']!=scope or r['entity_id']:raise a.Error(400,'Envie uma nova imagem para esta publicação.')
    return id

def file_access(a,c,u,id):
    r=c.execute('SELECT * FROM social_assets WHERE file_id=?',(id,)).fetchone()
    if not r:return False
    if r['scope']=='client':
        a.need(u,'clients')
        if r['entity_id']:agency_access.need(a,c,u,r['entity_id'])
    else:a.need(u,'social')
    if r['expires'] and r['expires']<=a.now():raise a.Error(404,'História expirada.')
    if not r['entity_id']:
        owner=c.execute('SELECT user_id FROM files WHERE id=?',(id,)).fetchone()[0]
        if owner!=u['id']:raise a.Error(403,'Arquivo ainda não publicado.')
    elif r['scope'] in ['post','story']:
        table='posts' if r['scope']=='post' else 'stories'
        if not c.execute('SELECT 1 FROM '+table+' WHERE id=?',(r['entity_id'],)).fetchone():raise a.Error(404,'Publicação removida.')
    return True

def serialize_post(c,r,u):
    v=dict(r);v['likes']=c.execute('SELECT COUNT(*) FROM post_likes WHERE post_id=?',(r['id'],)).fetchone()[0];v['liked']=bool(c.execute('SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?',(r['id'],u['id'])).fetchone());v['comments']=[dict(x) for x in c.execute('SELECT * FROM post_comments WHERE post_id=? ORDER BY created LIMIT 100',(r['id'],))];return v

def api(a,c,u,method,path,d,q):
    if path=='/api/presence' and method=='POST':
        return {'users':{r[0]:presence(c,r[0]) for r in c.execute('SELECT id FROM users WHERE active=1')}}
    if path.startswith('/api/profiles/') and method=='GET':
        id=path.split('/')[-1]
        if id!=u['id'] and not any(a.perm(u,k) for k in ['team','chats','social']):raise a.Error(403,'Sem acesso ao perfil.')
        row=c.execute('SELECT * FROM users WHERE id=? AND active=1',(id,)).fetchone()
        if not row:raise a.Error(404,'Perfil não encontrado.')
        keys=['id','name','title','area','bio','photo','cover','cover_x','cover_y','cover_zoom','birthday','thought','hired','corporate_email','created','active']
        result={k:row[k] for k in keys};result['career']=json.loads(row['career']);result.update(presence(c,id));result['work_month']=month_seconds(a,c,id)
        return result
    if path.startswith('/api/tasks/') and path.endswith('/time'):
        tid=path.split('/')[3];t=a.get_task(c,u,tid)
        if method=='GET':return {'entries':[dict(r) for r in c.execute('SELECT * FROM time_entries WHERE task_id=? ORDER BY created DESC',(tid,))],'timer':dict(r) if (r:=c.execute('SELECT * FROM running_timers WHERE user_id=?',(u['id'],)).fetchone()) else None}
        if method=='POST':
            a.need(u,'task_edit');action=d.get('action')
            if action=='start':
                if t['status']=='done':raise a.Error(400,'Reabra a tarefa antes de iniciar o cronômetro.')
                if c.execute('SELECT 1 FROM running_timers WHERE user_id=?',(u['id'],)).fetchone():raise a.Error(409,'Você já tem um cronômetro ativo. Pare-o primeiro.')
                c.execute('INSERT INTO running_timers VALUES(?,?,?)',(u['id'],tid,time.time()))
            elif action=='stop':
                row=c.execute('SELECT * FROM running_timers WHERE user_id=? AND task_id=?',(u['id'],tid)).fetchone()
                if not row:raise a.Error(400,'Não há cronômetro ativo nesta tarefa.')
                finish_timer(a,c,row)
            elif action=='manual':
                minutes=d.get('minutes')
                if isinstance(minutes,bool) or not isinstance(minutes,(float,int)) or not 1<=minutes<=1440:raise a.Error(400,'Informe entre 1 e 1440 minutos.')
                c.execute('INSERT INTO time_entries VALUES(?,?,?,?,?,?)',(a.uid(),tid,u['id'],int(minutes*60),a.textfield(d,'note',False,240),a.now()))
            else:raise a.Error(400,'Ação de tempo inválida.')
            a.audit(c,u,'task_time_'+action,tid);return {'ok':True}
    if path=='/api/clients':
        a.need(u,'clients')
        if method=='GET':return [dict(r)|{'checklist':json.loads(r['checklist'])} for r in c.execute('SELECT * FROM clients ORDER BY name') if agency_access.allowed(c,u,r['id'])]
        if method=='POST':
            a.need(u,'client_manage');id=a.uid();entered=day(a,d,'entered')
            if not entered:raise a.Error(400,'Informe a data de entrada.')
            c.execute('INSERT INTO clients(id,name,entered,product,description,checklist,created) VALUES(?,?,?,?,?,?,?)',(id,a.textfield(d,'name',True,120),entered,a.textfield(d,'product',True,240),a.textfield(d,'description',False,2000),json.dumps(checklist(a,d)),a.now()));agency_access.created(c,u,id);a.audit(c,u,'client_create',id);return {'id':id}
    if path.startswith('/api/clients/') and method=='PATCH':
        a.need(u,'clients');a.need(u,'client_manage');id=path.split('/')[-1];agency_access.need(a,c,u,id)
        if not c.execute('SELECT 1 FROM clients WHERE id=?',(id,)).fetchone():raise a.Error(404,'Cliente não encontrado.')
        fields={}
        for k in ['name','product','description']:
            if k in d:fields[k]=a.textfield(d,k,k!='description',2000 if k=='description' else 240)
        if 'entered' in d:
            fields['entered']=day(a,d,'entered')
            if not fields['entered']:raise a.Error(400,'Informe a data de entrada.')
        if 'checklist' in d:fields['checklist']=json.dumps(checklist(a,d))
        for k in ['photo','cover']:
            if k in d:
                fields[k]=asset(a,c,u,d[k],'client');c.execute('UPDATE social_assets SET entity_id=? WHERE file_id=?',(id,fields[k]))
        if fields:c.execute('UPDATE clients SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',list(fields.values())+[id])
        if 'name' in fields:c.execute('UPDATE rooms SET project=? WHERE client_id=?',(fields['name'],id))
        # Keep the same brand across all linked conversations.
        if any(k in fields for k in ['photo','cover']):
            brand={k:v for k,v in fields.items() if k in ['photo','cover']};c.execute('UPDATE rooms SET '+','.join(k+'=?' for k in brand)+' WHERE client_id=?',list(brand.values())+[id])
        a.audit(c,u,'client_update',id);return {'ok':True}
    if path.startswith('/api/rooms/') and path.endswith('/brand') and method=='PATCH':
        id=path.split('/')[3];a.room_access(c,u,id);a.need(u,'chat_manage')
        room=c.execute('SELECT * FROM rooms WHERE id=?',(id,)).fetchone()
        if room['kind']=='direct':raise a.Error(400,'Conversa individual usa a identidade do usuário.')
        client=c.execute('SELECT * FROM clients WHERE id=?',(d.get('client_id'),)).fetchone()
        a.need(u,'clients')
        if not client:raise a.Error(400,'Selecione um cliente cadastrado.')
        agency_access.need(a,c,u,client['id'])
        c.execute('UPDATE rooms SET client_id=?,photo=?,cover=?,project=? WHERE id=?',(client['id'],client['photo'],client['cover'],client['name'],id))
        c.execute('INSERT OR IGNORE INTO client_team SELECT ?,user_id FROM room_members WHERE room_id=?',(client['id'],id))
        a.audit(c,u,'room_brand',id);return {'ok':True}
    if path.startswith('/api/rooms/') and path.endswith('/reactions'):
        rid=path.split('/')[3];a.room_access(c,u,rid)
        if method=='GET':return [dict(r) for r in c.execute('SELECT r.* FROM message_reactions r JOIN messages m ON m.id=r.message_id WHERE m.room_id=?',(rid,))]
        if method=='POST':
            import teamwork
            teamwork.need_action(a,c,u,rid,'send')
            mid=d.get('message_id');emoji=d.get('emoji')
            if not c.execute('SELECT 1 FROM messages WHERE id=? AND room_id=?',(mid,rid)).fetchone():raise a.Error(404,'Mensagem não encontrada.')
            if emoji not in ['👍','❤️','😂','🎉','🔥','🥷','👏','✅']:raise a.Error(400,'Emoji inválido.')
            row=c.execute('SELECT emoji FROM message_reactions WHERE message_id=? AND user_id=?',(mid,u['id'])).fetchone()
            if row and row[0]==emoji:c.execute('DELETE FROM message_reactions WHERE message_id=? AND user_id=?',(mid,u['id']))
            else:c.execute('INSERT OR REPLACE INTO message_reactions VALUES(?,?,?)',(mid,u['id'],emoji))
            a.audit(c,u,'message_reaction',mid);return {'ok':True}
    if path=='/api/media' and method=='POST':
        scope=d.get('scope')
        if scope not in ['post','story','client']:raise a.Error(400,'Destino inválido.')
        if scope=='client':a.need(u,'clients');a.need(u,'client_manage')
        else:a.need(u,'social')
        try:
            from PIL import Image,ImageOps
            raw=base64.b64decode(d.get('data',''),validate=True)
            if not raw or len(raw)>a.MAX_FILE:raise ValueError()
            Image.MAX_IMAGE_PIXELS=20_000_000
            im=Image.open(io.BytesIO(raw));im.load();im=ImageOps.exif_transpose(im);im.thumbnail((1800,1800));out=io.BytesIO();im.convert('RGB').save(out,format='JPEG',quality=90);raw=out.getvalue()
        except Exception:raise a.Error(400,'Envie uma imagem válida de até 8 MB.')
        id=a.uid();(a.DATA/'uploads'/id).write_bytes(raw);c.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?)',(id,'imagem.jpg','image/jpeg',len(raw),u['id'],None,None,a.now()));c.execute('INSERT INTO social_assets VALUES(?,?,NULL,NULL)',(id,scope));return {'id':id}
    if path=='/api/posts':
        a.need(u,'social')
        if method=='GET':
            owner=q.get('user',[''])[0]
            rows=c.execute('SELECT * FROM posts'+(' WHERE user_id=?' if owner else '')+' ORDER BY created DESC,rowid DESC LIMIT 100',(owner,) if owner else ())
            return [serialize_post(c,r,u) for r in rows]
        if method=='POST':
            tx=a.textfield(d,'text',False,5000);image=asset(a,c,u,d.get('image'),'post');kind=d.get('kind','text')
            if kind not in ['text','thought']:raise a.Error(400,'Tipo de publicação inválido.')
            if not tx and not image:raise a.Error(400,'Escreva algo ou adicione uma foto.')
            id=a.uid();c.execute('INSERT INTO posts(id,user_id,text,kind,image,created) VALUES(?,?,?,?,?,?)',(id,u['id'],tx,kind,image,a.now()))
            if image:c.execute('UPDATE social_assets SET entity_id=? WHERE file_id=?',(id,image))
            a.notify_mentions(c,u,d,tx,'feed','messages');a.audit(c,u,'post_create',id);return {'id':id}
    if path.startswith('/api/posts/'):
        a.need(u,'social');parts=path.split('/');id=parts[3];post=c.execute('SELECT * FROM posts WHERE id=?',(id,)).fetchone()
        if not post:raise a.Error(404,'Publicação não encontrada.')
        if len(parts)==4 and method=='DELETE':
            if post['user_id']!=u['id'] and not u['master']:raise a.Error(403,'Somente o autor ou master pode excluir.')
            c.execute('DELETE FROM posts WHERE id=?',(id,));a.audit(c,u,'post_delete',id);return {'ok':True}
        if len(parts)==5 and parts[4]=='like' and method=='POST':
            row=c.execute('SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?',(id,u['id'])).fetchone()
            if row:c.execute('DELETE FROM post_likes WHERE post_id=? AND user_id=?',(id,u['id']))
            else:c.execute('INSERT INTO post_likes VALUES(?,?)',(id,u['id']))
            a.audit(c,u,'post_like',id);return {'ok':True}
        if len(parts)==5 and parts[4]=='comments' and method=='POST':
            parent=d.get('parent_id') or None
            if parent and not c.execute('SELECT 1 FROM post_comments WHERE id=? AND post_id=?',(parent,id)).fetchone():raise a.Error(400,'Comentário de origem inválido.')
            c.execute('INSERT INTO post_comments(id,post_id,user_id,text,created,parent_id) VALUES(?,?,?,?,?,?)',(a.uid(),id,u['id'],a.textfield(d,'text',True,2000),a.now(),parent));a.notify_mentions(c,u,d,a.textfield(d,'text',True,2000),'feed','messages');a.audit(c,u,'post_comment',id);return {'ok':True}
    if path=='/api/stories':
        a.need(u,'social')
        if method=='GET':return [dict(r) for r in c.execute('SELECT * FROM stories WHERE expires>? ORDER BY created',(a.now(),))]
        if method=='POST':
            tx=a.textfield(d,'text',False,500);image=asset(a,c,u,d.get('image'),'story')
            if not tx and not image:raise a.Error(400,'Adicione uma foto ou texto.')
            id=a.uid();expires=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat(timespec='seconds');c.execute('INSERT INTO stories VALUES(?,?,?,?,?,?)',(id,u['id'],tx,image,a.now(),expires))
            if image:c.execute('UPDATE social_assets SET entity_id=?,expires=? WHERE file_id=?',(id,expires,image))
            a.notify_mentions(c,u,d,tx,'feed','messages');a.audit(c,u,'story_create',id);return {'id':id,'expires':expires}
    if path.startswith('/api/stories/') and method=='DELETE':
        a.need(u,'social');id=path.split('/')[-1];r=c.execute('SELECT * FROM stories WHERE id=?',(id,)).fetchone()
        if not r:raise a.Error(404,'História não encontrada.')
        if r['user_id']!=u['id'] and not u['master']:raise a.Error(403,'Sem permissão para excluir.')
        c.execute('DELETE FROM stories WHERE id=?',(id,));a.audit(c,u,'story_delete',id);return {'ok':True}
    return None

def checklist(a,d):
    items=d.get('checklist',[])
    if not isinstance(items,list) or len(items)>80:raise a.Error(400,'Checklist inválido.')
    out=[]
    for item in items:
        if not isinstance(item,dict):raise a.Error(400,'Checklist inválido.')
        out.append({'text':a.textfield(item,'text',True,300),'done':bool(item.get('done'))})
    return out
