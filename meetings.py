"""Small authenticated group calls, with peer-specific WebRTC signaling."""
import time,json
import calls
MAX_PEOPLE=6

def init(c):
    c.executescript('''CREATE TABLE IF NOT EXISTS meetings(id TEXT PRIMARY KEY,room_id TEXT NOT NULL REFERENCES rooms(id),host TEXT NOT NULL REFERENCES users(id),mode TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS meeting_members(meeting_id TEXT REFERENCES meetings(id),user_id TEXT REFERENCES users(id),status TEXT NOT NULL,joined REAL NOT NULL DEFAULT 0,invited REAL NOT NULL,PRIMARY KEY(meeting_id,user_id));
CREATE TABLE IF NOT EXISTS meeting_signals(id INTEGER PRIMARY KEY AUTOINCREMENT,meeting_id TEXT REFERENCES meetings(id) ON DELETE CASCADE,sender TEXT REFERENCES users(id),recipient TEXT REFERENCES users(id),kind TEXT NOT NULL,payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_meeting_signals ON meeting_signals(meeting_id,recipient,id);''')

def busy(c,id):
    return bool(c.execute("SELECT 1 FROM calls WHERE (caller=? OR callee=?) AND status IN ('ringing','accepted') AND expires>?",(id,id,time.time())).fetchone() or c.execute("SELECT 1 FROM meeting_members p JOIN meetings m ON m.id=p.meeting_id WHERE p.user_id=? AND m.status='active' AND m.expires>? AND (p.status='joined' OR (p.status='invited' AND p.invited>?))",(id,time.time(),time.time()-60)).fetchone())

def refresh(c):
    c.execute("UPDATE meetings SET status='ended' WHERE expires<?",(time.time(),))
    c.execute("UPDATE meeting_members SET status='missed' WHERE status='invited' AND invited<?",(time.time()-60,))
    c.execute("UPDATE meeting_members SET status='removed' WHERE status IN ('joined','invited') AND (NOT EXISTS(SELECT 1 FROM users u WHERE u.id=meeting_members.user_id AND u.active=1) OR NOT EXISTS(SELECT 1 FROM room_members r JOIN meetings m ON m.room_id=r.room_id WHERE m.id=meeting_members.meeting_id AND r.user_id=meeting_members.user_id))")
    for m in c.execute("SELECT * FROM meetings WHERE status='active'").fetchall():
        host=c.execute("SELECT 1 FROM meeting_members WHERE meeting_id=? AND user_id=? AND status='joined'",(m['id'],m['host'])).fetchone()
        if not host:
            next=c.execute("SELECT user_id FROM meeting_members WHERE meeting_id=? AND status='joined' ORDER BY joined,user_id LIMIT 1",(m['id'],)).fetchone()
            if next:c.execute('UPDATE meetings SET host=? WHERE id=?',(next[0],m['id']))
            else:c.execute("UPDATE meetings SET status='ended' WHERE id=?",(m['id'],))
    c.execute('DELETE FROM meeting_signals WHERE meeting_id IN (SELECT id FROM meetings WHERE expires<?)',(time.time()-86400,))

def access(a,c,u,id):
    m=c.execute('SELECT * FROM meetings WHERE id=?',(id,)).fetchone()
    member=c.execute('SELECT * FROM meeting_members WHERE meeting_id=? AND user_id=?',(id,u['id'])).fetchone()
    if not m or not member or member['status']=='removed':raise a.Error(403,'Sem acesso a esta reunião.')
    a.room_access(c,u,m['room_id']);return m,member

def serialize(c,m,u):
    v=dict(m);v['members']=[dict(r) for r in c.execute('SELECT p.user_id,p.status,p.joined,u.name,u.photo FROM meeting_members p JOIN users u ON u.id=p.user_id WHERE p.meeting_id=? ORDER BY p.joined,p.user_id',(m['id'],))];v['my_status']=next((p['status'] for p in v['members'] if p['user_id']==u['id']),'removed');return v

