"""Small authenticated group calls, including invited client portal contacts."""
import time,json
import calls
MAX_PEOPLE=6

def init(c):
    c.executescript('''CREATE TABLE IF NOT EXISTS meetings(id TEXT PRIMARY KEY,room_id TEXT NOT NULL REFERENCES rooms(id),host TEXT NOT NULL REFERENCES users(id),mode TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS meeting_members(meeting_id TEXT REFERENCES meetings(id),user_id TEXT REFERENCES users(id),status TEXT NOT NULL,joined REAL NOT NULL DEFAULT 0,invited REAL NOT NULL,PRIMARY KEY(meeting_id,user_id));
CREATE TABLE IF NOT EXISTS meeting_signals(id INTEGER PRIMARY KEY AUTOINCREMENT,meeting_id TEXT REFERENCES meetings(id) ON DELETE CASCADE,sender TEXT REFERENCES users(id),recipient TEXT REFERENCES users(id),kind TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meeting_signal_events(id INTEGER PRIMARY KEY AUTOINCREMENT,meeting_id TEXT REFERENCES meetings(id) ON DELETE CASCADE,sender TEXT NOT NULL,recipient TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_meeting_signals ON meeting_signals(meeting_id,recipient,id);
CREATE INDEX IF NOT EXISTS ix_meeting_signal_events ON meeting_signal_events(meeting_id,recipient,id);''')

def actor(account_id):return 'portal:'+account_id

def busy(c,id):
    if id.startswith('portal:'):
        account=id.split(':',1)[1]
        return bool(c.execute("SELECT 1 FROM meeting_portal_members p JOIN meetings m ON m.id=p.meeting_id WHERE p.account_id=? AND m.status='active' AND m.expires>? AND (p.status='joined' OR (p.status='invited' AND p.invited>?))",(account,time.time(),time.time()-60)).fetchone())
    return bool(c.execute("SELECT 1 FROM calls WHERE (caller=? OR callee=?) AND status IN ('ringing','accepted') AND expires>?",(id,id,time.time())).fetchone() or c.execute("SELECT 1 FROM meeting_members p JOIN meetings m ON m.id=p.meeting_id WHERE p.user_id=? AND m.status='active' AND m.expires>? AND (p.status='joined' OR (p.status='invited' AND p.invited>?))",(id,time.time(),time.time()-60)).fetchone())

def refresh(c):
    now=time.time()
    c.execute("UPDATE meetings SET status='ended' WHERE expires<?",(now,))
    c.execute("UPDATE meeting_members SET status='missed' WHERE status='invited' AND invited<?",(now-60,))
    c.execute("UPDATE meeting_portal_members SET status='missed' WHERE status='invited' AND invited<?",(now-60,))
    c.execute("UPDATE meeting_members SET status='removed' WHERE status IN ('joined','invited') AND (NOT EXISTS(SELECT 1 FROM users u WHERE u.id=meeting_members.user_id AND u.active=1) OR NOT EXISTS(SELECT 1 FROM room_members r JOIN meetings m ON m.room_id=r.room_id WHERE m.id=meeting_members.meeting_id AND r.user_id=meeting_members.user_id))")
    c.execute("""UPDATE meeting_portal_members SET status='removed' WHERE status IN ('joined','invited') AND NOT EXISTS(
      SELECT 1 FROM portal_accounts p JOIN meetings m ON m.id=meeting_portal_members.meeting_id JOIN rooms r ON r.id=m.room_id
      WHERE p.id=meeting_portal_members.account_id AND p.active=1 AND r.client_id=p.client_id)""")
    for m in c.execute("SELECT * FROM meetings WHERE status='active'").fetchall():
        host=c.execute("SELECT 1 FROM meeting_members WHERE meeting_id=? AND user_id=? AND status='joined'",(m['id'],m['host'])).fetchone()
        if not host:
            next_member=c.execute("SELECT user_id FROM meeting_members WHERE meeting_id=? AND status='joined' ORDER BY joined,user_id LIMIT 1",(m['id'],)).fetchone()
            if next_member:c.execute('UPDATE meetings SET host=? WHERE id=?',(next_member[0],m['id']))
            else:c.execute("UPDATE meetings SET status='ended' WHERE id=?",(m['id'],))
    c.execute('DELETE FROM meeting_signals WHERE meeting_id IN (SELECT id FROM meetings WHERE expires<?)',(now-86400,))
    c.execute('DELETE FROM meeting_signal_events WHERE meeting_id IN (SELECT id FROM meetings WHERE expires<?)',(now-86400,))

