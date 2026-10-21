"""Client-scoped Meta campaign operations. New campaigns start paused."""
import json,re
from datetime import date
import agency_access as scope,agency_editorial as editorial,business,integrations
OBJECTIVES=['OUTCOME_AWARENESS','OUTCOME_TRAFFIC','OUTCOME_ENGAGEMENT','OUTCOME_LEADS','OUTCOME_APP_PROMOTION','OUTCOME_SALES']
def init(c):c.execute('CREATE TABLE IF NOT EXISTS ads_requests(nonce TEXT PRIMARY KEY,account_id TEXT NOT NULL,user_id TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,external_id TEXT,created TEXT NOT NULL)')
def account(a,c,u,id):
 acc=editorial.account(a,c,u,id)
 if acc['platform']!='ads' or not acc['active']:raise a.Error(409,'Selecione uma conta de anúncios ativa.')
 return acc

def api(a,c,u,method,path,d,q):
 if not path.startswith('/api/agency/ads'):return None
 a.need(u,'marketing');parts=path.split('/')[4:]
 if not parts and method=='GET':return {'accounts':[dict(r) for r in c.execute("SELECT id,client_id,name,target,active,verified FROM social_accounts WHERE platform='ads'") if scope.allowed(c,u,r['client_id'])],'objectives':OBJECTIVES,'requests':[dict(r) for r in c.execute("SELECT r.nonce,r.account_id,r.status,r.external_id,r.created,s.client_id FROM ads_requests r JOIN social_accounts s ON s.id=r.account_id WHERE r.status<>'confirmed'") if scope.allowed(c,u,r['client_id'])]}
 if parts==['accounts'] and method=='POST':
  a.need(u,'marketing_manage');a.need(u,'integrations_manage');cid=d.get('client_id');scope.need(a,c,u,cid);target=a.textfield(d,'target',True,100)
  if not re.fullmatch(r'act_\d+',target):raise a.Error(400,'Informe o ID da conta com prefixo act_.')
  id=a.uid();secret=integrations.cipher(a).encrypt(a.textfield(d,'token',True,4000).encode()).decode();c.execute("INSERT INTO social_accounts(id,client_id,name,platform,target,secret,created) VALUES(?,?,?,'ads',?,?,?)",(id,cid,a.textfield(d,'name',True,120),target,secret,a.now()));a.audit(c,u,'ads_account',id);return {'id':id}
 if len(parts)<2 or parts[0]!='accounts':raise a.Error(404,'Ação Meta Ads inválida.')
 acc=account(a,c,u,parts[1]);action=parts[2] if len(parts)>2 else ''
 if method=='PATCH' and not action:
  a.need(u,'marketing_manage');a.need(u,'integrations_manage')
  if 'token' in d:c.execute('UPDATE social_accounts SET secret=?,verified=NULL WHERE id=?',(integrations.cipher(a).encrypt(a.textfield(d,'token',True,4000).encode()).decode(),acc['id']))
  if d.get('active') is False:c.execute('UPDATE social_accounts SET active=0 WHERE id=?',(acc['id'],))
  a.audit(c,u,'ads_account_update',acc['id']);return {'ok':True}
 if action=='campaigns' and method=='GET':
  info=editorial.graph(a,acc,acc['target'],query={'fields':'id,name,currency,account_status'});cursor=q.get('after',[''])[0]
  if len(cursor)>2000:raise a.Error(400,'Página inválida.')
  result=editorial.graph(a,acc,acc['target']+'/campaigns',query={'fields':'id,name,status,effective_status,objective,daily_budget,lifetime_budget','limit':50,**({'after':cursor} if cursor else {})});c.execute('UPDATE social_accounts SET verified=? WHERE id=?',(a.now(),acc['id']))
  return {'account':info,'items':result.get('data',[]),'after':result.get('paging',{}).get('cursors',{}).get('after') if result.get('paging',{}).get('next') else None}
 if action=='insights' and method=='GET':
  start=business.day(a,q.get('start',[''])[0]);end=business.day(a,q.get('end',[''])[0])
  if not 0<=(date.fromisoformat(end)-date.fromisoformat(start)).days<=366:raise a.Error(400,'Consulte até 366 dias, com início anterior ao fim.')
  result=editorial.graph(a,acc,acc['target']+'/insights',query={'level':'campaign','fields':'campaign_id,campaign_name,impressions,clicks,spend,cpc,ctr,actions','time_range':json.dumps({'since':start,'until':end}),'limit':100})
  return {'items':result.get('data',[]),'has_more':bool(result.get('paging',{}).get('next')),'start':start,'end':end}
 a.need(u,'marketing_manage')
 if action=='campaigns' and method=='POST':
  objective=d.get('objective');categories=d.get('categories',[])
  if objective not in OBJECTIVES or not isinstance(categories,list) or any(x not in ['FINANCIAL_PRODUCTS_SERVICES','CREDIT','EMPLOYMENT','HOUSING','ISSUES_ELECTIONS_POLITICS'] for x in categories):raise a.Error(400,'Objetivo ou categoria inválida.')
  # BRL-only editing prevents interpreting minor units of other account currencies incorrectly.
  info=editorial.graph(a,acc,acc['target'],query={'fields':'id,currency'})
  if info.get('currency')!='BRL':raise a.Error(409,'A criação e a edição de orçamento neste formulário exigem conta em BRL.')
  amount=business.money(a,d.get('daily_budget'))
  if amount<=0:raise a.Error(400,'Defina o orçamento diário.')
  nonce=a.textfield(d,'nonce',True,100)
  if not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',nonce):raise a.Error(400,'Identificador de solicitação inválido.')
  payload={'name':a.textfield(d,'name',True,180),'objective':objective,'status':'PAUSED','special_ad_categories':json.dumps(categories),'daily_budget':amount,'bid_strategy':'LOWEST_COST_WITHOUT_CAP'};encoded=json.dumps(payload,sort_keys=True)
  if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
  old=c.execute('SELECT * FROM ads_requests WHERE nonce=?',(nonce,)).fetchone()
  if old:
   if old['account_id']!=acc['id'] or old['user_id']!=u['id'] or old['payload']!=encoded:raise a.Error(409,'Solicitação já utilizada.')
   return {'status':old['status'],'id':old['external_id']}
  c.execute("INSERT INTO ads_requests VALUES(?,?,?,?,'sending',NULL,?)",(nonce,acc['id'],u['id'],encoded,a.now()));c.commit()
  try:result=editorial.graph(a,acc,acc['target']+'/campaigns',payload);id=result['id']
  except Exception:c.execute("UPDATE ads_requests SET status='unknown' WHERE nonce=?",(nonce,));c.commit();raise a.Error(503,'Criação sem confirmação. Confira no Gerenciador de Anúncios antes de repetir.')
  c.execute("UPDATE ads_requests SET status='confirmed',external_id=? WHERE nonce=?",(id,nonce));a.audit(c,u,'ads_campaign_create',id);return {'id':id,'status':'confirmed'}
 if action=='campaigns' and len(parts)==4 and method=='PATCH':
  id=parts[3]
  if not re.fullmatch(r'\d+',id):raise a.Error(400,'Campanha inválida.')
  campaign=editorial.graph(a,acc,id,query={'fields':'id,account_id'})
  if str(campaign.get('account_id'))!=acc['target'].removeprefix('act_'):raise a.Error(403,'Campanha de outra conta.')
  payload={}
  if 'status' in d:
   if d['status'] not in ['ACTIVE','PAUSED']:raise a.Error(400,'Estado inválido.')
   payload['status']=d['status']
  if 'daily_budget' in d:
   info=editorial.graph(a,acc,acc['target'],query={'fields':'currency'})
   if info.get('currency')!='BRL':raise a.Error(409,'Edição de orçamento disponível para contas BRL.')
   payload['daily_budget']=business.money(a,d['daily_budget'])
   if payload['daily_budget']<=0:raise a.Error(400,'Orçamento deve ser positivo.')
  if not payload:raise a.Error(400,'Selecione uma alteração.')
  editorial.graph(a,acc,id,payload);a.audit(c,u,'ads_campaign_update',id,json.dumps(payload));return {'ok':True}
 raise a.Error(404,'Ação Meta Ads não encontrada.')
