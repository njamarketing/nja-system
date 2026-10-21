"""Run as an independent process: python scheduler.py [--once]."""
import calendar, json, os, time, sys, logging
from datetime import datetime, timedelta, timezone
from app import connect, init, now, notify, TZ
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')

def occurrences(e,after,before):
    start=datetime.fromisoformat(e['start']).astimezone(TZ);end=datetime.fromisoformat(e['end']).astimezone(TZ)
    duration=end-start;until=datetime.fromisoformat(e['until_date']) if e['until_date'] else start
    cursor=start;index=0
    while cursor<=before and cursor<=until and index<10000:
        if cursor+duration>=after:yield cursor,cursor+duration
        index+=1
        if e['recurrence']=='none':break
        if e['recurrence']=='daily':cursor=start+timedelta(days=index)
        elif e['recurrence']=='weekly':cursor=start+timedelta(weeks=index)
        else:
            n=start.month-1+index;y=start.year+n//12;m=n%12+1
            cursor=start.replace(year=y,month=m,day=min(start.day,calendar.monthrange(y,m)[1]))

def tick():
    current=datetime.now(timezone.utc)
    with connect() as c:
        for e in c.execute('SELECT * FROM events').fetchall():
            if e['reminder'] in (15,30,60):continue  # Managed by the three Ninja milestones below.
            for start,_ in occurrences(e,current-timedelta(minutes=5),current+timedelta(days=1)):
                trigger=start-timedelta(minutes=e['reminder'])
                # Catch up missed alerts only for an upcoming occurrence; never spam past events.
                if trigger<=current<=start+timedelta(minutes=5):
                    members={r[0] for r in c.execute('SELECT user_id FROM event_members WHERE event_id=?',(e['id'],))}
                    if e['shared']:members.update(r[0] for r in c.execute('SELECT id FROM users WHERE active=1'))
                    for m in members:
                        key=f'event:{e["id"]}:{start.isoformat()}:{m}'
                        if c.execute('INSERT OR IGNORE INTO reminder_log VALUES(?,?)',(key,now())).rowcount:
                            notify(c,m,'Compromisso se aproximando',e['title']+' • '+start.astimezone(TZ).strftime('%d/%m %H:%M'),'calendar','events')
        for t in c.execute("SELECT * FROM tasks WHERE due IS NOT NULL AND status<>'done'").fetchall():
            due=datetime.fromisoformat(t['due']);stage='late' if due<current else 'soon' if due-current<=timedelta(hours=24) else None
            if not stage:continue
            members={t['owner'],t['creator']}|{r[0] for r in c.execute('SELECT user_id FROM task_members WHERE task_id=?',(t['id'],))}
            for m in members:
                key=f'task:{t["id"]}:{t["due"]}:{stage}:{m}'
                if c.execute('INSERT OR IGNORE INTO reminder_log VALUES(?,?)',(key,now())).rowcount:notify(c,m,'Tarefa atrasada' if stage=='late' else 'Prazo se aproximando',t['title'],'tasks:'+t['id'],'tasks')
        import app as application_module, companion, business
        import agency_production
        agency_production.tick(application_module,c)
        import agency_commercial
        agency_commercial.tick(application_module,c)
        business.reminders(application_module,c,current)
        for person in c.execute('SELECT * FROM users WHERE active=1').fetchall():
            companion.ensure_alerts(application_module,c,application_module.user_public(c,person),current)
        c.execute('DELETE FROM companion_alerts WHERE occurrence<?',((current-timedelta(days=2)).isoformat(),))
        c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),));c.execute('DELETE FROM resets WHERE expires<?',(time.time(),))
        c.execute('DELETE FROM rate_limits WHERE until<?',(time.time(),))
    with connect() as c:c.execute('INSERT OR REPLACE INTO operation_state VALUES(?,?)',('scheduler_tick',now()))
    if os.getenv('NJA_BACKUP_DIR'):
        with connect() as c:last=c.execute("SELECT value FROM operation_state WHERE key='last_backup'").fetchone()
        if not last or (current-datetime.fromisoformat(last[0])).total_seconds()>86400:
            try:
                import agency_access, app
                agency_access.backup(app)
            except Exception:logging.exception('Falha na rotina de backup')
    import agency_editorial,app
    agency_editorial.tick(app)
    deliver_push()

def deliver_push():
    if not os.getenv('VAPID_PRIVATE_KEY'):return
    try:from pywebpush import webpush,WebPushException
    except ImportError:
        logging.error('Instale requirements.txt para enviar push.');return
    with connect() as c:
        rows=c.execute('SELECT push_outbox.*,notifications.user_id,notifications.title,notifications.body,notifications.link FROM push_outbox JOIN notifications ON notifications.id=push_outbox.notification_id WHERE next_attempt<=? LIMIT 100',(time.time(),)).fetchall()
        for r in rows:
            import app,agency_access
            raw=c.execute('SELECT * FROM users WHERE id=? AND active=1',(r['user_id'],)).fetchone()
            if not raw or not agency_access.notification_allowed(app,c,app.user_public(c,raw),r['link']):
                c.execute('DELETE FROM push_outbox WHERE id=?',(r['id'],));continue
            subs=c.execute('SELECT * FROM subscriptions WHERE user_id=?',(r['user_id'],)).fetchall();retry=False
            for s in subs:
                try:webpush(subscription_info=json.loads(s['subscription']),data=json.dumps({'title':r['title'],'body':r['body'],'url':'/#'+r['link']}),vapid_private_key=os.environ['VAPID_PRIVATE_KEY'],vapid_claims={'sub':os.getenv('VAPID_SUBJECT','mailto:admin@example.com')},timeout=10)
                except WebPushException as e:
                    status=e.response.status_code if e.response is not None else 0
                    if status in [404,410]:c.execute('DELETE FROM subscriptions WHERE endpoint=?',(s['endpoint'],))
                    else:retry=True
                except Exception:retry=True
            if retry:
                c.execute('UPDATE push_outbox SET attempts=attempts+1,next_attempt=?,last_error=? WHERE id=?',(time.time()+min(3600,60*2**min(r['attempts'],6)),'Falha temporária no serviço push',r['id']))
            else:c.execute('DELETE FROM push_outbox WHERE id=?',(r['id'],))

if __name__=='__main__':
    init()
    while True:
        try:tick()
        except Exception:logging.exception('Falha no processamento de lembretes')
        if '--once' in sys.argv:break
        time.sleep(30)
