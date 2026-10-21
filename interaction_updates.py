"""NJA 1.17: scoped chat replies, private story views and sales events."""
import json
from datetime import datetime, timedelta, timezone

EMOJIS = ['👍', '❤️', '😂', '🎉', '🔥', '🥷', '👏', '✅']


def init(c):
    c.executescript('''
CREATE TABLE IF NOT EXISTS message_replies(
 message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
 target_id TEXT NOT NULL, target_kind TEXT NOT NULL CHECK(target_kind IN ('message','file')));
CREATE TABLE IF NOT EXISTS file_reactions(
 file_id TEXT REFERENCES files(id) ON DELETE CASCADE, user_id TEXT REFERENCES users(id),
 emoji TEXT NOT NULL, PRIMARY KEY(file_id,user_id));
CREATE TABLE IF NOT EXISTS story_views(
 story_id TEXT REFERENCES stories(id) ON DELETE CASCADE, user_id TEXT REFERENCES users(id),
 viewed TEXT NOT NULL, PRIMARY KEY(story_id,user_id));
CREATE TABLE IF NOT EXISTS sale_celebrations(
 seq INTEGER PRIMARY KEY AUTOINCREMENT, sale_id TEXT NOT NULL UNIQUE REFERENCES sales(id),
 seller TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL,
 position INTEGER NOT NULL, assumed_first INTEGER NOT NULL, month TEXT NOT NULL, created TEXT NOT NULL);
''')


def chat_target(a, c, room_id, target_id, kind):
    if kind not in ('message', 'file') or not isinstance(target_id, str):
        raise a.Error(400, 'Mensagem de origem inválida.')
    table = 'messages' if kind == 'message' else 'files'
    r = c.execute('SELECT * FROM ' + table + ' WHERE id=? AND room_id=?', (target_id, room_id)).fetchone()
    if not r:
        raise a.Error(404, 'Mensagem de origem não encontrada nesta conversa.')
    # Room logos are files, but are not published messages.
    if kind == 'file' and c.execute('SELECT 1 FROM rooms WHERE photo=?', (target_id,)).fetchone():
        raise a.Error(404, 'Mensagem de origem não encontrada nesta conversa.')
    return dict(r)


def validate_reply(a, c, room_id, d):
    target = d.get('reply_to')
    if target is None:
        return None
    kind = d.get('reply_kind', 'message')
    chat_target(a, c, room_id, target, kind)
    return target, kind


def add_quotes(a, c, room_id, rows):
    for row in rows:
        r = c.execute('SELECT target_id,target_kind FROM message_replies WHERE message_id=?', (row['id'],)).fetchone()
        if not r:
            continue
        try:
            target = chat_target(a, c, room_id, r['target_id'], r['target_kind'])
        except a.Error:
            row['reply'] = {'unavailable': True}
            continue
        name = c.execute('SELECT name FROM users WHERE id=?', (target['user_id'],)).fetchone()
        row['reply'] = {'id': target['id'], 'kind': r['target_kind'], 'user_id': target['user_id'],
                        'name': name[0] if name else 'Usuário',
                        'text': (target['text'] if r['target_kind'] == 'message' else target['name'])[:400]}
    return rows


def ranking(c, month):
    return [r[0] for r in c.execute("""SELECT s.seller FROM sales s JOIN users u ON u.id=s.seller
      WHERE s.status='confirmed' AND substr(s.sold_on,1,7)=? GROUP BY s.seller
      ORDER BY SUM(s.amount) DESC,COUNT(*) DESC,u.name,s.seller""", (month,))]


def celebrate_sale(a, c, sale_id, seller, sold_on, previous):
    month = sold_on[:7]
    order = ranking(c, month)
    position = order.index(seller) + 1
    name = c.execute('SELECT name FROM users WHERE id=?', (seller,)).fetchone()[0]
    first = position == 1 and (not previous or previous[0] != seller)
    c.execute('INSERT INTO sale_celebrations(sale_id,seller,name,position,assumed_first,month,created) VALUES(?,?,?,?,?,?,?)',
              (sale_id, seller, name, position, int(first), month, a.now()))


