"""Authenticated WebRTC signaling. Media travels peer-to-peer or through TURN."""
import json,os,time

def init(c):
    c.executescript('''CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY,room_id TEXT NOT NULL REFERENCES rooms(id),caller TEXT NOT NULL REFERENCES users(id),callee TEXT NOT NULL REFERENCES users(id),mode TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS call_signals(id INTEGER PRIMARY KEY AUTOINCREMENT,call_id TEXT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,sender TEXT NOT NULL REFERENCES users(id),kind TEXT NOT NULL,payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_call_signals ON call_signals(call_id,id);''')

def ice(a):
    try:
        servers=json.loads(os.getenv('NJA_ICE_SERVERS','[{"urls":"stun:stun.l.google.com:19302"}]'))
        if not isinstance(servers,list) or len(servers)>10:raise ValueError()
        for server in servers:
            urls=server.get('urls');urls=[urls] if isinstance(urls,str) else urls
            if not isinstance(urls,list) or not urls or any(not isinstance(x,str) or not x.startswith(('stun:','stuns:','turn:','turns:')) for x in urls):raise ValueError()
        return servers
    except Exception:raise a.Error(503,'Configuração de chamadas inválida. Confira NJA_ICE_SERVERS no servidor.')

def ice_response(a):
    """Return ICE servers and whether a relay is available for restrictive/mobile networks."""
    servers=ice(a)
    urls=[]
    for server in servers:
        value=server.get('urls',[])
        urls.extend([value] if isinstance(value,str) else value)
    return {'ice_servers':servers,'turn_ready':any(url.startswith(('turn:','turns:')) for url in urls)}

def expire(c):
    c.execute("UPDATE calls SET status='missed' WHERE status='ringing' AND expires<?",(time.time(),))
    c.execute("UPDATE calls SET status='ended' WHERE status='accepted' AND expires<?",(time.time(),))
    c.execute('DELETE FROM call_signals WHERE call_id IN (SELECT id FROM calls WHERE expires<?)',(time.time()-86400,))

def allowed(a,c,u,id):
    call=c.execute('SELECT * FROM calls WHERE id=?',(id,)).fetchone()
    if not call or u['id'] not in [call['caller'],call['callee']]:raise a.Error(403,'Sem acesso a esta chamada.')
    a.room_access(c,u,call['room_id']);other=call['callee'] if u['id']==call['caller'] else call['caller']
    if not c.execute('SELECT 1 FROM room_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.user_id=? AND u.active=1',(call['room_id'],other)).fetchone():
        c.execute("UPDATE calls SET status='ended' WHERE id=?",(id,));c.commit();raise a.Error(403,'Participante removido ou desativado.')
    return call

