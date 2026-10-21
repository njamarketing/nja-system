# NJA System 1.3 — ativação das integrações da empresa

O código das integrações está incluído. O pacote não traz credenciais, conexões Google autorizadas nem saldo de API. A tela Configurações informa o estado de cada integração. As credenciais são configuradas no servidor, nunca no JavaScript nem em mensagens deste chat.

## 1. Gestores, fotos e unidades

Em Configurações → Unidades e gestores, selecione Nelson para Foz do Iguaçu e Igor Martins para Teixeira de Freitas. Se não houver seleção salva, Foz usa o master ativo mais antigo; Teixeira procura uma conta ativa com o nome Igor Martins. O sistema não cria uma conta fictícia de Igor. Cadastre-o normalmente se ainda não existir.

Em Unidade de cada colaborador, distribua as contas entre Foz e Teixeira. Por padrão, contas existentes começam em Foz. A foto exibida vem do perfil do gestor: envie a foto no editor de perfil. Sem foto cadastrada, aparecem as iniciais.

O master vê o panorama da empresa: clientes ativos, conversas cadastradas, chats com mensagem ou arquivo nos últimos sete dias, colaboradores online, tarefas concluídas, não concluídas, aguardando aprovação e atrasadas, além das últimas 15 ações registradas. Colaboradores veem tarefas e chats aos quais têm acesso; a unidade determina o gestor exibido, sem alterar as permissões das tarefas. Presença online depende da sessão em aba visível, com tolerância de aproximadamente 75 segundos. Chats ativos significam atividade recente, não uma pessoa digitando agora.

Clientes podem ser desativados/reativados nos detalhes do cadastro. Isso altera o indicador de clientes ativos sem apagar histórico ou conversas.

## 2. Arquivar e restaurar chats

No cabeçalho de uma conversa, use Arquivar. A opção Ver chats arquivados permite abrir e Restaurar a conversa. O arquivamento pertence ao usuário: não apaga mensagens, não remove participantes e não arquiva a conversa para os demais. Novas mensagens não restauram automaticamente a conversa; o histórico continua disponível na lista arquivada.

## 3. Google Drive da empresa

A integração é de leitura: navega pastas, pesquisa pelo nome, pagina resultados e abre arquivos no Google. Mostra drives compartilhados disponíveis à conta conectada. Não copia os arquivos para o banco do NJA nem modifica documentos. Cada colaborador conecta sua própria conta corporativa, respeitando as permissões concedidas pelo Google. O master não compartilha automaticamente suas credenciais com toda a equipe.

1. No Google Cloud da empresa, crie/abra o projeto e habilite Google Drive API.
2. Configure a tela de consentimento OAuth e as contas permitidas. Para Workspace, escolha o público apropriado à organização; para público externo, observe as exigências de verificação dos escopos Google.
3. Crie um cliente OAuth do tipo Aplicação Web. Registre a URI de redirecionamento exata: `https://SEU_DOMINIO/api/drive/callback`. Para testar localmente: `http://localhost:8000/api/drive/callback`.
4. Configure `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` no ambiente do servidor. `NJA_ORIGIN` deve corresponder ao endereço registrado, sem barra final.
5. Opcional: `GOOGLE_WORKSPACE_DOMAIN` restringe a conexão ao domínio corporativo; `GOOGLE_DRIVE_ROOT_ID` define a pasta inicial (não substitui as permissões do Google). A busca pelo nome pode encontrar outros arquivos acessíveis à conta, além dessa pasta.
6. Reinicie o servidor. No NJA, abra Google Drive → Conectar Google Drive e autorize a conta da empresa. O escopo solicitado é `drive.readonly`. A conta é vinculada ao usuário que iniciou a conexão.
7. Teste pastas, busca, documentos e drives compartilhados. A opção Desconectar remove a autorização local e tenta revogar o token no Google; se a rede estiver indisponível, remova também o acesso nas configurações de segurança da conta Google.

