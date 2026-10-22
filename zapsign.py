"""ZapSign document integration with account-wide contract ACLs."""
import base64
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

HOSTS = {
    'production': 'https://api.zapsign.com.br/api/v1/',
    'sandbox': 'https://sandbox.api.zapsign.com.br/api/v1/',
    'br': 'https://br.api.zapsign.com.br/api/v1/',
}
AUTH_MODES = {
    'assinaturaTela', 'tokenEmail', 'assinaturaTela-tokenEmail', 'tokenSms',
    'assinaturaTela-tokenSms', 'tokenWhatsapp', 'assinaturaTela-tokenWhatsapp',
    'certificadoDigital',
}
DOC_STATUSES = {'pending', 'signed', 'refused'}
TOKEN = re.compile(r'^[A-Za-z0-9-]{20,100}$')


def init(c):
    columns = [
        ('zapsign_token', 'TEXT'),
        ('zapsign_status', "TEXT NOT NULL DEFAULT ''"),
        ('zapsign_updated', 'TEXT'),
    ]
    current = {r[1] for r in c.execute('PRAGMA table_info(contracts)')}
    for name, definition in columns:
        if name not in current:
            c.execute('ALTER TABLE contracts ADD COLUMN ' + name + ' ' + definition)
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS contract_zapsign_token_unique ON contracts(zapsign_token) WHERE zapsign_token IS NOT NULL')


def settings():
    environment = os.getenv('ZAPSIGN_ENV', 'production')
    if environment not in HOSTS:
        environment = 'production'
    return environment, os.getenv('ZAPSIGN_API_TOKEN', '').strip()


def provider(a, method, route, body=None, query=None):
    environment, token = settings()
    if not token:
        raise a.Error(503, 'Configure ZAPSIGN_API_TOKEN no servidor.')
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', route) or '..' in route:
        raise a.Error(400, 'Rota ZapSign inválida.')
    url = HOSTS[environment] + route.lstrip('/')
    if query:
        url += ('&' if '?' in url else '?') + urlencode(query)
    raw = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + token}
    if raw is not None:
        headers['Content-Type'] = 'application/json'
    try:
        with urlopen(Request(url, data=raw, headers=headers, method=method), timeout=45) as response:
            payload = response.read(16 * 1024 * 1024 + 1)
            if len(payload) > 16 * 1024 * 1024:
                raise a.Error(503, 'A resposta da ZapSign excedeu o limite aceito.')
            return json.loads(payload) if payload else {}
    except HTTPError as error:
        try:
            detail = json.loads(error.read(65536) or b'{}').get('detail', '')
        except Exception:
            detail = ''
        if error.code in (401, 403):
            raise a.Error(503, 'A ZapSign recusou a credencial ou o plano não permite esta operação.')
        if error.code == 404:
            raise a.Error(404, 'Documento não encontrado na ZapSign.')
        if error.code == 429:
            raise a.Error(429, 'Limite temporário da ZapSign atingido. Aguarde e tente novamente.')
        if 400 <= error.code < 500:
            raise a.Error(400, ('A ZapSign recusou os dados. ' + str(detail))[:500])
        raise a.Error(503, 'A ZapSign não confirmou a operação. Verifique o painel antes de tentar novamente.')
    except (URLError, TimeoutError, ValueError, OSError):
        raise a.Error(503, 'Não foi possível acessar a ZapSign. Verifique a conexão do servidor.')


def text(a, value, label, required=False, limit=255):
    if not isinstance(value, str):
        raise a.Error(400, label + ' inválido.')
    value = value.strip()
    if required and not value:
        raise a.Error(400, 'Preencha ' + label.lower() + '.')
    if len(value) > limit or any(ord(ch) < 32 and ch not in '\n\t' for ch in value):
        raise a.Error(400, label + ' inválido.')
    return value


