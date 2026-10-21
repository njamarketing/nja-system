"""NJA 1.7: permission-scoped personal briefing, reminder delivery and weather."""
import json, math, os, time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BRANCHES = {
    'cascavel': ('Cascavel', -24.9555, -53.4552),
    'foz': ('Foz do Iguaçu', -25.5478, -54.5882),
    'teixeira': ('Teixeira de Freitas', -17.5397, -39.7419),
}

def init(c):
    c.executescript('''
CREATE TABLE IF NOT EXISTS companion_alerts(
 user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
 event_id TEXT REFERENCES events(id) ON DELETE CASCADE,
 occurrence TEXT NOT NULL, stage INTEGER NOT NULL,
 delivered INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(user_id,event_id,occurrence,stage));
CREATE TABLE IF NOT EXISTS companion_weather(
 branch TEXT PRIMARY KEY, payload TEXT NOT NULL, fetched REAL NOT NULL, retry_after REAL NOT NULL DEFAULT 0);
''')

def personal_events(a,c,u,after,before):
    if not a.perm(u,'calendar'):return []
    from scheduler import occurrences
    rows=c.execute('''SELECT DISTINCT e.* FROM events e LEFT JOIN event_members m ON m.event_id=e.id
      WHERE e.creator=? OR e.shared=1 OR m.user_id=?''',(u['id'],u['id'])).fetchall()
    result=[]
    for e in rows:
        for start,end in occurrences(e,after,before):
            if end<=after or start>=before:continue
            result.append({'id':e['id'],'title':e['title'],'start':start.astimezone(timezone.utc).isoformat(),
                           'end':end.astimezone(timezone.utc).isoformat(),'location':e['location']})
    return sorted(result,key=lambda x:x['start'])

def briefing(a,c,u,current=None):
    current=current or datetime.now(timezone.utc)
    start=current.astimezone(a.TZ).replace(hour=0,minute=0,second=0,microsecond=0)
    end=start+timedelta(days=1)
    tasks=None
    if a.perm(u,'tasks'):
        rows=c.execute('''SELECT DISTINCT t.* FROM tasks t LEFT JOIN task_members m ON m.task_id=t.id
          WHERE t.status<>'done' AND (t.owner=? OR m.user_id=?)''',(u['id'],u['id'])).fetchall()
        tasks={'open':len(rows),'due_today':sum(bool(t['due'] and start<=datetime.fromisoformat(t['due'])<end) for t in rows)}
    events=personal_events(a,c,u,start,end) if a.perm(u,'calendar') else None
    return {'name':u['name'].split()[0],'date':start.date().isoformat(),'tasks':tasks,'events':events,
            'branch':u.get('branch','foz'),'updated':current.isoformat()}

def upcoming_alerts(a,c,u,current=None):
    current=current or datetime.now(timezone.utc)
    if not a.perm(u,'calendar') or not u.get('preferences',{}).get('events',True):return []
    result=[]
    for e in personal_events(a,c,u,current,current+timedelta(minutes=61)):
        minutes=(datetime.fromisoformat(e['start'])-current).total_seconds()/60
        if not 0<minutes<=60:continue
        # Catch up only the nearest milestone, never announce three old alerts together.
        stage=next(n for n in (15,30,60) if minutes<=n)
        result.append(e|{'stage':stage,'minutes':max(1,math.ceil(minutes))})
    return result

def ensure_alerts(a,c,u,current=None):
    current=current or datetime.now(timezone.utc)
    alerts=upcoming_alerts(a,c,u,current)
    for e in alerts:
        inserted=c.execute('INSERT OR IGNORE INTO companion_alerts(user_id,event_id,occurrence,stage) VALUES(?,?,?,?)',
                           (u['id'],e['id'],e['start'],e['stage'])).rowcount
        if inserted:
            a.notify(c,u['id'],'Ninja · compromisso em breve',f'{e["title"]} começa em {e["minutes"]} min.','calendar','events')
    return alerts

