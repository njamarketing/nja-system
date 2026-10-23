import base64
import json
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import test_system as base
import app
import zapsign


class ZapSignTest(unittest.TestCase):
    setUp = base.SystemTest.setUp
    tearDown = base.SystemTest.tearDown
    call = base.SystemTest.call

    def grant(self, who, permissions):
        with app.connect() as connection:
            connection.execute(
                'INSERT OR REPLACE INTO roles VALUES(?,?,?)',
                ('zapsign-' + who, who, json.dumps(permissions)),
            )
            connection.execute(
                'UPDATE users SET role_id=? WHERE id=?',
                ('zapsign-' + who, who),
            )

    def contract(self):
        today = datetime.now(app.TZ).date()
        client = self.call('/api/clients', 'POST', {
            'name': 'Cliente ZapSign',
            'entered': today.isoformat(),
            'services': ['Gestão de redes sociais', 'Vídeos'],
        })[1]['id']
        result = self.call('/api/business/contracts', 'POST', {
            'contract_number': 'NJA-ZAP-001',
            'title': 'Contrato integrado',
            'client_id': client,
            'owner': 'master',
            'start': today.isoformat(),
            'expires': (today + timedelta(days=90)).isoformat(),
            'amount': '1200',
        })
        self.assertEqual(result[0], 200, result)
        return result[1]['id']

    @patch.dict(os.environ, {'ZAPSIGN_API_TOKEN': 'local-secret'}, clear=False)
    def test_list_documents_sanitizes_provider_response(self):
        provider_result = [{
            'open_id': 238,
            'token': 'doc-12345678901234567890',
            'status': 'pending',
            'name': 'Contrato exemplo.pdf',
            'folder_path': '/Contratos/',
            'original_file': 'https://files.example/doc.pdf',
            'unknown_secret': 'must-not-leak',
        }]
        with patch.object(zapsign, 'provider', return_value=provider_result) as provider:
            status, payload, _ = self.call('/api/business/zapsign/documents?page=1')
        self.assertEqual(status, 200)
        self.assertEqual(payload['items'][0]['name'], 'Contrato exemplo.pdf')
        self.assertNotIn('unknown_secret', payload['items'][0])
        self.assertNotIn('local-secret', json.dumps(payload))
        self.assertEqual(provider.call_args.args[:3], (app, 'GET', 'docs/'))
        self.assertEqual(provider.call_args.kwargs['query']['include_signers'], 'true')

    @patch.dict(os.environ, {'ZAPSIGN_API_TOKEN': 'local-secret'}, clear=False)
    def test_account_document_list_requires_contract_all(self):
        self.grant('alice', ['contracts', 'contract_manage'])
        with patch.object(zapsign, 'provider') as provider:
            status, _, _ = self.call('/api/business/zapsign/documents', who='alice')
        self.assertEqual(status, 403)
        provider.assert_not_called()

    @patch.dict(os.environ, {'ZAPSIGN_API_TOKEN': 'local-secret'}, clear=False)
    def test_create_document_links_local_contract_and_syncs_status(self):
        contract_id = self.contract()
        token = 'doc-12345678901234567890'
        created = {
            'open_id': 239,
            'token': token,
            'status': 'pending',
            'name': 'Contrato integrado.pdf',
            'folder_path': '/Contratos/',
            'signers': [{'name': 'Pessoa Cliente', 'status': 'new'}],
        }
        data = {
            'name': created['name'],
            'contract_id': contract_id,
            'folder_path': '/Contratos/',
            'base64_pdf': base64.b64encode(b'%PDF-1.4\ntest').decode(),
            'signers': [{
                'name': 'Pessoa Cliente',
                'email': 'cliente@example.com',
                'phone_country': '55',
                'phone_number': '45999999999',
                'auth_mode': 'assinaturaTela-tokenEmail',
                'send_automatic_email': True,
                'send_automatic_whatsapp': False,
            }],
            'reminder_every_n_days': '3',
            'signature_order_active': True,
        }
        with patch.object(zapsign, 'provider', return_value=created) as provider:
            status, payload, _ = self.call('/api/business/zapsign/documents', 'POST', data)
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload['token'], token)
        sent = provider.call_args.args[3]
        self.assertEqual(sent['signers'][0]['email'], 'cliente@example.com')
        self.assertIn({'key': 'nja_contract_id', 'value': contract_id}, sent['metadata'])
        self.assertIn({'key': 'nja_contract_number', 'value': 'NJA-ZAP-001'}, sent['metadata'])
        self.assertTrue(any(item['key'] == 'nja_client_id' for item in sent['metadata']))
        with app.connect() as connection:
            row = connection.execute(
                'SELECT zapsign_token,zapsign_status FROM contracts WHERE id=?',
                (contract_id,),
            ).fetchone()
        self.assertEqual(tuple(row), (token, 'pending'))

    @patch.dict(os.environ, {'ZAPSIGN_API_TOKEN': 'local-secret'}, clear=False)
    def test_rejects_bad_pdf_and_requires_delete_confirmation(self):
        invalid = {
            'name': 'Arquivo inválido',
            'base64_pdf': base64.b64encode(b'not-a-pdf').decode(),
            'signers': [{'name': 'Pessoa Cliente'}],
        }
        with patch.object(zapsign, 'provider') as provider:
            self.assertEqual(
                self.call('/api/business/zapsign/documents', 'POST', invalid)[0],
                400,
            )
            self.assertEqual(
                self.call(
                    '/api/business/zapsign/documents/doc-12345678901234567890',
                    'DELETE',
                    {},
                )[0],
                400,
            )
        provider.assert_not_called()

    @patch.dict(os.environ, {'ZAPSIGN_API_TOKEN': 'local-secret'}, clear=False)
    def test_upload_requires_registered_contract_link(self):
        data = {
            'name': 'Contrato sem vínculo.pdf',
            'base64_pdf': base64.b64encode(b'%PDF-1.4\ntest').decode(),
            'signers': [{'name': 'Pessoa Cliente'}],
        }
        with patch.object(zapsign, 'provider') as provider:
            status, payload, _ = self.call('/api/business/zapsign/documents', 'POST', data)
        self.assertEqual(status, 400, payload)
        self.assertIn('contrato NJA', payload['error'])
        provider.assert_not_called()


if __name__ == '__main__':
    unittest.main()
