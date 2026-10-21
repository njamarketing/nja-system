import unittest, os, json, time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import test_system, companion
app=test_system.app

class CompanionTest(unittest.TestCase):
    setUp=test_system.SystemTest.setUp
    tearDown=test_system.SystemTest.tearDown
    call=test_system.SystemTest.call
    make_task=test_system.SystemTest.make_task

    def event(self,start,members=None,**kw):
        status,r,_=self.call('/api/events','POST',{'title':'Reunião NJA','start':start.isoformat(),'end':(start+timedelta(hours=1)).isoformat(),'members':members or ['alice'],**kw})
        self.assertEqual(status,200,r);return r['id']

    def person(self,c,id='alice'):
        return app.user_public(c,c.execute('SELECT * FROM users WHERE id=?',(id,)).fetchone())

    def test_briefing_personal_scope_not_all_master_records(self):
        self.make_task(owner='alice');done=self.make_task(owner='alice');self.call('/api/tasks/'+done,'PATCH',{'status':'done'})
        self.make_task(owner='bob')
        now=datetime.now(timezone.utc);self.event(now)
        alice=self.call('/api/companion/briefing',who='alice')[1]
        bob=self.call('/api/companion/briefing',who='bob')[1]
        master=self.call('/api/companion/briefing')[1]
        self.assertEqual(alice['tasks']['open'],1);self.assertEqual(len(alice['events']),1)
        self.assertEqual(len(bob['events']),0);self.assertEqual(master['tasks']['open'],0)

    def test_recurrence_timezone_and_permissions(self):
        start=datetime(2026,10,14,22,tzinfo=app.TZ)
        self.event(start,recurrence='daily',until_date=(start+timedelta(days=4)).isoformat())
        with app.connect() as c:
            data=companion.briefing(app,c,self.person(c),datetime(2026,10,16,1,30,tzinfo=timezone.utc))
            self.assertEqual(data['date'],'2026-10-15');self.assertEqual(len(data['events']),1)
            u=self.person(c);u['permissions']=[]
            self.assertIsNone(companion.briefing(app,c,u)['tasks']);self.assertIsNone(companion.briefing(app,c,u)['events'])
            self.assertEqual(companion.claim_alerts(app,c,u)['alerts'],[])

    def test_three_milestones_deduplicated_across_requests(self):
        start=datetime.now(timezone.utc)+timedelta(hours=2);self.event(start)
        with app.connect() as c:
            u=self.person(c)
            for minutes in [60,30,15]:
                now=start-timedelta(minutes=minutes)
                r=companion.claim_alerts(app,c,u,now)['alerts']
                self.assertEqual(len(r),1);self.assertEqual(r[0]['stage'],minutes)
                self.assertEqual(companion.claim_alerts(app,c,u,now)['alerts'],[])
            self.assertEqual(c.execute('SELECT COUNT(*) FROM companion_alerts WHERE user_id=?',('alice',)).fetchone()[0],3)
            self.assertEqual(companion.claim_alerts(app,c,u,start+timedelta(seconds=1))['alerts'],[])

    def test_catchup_nearest_only_no_other_users_events(self):
        start=datetime.now(timezone.utc)+timedelta(minutes=10);self.event(start)
        with app.connect() as c:
            result=companion.claim_alerts(app,c,self.person(c))['alerts']
            self.assertEqual([r['stage'] for r in result],[15])
            self.assertEqual(companion.claim_alerts(app,c,self.person(c,'bob'))['alerts'],[])

    def test_reschedule_cancellation_and_event_preferences(self):
        start=datetime.now(timezone.utc)+timedelta(minutes=25);eid=self.event(start)
        self.assertEqual(len(self.call('/api/companion/alerts','POST',{},who='alice')[1]['alerts']),1)
        start+=timedelta(minutes=3);self.call('/api/events/'+eid,'PATCH',{'start':start.isoformat(),'end':(start+timedelta(hours=1)).isoformat()})
        self.assertEqual(len(self.call('/api/companion/alerts','POST',{},who='alice')[1]['alerts']),1)
        self.call('/api/events/'+eid,'DELETE',{})
        self.assertEqual(self.call('/api/companion/alerts','POST',{},who='alice')[1]['alerts'],[])
        self.event(start)
        with app.connect() as c:
            u=self.person(c);u['preferences']['events']=False
            self.assertEqual(companion.claim_alerts(app,c,u)['alerts'],[])

    def test_alert_claim_requires_auth_and_csrf(self):
        self.assertEqual(self.call('/api/companion/briefing',login=False)[0],401)
        self.assertEqual(self.call('/api/companion/alerts','POST',{},csrf=False)[0],403)

    def current_weather(self):return {'main':{'temp':25.5,'feels_like':26.2},'weather':[{'description':'céu limpo'}],'dt':int(time.time())}
    def forecast(self):return {'list':[{'dt':int(time.time()+10800),'main':{'temp':24},'weather':[{'description':'chuva leve'}],'pop':0.42}]}

    def test_weather_configuration_branch_cache_and_no_key_exposure(self):
        with patch.dict(os.environ,{'OPENWEATHER_API_KEY':''}):
            self.assertFalse(self.call('/api/companion/weather',who='alice')[1]['available'])
        self.call('/api/users/alice/branch','PATCH',{'branch':'teixeira'})
        with patch.dict(os.environ,{'OPENWEATHER_API_KEY':'test-private-key'}),patch('companion.fetch_weather',side_effect=[self.current_weather(),self.forecast()]) as fetch:
            data=self.call('/api/companion/weather',who='alice')[1]
            self.assertEqual(data['city'],'Teixeira de Freitas');self.assertEqual(data['forecast'][0]['rain_probability'],42)
            self.assertNotIn('test-private-key',json.dumps(data));self.assertEqual(fetch.call_count,2)
            self.assertTrue(self.call('/api/companion/weather',who='alice')[1]['available']);self.assertEqual(fetch.call_count,2)
            self.assertAlmostEqual(fetch.call_args_list[0].args[1]['lat'],-17.5397)

    def test_weather_outage_stale_and_partial_forecast(self):
        with patch.dict(os.environ,{'OPENWEATHER_API_KEY':'key'}):
            with patch('companion.fetch_weather',side_effect=[self.current_weather(),RuntimeError('forecast down')]):
                data=self.call('/api/companion/weather',who='alice')[1];self.assertTrue(data['available']);self.assertEqual(data['forecast'],[])
            with app.connect() as c:c.execute('UPDATE companion_weather SET fetched=?',(time.time()-1000,))
            with patch('companion.fetch_weather',side_effect=RuntimeError('down')):
                self.assertTrue(self.call('/api/companion/weather',who='alice')[1]['stale'])
            with app.connect() as c:c.execute('UPDATE companion_weather SET fetched=?,retry_after=0',(time.time()-4000,))
            with patch('companion.fetch_weather',side_effect=RuntimeError('down')) as fetch:
                self.assertFalse(self.call('/api/companion/weather',who='alice')[1]['available'])
                self.call('/api/companion/weather',who='alice');self.assertEqual(fetch.call_count,1)

    def test_scheduler_creates_milestone_and_browser_claims_once(self):
        import scheduler
        self.event(datetime.now(timezone.utc)+timedelta(minutes=29))
        scheduler.tick();scheduler.tick()
        notices=self.call('/api/notifications',who='alice')[1]
        reminders=[n for n in notices if n['title']=='Ninja · compromisso em breve']
        self.assertEqual(len(reminders),1)
        self.assertEqual(len(self.call('/api/companion/alerts','POST',{},who='alice')[1]['alerts']),1)
        self.assertEqual(self.call('/api/companion/alerts','POST',{},who='alice')[1]['alerts'],[])
