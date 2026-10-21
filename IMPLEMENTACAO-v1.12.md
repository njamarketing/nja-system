# NJA 1.12 — Operação da agência

Estado: implementação local validada por testes automatizados; **não publicada e não homologada com contas externas reais**. Este pacote não significa que todas as integrações estejam ativas. Nenhum dado de produção, credencial ou conta fictícia está incluído.

## 1. Acesso e continuidade

- Carteira explícita por cliente, unidade e equipe. Foz do Iguaçu, Teixeira de Freitas e Cascavel.
- Acesso a um módulo não libera todos os clientes. Tarefas, conversas, documentos, portal, produção e novos relatórios reaplicam o escopo no servidor.
- Permissões novas não são concedidas automaticamente aos perfis existentes. O master configura os perfis.
- Migração conserva vínculos explícitos anteriores. Clientes antigos sem unidade aparecem como pendência em Saúde do sistema.
- Notificações e push reaplicam o acesso ao recurso; atribuição de tarefas de cliente exige equipe autorizada.
- Saúde do sistema: sessões ativas, revogação, execução do scheduler, backup manual e diário quando configurado.
- Backup usa snapshot SQLite, verifica integridade e inclui uploads e chave local de criptografia. Configure destino externo separado, acesso restrito e política de retenção. Não há exclusão automática de backups.

## 2. Produção

- Pacotes configuráveis: serviços, quantidades, responsáveis, estimativas, dia/horário, vigência e limite de revisões opcional.
- Geração mensal manual ou automática do mês atual, sem duplicar pacote/competência. Meses anteriores perdidos são gerados manualmente.
- Projetos conservam o retrato do pacote usado. Alterar pacote afeta gerações futuras.
- Prazos no último dia válido quando o mês é mais curto. Horário explicitado no formulário; fuso da instalação.
- Dependências com bloqueio de ciclos e de conclusão antes das predecessoras.
- Extras identificados e rodadas de revisão contabilizadas. Excesso avisa para revisar o escopo; não cobra valores nem bloqueia atendimento automaticamente.
- Mensalidade visível somente com acesso financeiro; edição exige gestão financeira.

## 3. Aprovações e portal

- Versões imutáveis de texto/legenda e até dez arquivos de tarefas do mesmo cliente. SHA-256 do conteúdo e histórico.
- Comentários, posição na imagem e segundo do vídeo; decisão vinculada à versão. Arquivos do carrossel seguem a ordem da lista de seleção.
- Nova versão volta para revisão. Decisões antigas permanecem no histórico.
- A equipe com permissão de aprovação também pode aprovar; a identificação distingue equipe e contato do cliente. Não exige aprovação exclusivamente externa.
- Portal separado em `/portal.html`, contatos por cliente, convite de uso único por 48 horas, senha própria e sessão independente.
- Compartilhamento explícito de materiais e PDFs; contato pode comentar ou aprovar conforme autorização. Desativação encerra sessões.
- Projetos exibem progresso sem custos ou conversas internas. Upload de materiais do cliente: até 8 MB. Vídeos compartilhados usam download protegido; o navegador ainda carrega o arquivo para visualização.
- Convite retorna link para a equipe compartilhar. Não envia e-mail automaticamente. Recuperação do portal por novo convite.

## 4. Editorial e Google Calendar

