# Atualização 1.17

Chat flutuante com presença e chamadas, respostas e reações, marca lateral com contorno, espectadores privados de stories, comemoração de vendas, menu de movimentos do Ninja e campo da IA ampliado. Checklist: `IMPLEMENTACAO-v1.17.md`. Atualização preservando os dados da VPS: `GUIA-ATUALIZACAO-VPS-v1.17.md` e `ATUALIZAR-NJA.sh`.

# Atualização 1.16

Google Drive com Lista/Miniaturas, prévias privadas e correção da pasta inicial vazia. Instalação na VPS existente: `IMPLEMENTACAO-v1.16.md` e `ATUALIZAR-DRIVE.sh`. Preserve as configurações e o DNS da instalação.

# Atualização 1.15

Chats responsivos, fotos em modal, controles master de usuários, kit de marca, respostas a stories e edição/respostas no feed. Consulte `IMPLEMENTACAO-v1.15.md` para uso, instalação e limites dos testes de chamadas em grupo.

# Atualização 1.14

Chat de atendimento no portal, com o mesmo login do cliente. Uso, permissões e atualização em `IMPLEMENTACAO-v1.14.md`.

# Atualização 1.13

Menu mobile com botão Fechar, comentários maiores e barra de emojis/menções. Consulte `IMPLEMENTACAO-v1.13.md`.

# Atualização 1.12

Gestão da agência: carteiras, produção mensal, aprovações/portal, editorial, propostas, metas, comissões e relatórios. Implementação local, ainda não publicada. Consulte `IMPLEMENTACAO-v1.12.md` para uso, migração e permissões; `PROXIMAS-ETAPAS.md` registra bloqueios e funções ainda pendentes.

# Atualização 1.11

Movimento com imagens intermediárias e reprodução a 60 fps; preparação e fumaça do jutsu revisadas. Veja `IMPLEMENTACAO-v1.11.md`.

# Atualização 1.10

Tutorial, grupos com permissões, ranking comercial, unidade Cascavel e nova tela de carregamento. Veja `IMPLEMENTACAO-v1.10.md`.

# Atualização 1.9

Novo ninja com 12 frames de caminhada, braços cruzados, notebook, cambalhotas, saltos e jutsu com fumaça. Checklist e instruções: `IMPLEMENTACAO-v1.9.md`. Laboratório: `/ninja-lab.html` no servidor do NJA.

# Atualização 1.8

CRM, financeiro, contratos e conectores empresariais: consulte `IMPLEMENTACAO-v1.8.md` para uso, permissões, configuração e limites. Itaú e InfinitePay têm controle manual; a sincronização geral ainda está pendente. Faça backup da pasta de dados antes de atualizar.

# Atualização 1.7

Veja `IMPLEMENTACAO-v1.7.md` para o novo ninja, chat, clima e lembretes. Consulte `PROXIMAS-ETAPAS.md` para Meta, financeiro, contratos e CRM ainda pendentes.

# Atualização 1.6

Veja `IMPLEMENTACAO-v1.6.md` para fontes, calendário e mini ninja. As instruções de hospedagem/integrações da versão 1.5 continuam válidas.

# NJA System — Sistema do Ninja

Versão 1.5 funcional para a NJA Consultoria & Marketing. Aplicação web PWA com backend Python, banco SQLite e frontend próprio em português. Não foi publicada. Não há contas, tarefas ou resultados fictícios no banco entregue. A marca NJA System utiliza o símbolo oficial enviado, com a tipografia original da interface. A assinatura “Desenvolvido por NJA” usa a logo institucional original. A paleta utiliza azul e ciano da identidade da NJA. Os arquivos originais são preservados, sem redesenho da logo.

## Testar no seu computador

**Windows:** instale Python 3.12 ou superior, extraia o ZIP e execute `iniciar-windows.bat`. O iniciador instala Pillow, tzdata e cryptography, incluindo os fusos horarios exigidos no Windows. O iniciador verifica Python, conserva as mensagens de erro e espera o servidor responder antes de abrir o navegador. Se ocorrer erro, envie uma foto da janela aberta. No primeiro acesso, escolha o e-mail do master e sua senha (mínimo 10 caracteres). O arquivo abre `http://localhost:8000`. Se a página abrir antes do servidor, atualize-a. Mantenha abertas as janelas do servidor e de alertas. O modo local não fica acessível pela internet e não instala em outros celulares.