def folder(a, value):
    value = text(a, value or '/', 'Pasta', False, 255).replace('\\', '/')
    if not value.startswith('/'):
        value = '/' + value
    if not value.endswith('/'):
        value += '/'
    parts = [part for part in value.split('/') if part]
    if len(parts) > 5 or any(len(part) > 50 or part in ('.', '..') for part in parts):
        raise a.Error(400, 'A pasta aceita até 5 níveis e 50 caracteres por nível.')
    return '/' + '/'.join(parts) + ('/' if parts else '')


def email(a, value):
    value = text(a, value or '', 'E-mail', False, 255)
    if value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise a.Error(400, 'E-mail do signatário inválido.')
    return value


def safe_link(value):
    if not isinstance(value, str):
        return ''
    parsed = urlparse(value)
    return value if parsed.scheme == 'https' and parsed.hostname else ''


def signer_json(item):
    if not isinstance(item, dict):
        return {}
    result = {key: item.get(key) for key in (
        'token', 'status', 'name', 'email', 'phone_country', 'phone_number',
        'times_viewed', 'last_view_at', 'signed_at', 'auth_mode', 'qualification'
    )}
    result['sign_url'] = safe_link(item.get('sign_url') or item.get('signing_url'))
    return result


def document_json(item, detailed=False):
    if not isinstance(item, dict):
        return {}
    result = {key: item.get(key) for key in (
        'open_id', 'token', 'status', 'name', 'folder_path', 'created_at',
        'last_update_at', 'date_limit_to_sign', 'deleted', 'deleted_at', 'rejected_reason'
    )}
    result['original_file'] = safe_link(item.get('original_file'))
    result['signed_file'] = safe_link(item.get('signed_file'))
    if detailed or isinstance(item.get('signers'), list):
        result['signers'] = [signer_json(s) for s in item.get('signers', [])]
    return result


def page_number(a, q):
    try:
        page = int(q.get('page', ['1'])[0])
    except (ValueError, TypeError):
        raise a.Error(400, 'Página inválida.')
    if page < 1 or page > 10000:
        raise a.Error(400, 'Página inválida.')
    return page


def list_documents(a, q):
    page = page_number(a, q)
    query = {'page': page, 'deleted': q.get('deleted', ['false'])[0],
             'include_signers': 'true'}
    status = q.get('status', [''])[0]
    if status:
        if status not in DOC_STATUSES:
            raise a.Error(400, 'Status ZapSign inválido.')
        query['status'] = status
    selected_folder = q.get('folder_path', [''])[0]
    if selected_folder:
        query['folder_path'] = folder(a, selected_folder)
    query['sort_order'] = 'asc' if q.get('sort_order', ['desc'])[0] == 'asc' else 'desc'
    result = provider(a, 'GET', 'docs/', query=query)
    if isinstance(result, list):
        raw, count, has_more = result, None, len(result) == 25
    elif isinstance(result, dict) and isinstance(result.get('results'), list):
        raw, count, has_more = result['results'], result.get('count'), bool(result.get('next'))
    else:
        raise a.Error(503, 'A ZapSign retornou uma lista de documentos em formato inesperado.')
    items = [document_json(item) for item in raw]
    folders = sorted({item.get('folder_path') or '/' for item in items})
    counts = {status: sum(item.get('status') == status for item in items) for status in DOC_STATUSES}
    return {'configured': True, 'items': items, 'page': page, 'count': count,
            'has_more': has_more, 'folders': folders, 'counts': counts}


def contract_link(c, token):
    row = c.execute('SELECT id,title,client_id,start,expires,renewal,zapsign_status FROM contracts WHERE zapsign_token=?', (token,)).fetchone()
    return dict(row) if row else None