def all_members(c,meeting_id):
    internal=[dict(r)|{'external':False} for r in c.execute('SELECT p.user_id,p.status,p.joined,u.name,u.photo FROM meeting_members p JOIN users u ON u.id=p.user_id WHERE p.meeting_id=?',(meeting_id,))]
    external=[{'user_id':actor(r['account_id']),'status':r['status'],'joined':r['joined'],'name':r['name'],'photo':r['photo'],'external':True} for r in c.execute('''SELECT p.account_id,p.status,p.joined,a.name,cl.photo FROM meeting_portal_members p JOIN portal_accounts a ON a.id=p.account_id JOIN clients cl ON cl.id=a.client_id WHERE p.meeting_id=?''',(meeting_id,))]
    return sorted(internal+external,key=lambda item:(item['joined'],item['user_id']))

def serialize_for(c,m,identity):
    value=dict(m);value['members']=all_members(c,m['id']);value['my_status']=next((person['status'] for person in value['members'] if person['user_id']==identity),'removed')
    host=c.execute('SELECT name,photo FROM users WHERE id=?',(m['host'],)).fetchone();value['host_name']=host['name'] if host else 'Equipe NJA';value['host_photo']=host['photo'] if host else None
    return value

def access(a,c,u,id):
    m=c.execute('SELECT * FROM meetings WHERE id=?',(id,)).fetchone();member=c.execute('SELECT * FROM meeting_members WHERE meeting_id=? AND user_id=?',(id,u['id'])).fetchone()
    if not m or not member or member['status']=='removed':raise a.Error(403,'Sem acesso a esta reunião.')
    a.room_access(c,u,m['room_id']);return m,member

def portal_access(a,c,p,id):
    m=c.execute('SELECT m.* FROM meetings m JOIN rooms r ON r.id=m.room_id WHERE m.id=? AND r.client_id=?',(id,p['client_id'])).fetchone();member=c.execute('SELECT * FROM meeting_portal_members WHERE meeting_id=? AND account_id=?',(id,p['id'])).fetchone()
    if not m or not member or member['status']=='removed':raise a.Error(403,'Sem acesso a esta reunião.')
    return m,member

def joined(c,meeting_id,identity):
    if identity.startswith('portal:'):return bool(c.execute("SELECT 1 FROM meeting_portal_members WHERE meeting_id=? AND account_id=? AND status='joined'",(meeting_id,identity.split(':',1)[1])).fetchone())
    return bool(c.execute("SELECT 1 FROM meeting_members WHERE meeting_id=? AND user_id=? AND status='joined'",(meeting_id,identity)).fetchone())

def joined_count(c,meeting_id):
    return c.execute("SELECT COUNT(*) FROM meeting_members WHERE meeting_id=? AND status='joined'",(meeting_id,)).fetchone()[0]+c.execute("SELECT COUNT(*) FROM meeting_portal_members WHERE meeting_id=? AND status='joined'",(meeting_id,)).fetchone()[0]

def validate_signal(a,c,meeting,identity,d):
    if meeting['status']!='active':raise a.Error(409,'Reunião encerrada.')
    target=d.get('recipient');kind=d.get('kind');payload=d.get('payload')
    if target==identity or not isinstance(target,str) or not joined(c,meeting['id'],target):raise a.Error(403,'Destinatário indisponível.')
    if kind not in ['offer','answer','candidate','restart'] or not isinstance(payload,dict) or len(json.dumps(payload))>120000:raise a.Error(400,'Sinal inválido.')
    if kind in ['offer','answer'] and (payload.get('type')!=kind or not isinstance(payload.get('sdp'),str)):raise a.Error(400,'SDP inválido.')
    if kind=='candidate' and not isinstance(payload.get('candidate'),str):raise a.Error(400,'Candidato inválido.')
    if c.execute('SELECT COUNT(*) FROM meeting_signal_events WHERE meeting_id=?',(meeting['id'],)).fetchone()[0]>=10000:raise a.Error(429,'Limite de sinalização atingido.')
    c.execute('INSERT INTO meeting_signal_events(meeting_id,sender,recipient,kind,payload) VALUES(?,?,?,?,?)',(meeting['id'],identity,target,kind,json.dumps(payload)));return {'ok':True}