Tokens ficam criptografados no banco com Fernet. A chave é `NJA_TOKEN_KEY`, se fornecida, ou o arquivo privado `data/integration.key`, criado automaticamente. O comando de backup inclui esse arquivo; preserve-o ao restaurar. Se usar uma chave no ambiente, mantenha uma cópia segura fora do ZIP. Trocar/perder a chave exige reconectar as contas. O estado OAuth tem validade de dez minutos e uso único. Tokens e segredos não são expostos pela API do NJA.

## 4. Ninja IA na conta da empresa

A integração usa OpenAI API, com uma chave do projeto da empresa. Não conecta automaticamente esta conversa do ChatGPT nem inclui a memória desta conta. A assinatura do ChatGPT e o uso da API têm cobrança independente.

Configure no ambiente:

- `OPENAI_API_KEY`: chave do projeto corporativo.
- `OPENAI_PROJECT`: identificador do projeto, se necessário para a organização.
- `OPENAI_MODEL`: padrão `gpt-5-mini`; pode ser alterado para outro modelo compatível com Responses API e habilitado no projeto.
- `OPENAI_TRANSCRIBE_MODEL`: padrão `gpt-4o-mini-transcribe`.
- `NJA_AI_DAILY_LIMIT`: padrão 300 operações/dia para toda a empresa.
- `NJA_AI_USER_DAILY_LIMIT`: padrão 30 operações/dia por usuário. Transcrições e respostas contam separadamente; tentativas com falha também contam. Os limites são por dia UTC e não substituem o controle de orçamento no projeto OpenAI.

Reinicie o servidor. O menu Ninja IA abre uma conversa exclusiva de cada usuário. Nesse chat, o Ninja responde a cada mensagem e aos áudios transcritos quando configurado. Nos demais chats, escreva `@ninja` ou use Perguntar ao Ninja. Uma resposta pedida em um grupo aparece para os participantes do grupo.

O Ninja está disponível por padrão nas conversas. Nas informações do chat, um administrador de chats pode desativá-lo. O aviso de presença da IA é exibido acima das mensagens. O acesso depende da permissão IA do usuário e de sua participação na conversa.

Contexto enviado à OpenAI: as últimas 60 mensagens e as últimas 20 transcrições disponíveis dessa conversa, limitado a aproximadamente 40 mil caracteres. O sistema não envia outros chats nem arquivos do Drive como contexto, e não dá à IA ferramentas para executar alterações. A IA recebe as mensagens quando chamada; não há leitura contínua de todos os chats em segundo plano. Áudios enviados por usuários com permissão IA são transcritos automaticamente se a chave estiver configurada e a IA habilitada naquele chat. Isso envia o áudio à API OpenAI. Há transcrição manual para tentar novamente em caso de erro. Confirme nomes, prazos e números importantes: transcrições e respostas podem conter erros.

A resposta é salva como mensagem do Ninja IA. Se a API falhar, a mensagem ou o áudio original permanece salvo e a interface informa a falha. Requisições Responses usam `store:false`; isso não substitui as regras de retenção aplicáveis à organização na OpenAI. Operações externas são síncronas nesta versão, com limite de 50 segundos por chamada à API; a interface indica processamento. Em escala maior, migre essas operações para uma fila de trabalhos.

## 5. Mensagens de áudio

Use o botão vermelho Gravar áudio. Autorize o microfone, grave por até três minutos, toque em Parar e ouvir e depois em Enviar áudio. A gravação tem prévia e pode ser descartada antes do envio. É necessário HTTPS fora de localhost e um navegador com MediaRecorder. Formatos usados pelo navegador: WebM/Opus, Ogg/Opus ou MP4. O backend também aceita WAV. Limite por arquivo: 8 MB.

O áudio é protegido pelas mesmas permissões da conversa, pode ser reproduzido dentro do chat principal ou flutuante e, quando houver IA configurada, ganha transcrição. Transcrição não grava nem analisa chamadas ao vivo.

## 6. Chamadas de voz e vídeo

