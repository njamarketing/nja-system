"""Abra este arquivo no Pydroid 3 e toque em Executar. Veja ANDROID.md."""
import getpass
import hashlib
import os
from pathlib import Path
import re
from socketserver import ThreadingMixIn
import sys
import threading
import webbrowser
from wsgiref.simple_server import WSGIServer, make_server

ROOT = Path(__file__).resolve().parent


def configure():
    if sys.version_info < (3, 10):
        raise RuntimeError('É necessário Python 3.10 ou superior.')
    if not (ROOT / 'app.py').is_file():
        raise RuntimeError('Extraia o ZIP completo. Este arquivo deve ficar ao lado de app.py.')
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo('America/Sao_Paulo')
    except ZoneInfoNotFoundError:
        raise RuntimeError('Instale tzdata na opção Pip do Pydroid e execute novamente.') from None
    if not hasattr(hashlib, 'scrypt'):
        raise RuntimeError('Este Python não oferece scrypt, necessário para proteger as senhas. Use uma instalação com suporte a scrypt.')
    port = int(os.environ.get('NJA_ANDROID_PORT', '8000'))
    if not 1024 <= port <= 65535:
        raise RuntimeError('NJA_ANDROID_PORT deve estar entre 1024 e 65535.')
    os.environ['NJA_ORIGIN'] = f'http://localhost:{port}'
    os.environ['NJA_DATA'] = str(ROOT / 'data')
    os.chdir(ROOT)
    return port


def ensure_master(app):
    with app.connect() as db:
        if db.execute('SELECT 1 FROM users WHERE master=1').fetchone():
            return
    print('\nPrimeiro acesso: crie seu administrador. Não há senha padrão.')
    name = input('Nome: ').strip() or 'Administrador NJA'
    email = input('E-mail: ').strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise RuntimeError('E-mail inválido. Execute novamente.')
    password = getpass.getpass('Senha (mínimo 10 caracteres): ')
    confirmation = getpass.getpass('Repita a senha: ')
    if len(password) < 10 or password != confirmation:
        raise RuntimeError('Senha curta ou confirmação diferente. Execute novamente.')
    hashed = app.hash_password(password)
    with app.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM users WHERE master=1').fetchone():
            return
        ident = app.uid()
        db.execute('INSERT INTO users(id,email,name,password,role_id,master,title,area,bio,created) VALUES(?,?,?,?,?,1,?,?,?,?)',
                   (ident, email, name, hashed, 'master', 'Administrador master', 'Direção', '', app.now()))
        db.execute('INSERT INTO room_members(room_id,user_id) VALUES(?,?)', ('general', ident))
    print('Administrador criado.')


def reminders(stop, tick):
    while not stop.is_set():
        try:
            tick()
        except Exception:
            print('Não foi possível atualizar os lembretes. Nova tentativa em 30 segundos.')
        stop.wait(30)


class LocalServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def main():
    port = configure()
    import app
    # Reserve a porta antes de criar contas ou iniciar rotinas.
    try:
        server = make_server('127.0.0.1', port, app.application, server_class=LocalServer)
    except OSError:
        raise RuntimeError(f'Não foi possível abrir a porta {port}. Encerre outra execução do NJA e tente novamente.') from None
    stop = threading.Event()
    try:
        app.init()
        ensure_master(app)
        import scheduler
        threading.Thread(target=reminders, args=(stop, scheduler.tick), daemon=True).start()
        url = f'http://localhost:{port}'
        print(f'\nNJA iniciado: {url}\nDados: {app.DATA}')
        print('Mantenha o Pydroid aberto. Para encerrar, use Parar ou Ctrl+C.')
        def open_browser():
            try:
                webbrowser.open(url)
            except Exception:
                print('Abra manualmente no navegador: ' + url)
        threading.Thread(target=open_browser, daemon=True).start()
        server.serve_forever(poll_interval=0.3)
    finally:
        stop.set()
        server.server_close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nNJA encerrado.')
    except Exception as exc:
        print(f'\nNão foi possível iniciar: {exc}')
        print('Consulte ANDROID.md na pasta do sistema.')
