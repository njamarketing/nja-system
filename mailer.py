"""SMTP password recovery with validated configuration and branded messages."""
import os,ssl,smtplib,html
from email.message import EmailMessage
from email.utils import parseaddr

def config():
    mode=os.getenv('SMTP_SECURITY','starttls').lower();host=os.getenv('SMTP_HOST','').strip();sender=os.getenv('SMTP_FROM','').strip();username=os.getenv('SMTP_USER','');password=os.getenv('SMTP_PASSWORD','')
    try:port=int(os.getenv('SMTP_PORT') or ('465' if mode=='ssl' else '587'))
    except ValueError:port=0
    address=parseaddr(sender)[1]
    ready=bool(host and address and '@' in address and '\n' not in sender and '\r' not in sender and mode in ['starttls','ssl'] and 1<=port<=65535 and bool(username)==bool(password))
    return {'ready':ready,'mode':mode,'host':host,'sender':sender,'port':port,'user':username,'password':password}

def send(email,subject,plain,body):
    cfg=config()
    if not cfg['ready']:raise ValueError('SMTP não configurado corretamente.')
    msg=EmailMessage();msg['Subject']=subject;msg['From']=cfg['sender'];msg['To']=email;msg.set_content(plain);msg.add_alternative(body,subtype='html')
    context=ssl.create_default_context();cls=smtplib.SMTP_SSL if cfg['mode']=='ssl' else smtplib.SMTP
    kwargs={'host':cfg['host'],'port':cfg['port'],'timeout':15}
    if cfg['mode']=='ssl':kwargs['context']=context
    with cls(**kwargs) as smtp:
        if cfg['mode']=='starttls':smtp.starttls(context=context)
        if cfg['user']:smtp.login(cfg['user'],cfg['password'])
        smtp.send_message(msg)

def send_reset(origin,email,token):
    link=origin+'/?reset='+token
    plain='NJA System — recuperação de acesso\n\nPara criar uma nova senha, abra:\n'+link+'\n\nO link é válido por 30 minutos e só pode ser usado uma vez. Se você não solicitou, ignore este e-mail.\nNJA Consultoria & Marketing'
    body=f'''<html lang="pt-BR"><body style="margin:0;background:#f1f5fa;font-family:Arial,sans-serif;color:#1a2940"><div style="max-width:560px;margin:30px auto;padding:32px;background:white;border-radius:16px"><h2 style="color:#1765d8">NJA System</h2><h1 style="font-size:24px">Recupere seu acesso</h1><p>Recebemos uma solicitação para criar uma nova senha.</p><p style="margin:28px 0"><a href="{html.escape(link,quote=True)}" style="background:#1765d8;color:white;padding:14px 22px;border-radius:8px;text-decoration:none">Criar nova senha</a></p><p>Este link expira em <strong>30 minutos</strong> e só pode ser usado uma vez.</p><p>Se você não solicitou a recuperação, ignore este e-mail. Sua senha continuará a mesma.</p><hr style="border:0;border-top:1px solid #e2e9f1"><small>NJA Consultoria &amp; Marketing · Sistema do Ninja</small></div></body></html>'''
    send(email,'Redefina sua senha — NJA System',plain,body)

def send_portal_access(email,name,client,url):
    plain=f'NJA System — acesso do cliente\n\nOlá, {name}. Um novo link de acesso foi criado para {client}:\n{url}\n\nO link é válido por 48 horas e pode ser usado uma vez.'
    body=f'''<html lang="pt-BR"><body style="margin:0;background:#f1f5fa;font-family:Arial,sans-serif;color:#1a2940"><div style="max-width:560px;margin:30px auto;padding:32px;background:white;border-radius:16px"><h2 style="color:#1765d8">NJA System</h2><h1 style="font-size:24px">Seu acesso ao portal</h1><p>Olá, {html.escape(name)}. A equipe NJA criou um novo acesso para <strong>{html.escape(client)}</strong>.</p><p style="margin:28px 0"><a href="{html.escape(url,quote=True)}" style="background:#1765d8;color:white;padding:14px 22px;border-radius:8px;text-decoration:none">Criar nova senha</a></p><p>Este link expira em <strong>48 horas</strong> e pode ser usado uma vez.</p><hr style="border:0;border-top:1px solid #e2e9f1"><small>NJA Consultoria &amp; Marketing · Sistema do Ninja</small></div></body></html>'''
    send(email,'Novo acesso ao Portal do Cliente — NJA System',plain,body)

def api(a,c,u,method,path,d,q):
    if path not in ['/api/mail/status','/api/mail/test']:return None
    if not u['master']:raise a.Error(403,'Somente o master pode testar o envio de e-mail.')
    cfg=config()
    if path.endswith('/status') and method=='GET':return {k:cfg[k] for k in ['ready','mode','port','sender']}
    if path.endswith('/test') and method=='POST':
        if not cfg['ready']:raise a.Error(503,'Configure SMTP_HOST, SMTP_FROM, SMTP_SECURITY, porta e credenciais no servidor.')
        a.throttle(c,'smtp-test:'+u['id'],3);c.commit()
        try:send(u['email'],'Teste de e-mail — NJA System','O envio de e-mails do NJA System está funcionando.','<h2>NJA System</h2><p>O envio de e-mails está funcionando.</p>')
        except Exception:raise a.Error(503,'Falha ao enviar o teste. Confira host, porta, modo TLS e credenciais SMTP.')
        a.audit(c,u,'smtp_test',u['id']);return {'message':'E-mail de teste enviado para '+u['email']+'. Confira sua caixa de entrada.'}
    raise a.Error(404,'Recurso de e-mail não encontrado.')