def signal_feed(a,c,meeting,identity,q):
    try:cursor=int(q.get('after',['0'])[0])
    except ValueError:raise a.Error(400,'Cursor inválido.')
    return [dict(r)|{'payload':json.loads(r['payload'])} for r in c.execute('SELECT * FROM meeting_signal_events WHERE meeting_id=? AND recipient=? AND id>? ORDER BY id LIMIT 200',(meeting['id'],identity,cursor))]

def api(a,c,u,method,path,d,q):
    if not path.startswith('/api/meetings'):return None
    a.need(u,'chats');refresh(c)
    if path=='/api/meetings' and method=='GET':
        out=[];rid=q.get('room_id',[''])[0]
        if rid:a.room_access(c,u,rid)
        sql="SELECT m.* FROM meetings m JOIN meeting_members p ON p.meeting_id=m.id WHERE m.status='active' AND p.user_id=?"+((" AND m.room_id=? AND p.status<>'removed'") if rid else " AND p.status IN ('invited','joined')")
        for m in c.execute(sql+' ORDER BY m.created',(u['id'],rid) if rid else (u['id'],)).fetchall():
            try:access(a,c,u,m['id']);out.append(serialize_for(c,m,u['id']))
            except a.Error:pass
        return {'meetings':out,'max_people':MAX_PEOPLE}|calls.ice_response(a)
    if path=='/api/meetings' and method=='POST':
        rid=d.get('room_id');a.room_access(c,u,rid);room=c.execute('SELECT * FROM rooms WHERE id=?',(rid,)).fetchone()
        if room['kind'] not in ['general','group']:raise a.Error(400,'Abra um grupo para iniciar uma reunião.')
        requested=d.get('members',[])
        if not isinstance(requested,list) or len(set(requested))!=len(requested) or any(not isinstance(x,str) for x in requested):raise a.Error(400,'Participantes inválidos.')
        requested=[x for x in requested if x!=u['id']]
        if not 1<=len(requested)<MAX_PEOPLE:raise a.Error(400,'Selecione de um a cinco participantes (até seis pessoas incluindo você).')
        if d.get('mode') not in ['audio','video']:raise a.Error(400,'Modo inválido.')
        internals=[];portals=[]
        for person in requested:
            if person.startswith('portal:'):
                account_id=person.split(':',1)[1];account=c.execute('SELECT p.* FROM portal_accounts p JOIN clients cl ON cl.id=p.client_id WHERE p.id=? AND p.active=1 AND cl.active=1',(account_id,)).fetchone()
                if not account or room['kind']!='group' or not room['client_id'] or account['client_id']!=room['client_id']:raise a.Error(403,'Convide apenas participantes desta conversa.')
                portals.append(account_id)
            else:
                valid=a.active_ids(c,[person])[0]
                if not c.execute('SELECT 1 FROM room_members WHERE room_id=? AND user_id=?',(rid,valid)).fetchone():raise a.Error(403,'Convide apenas participantes desta conversa.')
                internals.append(valid)
        a.throttle(c,'meeting-start:'+u['id'],20)
        for identity in internals+[actor(x) for x in portals]+[u['id']]:
            if busy(c,identity):raise a.Error(409,'Um dos participantes já tem chamada ou convite em andamento.')
        id=a.uid();ts=time.time();c.execute('INSERT INTO meetings VALUES(?,?,?,?,?,?,?)',(id,rid,u['id'],d['mode'],'active',ts,ts+7200))
        for person in internals+[u['id']]:c.execute('INSERT INTO meeting_members VALUES(?,?,?,?,?)',(id,person,'joined' if person==u['id'] else 'invited',ts if person==u['id'] else 0,ts))
        for account_id in portals:c.execute('INSERT INTO meeting_portal_members VALUES(?,?,?,?,?)',(id,account_id,'invited',0,ts))
        for person in internals:a.notify(c,person,u['name'],'Convidou você para uma reunião de '+('vídeo' if d['mode']=='video' else 'voz'),'chats:'+rid,'messages')
        a.audit(c,u,'meeting_start',id);return {'meeting':serialize_for(c,c.execute('SELECT * FROM meetings WHERE id=?',(id,)).fetchone(),u['id'])}|calls.ice_response(a)
    parts=path.split('/')
    if len(parts)<4:raise a.Error(404,'Reunião não encontrada.')
    id=parts[3];meeting,member=access(a,c,u,id)
    if len(parts)==4 and method=='GET':return {'meeting':serialize_for(c,meeting,u['id'])}
    if len(parts)==5 and parts[4]=='action' and method=='POST':
        action=d.get('action')
        if meeting['status']!='active':raise a.Error(409,'Reunião encerrada.')
        if action=='join':
            if member['status']=='joined':return {'ok':True}
            if busy(c,u['id']) and member['status']!='invited':raise a.Error(409,'Você já está em outra chamada.')
            if joined_count(c,id)>=MAX_PEOPLE:raise a.Error(409,'A reunião está cheia.')
            c.execute("UPDATE meeting_members SET status='joined',joined=? WHERE meeting_id=? AND user_id=?",(time.time(),id,u['id']));c.execute('DELETE FROM meeting_signal_events WHERE meeting_id=? AND (sender=? OR recipient=?)',(id,u['id'],u['id']))
        elif action in ['leave','decline']:
            c.execute('UPDATE meeting_members SET status=? WHERE meeting_id=? AND user_id=?',('left' if action=='leave' else 'declined',id,u['id']));refresh(c)
        elif action=='end':
            if meeting['host']!=u['id']:raise a.Error(403,'Somente o anfitrião pode encerrar para todos.')
            c.execute("UPDATE meetings SET status='ended' WHERE id=?",(id,))
        else:raise a.Error(400,'Ação inválida.')
        a.audit(c,u,'meeting_'+action,id);return {'ok':True}
    if len(parts)==5 and parts[4]=='signals':
        if member['status']!='joined':raise a.Error(403,'Entre na reunião antes de trocar mídia.')
        if method=='GET':return {'meeting':serialize_for(c,meeting,u['id']),'signals':signal_feed(a,c,meeting,u['id'],q)}
        if method=='POST':return validate_signal(a,c,meeting,u['id'],d)
    raise a.Error(404,'Recurso de reunião não encontrado.')

