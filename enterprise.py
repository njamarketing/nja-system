"""NJA 1.3: company overview and external integrations."""
import json,os,time
import social,agency_access

def init(c):
    for table,col,definition in [('tasks','client_id','TEXT REFERENCES clients(id)'),('users','branch',"TEXT NOT NULL DEFAULT 'foz'"),('clients','active','INTEGER NOT NULL DEFAULT 1'),('rooms','ai_enabled','INTEGER NOT NULL DEFAULT 1')]:
        if col not in [r[1] for r in c.execute('PRAGMA table_info('+table+')')]:c.execute('ALTER TABLE '+table+' ADD COLUMN '+col+' '+definition)
    c.executescript('''CREATE TABLE IF NOT EXISTS company_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enterprise_schema(version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS room_archives(user_id TEXT REFERENCES users(id),room_id TEXT REFERENCES rooms(id),PRIMARY KEY(user_id,room_id));''')

    if not c.execute('SELECT 1 FROM enterprise_schema WHERE version=1').fetchone():
        for row in c.execute('SELECT * FROM roles').fetchall():
            if row['id'] in ['member','master']:
                ps=list(dict.fromkeys(json.loads(row['permissions'])+['drive','ai']))
                c.execute('UPDATE roles SET permissions=? WHERE id=?',(json.dumps(ps),row['id']))
        c.execute('INSERT INTO enterprise_schema VALUES(1)')

def setting(c,key,default=''):
    r=c.execute('SELECT value FROM company_settings WHERE key=?',(key,)).fetchone();return r[0] if r else default

def branches(c):
    result=[]
    for id,name in [('foz','Foz do Iguaçu/PR'),('teixeira','Teixeira de Freitas/BA'),('cascavel','Cascavel/PR')]:
        manager=setting(c,'manager_'+id,None)
        if manager is None:
            row=c.execute('SELECT id FROM users WHERE active=1 AND master=1 ORDER BY created LIMIT 1').fetchone() if id=='foz' else c.execute("SELECT id FROM users WHERE active=1 AND lower(name)='igor martins' LIMIT 1").fetchone() if id=='teixeira' else None
            manager=row[0] if row else ''
        result.append({'id':id,'name':name,'manager_id':manager})
    return result

def api(a,c,u,method,path,d,q):
    if path.startswith('/api/rooms/') and path.endswith('/archive') and method=='POST':
        rid=path.split('/')[3];a.room_access(c,u,rid)
        if not isinstance(d.get('archived'),bool):raise a.Error(400,'Status de arquivo inválido.')
        if d['archived']:c.execute('INSERT OR IGNORE INTO room_archives VALUES(?,?)',(u['id'],rid))
        else:c.execute('DELETE FROM room_archives WHERE user_id=? AND room_id=?',(u['id'],rid))
        a.audit(c,u,'room_archive' if d['archived'] else 'room_restore',rid);return {'ok':True}
    if path=='/api/company' and method=='GET':return {'branches':branches(c)}
    if path=='/api/company' and method=='PATCH':
        if not u['master']:raise a.Error(403,'Somente o master pode configurar a empresa.')
        for b in branches(c):
            key='manager_'+b['id']
            if key in d:
                id=d[key]
                if id and not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(id,)).fetchone():raise a.Error(400,'Selecione um gestor ativo.')
                c.execute('INSERT OR REPLACE INTO company_settings VALUES(?,?)',(key,id))
        a.audit(c,u,'company_managers','company');return {'ok':True}
    if path.startswith('/api/users/') and path.endswith('/branch') and method=='PATCH':
        a.need(u,'user_manage');id=path.split('/')[3]
        if d.get('branch') not in ['foz','teixeira','cascavel']:raise a.Error(400,'Unidade inválida.')
        if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(id,)).fetchone():raise a.Error(404,'Usuário não encontrado.')
        c.execute('UPDATE users SET branch=? WHERE id=?',(d['branch'],id));a.audit(c,u,'user_branch',id);return {'ok':True}
    if path.startswith('/api/clients/') and path.endswith('/active') and method=='PATCH':
        a.need(u,'clients');a.need(u,'client_manage');id=path.split('/')[3];agency_access.need(a,c,u,id)
        if not isinstance(d.get('active'),bool):raise a.Error(400,'Status inválido.')
        if not c.execute('SELECT 1 FROM clients WHERE id=?',(id,)).fetchone():raise a.Error(404,'Cliente não encontrado.')
        c.execute('UPDATE clients SET active=? WHERE id=?',(int(d['active']),id));a.audit(c,u,'client_status',id);return {'ok':True}
    if path=='/api/overview' and method=='GET':
        a.need(u,'dashboard');master=bool(u['master'])
        tasks=[dict(r) for r in c.execute('SELECT * FROM tasks') if master or a.task_access(c,u,r)] if a.perm(u,'tasks') else []
        rooms=[dict(r) for r in c.execute('SELECT * FROM rooms') if agency_access.allowed(c,u,r['client_id']) and (master or c.execute('SELECT 1 FROM room_members WHERE user_id=? AND room_id=?',(u['id'],r['id'])).fetchone())] if a.perm(u,'chats') else []
        cutoff=time.time()-7*86400
        from datetime import datetime,timezone
        since=datetime.fromtimestamp(cutoff,timezone.utc).isoformat(timespec='seconds')
        online=[{'id':r['id'],'name':r['name'],'photo':r['photo'],'branch':r['branch']} for r in c.execute('SELECT * FROM users WHERE active=1') if social.presence(c,r['id'])['online']]
        counts={s:sum(t['status']==s for t in tasks) for s in a.STATES}
        recent=[dict(r) for r in c.execute('SELECT audit.*,users.name FROM audit LEFT JOIN users ON users.id=audit.user_id ORDER BY audit.id DESC LIMIT 15')] if master else []
        return {'scope':'company' if master else 'accessible','tasks':counts,'overdue':sum(bool(t['status']!='done' and t['due'] and t['due']<a.now()) for t in tasks),'clients_active':sum(agency_access.allowed(c,u,r[0]) for r in c.execute('SELECT id FROM clients WHERE active=1')) if a.perm(u,'clients') else None,'rooms_total':len(rooms),'rooms_active':sum(bool(c.execute('SELECT 1 FROM messages WHERE room_id=? AND created>=? UNION SELECT 1 FROM files WHERE room_id=? AND created>=? LIMIT 1',(r['id'],since,r['id'],since)).fetchone()) for r in rooms),'online':online if a.perm(u,'team') else [],'activity':recent,'updated':a.now()}
    return None


def task_client(a,c,u,d,current=None):
    if 'client_id' not in d:
        if current and current['client_id']:
            r=c.execute('SELECT name FROM clients WHERE id=?',(current['client_id'],)).fetchone()
            return {'project':r['name']} if r else {}
        return {}
    a.need(u,'clients');id=d.get('client_id') or None
    if id is not None and not isinstance(id,str):raise a.Error(400,'Cliente inválido.')
    if not id:return {'client_id':None}
    row=c.execute('SELECT * FROM clients WHERE id=?',(id,)).fetchone()
    if not row or (not row['active'] and (not current or current['client_id']!=id)):raise a.Error(400,'Selecione um cliente ativo cadastrado.')
    agency_access.need(a,c,u,id)
    return {'client_id':id,'project':row['name']}