def claim_alerts(a,c,u,current=None):
    result=[]
    for e in ensure_alerts(a,c,u,current):
        if c.execute('UPDATE companion_alerts SET delivered=1 WHERE user_id=? AND event_id=? AND occurrence=? AND stage=? AND delivered=0',
                     (u['id'],e['id'],e['start'],e['stage'])).rowcount:result.append(e)
    return {'alerts':result}

def fetch_weather(kind,params):
    # Fixed provider/paths: no caller-controlled URL; the key stays on the server.
    url='https://api.openweathermap.org/data/2.5/'+kind+'?'+urlencode(params)
    with urlopen(Request(url,headers={'Accept':'application/json','User-Agent':'NJA-System/1.7'}),timeout=8) as response:
        return json.loads(response.read(2_000_000))

def weather(a,c,u):
    branch=u.get('branch','foz')
    if branch not in BRANCHES:branch='foz'
    city,lat,lon=BRANCHES[branch];key=os.getenv('OPENWEATHER_API_KEY','').strip()
    base={'city':city,'branch':branch,'configured':bool(key),'source':'OpenWeather','source_url':'https://openweathermap.org/'}
    if not key:return base|{'available':False,'message':'O clima aguarda ativação pelo administrador.'}
    current=time.time();cached=c.execute('SELECT * FROM companion_weather WHERE branch=?',(branch,)).fetchone()
    if cached and current-cached['fetched']<900:
        return base|json.loads(cached['payload'])|{'available':True,'stale':False}
    if cached and cached['retry_after']>current:
        if cached['fetched']>0 and current-cached['fetched']<3600:
            return base|json.loads(cached['payload'])|{'available':True,'stale':True}
        return base|{'available':False,'message':'Clima temporariamente indisponível. Tente novamente em alguns minutos.'}
    params={'lat':lat,'lon':lon,'appid':key,'units':'metric','lang':'pt_br'}
    try:
        raw=fetch_weather('weather',params)
        temp=float(raw['main']['temp']);feels=float(raw['main']['feels_like'])
        if not math.isfinite(temp) or not math.isfinite(feels):raise ValueError('Invalid temperature')
        payload={'temperature':round(temp,1),'feels_like':round(feels,1),'description':str(raw['weather'][0]['description'])[:150],
                 'observed':datetime.fromtimestamp(int(raw['dt']),timezone.utc).isoformat(),'fetched':datetime.fromtimestamp(current,timezone.utc).isoformat(),'forecast':[]}
        # A forecast outage must not discard valid current observations.
        try:
            forecast=fetch_weather('forecast',params)
            for item in forecast.get('list',[])[:8]:
                t=float(item['main']['temp'])
                if int(item['dt'])<=current or not math.isfinite(t):continue
                payload['forecast'].append({'time':datetime.fromtimestamp(int(item['dt']),timezone.utc).isoformat(),
                    'temperature':round(t,1),'description':str(item['weather'][0]['description'])[:150],
                    'rain_probability':round(100 * max(0,min(1,float(item.get('pop',0)))))})
        except Exception:pass
        c.execute('INSERT OR REPLACE INTO companion_weather VALUES(?,?,?,0)',(branch,json.dumps(payload),current))
        return base|payload|{'available':True,'stale':False}
    except Exception:
        if cached:c.execute('UPDATE companion_weather SET retry_after=? WHERE branch=?',(current+120,branch))
        else:c.execute('INSERT INTO companion_weather VALUES(?,?,?,?)',(branch,'{}',0,current+120))
        if cached and cached['fetched']>0 and current-cached['fetched']<3600:
            return base|json.loads(cached['payload'])|{'available':True,'stale':True}
        return base|{'available':False,'message':'Clima temporariamente indisponível. Verifique a chave e a conexão do servidor.'}

def api(a,c,u,method,path,d,q):
    if path=='/api/companion/briefing' and method=='GET':return briefing(a,c,u)
    if path=='/api/companion/alerts' and method=='POST':return claim_alerts(a,c,u)
    if path=='/api/companion/weather' and method=='GET':return weather(a,c,u)
    return None