def api(a,c,u,method,path,d,q):
    if not path.startswith('/api/calls'):return None
    a.need(u,'chats');expire(c)
    if path=='/api/calls' and method=='GET':
        rows=[]
        for r in c.execute("SELECT * FROM calls WHERE (caller=? OR callee=?) AND status IN ('ringing','accepted') ORDER BY created DESC",(u['id'],u['id'])).fetchall():
            try:allowed(a,c,u,r['id']);rows.append(dict(r))
            except a.Error:pass
        return {'calls':rows}|ice_response(a)
    if path=='/api/calls' and method=='POST':
        rid=d.get('room_id');a.room_access(c,u,rid);other=d.get('callee');mode=d.get('mode')
        if mode not in ['audio','video']:raise a.Error(400,'Tipo de chamada inválido.')
        if other==u['id'] or not c.execute('SELECT 1 FROM room_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.user_id=? AND u.active=1',(rid,other)).fetchone():raise a.Error(400,'Escolha outro participante ativo desta conversa.')
        a.throttle(c,'call:'+u['id'],30)
        import meetings
        for person in [u['id'],other]:
            if c.execute("SELECT 1 FROM meeting_members p JOIN meetings m ON m.id=p.meeting_id WHERE p.user_id=? AND m.status='active' AND m.expires>? AND (p.status='joined' OR (p.status='invited' AND p.invited>?))",(person,time.time(),time.time()-60)).fetchone():raise a.Error(409,'Um participante já está em uma reunião.')
        if c.execute("SELECT 1 FROM calls WHERE status IN ('ringing','accepted') AND (caller IN (?,?) OR callee IN (?,?))",(u['id'],other,u['id'],other)).fetchone():raise a.Error(409,'Você ou o participante já tem uma chamada em andamento.')
        id=a.uid();c.execute('INSERT INTO calls VALUES(?,?,?,?,?,?,?,?)',(id,rid,u['id'],other,mode,'ringing',time.time(),time.time()+60));a.notify(c,other,u['name'],'Chamada de '+('vídeo' if mode=='video' else 'voz'),'chats:'+rid,'messages');a.audit(c,u,'call_start',id)
        return {'call':dict(c.execute('SELECT * FROM calls WHERE id=?',(id,)).fetchone())}|ice_response(a)
    parts=path.split('/')
    if len(parts)<4:raise a.Error(404,'Chamada não encontrada.')
    id=parts[3];call=allowed(a,c,u,id)
    if len(parts)==4 and method=='GET':return {'call':dict(call)}
    if len(parts)==5 and parts[4]=='action' and method=='POST':
        action=d.get('action')
        if action=='accept':
            if u['id']!=call['callee'] or call['status']!='ringing':raise a.Error(409,'Esta chamada não pode ser aceita agora.')
            c.execute("UPDATE calls SET status='accepted',expires=? WHERE id=?",(time.time()+7200,id))
        elif action in ['decline','end']:
            if action=='decline' and u['id']!=call['callee']:raise a.Error(403,'Somente o destinatário pode recusar.')
            c.execute('UPDATE calls SET status=? WHERE id=?',('declined' if action=='decline' else 'ended',id))
        else:raise a.Error(400,'Ação inválida.')
        a.audit(c,u,'call_'+action,id);return {'ok':True}
    if len(parts)==5 and parts[4]=='signals':
        if method=='GET':
            try:cursor=int(q.get('after',['0'])[0])
            except ValueError:raise a.Error(400,'Cursor inválido.')
            return {'call':dict(call),'signals':[dict(r)|{'payload':json.loads(r['payload'])} for r in c.execute('SELECT * FROM call_signals WHERE call_id=? AND sender<>? AND id>? ORDER BY id LIMIT 100',(id,u['id'],cursor))]}
        if method=='POST':
            if call['status'] not in ['ringing','accepted']:raise a.Error(409,'Chamada encerrada.')
            kind=d.get('kind');payload=d.get('payload')
            if kind not in ['offer','answer','candidate','restart'] or not isinstance(payload,dict) or len(json.dumps(payload))>120000:raise a.Error(400,'Sinal inválido.')
            if kind=='offer' and u['id']!=call['caller']:raise a.Error(403,'Oferta inválida.')
            if kind=='answer' and (u['id']!=call['callee'] or call['status']!='accepted'):raise a.Error(403,'Resposta inválida.')
            if kind=='restart' and call['status']!='accepted':raise a.Error(409,'A chamada ainda não foi atendida.')
            if kind in ['offer','answer'] and (payload.get('type')!=kind or not isinstance(payload.get('sdp'),str)):raise a.Error(400,'SDP inválido.')
            if kind=='candidate' and not isinstance(payload.get('candidate'),str):raise a.Error(400,'Candidato inválido.')
            if c.execute('SELECT COUNT(*) FROM call_signals WHERE call_id=?',(id,)).fetchone()[0]>=1000:raise a.Error(429,'Limite de sinalização atingido.')
            c.execute('INSERT INTO call_signals(call_id,sender,kind,payload) VALUES(?,?,?,?)',(id,u['id'],kind,json.dumps(payload)));return {'ok':True}
    raise a.Error(404,'Recurso de chamada não encontrado.')