def portal_api(a,c,p,method,action,d,q):
    """Portal-only meeting endpoints. The caller was already authenticated by agency_portal."""
    refresh(c);identity=actor(p['id'])
    if action=='meetings' and method=='GET':
        rows=c.execute("SELECT m.* FROM meetings m JOIN meeting_portal_members x ON x.meeting_id=m.id JOIN rooms r ON r.id=m.room_id WHERE x.account_id=? AND r.client_id=? AND m.status='active' AND x.status IN ('invited','joined') ORDER BY m.created",(p['id'],p['client_id'])).fetchall()
        return {'meetings':[serialize_for(c,m,identity) for m in rows],'max_people':MAX_PEOPLE}|calls.ice_response(a)
    if not action.startswith('meetings/'):return None
    parts=action.split('/');id=parts[1];meeting,member=portal_access(a,c,p,id)
    if len(parts)==2 and method=='GET':return {'meeting':serialize_for(c,meeting,identity)}
    if len(parts)==3 and parts[2]=='action' and method=='POST':
        if meeting['status']!='active':raise a.Error(409,'Reunião encerrada.')
        action_name=d.get('action')
        if action_name=='join':
            if member['status']=='joined':return {'ok':True}
            if member['status'] not in ['invited','left']:raise a.Error(409,'Este convite não está mais disponível.')
            if busy(c,identity) and member['status']!='invited':raise a.Error(409,'Você já está em outra chamada.')
            if joined_count(c,id)>=MAX_PEOPLE:raise a.Error(409,'A reunião está cheia.')
            c.execute("UPDATE meeting_portal_members SET status='joined',joined=? WHERE meeting_id=? AND account_id=?",(time.time(),id,p['id']));c.execute('DELETE FROM meeting_signal_events WHERE meeting_id=? AND (sender=? OR recipient=?)',(id,identity,identity))
        elif action_name in ['leave','decline']:
            c.execute('UPDATE meeting_portal_members SET status=? WHERE meeting_id=? AND account_id=?',('left' if action_name=='leave' else 'declined',id,p['id']));refresh(c)
        else:raise a.Error(400,'Ação inválida.')
        return {'ok':True}
    if len(parts)==3 and parts[2]=='signals':
        if member['status']!='joined':raise a.Error(403,'Entre na reunião antes de trocar mídia.')
        if method=='GET':return {'meeting':serialize_for(c,meeting,identity),'signals':signal_feed(a,c,meeting,identity,q)}
        if method=='POST':return validate_signal(a,c,meeting,identity,d)
    raise a.Error(404,'Recurso de reunião não encontrado.')
