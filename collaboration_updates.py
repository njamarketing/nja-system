"""Projects, task deletion and cross-device collaboration additions."""


def init(c):
    additions = [
        ('tasks', 'client_project_id', 'TEXT REFERENCES client_projects(id)'),
        ('users', 'cover_x', 'INTEGER NOT NULL DEFAULT 50'),
        ('users', 'cover_y', 'INTEGER NOT NULL DEFAULT 50'),
        ('users', 'cover_zoom', 'INTEGER NOT NULL DEFAULT 100'),
    ]
    # Projects must exist before tasks can reference them on fresh databases.
    c.executescript('''
CREATE TABLE IF NOT EXISTS client_projects(
 id TEXT PRIMARY KEY,
 client_id TEXT NOT NULL REFERENCES clients(id),
 name TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'active',
 creator TEXT NOT NULL REFERENCES users(id),
 created TEXT NOT NULL,
 updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS client_project_members(
 project_id TEXT NOT NULL REFERENCES client_projects(id) ON DELETE CASCADE,
 user_id TEXT NOT NULL REFERENCES users(id),
 PRIMARY KEY(project_id,user_id)
);
CREATE INDEX IF NOT EXISTS ix_client_projects_client ON client_projects(client_id,status,name);
''')
    for table, column, definition in additions:
        if column not in [r[1] for r in c.execute('PRAGMA table_info('+table+')')]:
            c.execute('ALTER TABLE '+table+' ADD COLUMN '+column+' '+definition)


def serialize(c, row):
    value = dict(row)
    value['members'] = [r[0] for r in c.execute(
        'SELECT user_id FROM client_project_members WHERE project_id=? ORDER BY user_id',
        (row['id'],),
    )]
    value['task_count'] = c.execute(
        'SELECT COUNT(*) FROM tasks WHERE client_project_id=?', (row['id'],)
    ).fetchone()[0]
    return value


def project(a, c, u, project_id, client_id=None):
    if not project_id:
        return None
    row = c.execute('SELECT * FROM client_projects WHERE id=?', (project_id,)).fetchone()
    if not row or (client_id and row['client_id'] != client_id):
        raise a.Error(400, 'Projeto não pertence ao cliente selecionado.')
    import agency_access
    agency_access.need(a, c, u, row['client_id'])
    return row


def _manage(a, c, u, row):
    if row['creator'] != u['id'] and not a.perm(u, 'client_manage') and not a.perm(u, 'task_all'):
        raise a.Error(403, 'Sem permissão para administrar este projeto.')


def _members(a, c, u, data):
    members = a.active_ids(c, data.get('members', []))
    if members and not a.perm(u, 'task_assign') and not a.perm(u, 'client_manage'):
        raise a.Error(403, 'Sem permissão para convidar participantes.')
    return members