Os botões de telefone e câmera no cabeçalho iniciam chamadas individuais. Num grupo, selecione outro participante. O destinatário recebe a opção Atender ou Recusar enquanto estiver conectado ao sistema. Não há conferência de múltiplas pessoas, gravação de chamadas nem transcrição da chamada ao vivo.

É possível silenciar o microfone, desligar a câmera e encerrar. Microfone/câmera só são solicitados ao iniciar ou atender uma chamada. O navegador controla a autorização. Uma chamada toca por até 60 segundos; uma sessão aceita tem duração máxima de duas horas. Recarregar/sair da página encerra a sessão. Se uma aba terminar abruptamente, uma nova entrada encerra a sessão anterior.

A mídia usa WebRTC entre os navegadores, com sinalização autenticada no servidor. A aba precisa permanecer ativa para receber o diálogo de chamada; a notificação interna/push depende da configuração já existente e não substitui uma chamada telefônica no celular bloqueado.

Para conexões entre redes diferentes (por exemplo Foz e Teixeira), configure servidor TURN, HTTPS e liberação das portas do serviço TURN. Sem TURN, algumas redes não conseguem se conectar. A configuração padrão usa apenas STUN e permite testes em redes compatíveis.

`NJA_ICE_SERVERS` é um array JSON de servidores ICE. Exemplo de formato:

```json
[{"urls":"stun:stun.l.google.com:19302"},{"urls":["turn:SEU_SERVIDOR:3478","turns:SEU_SERVIDOR:5349"],"username":"USUARIO_TURN","credential":"SENHA_TURN"}]
```

As credenciais TURN precisam chegar aos navegadores autenticados para estabelecer a mídia. Use credenciais dedicadas, quota e rotação no serviço TURN; o exemplo desta versão usa credenciais estáticas. Configure o serviço/provedor de sua escolha e teste com dois aparelhos reais em redes diferentes antes de uso operacional. Nenhum serviço TURN foi contratado ou ativado neste pacote.

## 7. Configuração no Windows e Docker

Windows: copie `configuracao-local.bat.example` para `configuracao-local.bat` e preencha somente as variáveis que usar. Execute `iniciar-windows.bat`. Esse arquivo privado é carregado pelo iniciador e não deve ser compartilhado. O iniciador instala o suporte de criptografia além de imagens e fuso horário.

Docker: copie `.env.example` para `.env`, preencha as variáveis e reconstrua a imagem. O Compose lê `.env` e mantém o volume de dados. Em instalação manual Linux/macOS, exporte as variáveis no ambiente; Python não lê `.env` automaticamente. Ao atualizar uma instalação existente, mantenha o banco, uploads e a chave de criptografia juntos e faça backup primeiro.

## 8. Validação e identidade visual

Os testes automatizados cobrem permissões, arquivamento individual, unidades, indicadores, estados OAuth e isolamento de tokens, renovação de autorização, IA com contexto limitado, preservação em falhas, áudio e sinalização de chamadas. Google e OpenAI foram simulados nos testes: não houve autorização de conta Google real nem chamadas cobradas à API.

No Chromium foram testadas chamadas de voz e vídeo entre duas sessões, usando dispositivos de áudio/vídeo simulados, além de gravar/enviar/reproduzir uma mensagem de áudio, arquivar/restaurar chat, configuração de gestores e navegação móvel. O ambiente de testes precisou permitir WebRTC na interface de loopback por não ter uma rede externa normal. A conexão real Foz–Teixeira, permissões em celulares e TURN continuam pendentes de teste na hospedagem.

As três imagens NJA Systems enviadas foram preservadas, sem redesenho. A logo escura é usada no login/menu sobre base clara; o ícone é aplicado ao sistema e à PWA, com versões dimensionadas para instalação. A assinatura Desenvolvido por NJA mantém a marca institucional. A arte animada do ninja no login permanece integrada.

Fontes técnicas: documentação oficial OpenAI Responses e Speech-to-text, Google Drive API/OAuth Web Server e MDN WebRTC. Consulte as configurações atuais dos respectivos provedores antes de ativar serviços.