- Planejamento por mês/cliente, contas Meta por cliente, tokens criptografados, verificação e desativação de contas.
- Facebook: texto e imagem. Instagram: imagem JPEG, Reel MP4 e carrossel de 2–10 JPEGs. Outros formatos não estão implementados.
- Agendamento usa arquivos e legenda da versão aprovada. Exige conta verificada, data futura e HTTPS público para mídia. A Meta pode rejeitar mídia por dimensões, duração ou outras condições da conta.
- O scheduler verifica novamente aprovação, carteira, permissões e conta antes de enviar. Nova versão bloqueia o agendamento anterior.
- Preparação de mídia e consulta de processamento do Instagram. Links temporários com segredo aleatório permitem que a Meta obtenha os arquivos autorizados.
- Envio ambíguo não é repetido: estado **Conferir na Meta**. Conferir externamente antes de criar novo agendamento. Cancelar no sistema não remove conteúdo já publicado.
- Meta Ads por cliente: consulta paginada de campanhas, criação pausada com objetivo/categorias/orçamento definidos pelo gestor, alteração de estado e orçamento, indicadores por período. Criação/edição de orçamento limitada a contas BRL. Indicadores retornam até 100 linhas e avisam quando há mais resultados. Conjuntos, segmentação e criativos são finalizados no Gerenciador da Meta; não há criador completo de anúncios nesta versão.
- WhatsApp: histórico paginado, download de mídia recebida até 8 MB, upload/envio de JPEG/PNG (5 MB), MP4/PDF (8 MB) na janela de atendimento. Templates aprovados com corpo/rodapé e parâmetros numéricos são consultados e enviados com confirmação explícita; cabeçalhos, botões e parâmetros nomeados não são suportados. `WHATSAPP_BUSINESS_ID` é necessário para consultar templates. Upload fica vinculado ao lead e vendedor. Somente o comercial responsável envia; respostas ambíguas não são reenviadas automaticamente.
- Conexão Google Calendar separada do Drive. Criação de evento na agenda principal e link Meet com ID estável para prevenir duplicidade em tentativas repetidas.
- Apenas o criador do compromisso cria o vínculo. Sem recorrência, convites por e-mail ou sincronização bidirecional nesta versão. Alterações/exclusão locais não alteram automaticamente o Google.
- Google pode retornar conferência em processamento; use Consultar estado. Disponibilidade do Meet depende da conta Google.

## 5. Comercial

- Propostas com itens, quantidades, valores, condições, validade e versões. Impressão/salvar PDF pelo navegador.
- Registro interno de envio, aceite, recusa e vencimento com evidência. Não é assinatura eletrônica. Nenhuma mensagem enviada ao marcar como enviada.
- Proposta aceita/recusada fica encerrada; outra negociação usa nova proposta. Não gera contrato ou receita automaticamente.
- Retornos comerciais com lembrete no sistema para o responsável atual pelo lead; conclusão manual.
- Metas por mês/unidade/vendedor, valor ou quantidade de vendas confirmadas. Resultados limitados à carteira visível.
- Comissão com regra explicitamente aplicada à venda: percentual, vigência, unidade e base (venda ou recebimento registrado).
- A regra aplicada fica congelada. Venda cancelada zera a comissão calculada. Recebimentos são registrados com referência única, limite do valor vendido e acesso financeiro.
- Comissões não efetuam pagamento e não geram lançamentos no razão automaticamente.

## 6. Gestão financeira e resultados

- Lançamentos gerenciais de receitas/despesas por unidade, cliente e projeto, competência, data de caixa e referência única.
- Correções por anulação com motivo e novo lançamento. Histórico preservado.
- Custo-hora por pessoa/vigência e capacidade mensal configurável.
- Relatórios por competência e cliente: entregas, atrasos, extras, horas, capacidade e, quando autorizado, receitas/despesas/caixa/margem.
- Margem parcial = receitas cadastradas − despesas cadastradas − horas apontadas × custo-hora vigente. Sem rateio automático. Horas sem taxa são sinalizadas; tempo não apontado não é estimado.
- Custos da equipe incluídos no custo-hora não devem ser lançados novamente como despesa. Mensalidades previstas são separadas de receitas registradas; boletos também não são contabilizados automaticamente.
- Exportação CSV com neutralização de fórmulas em campos de texto.
- Estes relatórios são gerenciais, não uma DRE fiscal ou apuração contábil.

## Permissões principais

Configure em Perfis, além das permissões existentes. Cadastre os clientes e equipes antes de distribuir tarefas.

