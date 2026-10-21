import unittest
import test_system
app=test_system.app
class MentionTest(unittest.TestCase):
 setUp=test_system.SystemTest.setUp
 tearDown=test_system.SystemTest.tearDown
 call=test_system.SystemTest.call
 make_task=test_system.SystemTest.make_task
 def test_mentions_do_not_leak_task_or_room(self):
  task=self.make_task()
  self.assertEqual(self.call('/api/tasks/'+task+'/comments','POST',{'text':'Olá @Bob','mentions':['bob']},who='alice')[0],200)
  with app.connect() as c:
   self.assertEqual(c.execute("SELECT count(*) FROM notifications WHERE user_id='bob' AND link=?",('tasks:'+task,)).fetchone()[0],0)
  room=self.call('/api/rooms','POST',{'kind':'group','name':'Privado','members':['alice']})[1]['id']
  self.assertEqual(self.call('/api/rooms/'+room+'/messages','POST',{'text':'Olá @Bob','mentions':['bob']})[0],200)
  with app.connect() as c:self.assertEqual(c.execute("SELECT count(*) FROM notifications WHERE user_id='bob' AND link=?",('chats:'+room,)).fetchone()[0],0)
 def test_feed_mentions_deduplicate_and_require_text(self):
  status,r,_=self.call('/api/posts','POST',{'text':'Olá @Alice','mentions':['alice','alice','bob']})
  self.assertEqual(status,200,r)
  with app.connect() as c:
   self.assertEqual(c.execute("SELECT count(*) FROM notifications WHERE user_id='alice' AND title LIKE '%mencionou%' ").fetchone()[0],1)
   self.assertEqual(c.execute("SELECT count(*) FROM notifications WHERE user_id='bob' AND title LIKE '%mencionou%' ").fetchone()[0],0)
