import argparse,getpass,os,shutil
from datetime import datetime
from app import init,connect,hash_password,uid,now,DATA
p=argparse.ArgumentParser();p.add_argument('command',choices=['init-master','reset-password','backup']);p.add_argument('--email');p.add_argument('--name',default='Nelson Zeni Junior');p.add_argument('--output');a=p.parse_args();init()
if a.command=='backup':
    target=a.output or str(DATA/'backups'/datetime.now().strftime('%Y%m%d-%H%M%S'));os.makedirs(target,exist_ok=False)
    import sqlite3
    with connect() as c,sqlite3.connect(target+'/nja.sqlite3') as out:c.backup(out)
    shutil.copytree(DATA/'uploads',target+'/uploads',ignore=shutil.ignore_patterns('.incoming-*'));
    if (DATA/'integration.key').exists():shutil.copy2(DATA/'integration.key',target+'/integration.key')
    print('Backup criado em '+target)
else:
    email=(a.email or input('E-mail: ')).strip().lower()
    import re
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise SystemExit('E-mail inválido.')
    password=getpass.getpass('Senha (mínimo 10 caracteres): ')
    if len(password)<10 or password!=getpass.getpass('Repita a senha: '):raise SystemExit('Senha inválida ou confirmação diferente.')
    with connect() as c:
        if a.command=='init-master':
            if c.execute('SELECT 1 FROM users WHERE master=1').fetchone():raise SystemExit('Já existe um master.')
            id=uid();c.execute('INSERT INTO users(id,email,name,password,role_id,master,title,area,bio,created) VALUES(?,?,?,?,?,1,?,?,?,?)',(id,email,a.name,hash_password(password),'master','Administrador master','Direção','Gestão da NJA e da equipe.',now()));c.execute('INSERT INTO room_members(room_id,user_id) VALUES(?,?)',('general',id));print('Master criado. Nenhuma senha padrão é utilizada.')
        else:
            r=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
            if not r:raise SystemExit('Conta não encontrada.')
            c.execute('UPDATE users SET password=? WHERE id=?',(hash_password(password),r[0]));c.execute('DELETE FROM sessions WHERE user_id=?',(r[0],));c.execute('DELETE FROM resets WHERE user_id=?',(r[0],));print('Senha redefinida e sessões encerradas.')