| Área | Consultar | Gerenciar |
|---|---|---|
| Carteiras | `client_scope_manage` | mesma permissão; exige acesso ao cliente |
| Escopo ampliado | `client_unit_all` ou `client_company_all` | não substitui permissão do módulo |
| Produção | `production` | `production_manage`; responsáveis precisam de tarefas e acesso ao cliente |
| Aprovações | `approvals` | `approval_manage`; portal exige `portal_manage` |
| Editorial | `editorial` | `editorial_manage`; contas exigem `integrations_manage` |
| Comercial | `commercial_ops` e `crm` | `crm_edit`; regras/metas exigem `commercial_manage` |
| Gestão financeira | `agency_finance` | `agency_finance_manage` |
| Relatórios | `agency_reports` | valores exigem também `agency_finance` |
| Saúde | `operations` | acesso administrativo amplo |

Conceda `clients` aos usuários que precisam selecionar clientes nos formulários. Mantenha permissões administrativas apenas para gestores autorizados. A área Meta legada usa contas globais e agora exige `client_company_all`; use Editorial para contas por cliente.

## Instalação e homologação pendentes

1. Backup da instalação existente e das variáveis de ambiente; preservar `NJA_DATA`, uploads e chave de criptografia. Pare web/scheduler durante a atualização e substitua só os arquivos do programa. A inicialização migra o banco.
2. HTTPS, cookies seguros, volume persistente e scheduler ativo. Hospedagem precisa executar Python/WSGI e processo periódico/contínuo. Não basta enviar arquivos para hospedagem apenas PHP.
3. Backup: `NJA_BACKUP_DIR` deve apontar a um diretório externo montado e gravável pelo serviço. No Docker, monte explicitamente esse destino nos dois serviços; o compose básico só inclui os dados da aplicação.
4. Meta: configurar `META_GRAPH_VERSION` e cadastrar credencial autorizada/ID de cada conta. Verificação de ID não prova que todas as permissões de publicação foram aprovadas; homologar publicação em conta de teste antes de agenda real.
5. Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, opcional `GOOGLE_WORKSPACE_DOMAIN`. Registrar a URL de retorno `https://SEU-DOMINIO/api/agency/calendar/callback`. Autorizar pela própria agenda no sistema. Escopo `calendar.events.owned` e e-mail verificado.
6. Cora e WhatsApp mantêm requisitos do guia 1.8. Itaú/InfinitePay dependem de documentação e habilitação específicas; não foram conectados.
7. Testar com dois perfis internos e dois clientes, revisar dados migrados, testar recuperação do backup, homologar contas externas e validar navegador/celular.

## Validação realizada

- 100 testes Python passaram na execução completa, cobrindo módulos anteriores e novos fluxos de acesso, produção, revisão, portal, publicação sem duplicidade, comissões, margem e Meet.
- Oito suítes JavaScript passaram, incluindo renderização/escape e permissões dos novos módulos; sintaxe dos scripts conferida.
- Os testes específicos incluem escopo de mídia do WhatsApp, paginação sem repetição, envio idempotente de templates, criação pausada de campanhas e bloqueio de campanhas de outra conta.
- Chamadas externas foram simuladas nos testes. Não houve publicação real, conexão bancária real, teste visual em navegador ou validação em dispositivos nesta sessão.
- Animações do Ninja 1.11 preservadas; não foram produzidos novos desenhos nesta atualização.

## Referências de fluxo e API

- Asana, aprovações: https://help.asana.com/s/article/approvals
- Filestage, revisão de versões: https://help.filestage.io/
- Meta, coleção oficial Instagram: https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api
- Meta, WhatsApp oficial: https://www.postman.com/meta/whatsapp-business-platform/
- Meta, Marketing API oficial: https://www.postman.com/meta/facebook-marketing-api/
- Google Calendar, eventos/Meet: https://developers.google.com/workspace/calendar/api/guides/create-events
- Google Calendar, escopos: https://developers.google.com/workspace/calendar/api/auth

Referências orientam os padrões de fluxo; identidade e interface são próprias da NJA. Consulte a documentação vigente da conta antes da homologação.
