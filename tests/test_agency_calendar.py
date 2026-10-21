import unittest,os,time
from unittest.mock import patch
from urllib.parse import urlparse,parse_qs
from datetime import datetime,timedelta,timezone
import test_system as base
import app,agency_calendar,integrations
class CalendarTest(unittest.TestCase):
 setUp=base.SystemTest.setUp
 tearDown=base.SystemTest.tearDown
 call=base.SystemTest.call
 def test_oauth_is_separate_single_use_and_scoped(self):
  with patch.dict(os.environ,{'GOOGLE_CLIENT_ID':'test','GOOGLE_CLIENT_SECRET':'test','GOOGLE_WORKSPACE_DOMAIN':'nja.test'}):
   url=self.call('/api/agency/calendar/connect','POST',who='alice')[1]['url'];state=parse_qs(urlparse(url).query)['state'][0]
   self.assertIn('calendar.events.owned',url)
   self.assertEqual(self.call('/api/agency/calendar/callback?state='+state+'&code=x',who='bob')[0],403)
   with patch.object(integrations,'external',side_effect=[{'access_token':'secret','refresh_token':'refresh','scope':agency_calendar.SCOPE,'expires_in':3600},{'email':'alice@nja.test','verified_email':True}]):self.assertEqual(self.call('/api/agency/calendar/callback?state='+state+'&code=x',who='alice')[0],303)
   self.assertFalse(self.call('/api/integrations',who='alice')[1]['drive_connected'])
   self.assertEqual(self.call('/api/agency/calendar/callback?state='+state+'&code=x',who='alice')[0],403)
 def test_meet_same_event_id_and_no_email_invites(self):
  start=datetime.now(timezone.utc)+timedelta(hours=2);eid=self.call('/api/events','POST',{'title':'Meet teste','start':start.isoformat(),'end':(start+timedelta(hours=1)).isoformat()})[1]['id']
  with app.connect() as c:agency_calendar.save(app,c,{'id':'master'},{'access_token':'x','refresh_token':'r','expires':time.time()+3600},'master@nja.test')
  with patch.object(agency_calendar,'remote',return_value={'hangoutLink':'https://meet.google.com/abc-defg-hij'}) as remote:
   self.assertEqual(self.call('/api/agency/calendar/events/'+eid,'POST')[0],200);gid=remote.call_args.args[2];payload=remote.call_args.args[3];self.assertNotIn('attendees',payload)
   self.call('/api/agency/calendar/events/'+eid,'POST');self.assertEqual(remote.call_args.args[2],gid)
  self.assertEqual(self.call('/api/agency/calendar/events/'+eid,'POST',who='alice')[0],403)