def api(a, c, u, method, path, d, q):
    parts = path.split('/')
    if len(parts) == 5 and parts[2] == 'rooms' and parts[4] == 'interactions':
        rid = parts[3]
        a.room_access(c, u, rid)
        if method == 'GET':
            reactions = [dict(r) | {'kind': 'message'} for r in c.execute(
                'SELECT r.message_id AS target_id,r.user_id,r.emoji FROM message_reactions r JOIN messages m ON m.id=r.message_id WHERE m.room_id=?', (rid,))]
            reactions += [dict(r) | {'kind': 'file'} for r in c.execute(
                'SELECT r.file_id AS target_id,r.user_id,r.emoji FROM file_reactions r JOIN files f ON f.id=r.file_id WHERE f.room_id=?', (rid,))]
            return {'reactions': reactions}
        if method == 'POST':
            import teamwork
            teamwork.need_action(a, c, u, rid, 'send')
            kind = d.get('kind', 'message'); target = d.get('target_id'); emoji = d.get('emoji')
            chat_target(a, c, rid, target, kind)
            if emoji not in EMOJIS:
                raise a.Error(400, 'Emoji inválido.')
            table, column = ('message_reactions', 'message_id') if kind == 'message' else ('file_reactions', 'file_id')
            row = c.execute('SELECT emoji FROM ' + table + ' WHERE ' + column + '=? AND user_id=?', (target, u['id'])).fetchone()
            if row and row[0] == emoji:
                c.execute('DELETE FROM ' + table + ' WHERE ' + column + '=? AND user_id=?', (target, u['id']))
            else:
                c.execute('INSERT OR REPLACE INTO ' + table + ' VALUES(?,?,?)', (target, u['id'], emoji))
            a.audit(c, u, 'message_reaction', target)
            return {'ok': True}
    if len(parts) == 5 and parts[2] == 'stories' and parts[4] in ('view', 'viewers'):
        a.need(u, 'social')
        s = c.execute('SELECT * FROM stories WHERE id=?', (parts[3],)).fetchone()
        if not s:
            raise a.Error(404, 'História não encontrada.')
        if parts[4] == 'viewers' and method == 'GET':
            if s['user_id'] != u['id']:
                raise a.Error(403, 'Somente o autor pode consultar quem visualizou.')
            rows = [dict(r) for r in c.execute('SELECT v.user_id,u.name,u.photo,v.viewed FROM story_views v JOIN users u ON u.id=v.user_id WHERE v.story_id=? ORDER BY v.viewed DESC', (s['id'],))]
            return {'count': len(rows), 'viewers': rows}
        if parts[4] == 'view' and method == 'POST':
            if s['expires'] <= a.now():
                raise a.Error(410, 'Esta história expirou.')
            if s['user_id'] != u['id']:
                c.execute('INSERT OR IGNORE INTO story_views VALUES(?,?,?)', (s['id'], u['id'], a.now()))
            return {'ok': True}
    if path == '/api/celebrations' and method == 'GET':
        # All authenticated staff can see this deliberately minimal event.
        latest = c.execute('SELECT COALESCE(MAX(seq),0) FROM sale_celebrations').fetchone()[0]
        if 'after' not in q:
            return {'cursor': latest, 'items': []}
        try:
            after = int(q['after'][0])
            if after < 0: raise ValueError()
        except (ValueError, TypeError):
            raise a.Error(400, 'Marcador de eventos inválido.')
        since = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(timespec='seconds')
        rows = [dict(r) for r in c.execute("""SELECT e.seq,e.seller,e.name,e.position,e.assumed_first,e.month,e.created
          FROM sale_celebrations e JOIN sales s ON s.id=e.sale_id
          WHERE e.seq>? AND e.created>=? AND s.status='confirmed' ORDER BY e.seq LIMIT 20""", (after, since))]
        return {'cursor': rows[-1]['seq'] if len(rows) == 20 else latest, 'items': rows}
    return None