**Linux/macOS:**

```bash
cd nja-system
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py init-master --email SEU_EMAIL --name "Nelson Zeni Junior"
python app.py
```

Em outro terminal, com o mesmo ambiente virtual ativado:

```bash
python scheduler.py
```

Acesse `http://localhost:8000`. Não existe senha padrão. O master é criado interativamente e as senhas nunca são incluídas no pacote. Na tela Equipe, cadastre os integrantes e distribua os acessos. Cada pessoa altera sua senha em Configurações.

## Funções entregues

- Login individual, cookies HttpOnly, sessões de 24 horas, senhas scrypt, limite de tentativas, proteção CSRF e controle de origem.
- Master, criação/edição/desativação da equipe, função, área, descrição, avatar e perfis com permissões personalizadas. E-mail de uma conta existente é imutável nesta versão.
- Tarefas com responsável, participantes, cliente/projeto, prioridade, início, prazo, subtarefas, checklist, comentários e anexos. Lista e Kanban com mudança por arrastar no computador ou pelos botões nos detalhes, no celular.
- Estados pendente, em andamento, em aprovação e concluída. Atraso derivado do prazo, sem alterar o estado. Concluir uma tarefa em aprovação exige a permissão de aprovação.
- Calendário mensal, semanal e diário, participantes, agenda individual e compartilhada. Recorrência diária, semanal e mensal com data limite. Nas recorrências mensais, dias 29–31 são ajustados ao último dia de cada mês.
- Edição de título, descrição, local e horário dos compromissos; cancelamento de toda a série. Edição de participantes, regra recorrente e lembrete após criação ainda não está disponível: cancele e recrie o compromisso. Não há edição de uma ocorrência isolada.
- Central de notificações. Alertas do servidor para compromissos, tarefas próximas do prazo (24h), atrasos, atribuições, comentários e mensagens.
- Chat individual, grupos e grupo geral. Administração de participantes, indicação de mensagens não lidas, imagens e PDFs. Eventos SSE atualizam clientes conectados aproximadamente a cada 5 segundos; gravação da mensagem é confirmada antes de limpar o campo. Cada conversa mostra as últimas 200 mensagens, mantendo o histórico completo no banco. Paginação de conversas longas ainda não está implementada.
- Indicadores reais por 7, 30 ou 90 dias. Master vê toda a equipe; demais veem os próprios indicadores. Base: tarefas criadas no período e atualmente atribuídas ao usuário; percentual = tarefas atualmente concluídas / total dessa base. Alterar responsável muda a atribuição da métrica.
- Histórico de ações administrativas e da tarefa; manifesto, ícones, service worker e página offline.

Clientes possuem cadastro próprio com produto, entrada e onboarding. Nas tarefas, o campo projeto continua textual; não há pipeline de vendas.

## Arquitetura e segurança

`app.py` expõe API WSGI e os arquivos estáticos. `wsgi.py` inicializa o esquema e exporta a aplicação para Gunicorn. `scheduler.py` processa lembretes e fila push independentemente das abas abertas. `manage.py` cria o master, redefine senha e realiza backup. `static/` contém o frontend, PWA e ícones. `tests/` contém os testes de integração.

Dados ficam em `data/nja.sqlite3` e `data/uploads/`, ou em `NJA_DATA`. Configure um volume persistente. SQLite usa WAL e chaves estrangeiras. O servidor aplica as permissões a cada operação e download: ocultar menus não é o mecanismo de segurança.

Equipe: colaboradores comuns veem os nomes, fotos, cargos, áreas e descrições dos usuários ativos. Dados administrativos e indicadores completos são restritos. Usuários desativados perdem acesso imediatamente. Permissões `user_manage` e `role_manage` são privilégios administrativos amplos: conceda apenas a pessoas de confiança.