def api(a, c, u, method, path, d, q):
    import agency_access

    if path == '/api/client-projects' and method == 'GET':
        a.need(u, 'clients')
        requested = q.get('client_id', [''])[0]
        rows = c.execute(
            'SELECT * FROM client_projects WHERE (?="" OR client_id=?) ORDER BY status,name',
            (requested, requested),
        )
        return [serialize(c, row) for row in rows if agency_access.allowed(c, u, row['client_id'])]

    if path == '/api/client-projects' and method == 'POST':
        a.need(u, 'clients'); a.need(u, 'task_create')
        client_id = a.textfield(d, 'client_id', True, 80)
        agency_access.need(a, c, u, client_id)
        members = _members(a, c, u, d)
        project_id = a.uid(); stamp = a.now()
        c.execute(
            'INSERT INTO client_projects VALUES(?,?,?,?,?,?,?,?)',
            (project_id, client_id, a.textfield(d, 'name', True, 160),
             a.textfield(d, 'description', False, 3000), 'active', u['id'], stamp, stamp),
        )
        for member in set(members + [u['id']]):
            c.execute('INSERT INTO client_project_members VALUES(?,?)', (project_id, member))
            c.execute('INSERT OR IGNORE INTO client_team VALUES(?,?)', (client_id, member))
            if member != u['id']:
                a.notify(c, member, 'Novo projeto', d.get('name', ''), 'clients', 'tasks')
        a.audit(c, u, 'client_project_create', project_id, d.get('name', ''))
        return {'id': project_id}

    if path.startswith('/api/client-projects/'):
        project_id = path.split('/')[3]
        row = project(a, c, u, project_id)
        if method == 'GET':
            return serialize(c, row)
        _manage(a, c, u, row)
        if method == 'PATCH':
            fields = {}
            for key, limit in [('name', 160), ('description', 3000)]:
                if key in d:
                    fields[key] = a.textfield(d, key, key == 'name', limit)
            if 'status' in d:
                if d['status'] not in ['active', 'paused', 'done']:
                    raise a.Error(400, 'Estado do projeto inválido.')
                fields['status'] = d['status']
            if 'members' in d:
                members = _members(a, c, u, d)
                c.execute('DELETE FROM client_project_members WHERE project_id=?', (project_id,))
                for member in set(members + [row['creator']]):
                    c.execute('INSERT INTO client_project_members VALUES(?,?)', (project_id, member))
                    c.execute('INSERT OR IGNORE INTO client_team VALUES(?,?)', (row['client_id'], member))
            fields['updated'] = a.now()
            c.execute('UPDATE client_projects SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',
                      list(fields.values())+[project_id])
            a.audit(c, u, 'client_project_update', project_id, ','.join(fields))
            return {'ok': True}
        if method == 'DELETE':
            if c.execute('SELECT 1 FROM tasks WHERE client_project_id=? LIMIT 1', (project_id,)).fetchone():
                raise a.Error(409, 'Mova ou exclua as tarefas deste projeto antes de removê-lo.')
            c.execute('DELETE FROM client_projects WHERE id=?', (project_id,))
            a.audit(c, u, 'client_project_delete', project_id, row['name'])
            return {'ok': True}

    if path.startswith('/api/tasks/') and path.count('/') == 3 and method == 'DELETE':
        task_id = path.split('/')[3]
        task = a.get_task(c, u, task_id)
        if task['creator'] != u['id'] and task['owner'] != u['id'] and not a.perm(u, 'task_all'):
            raise a.Error(403, 'Somente quem criou, o responsável ou um administrador pode excluir esta tarefa.')
        participants = {task['creator'], task['owner']} | {
            r[0] for r in c.execute('SELECT user_id FROM task_members WHERE task_id=?', (task_id,))
        }
        files = [r[0] for r in c.execute('SELECT id FROM files WHERE task_id=?', (task_id,))]
        # Clear dependent records in a deliberate order so existing installations
        # with older foreign-key definitions can delete safely.
        c.execute('UPDATE tasks SET parent=NULL WHERE parent=?', (task_id,))
        c.execute('DELETE FROM task_dependencies WHERE task_id=? OR depends_on=?', (task_id, task_id))
        c.execute('DELETE FROM deliverables WHERE task_id=?', (task_id,))
        c.execute('DELETE FROM running_timers WHERE task_id=?', (task_id,))
        c.execute('DELETE FROM time_entries WHERE task_id=?', (task_id,))
        c.execute('DELETE FROM comments WHERE task_id=?', (task_id,))
        c.execute('DELETE FROM task_members WHERE task_id=?', (task_id,))
        c.execute('DELETE FROM files WHERE task_id=?', (task_id,))
        c.execute('DELETE FROM tasks WHERE id=?', (task_id,))
        a.audit(c, u, 'task_delete', task_id, task['title'])
        for member in participants - {u['id']}:
            a.notify(c, member, 'Tarefa excluída', task['title'], 'tasks', 'tasks')
        for file_id in files:
            try:
                (a.DATA/'uploads'/file_id).unlink(missing_ok=True)
            except OSError:
                pass
        return {'ok': True}

    return None