def prepare_signers(a, values):
    if not isinstance(values, list) or not 1 <= len(values) <= 20:
        raise a.Error(400, 'Adicione de 1 a 20 signatários.')
    result = []
    for index, raw in enumerate(values, 1):
        if not isinstance(raw, dict):
            raise a.Error(400, 'Signatário inválido.')
        name = text(a, raw.get('name', ''), 'Nome do signatário', True)
        signer_email = email(a, raw.get('email', ''))
        country = re.sub(r'\D', '', str(raw.get('phone_country', '55')))
        phone = re.sub(r'\D', '', str(raw.get('phone_number', '')))
        if country and not re.fullmatch(r'[1-9][0-9]{0,3}', country):
            raise a.Error(400, 'DDI do signatário inválido.')
        if phone and not re.fullmatch(r'[1-9][0-9]{7,14}', phone):
            raise a.Error(400, 'Telefone do signatário inválido.')
        auth_mode = raw.get('auth_mode', 'assinaturaTela')
        if auth_mode not in AUTH_MODES:
            raise a.Error(400, 'Autenticação do signatário inválida.')
        send_email = raw.get('send_automatic_email') is True
        send_whatsapp = raw.get('send_automatic_whatsapp') is True
        if send_email and not signer_email:
            raise a.Error(400, 'Informe o e-mail para o envio automático.')
        if send_whatsapp and not phone:
            raise a.Error(400, 'Informe o telefone para o envio automático por WhatsApp.')
        result.append({'name': name, 'email': signer_email, 'phone_country': country,
                       'phone_number': phone, 'auth_mode': auth_mode,
                       'send_automatic_email': send_email,
                       'send_automatic_whatsapp': send_whatsapp,
                       'order_group': index})
    return result


