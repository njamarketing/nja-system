# NJA System 1.8 — Comercial, financeiro e contratos

Esta atualização acrescenta módulos ao sistema Python existente e preserva o ninja 1.7. Não foi publicada. Não inclui credenciais nem dados de demonstração. A migração cria tabelas e um perfil Comercial; não concede novos acessos automaticamente aos colaboradores existentes.

## CRM
Cadastro e edição de leads, funil com sete etapas, carteira por responsável, cidade livre (Foz, Teixeira ou outra), empresa, contato, ramo, produto, orçamento, notas e atividades. O perfil pessoal mostra a carteira atribuída, respeitando permissões. Supervisores podem visualizar a fila sem responsável e reatribuir contatos.

Conversão em cliente copia os dados para o cadastro existente de Clientes, preserva o vínculo e o histórico do lead e evita repetir a conversão. Se o nome já existir, exige escolher o cliente existente. Criar reuniões pelo lead grava um compromisso na agenda e vincula sua atividade. É possível colar um link Google Meet existente; criação automática de links Meet ainda não foi implementada.

O chat do lead envia texto pela WhatsApp Cloud API quando configurada. Novos leads automáticos exigem webhook assinado com referral.source_type=ad e source_id do anúncio. Contatos novos sem essa origem são ignorados. Mensagens de um contato já cadastrado manualmente são vinculadas ao lead existente. Duplicatas de webhook são descartadas pelo identificador externo.

Somente o responsável com acesso CRM e permissão comercial de resposta pode enviar. Supervisão não autoriza responder pela carteira de outro usuário: reatribua primeiro. Respostas são limitadas à janela de 24 horas desde a mensagem recebida. Templates fora dessa janela, anexos, áudios e mídias no chat comercial ainda não estão implementados; mídias recebidas aparecem como aviso textual. O histórico mostra até 200 mensagens recentes. O banco mantém os registros anteriores.

## Financeiro
Cadastro de cobranças/faturas por Itaú, Cora ou InfinitePay, referência única por banco, pagador, cliente vinculado, valor, vencimento e situação. Filtros por banco, status e datas; indicadores de cobranças abertas, vencidas e registradas como pagas; gráficos por banco e mês. Não são saldos bancários e não representam conciliação de extrato.

PDFs até 8 MB podem ser anexados e baixados com autorização. Situação manual não movimenta dinheiro. Não existem endpoints de pagamento, transferência, liquidação ou emissão de cobrança bancária.

Cora: adaptador de consulta com mTLS e token client credentials, listagem por vencimento em páginas de 20, consulta detalhada e atualização dos registros da API. O usuário consulta uma página por vez; a resposta informa quando continuar. A consulta de PDF obtém o endereço do documento da resposta autenticada do banco, após checar permissão de download. O documento abre no provedor para visualizar e salvar. O sistema não copia automaticamente o PDF remoto para o banco local. Registros stage têm prefixo stage: e são excluídos dos indicadores/listagem de produção.

Itaú e InfinitePay: cadastro manual e PDFs funcionam. Não há sincronização geral implementada: Itaú requer acesso à API contratada da conta; a API pública InfinitePay consultada é de checkout e não comprova acesso geral às faturas/boletos. Não foram criadas conexões fictícias. Esses conectores precisam da documentação e da habilitação correspondentes antes do desenvolvimento final.

## Contratos
Título, cliente, responsável, início, vencimento, data de renovação, valor, notas, situação e PDFs. Editar/renovar atualiza o cadastro e registra auditoria; PDFs anexados permanecem disponíveis. Não há assinatura eletrônica nem geração jurídica automática.

O scheduler envia lembretes em 30, 15, 7 e 1 dia e no vencimento, tanto para vencimento quanto renovação. Após interrupção do processo, usa o marco mais próximo, sem enviar todos os anteriores. Lembretes são deduplicados por contrato/data/marco/usuário; alterar a data habilita os lembretes para o novo prazo. Somente pessoas ativas com acesso à carteira recebem avisos.

## Meta
Rascunhos de publicações, revisão e envio imediato para Facebook (texto ou imagem) e Instagram (imagem com legenda), usando contas definidas no ambiente do servidor. Imagens precisam de URL pública HTTPS. Não há upload de mídia, Reels, carrossel ou agendamento automático nesta versão.

Consulta das primeiras 100 campanhas da conta de anúncios configurada e ações de pausar/ativar. Ativação exige confirmação explícita na interface porque pode retomar gastos. Não há criação de campanhas, edição de orçamento ou relatórios de desempenho nesta versão.

Envios externos têm estados de confirmação. Falhas ambíguas não repetem automaticamente publicação/mensagem; confira no provedor antes de criar novo envio. Não existe OAuth Meta pela interface: administrador configura os tokens no servidor e faz a rotação quando necessário.

## Permissões
Configure na tela Equipe / perfis de acesso e atribua o perfil ao usuário. Pode criar um perfil específico para uma pessoa. Master mantém o acesso administrativo existente.