def api(a,c,u,method,path,d,q):
    if not path.startswith('/api/meetings'):return None
    a.need(u,'chats');refresh(c)
    if path=='/api/meetings' and method=='GET':
        out=[]
        rid=q.get('room_id',[''])[0]
        if rid:a.room_access(c,u,rid)
        sql="SELECT m.* FROM meetings m JOIN meeting_members p ON p.meeting_id=m.id WHERE m.status='active' AND p.user_id=?"
        sql+=" AND m.room_id=? AND p.status<>'removed'" if rid else " AND p.status IN ('invited','joined')"
        for m in c.execute(sql+' ORDER BY m.created',(u['id'],rid) if rid else (u['id'],)).fetchall():
            try:access(a,c,u,m['id']);out.append(serialize(c,m,u))
            except a.Error:pass
        return {'meetings':out,'ice_servers':calls.ice(a),'max_people':MAX_PEOPLE}
    if path=='/api/meetings' and method=='POST':
        rid=d.get('room_id');a.room_access(c,u,rid)
        room=c.execute('SELECT * FROM rooms WHERE id=?',(rid,)).fetchone()
        if room['kind'] not in ['general','group']:raise a.Error(400,'Abra um grupo para iniciar uma reunião.')
        members=a.active_ids(c,d.get('members',[]));members=[id for id in members if id!=u['id']]
        if not 1<=len(members)<MAX_PEOPLE:raise a.Error(400,'Selecione de um a cinco colegas (até seis pessoas incluindo você).')
        if d.get('mode') not in ['audio','video']:raise a.Error(400,'Modo inválido.')
        for id in members:
            if not c.execute('SELECT 1 FROM room_members WHERE room_id=? AND user_id=?',(rid,id)).fetchone():raise a.Error(403,'Convide apenas participantes desta conversa.')
        a.throttle(c,'meeting-start:'+u['id'],20)
        for id in members+[u['id']]:
            if busy(c,id):raise a.Error(409,'Um dos participantes já tem chamada ou convite em andamento.')
        id=a.uid();ts=time.time();c.execute('INSERT INTO meetings VALUES(?,?,?,?,?,?,?)',(id,rid,u['id'],d['mode'],'active',ts,ts+7200))
        for person in members+[u['id']]:c.execute('INSERT INTO meeting_members VALUES(?,?,?,?,?)',(id,person,'joined' if person==u['id'] else 'invited',ts if person==u['id'] else 0,ts))
        for person in members:a.notify(c,person,u['name'],'Convidou você para uma reunião de '+('vídeo' if d['mode']=='video' else 'voz'),'chats:'+rid,'messages')
        a.audit(c,u,'meeting_start',id);return {'meeting':serialize(c,c.execute('SELECT * FROM meetings WHERE id=?',(id,)).fetchone(),u),'ice_servers':calls.ice(a)}
    parts=path.split('/')
    if len(parts)<4:raise a.Error(404,'Reunião não encontrada.')
    id=parts[3];meeting,member=access(a,c,u,id)
    if len(parts)==4 and method=='GET':return {'meeting':serialize(c,meeting,u)}
    if len(parts)==5 and parts[4]=='action' and method=='POST':
        action=d.get('action')
        if meeting['status']!='active':raise a.Error(409,'Reunião encerrada.')
        if action=='join':
            if member['status']=='joined':return {'ok':True}
            # Serialize against concurrent starts/joins using the transaction already held by refresh.
            if c.execute("SELECT 1 FROM calls WHERE (caller=? OR callee=?) AND status IN ('ringing','accepted') AND expires>?",(u['id'],u['id'],time.time())).fetchone() or c.execute("SELECT 1 FROM meeting_members p JOIN meetings m ON m.id=p.meeting_id WHERE p.user_id=? AND p.meeting_id<>? AND p.status='joined' AND m.status='active'",(u['id'],id)).fetchone():raise a.Error(409,'Você já está em outra chamada.')
            if c.execute("SELECT COUNT(*) FROM meeting_members WHERE meeting_id=? AND status='joined'",(id,)).fetchone()[0]>=MAX_PEOPLE:raise a.Error(409,'A reunião está cheia.')
            c.execute("UPDATE meeting_members SET status='joined',joined=? WHERE meeting_id=? AND user_id=?",(time.time(),id,u['id']));c.execute('DELETE FROM meeting_signals WHERE meeting_id=? AND (sender=? OR recipient=?)',(id,u['id'],u['id']))
        elif action in ['leave','decline']:
            c.execute('UPDATE meeting_members SET status=? WHERE meeting_id=? AND user_id=?',('left' if action=='leave' else 'declined',id,u['id']));refresh(c)
        elif action=='end':
            if meeting['host']!=u['id']:raise a.Error(403,'Somente o anfitrião pode encerrar para todos.')
            c.execute("UPDATE meetings SET status='ended' WHERE id=?",(id,))
        else:raise a.Error(400,'Ação inválida.')
        a.audit(c,u,'meeting_'+action,id);return {'ok':True}
    if len(parts)==5 and parts[4]=='signals':
        if member['status']!='joined':raise a.Error(403,'Entre na reunião antes de trocar mídia.')
        if method=='GET':
            try:cursor=int(q.get('after',['0'])[0])
            except ValueError:raise a.Error(400,'Cursor inválido.')
            return {'meeting':serialize(c,meeting,u),'signals':[dict(r)|{'payload':json.loads(r['payload'])} for r in c.execute('SELECT * FROM meeting_signals WHERE meeting_id=? AND recipient=? AND id>? ORDER BY id LIMIT 200',(id,u['id'],cursor))]}
        if method=='POST':
            if meeting['status']!='active':raise a.Error(409,'Reunião encerrada.')
            target=d.get('recipient');kind=d.get('kind');payload=d.get('payload')
            if target==u['id'] or not c.execute("SELECT 1 FROM meeting_members WHERE meeting_id=? AND user_id=? AND status='joined'",(id,target)).fetchone():raise a.Error(403,'Destinatário indisponível.')
            if kind not in ['offer','answer','candidate','restart'] or not isinstance(payload,dict) or len(json.dumps(payload))>120000:raise a.Error(400,'Sinal inválido.')
            if kind in ['offer','answer'] and (payload.get('type')!=kind or not isinstance(payload.get('sdp'),str)):raise a.Error(400,'SDP inválido.')
            if kind=='candidate' and not isinstance(payload.get('candidate'),str):raise a.Error(400,'Candidato inválido.')
            if c.execute('SELECT COUNT(*) FROM meeting_signals WHERE meeting_id=?',(id,)).fetchone()[0]>=10000:raise a.Error(429,'Limite de sinalização atingido.')
            c.execute('INSERT INTO meeting_signals(meeting_id,sender,recipient,kind,payload) VALUES(?,?,?,?,?)',(id,u['id'],target,kind,json.dumps(payload)));return {'ok':True}
    raise a.Error(404,'Recurso de reunião não encontrado.')