def api(a, c, u, method, parts, d, q):
    a.need(u, 'contracts')
    a.need(u, 'contract_all')
    environment, token = settings()
    if not parts or parts == ['status']:
        return {'configured': bool(token), 'environment': environment,
                'web_app': 'https://app.zapsign.com.br/conta/documentos'}
    resource = parts[0]
    identifier = parts[1] if len(parts) > 1 else None
    if resource == 'documents':
        if method == 'GET' and not identifier:
            if not token:
                return {'configured': False, 'items': [], 'page': 1, 'count': 0,
                        'has_more': False, 'folders': [], 'counts': {s: 0 for s in DOC_STATUSES}}
            return list_documents(a, q)
        if identifier and not TOKEN.fullmatch(identifier):
            raise a.Error(400, 'Token de documento inválido.')
        if method == 'GET' and identifier:
            result = document_json(provider(a, 'GET', 'docs/' + identifier + '/'), True)
            result['linked_contract'] = contract_link(c, identifier)
            return result
        if method == 'POST' and not identifier:
            a.need(u, 'contract_manage')
            name = text(a, d.get('name', ''), 'Nome do documento', True)
            encoded = d.get('base64_pdf', '')
            try:
                raw = base64.b64decode(encoded, validate=True)
            except Exception:
                raise a.Error(400, 'PDF inválido.')
            if not raw.startswith(b'%PDF-') or len(raw) > 8 * 1024 * 1024:
                raise a.Error(400, 'Envie um PDF válido de até 8 MB.')
            contract_id = d.get('contract_id') or None
            client_id = d.get('client_id') or None
            metadata = [{'key': 'nja_source', 'value': 'nja-system'}]
            if contract_id:
                import business
                linked = business.access(a, c, u, 'contracts', contract_id)
                client_id = linked.get('client_id') or client_id
                metadata.append({'key': 'nja_contract_id', 'value': contract_id})
            if client_id:
                import business
                business.client(a, c, u, client_id)
                metadata.append({'key': 'nja_client_id', 'value': client_id})
            limit = d.get('date_limit_to_sign') or ''
            if limit:
                import business
                limit = business.day(a, limit)
            try:
                reminder = int(d.get('reminder_every_n_days', 3))
            except (ValueError, TypeError):
                raise a.Error(400, 'Intervalo de lembretes inválido.')
            if reminder < 0 or reminder > 90:
                raise a.Error(400, 'O intervalo de lembretes deve ficar entre 0 e 90 dias.')
            payload = {'name': name, 'base64_pdf': encoded,
                       'signers': prepare_signers(a, d.get('signers')),
                       'lang': 'pt-br', 'folder_path': folder(a, d.get('folder_path')),
                       'signature_order_active': d.get('signature_order_active') is True,
                       'allow_refuse_signature': d.get('allow_refuse_signature') is True,
                       'reminder_every_n_days': reminder, 'metadata': metadata}
            if limit:
                payload['date_limit_to_sign'] = limit
            created = document_json(provider(a, 'POST', 'docs/', payload), True)
            doc_token = created.get('token')
            if not isinstance(doc_token, str) or not TOKEN.fullmatch(doc_token):
                raise a.Error(503, 'A ZapSign criou o documento sem retornar um identificador válido. Confira o painel.')
            if contract_id:
                c.execute('UPDATE contracts SET zapsign_token=?,zapsign_status=?,zapsign_updated=? WHERE id=?',
                          (doc_token, created.get('status') or 'pending', a.now(), contract_id))
            a.audit(c, u, 'zapsign_document_create', doc_token, name)
            return created
        if method in ('PATCH', 'PUT') and identifier:
            a.need(u, 'contract_manage')
            payload = {}
            if 'name' in d:
                payload['name'] = text(a, d['name'], 'Nome do documento', True)
            if 'folder_path' in d:
                payload['folder_path'] = folder(a, d['folder_path'])
            if 'date_limit_to_sign' in d:
                import business
                payload['date_limit_to_sign'] = business.day(a, d['date_limit_to_sign'])
            if not payload:
                raise a.Error(400, 'Informe ao menos uma alteração.')
            result = provider(a, 'PUT', 'docs/' + identifier + '/', payload)
            a.audit(c, u, 'zapsign_document_update', identifier)
            return {'ok': True, 'provider': result}
        if method == 'DELETE' and identifier:
            a.need(u, 'contract_manage')
            if d.get('confirmed') is not True:
                raise a.Error(400, 'Confirme a exclusão do documento.')
            provider(a, 'DELETE', 'docs/' + identifier + '/')
            c.execute("UPDATE contracts SET zapsign_status='deleted',zapsign_updated=? WHERE zapsign_token=?", (a.now(), identifier))
            a.audit(c, u, 'zapsign_document_delete', identifier)
            return {'ok': True}
    if resource == 'templates' and method == 'GET':
        if not token:
            return {'configured': False, 'items': [], 'page': 1, 'count': 0, 'has_more': False}
        page = page_number(a, q)
        result = provider(a, 'GET', 'templates/', query={'page': page})
        raw = result.get('results', []) if isinstance(result, dict) else result if isinstance(result, list) else []
        items = [{key: item.get(key) for key in ('token', 'name', 'template_type', 'active', 'folder_path', 'created_at', 'last_update_at')} | {'template_file': safe_link(item.get('template_file'))} for item in raw if isinstance(item, dict)]
        return {'configured': True, 'items': items, 'page': page,
                'count': result.get('count') if isinstance(result, dict) else None,
                'has_more': bool(result.get('next')) if isinstance(result, dict) else len(items) == 20}
    if resource == 'sync' and method == 'POST':
        a.need(u, 'contract_manage')
        linked = [dict(r) for r in c.execute("SELECT id,zapsign_token FROM contracts WHERE zapsign_token IS NOT NULL AND zapsign_token<>''")]
        updated = 0
        for row in linked[:100]:
            detail = document_json(provider(a, 'GET', 'docs/' + row['zapsign_token'] + '/'), True)
            c.execute('UPDATE contracts SET zapsign_status=?,zapsign_updated=? WHERE id=?', (detail.get('status') or '', a.now(), row['id']))
            updated += 1
        a.audit(c, u, 'zapsign_sync', 'contracts', updated)
        return {'updated': updated}
    raise a.Error(404, 'Recurso ZapSign não encontrado.')
