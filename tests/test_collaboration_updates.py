import test_system


class CollaborationUpdatesTest(test_system.SystemTest):
    def create_client(self):
        status, result, _ = self.call('/api/clients', 'POST', {
            'name': 'Cliente Projetos',
            'entered': '2026-10-23',
            'product': 'Plano completo',
        })
        self.assertEqual(status, 200)
        return result['id']

    def test_client_project_task_observers_and_delete(self):
        client_id = self.create_client()
        status, result, _ = self.call('/api/client-projects', 'POST', {
            'client_id': client_id,
            'name': 'Campanha de verão',
            'description': 'Referência https://example.com/briefing',
            'members': ['alice', 'bob'],
        })
        self.assertEqual(status, 200)
        project_id = result['id']
        project = self.call('/api/client-projects/'+project_id)[1]
        self.assertEqual(set(project['members']), {'master', 'alice', 'bob'})

        status, result, _ = self.call('/api/tasks', 'POST', {
            'title': 'Criar peças',
            'description': 'Confira https://example.com',
            'client_id': client_id,
            'project_id': project_id,
            'owner': 'alice',
            'members': [],
        })
        self.assertEqual(status, 200)
        task_id = result['id']
        task = self.call('/api/tasks/'+task_id, who='bob')[1]
        self.assertEqual(task['client_project_id'], project_id)
        self.assertEqual(task['project'], 'Campanha de verão')
        self.assertEqual(task['creator'], 'master')
        self.assertEqual(task['members'], [])
        # Bob can see it through the project invitation even without being an observer.
        self.assertEqual(self.call('/api/tasks/'+task_id, who='bob')[0], 200)

        self.assertEqual(self.call('/api/tasks/'+task_id, 'DELETE', {}, who='bob')[0], 403)
        self.assertEqual(self.call('/api/tasks/'+task_id, 'DELETE', {}, who='alice')[0], 200)
        self.assertEqual(self.call('/api/tasks/'+task_id)[0], 404)

    def test_profile_cover_position_is_validated_and_persisted(self):
        self.assertEqual(self.call('/api/users/alice', 'PATCH', {
            'cover_x': 22, 'cover_y': 74, 'cover_zoom': 145,
        }, who='alice')[0], 200)
        profile = self.call('/api/profiles/alice', who='alice')[1]
        self.assertEqual((profile['cover_x'], profile['cover_y'], profile['cover_zoom']), (22, 74, 145))
        self.assertEqual(self.call('/api/users/alice', 'PATCH', {'cover_zoom': 999}, who='alice')[0], 400)

    def test_push_logout_only_removes_current_endpoint(self):
        with test_system.app.connect() as connection:
            connection.execute('INSERT INTO subscriptions VALUES(?,?,?)', ('https://fcm.googleapis.com/a', 'alice', '{}'))
            connection.execute('INSERT INTO subscriptions VALUES(?,?,?)', ('https://fcm.googleapis.com/b', 'alice', '{}'))
        self.assertEqual(self.call('/api/push', 'DELETE', {'endpoint': 'https://fcm.googleapis.com/a'}, who='alice')[0], 200)
        with test_system.app.connect() as connection:
            endpoints = [row[0] for row in connection.execute('SELECT endpoint FROM subscriptions WHERE user_id=?', ('alice',))]
        self.assertEqual(endpoints, ['https://fcm.googleapis.com/b'])


if __name__ == '__main__':
    test_system.unittest.main()