Materiais das tarefas/chats: imagens JPEG, PNG, WebP e GIF; PDF; documentos DOC/DOCX, XLS/XLSX, PPT/PPTX, ODT/ODS/ODP, TXT/CSV; vídeos MP4/M4V, MOV e WebM. Limite de 100 MB por material, com envio binário em blocos para o armazenamento e conferência do formato/contêiner. Fotos de perfil/capa e mensagens de áudio mantêm o limite de 8 MB. Foto de perfil é decodificada, reduzida e regravada, removendo metadados. PDFs são baixados como anexos. Arquivos nunca são disponibilizados por uma pasta pública. Não há antivírus nem análise de conteúdo dos documentos: para arquivos não confiáveis, integre varredura antes de ampliar a operação.

O cache offline inclui apenas a interface pública. Dados de contas, tarefas, chats e arquivos não são armazenados no cache do service worker. Offline não permite operar ou enfileirar alterações. A interface informa perda de conexão; somente respostas bem-sucedidas do servidor confirmam a gravação. Depois de recarregar offline, é mostrada a tela de acesso, sem dados privados.

## Hospedagem com Docker

Esta versão usa Python e não é compatível diretamente com hospedagem estática, PHP puro ou o runtime Cloudflare Workers do Sites. Precisa de servidor com suporte a Python, volume persistente e dois processos (web e scheduler).

1. Copie `.env.example` para `.env`, definindo `NJA_ORIGIN=https://SEU_DOMINIO`. Não deixe a origem localhost em produção. Mantenha `NJA_DATA=/var/lib/nja` para Docker.
2. Execute `docker compose build`.
3. Crie o master: `docker compose run --rm web python manage.py init-master --email SEU_EMAIL`.
4. Execute `docker compose up -d`.
5. Configure proxy reverso Caddy ou Nginx com HTTPS encaminhando para `127.0.0.1:8000`. No Nginx, desative buffering na rota `/api/stream`, ajuste `proxy_read_timeout` para 130s e `client_max_body_size` para 120m. Restrinja o acesso direto à porta de backend.
6. Confira os logs de web e scheduler. Cadastre dois usuários e valide os fluxos reais em dois dispositivos antes de colocar a equipe em operação.

A imagem usa usuário sem privilégios. Os contêineres compartilham o volume do banco e anexos. Rode apenas **um scheduler** para esta implantação. O servidor `python app.py` é apenas para desenvolvimento; Gunicorn serve em produção. A arquitetura atende uma primeira operação de equipe; grandes volumes e muitos clientes SSE devem migrar para PostgreSQL e um serviço de eventos dedicado.

Não publique `data/`, `.env`, chaves privadas ou backups. Nada desses arquivos é incluído no pacote entregue.

## Recuperação de senha por e-mail

Configure `SMTP_HOST`, `SMTP_PORT` (padrão 587), `SMTP_FROM`, `SMTP_USER` e `SMTP_PASSWORD`. Utiliza STARTTLS e envia link com validade de 30 minutos. Tokens são armazenados como hash e só podem ser usados uma vez. Redefinir senha encerra as sessões. Sem SMTP, a interface informa que a recuperação está pendente; o administrador pode redefinir pela tela de equipe ou por `python manage.py reset-password --email EMAIL`.

Em implantação manual, variáveis precisam ser exportadas no ambiente. Python não lê `.env` automaticamente. O Docker Compose lê `.env` por `env_file`.

## Alertas push e celular