- CRM: acessar, editar, responder como comercial, atribuir, supervisionar toda carteira e converter são permissões distintas. Converter também exige Clientes e Gerenciar clientes.
- Financeiro: visualizar, cadastrar/importar e baixar PDFs são distintos; cada banco exige sua própria permissão. Integrações + financeiro + gerenciar financeiro + Cora são necessárias para consultar/sincronizar a Cora.
- Contratos: acessar, editar, supervisionar toda carteira e baixar PDFs são distintos. Sem supervisão, cada usuário vê apenas os contratos atribuídos a ele.
- Meta: visualizar e publicar/alterar campanhas são separados. A permissão Meta dá acesso à conta empresarial única configurada neste servidor; não há múltiplas contas com ACL individual nesta versão.
- Administrar integrações é separado dos módulos. Tokens nunca são retornados nos status. Documentos são armazenados em tabela privada, sem rota pública de arquivos.

## Configurar provedores
Variáveis estão em .env.example e configuracao-local.bat.example. O iniciador Windows utiliza configuracao-local.bat. Linux/Docker deve carregar as variáveis no ambiente conforme a instalação existente; o app não lê .env sozinho.

Cora: solicite Client ID, certificado e chave para Integração Direta; configure CORA_CLIENT_ID, CORA_CERT_PATH, CORA_KEY_PATH e CORA_ENV=stage. Os caminhos devem existir no servidor. Valide com credenciais de testes antes de usar CORA_ENV=production e os certificados de produção. Consulte Integrações > Cora e informe intervalo de vencimento/página.

Meta: configure META_GRAPH_VERSION com versão habilitada no app Meta, META_ACCESS_TOKEN com permissões de Instagram/anúncios necessárias, META_PAGE_ACCESS_TOKEN com token da Página, META_PAGE_ID, META_INSTAGRAM_ID e META_AD_ACCOUNT_ID no formato act_ID. O app Meta, as permissões e o acesso às contas precisam estar habilitados pelo provedor. Estado “credenciais configuradas” não atesta que o token é válido.

WhatsApp: configure WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_VERIFY_TOKEN e META_APP_SECRET, além de META_GRAPH_VERSION. Publique o servidor com HTTPS antes de registrar o webhook /webhooks/whatsapp no aplicativo Meta e assinar eventos de mensagens. Selecione o responsável padrão em Integrações. O responsável precisa das permissões CRM + Comercial: responder WhatsApp. Sem responsável válido, o lead fica na fila visível à supervisão.

Mantenha scheduler.py ativo para os lembretes. Push fora do aplicativo depende também da configuração push existente e autorização do dispositivo.

## Atualizar sem perder os dados
1. Encerre servidor e scheduler e faça backup da pasta data inteira, incluindo banco, uploads e integration.key, ou do caminho configurado em NJA_DATA.
2. Substitua os arquivos de código pelo pacote, preservando data, credenciais e configuracao-local.bat.
3. Inicie normalmente. A migração é aditiva e executada na inicialização.
4. Entre como master, ajuste os perfis de acesso e teste com um usuário comercial e um financeiro antes de liberar à equipe.

## Verificação
Validação: 58 testes anteriores e 11 novos testes empresariais aprovados; migração 1.7 → 1.8 testada com preservação de cadastro e execução repetida. Testes de API cobrem isolamento de carteira, atribuição, conversão idempotente, duplicidade de cliente, criação de evento, CSRF, valores monetários, bancos e PDFs, lembretes, assinatura/origem/deduplicação de webhook, janela de atendimento, controle de repetição, consulta Cora e publicação Meta. Chamadas externas foram simuladas, sem credenciais ou operações reais. Testes JavaScript verificam renderização estrutural, escape de texto, navegação por permissões e exclusão dos dados stage.

Não foi feita nova validação visual em navegador nesta atualização, pois o recurso de navegador exigido pelo ambiente não estava disponível. Validação visual em aparelhos e homologação com contas reais permanecem pendentes.

## Referências técnicas consultadas
- https://developers.cora.com.br/docs/client-credentials-int-direta
- https://developers.cora.com.br/docs/utilização-das-apis
- https://developers.cora.com.br/reference/consultar-boletos-v2
- https://developers.cora.com.br/reference/consultar-detalhes-de-um-boleto-v2
- https://developers.cora.com.br/reference/emissão-de-boleto-registrado-v2 (estrutura BankSlip; emissão NÃO implementada)
- https://devportal.itau.com.br/conheca-o-portal
- https://www.infinitepay.io/checkout-documentacao
- https://developers.facebook.com/documentation/instagram-platform/content-publishing
- https://developers.facebook.com/docs/pages-api/posts/
- https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components
- https://developers.facebook.com/docs/marketing-api/reference/ad-campaign-group/
Algumas páginas Meta limitaram a leitura automatizada. Os adaptadores precisam de homologação com o app/versão real antes do uso de produção.