1. Instale as dependências de `requirements.txt`.
2. Execute `python generate_push_keys.py`. Copie os valores para o ambiente do servidor e scheduler: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` e `VAPID_SUBJECT=mailto:SEU_EMAIL`. Guarde a chave privada com cuidado.
3. Reinicie os processos. O scheduler verifica lembretes a cada 30 segundos e envia push por assinatura, com tentativas posteriores para falhas temporárias. Assinaturas expiradas são removidas. A central interna continua funcionando sem VAPID.
4. No Android, abra no Chrome e use Instalar aplicativo/Adicionar à tela inicial. No iPhone, abra no Safari, Compartilhar → Adicionar à Tela de Início; abra pelo ícone.
5. Em Configurações do NJA System, toque em Ativar alertas neste dispositivo. iPhone: iOS 16.4+ e app na Tela de Início. HTTPS é necessário fora de localhost.

O usuário controla as permissões; conexão, Foco, economia de energia e decisões do sistema operacional podem adiar ou impedir entregas. Não há garantia de entrega no horário exato. O lembrete não depende de uma aba aberta, mas o servidor e scheduler devem permanecer funcionando. Requisições push usam apenas provedores de navegador permitidos; outros provedores exigem revisão da lista no backend.

Fontes oficiais consultadas: https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/ e https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers.

## Backup e restauração

Execute diariamente, por tarefa do servidor, `python manage.py backup --output /CAMINHO_SEGURO/backup-DATA`. O diretório de saída deve ser novo. Em Docker: `docker compose exec web python manage.py backup` cria em `/var/lib/nja/backups/`, mas copie depois para armazenamento externo; o mesmo disco não é uma cópia independente. O backup usa a API SQLite de snapshot e copia anexos imutáveis. Proteja backups com criptografia e acesso restrito. Defina retenção e teste restauração periodicamente.

Para restaurar: pare web e scheduler; preserve uma cópia da situação atual; substitua `nja.sqlite3` e `uploads/` pelas cópias do mesmo backup; remova arquivos WAL/SHM antigos somente com os processos parados; ajuste propriedade do volume; reinicie e confirme usuários, tarefas e arquivos. Sessões presentes no backup podem ser revogadas com `DELETE FROM sessions` em manutenção para exigir novo login.

## Custos e configuração externa

- Código entregue sem assinatura ou licença paga obrigatória.
- Necessários para acesso externo: hospedagem compatível, domínio/endereço e HTTPS. Custos dependem do provedor escolhido; nenhum serviço foi contratado.
- Recuperação por e-mail depende de serviço SMTP, com limite/custo do provedor.
- Push utiliza os serviços do navegador e suas chaves VAPID; não foi integrada uma plataforma de notificações paga.
- Backup externo, monitoramento e eventual antivírus dependem da infraestrutura escolhida.

## Validação e limites desta entrega

28 testes de integração passaram, incluindo os novos recursos sociais, além de: autenticação, hash de senha, CSRF, origem, permissões, isolamento de tarefas/chats/calendário/arquivos, desativação, perfis personalizados, aprovação, comentários, subtarefas, métricas, persistência, redefinição de senha e lembretes sem duplicação. Verificação de sintaxe Python e JavaScript passou. Os testes estruturais do frontend também passaram: sete telas, lista/Kanban, três visões da agenda, escape de conteúdo HTML e expansão de recorrências.

Houve validação de interações em Chromium automatizado, com dimensões de computador e celular. Não houve testes físicos de instalação Android/iPhone. SMTP e push não foram enviados a serviços reais porque exigem configurações da hospedagem. Antes de uso em produção, valide HTTPS, e-mails, inscrições push, retorno após reinício, backup/restauração e interação móvel com as configurações reais. O pacote é a primeira versão funcional; a ativação operacional ainda depende desses passos.

## Versão 1.1 — chats, perfis e login NJA

- Login em duas etapas (e-mail, depois senha), com cartão sobre fundo escuro, ninja em pose de lançamento e shurikens animados. A animação respeita a preferência de redução de movimento do dispositivo.
- Conversas com busca, filtro de não lidas e fotos dos grupos/clientes. Para definir a imagem: abra a conversa, clique em Informações e, como administrador de grupos, em Alterar imagem.
- Em Editar grupo, preencha Cliente / projeto com o mesmo nome do projeto das tarefas para exibir as tarefas correspondentes no painel. Os participantes continuam sujeitos às permissões do servidor.
- Informações da conversa mostram participantes, arquivos e imagens, tarefas e links compartilhados. Imagens anexadas têm prévia no chat.
- Clique no nome de um participante ou integrante da equipe para abrir o perfil. Abas: Perfil, Tarefas, Calendário e Atividades (quando autorizadas). Cada usuário pode alterar sua foto e capa.
- Formulários e detalhes abrem em painel pela direita; no celular, ocupam a tela inteira. Escape e clique no fundo fecham o painel.
- O ZIP não contém banco de dados, senhas, anexos ou usuários de demonstração. Para iniciar uma nova configuração, extraia em uma nova pasta e execute iniciar-windows.bat. Crie sua conta master quando solicitado.
- Chamadas de voz/vídeo, login por QR ou redes sociais, reações/favoritos e exclusão automática de mensagens não foram adicionados nesta versão.
- Validação: 18 testes de integração e verificações estruturais da interface. A instalação e o push em Android/iPhone continuam exigindo validação após configurar HTTPS. A renderização em navegadores e aparelhos reais deve ser conferida durante a instalação.

Arte de login: criada com a ferramenta de geração de imagem usando os dois ninjas enviados como referência. Prompt: preservar o ninja 3D preto com olhos azuis, criar pose de lançamento de uma shuriken, corpo inteiro sobre fundo transparente, sem texto ou cenário. Arquivo integrado: static/ninja-throw.png. O movimento do ninja e das shurikens é produzido por CSS, sem serviços externos.


## Versão 1.2 — perfis sociais, clientes e chats interativos

### Perfil e horas

Abra Meu perfil ou clique no nome de alguém da equipe. O titular pode editar nome, aniversário, pensamento, biografia, contratação, e-mail corporativo, cargo e histórico de funções/promoções. Foto e capa podem ser trocadas pelo editor. O e-mail corporativo exibido é separado do e-mail de login. Administradores mantêm os controles de acesso da equipe.

O status online depende de atividade da sessão em aba visível, com atualização a cada 30 segundos e tolerância de aproximadamente 75 segundos. O perfil também mostra o último acesso.

Nos detalhes de uma tarefa, use o cronômetro ou registre minutos manualmente. Há um cronômetro ativo por usuário. Concluir a tarefa encerra seus cronômetros. As horas mensais somam o tempo registrado por cada pessoa nas tarefas concluídas no mês atual, no fuso de São Paulo, mesmo quando parte do esforço foi registrada antes desse mês. Reabrir a tarefa retira suas horas dessa soma até nova conclusão. O cálculo não mede tempo de login nem substitui controle de ponto.

### Clientes e conversas

Em Clientes, cadastre nome, data de entrada, produto contratado e checklist de onboarding. Abra o cliente para editar o checklist e enviar marca e capa. Nas informações de um grupo, selecione o cliente e aplique o vínculo para usar sua identidade na conversa. A gestão depende da permissão de gerenciar clientes/grupos.

O chat oferece seletor de oito emojis com animação, reações e janela flutuante. Use o botão de expandir/flutuar no cabeçalho; arraste pelo topo, minimize ou feche. Uma janela flutuante pode ficar aberta enquanto você navega em outras páginas. A aparência dos emojis segue o sistema operacional. Botões principais têm o símbolo ninja e efeitos de mouse; a preferência de redução de movimento é respeitada.

### Feed e histórias

Em Feed, publique foto, texto ou pensamento, curta e comente. O autor pode excluir suas publicações; o master também pode moderar. O feed carrega as 100 publicações mais recentes.

Publique histórias e abra-as pelos avatares destacados. Cada história fica visível por 24 horas após a publicação. O servidor bloqueia também o acesso à imagem expirada. Os arquivos originais permanecem no armazenamento; não há limpeza física automática nesta versão.

### Nova configuração e validação

Para começar do zero, extraia o ZIP em uma pasta nova e execute iniciar-windows.bat. O pacote não inclui banco, contas, senhas ou dados de teste. Em instalações existentes, faça backup antes de atualizar; as tabelas sociais são criadas automaticamente. O perfil padrão Equipe recebe acesso social e consulta de clientes. Confira permissões de perfis personalizados.

Validação da versão: 28 testes automatizados passaram, assim como sintaxe JavaScript e testes estruturais de sete telas. No Chromium foram conferidos perfil e carreira, upload de imagens, clientes e capa de chat, reações, mensagens flutuantes, feed, histórias, registro de tempo, controles administrativos e layout móvel. O menu móvel foi validado também com redução de movimento ativada. Instalação PWA e push em aparelhos físicos continuam pendentes da configuração real.


## Versão 1.3 — empresa, integrações e comunicação

Dashboard completo e gestor por unidade, arquivamento/restauração de conversas, Google Drive no menu, Ninja IA em chat exclusivo ou chamado nas conversas, mensagens de áudio e chamadas individuais de voz/vídeo. A identidade NJA Systems enviada é aplicada ao login, menu e ícones, junto da assinatura institucional NJA.

As integrações Google/OpenAI estão implementadas e dependem das credenciais da empresa. Chamadas entre redes diferentes podem exigir TURN. Veja **INTEGRACOES-v1.3.md** para ativar os serviços, definir Nelson e Igor como gestores e cadastrar suas fotos. O pacote não tem credenciais nem configurações pessoais. O checklist completo é **IMPLEMENTACAO-v1.3.md**.

Validação desta versão: 38 testes automatizados; interações no Chromium desktop/móvel, chamadas individuais de voz/vídeo entre duas sessões com dispositivos simulados, gravação/envio/reprodução de áudio, arquivamento/restauração, gestores e estados de integração. Google/OpenAI foram simulados nos testes; autorização de contas reais e chamadas em aparelhos físicos/redes diferentes seguem pendentes.


## Versão 1.4 — materiais das tarefas e vídeos nos chats

- Nos detalhes da tarefa, a seção Materiais da tarefa permite enviar até 20 arquivos por seleção, cada um com até 100 MB. Há progresso e cancelamento de envio; os materiais já confirmados permanecem salvos.
- Imagens mostram prévia, documentos oferecem download e vídeos têm player com controles. Nos chats principal e flutuante, vídeos enviados pelo botão de anexo aparecem com player. O botão de telefone usa o símbolo de um aparelho e o de vídeo usa uma câmera em SVG, no estilo familiar de mensageiros.
- Tipos de materiais: JPG/JPEG, PNG, WebP, GIF, PDF, DOC/DOCX, XLS/XLSX, PPT/PPTX, ODT/ODS/ODP, TXT/CSV (UTF-8), MP4/M4V, MOV e WebM. Documentos com macros nos formatos modernos não são aceitos. Não há envio de executáveis nem ZIP genérico.
- Os arquivos são armazenados no servidor da NJA, protegidos pelas permissões da tarefa/conversa. Os vídeos são fornecidos por blocos HTTP para permitir avançar a reprodução. Não são transcodificados; a compatibilidade depende do codec/navegador. Quando não reproduzir, use Baixar arquivo.
- Em hospedagem com Nginx, ajuste `client_max_body_size 120m` e verifique também os limites do provedor/proxy/CDN. A interface informa se o servidor recusar um envio. Fotos e áudios mantêm seus limites anteriores. O comando de backup ignora uploads temporários ainda em andamento.
- Validação: 43 testes automatizados; testes no Chromium de envio múltiplo de imagem, DOCX e MP4 nas tarefas, vídeo no chat, reprodução e avanço, janela flutuante, ícones SVG e layout em dimensões móveis.


## Versão 1.5 — reuniões e recuperação de acesso

Chamadas em grupo para até seis pessoas, compartilhamento de tela, tarefas vinculadas ao cadastro do cliente, recuperação por e-mail com SMTP STARTTLS/SSL e botão de teste para o master. Os atalhos para Site da NJA e Sites do Ninja estão no menu.

Veja **GUIA-v1.5.md** para operação, migração e configuração SMTP. A versão mantém chamadas individuais e os recursos anteriores. A recuperação aguarda os dados reais do provedor SMTP; reuniões entre redes diferentes dependem de HTTPS/TURN. A mudança de fontes e a experiência visual inspirada no site estão anotadas para a próxima etapa.

Validação: 49 testes automatizados e reuniões de voz/vídeo entre três sessões Chromium com captura simulada, compartilhamento de tela com fonte simulada, saída/retorno, vínculo tarefa-cliente, atalhos e layout móvel. SMTP foi simulado nos testes; envio real e operação em aparelhos físicos continuam pendentes.
# Android

Abra `iniciar_android.py` no Pydroid 3 após extrair o pacote completo. Consulte `ANDROID.md` para instalação, primeiro acesso e limitações da execução local.

