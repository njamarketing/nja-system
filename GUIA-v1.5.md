# NJA System 1.5 — reuniões, clientes e recuperação de acesso

## Chamadas em grupo

Abra uma conversa de grupo ou Equipe NJA e toque no ícone de telefone ou câmera. Selecione de um a cinco colegas e use Iniciar chamada em grupo. A reunião permite até seis pessoas contando quem iniciou. Também permanece disponível a opção de ligar individualmente.

Os convidados recebem um diálogo para entrar ou recusar enquanto estiverem conectados. Os convites tocam por até 60 segundos. Um convidado que não atendeu, recusou ou saiu pode abrir o chat e usar Entrar na reunião ativa, enquanto a reunião estiver disponível. Somente os participantes selecionados podem entrar; pertencer ao chat não autoriza automaticamente uma pessoa que não foi convidada.

Cada pessoa controla o microfone e a câmera. Compartilhar tela solicita a seleção de uma janela, aba ou tela pelo navegador. Parar compartilhamento volta à câmera, se houver. Em chamada de voz, é possível compartilhar tela sem ligar a câmera. Áudio do sistema/tela não é transmitido: a reunião mantém o microfone. O compartilhamento depende de suporte e autorização do navegador; não se pode garantir em todos os celulares.

Sair da reunião remove apenas sua participação. Encerrar para todos é exclusivo do anfitrião atual. Quando o anfitrião sai, a função passa para o participante presente há mais tempo; se não restar ninguém presente, a reunião termina. As reuniões têm duração máxima de duas horas. Recarregar a página encerra a participação antiga; um convidado pode voltar pelo chat. Remoção do chat ou desativação da conta retira o acesso à reunião.

Esta versão usa conexões diretas WebRTC entre os participantes (malha). Cada navegador envia a mídia aos demais, por isso o limite é de seis e a qualidade depende da conexão/aparelho. HTTPS e TURN continuam necessários para operação consistente em redes diferentes. As configurações `NJA_ICE_SERVERS` da versão 1.3 também servem às reuniões. Para grupos maiores, implemente servidor de mídia/conferência em vez de ampliar este limite. Nenhum serviço externo foi contratado.

## Vínculo de tarefas com clientes

O formulário de tarefa tem Cliente cadastrado. Escolha um cliente ativo para associar a tarefa ao cadastro, em vez de depender de um nome digitado. A tarefa continua associada quando o cliente muda de nome. O campo Projeto/campanha permanece disponível para tarefas sem vínculo.

No cadastro do cliente, Tarefas deste cliente lista apenas as tarefas vinculadas que o usuário pode acessar. Criar tarefa para este cliente preenche o vínculo. Novas subtarefas oferecem o cliente da tarefa pai como seleção inicial.

A migração acrescenta um campo opcional sem apagar tarefas antigas. Tarefas antigas com nomes textuais não são vinculadas automaticamente: edite e selecione o cliente correto para evitar associações incorretas. Clientes inativos não podem ser escolhidos em novas tarefas, mas os vínculos existentes permanecem no histórico.

## Recuperação de senha por e-mail

O fluxo está programado e validado com SMTP simulado. Para enviar e-mails reais, configure no servidor ou no arquivo de configuração local privado:

- `SMTP_HOST`: servidor de saída fornecido pelo provedor.
- `SMTP_PORT`: normalmente 587 para STARTTLS ou 465 para SSL, conforme seu provedor.
- `SMTP_SECURITY`: `starttls` ou `ssl`.
- `SMTP_FROM`: e-mail remetente autorizado; pode usar `NJA System <acesso@SEU_DOMINIO>`.
- `SMTP_USER` e `SMTP_PASSWORD`: credenciais SMTP, quando exigidas pelo provedor. Preencha ambos ou deixe ambos vazios se o relay autorizado não exigir login.
- `NJA_ORIGIN`: endereço que os usuários acessam, com HTTPS em produção, sem barra final. Esse endereço compõe o link de recuperação.

Windows: copie configuracao-local.bat.example para configuracao-local.bat, preencha os campos e execute iniciar-windows.bat. Docker: use as variáveis em .env e reinicie o serviço web. Não envie a senha SMTP em mensagens nem compartilhe arquivos de configuração preenchidos.

Como master, abra Configurações → Recuperação de senha por e-mail → Enviar teste para meu e-mail. O teste só é enviado ao e-mail da própria conta master. Confira caixa de entrada e spam. O estado SMTP configurado indica campos válidos, não comprova entrega real. Se houver falha, confira host, porta, modo TLS, credenciais e autorização do remetente.

Cada colaborador usa Esqueci minha senha na tela de acesso. O e-mail tem botão Criar nova senha e alternativa em texto. O link expira em 30 minutos e só pode ser usado uma vez. O formulário pede confirmação da nova senha. Redefinir encerra todas as sessões da conta. Tokens ficam armazenados como hash. A resposta pública é igual para contas existentes e inexistentes; uma falha SMTP invalida o token daquela tentativa. Contas desativadas não podem usar a recuperação.

## Atalhos da empresa e próxima etapa visual

No menu, Universo NJA tem dois botões que abrem em outra aba:

- Site da NJA: https://njamarketing.com.br/
- Sites do Ninja: https://sitesdoninja.com.br/

Ficou anotada a próxima etapa: fontes tecnológicas semelhantes à logo, animações nos títulos/destaques e adaptação da experiência visual/textual do site institucional ao sistema. Essa reformulação visual não foi aplicada nesta versão; os atalhos foram adicionados. A análise textual da referência não substitui a inspeção visual das animações antes da reformulação.

## Validação e atualização

49 testes automatizados aprovados. No Chromium: tarefa vinculada criada pelo formulário e exibida no cliente, atalhos externos, estado de SMTP, reunião de voz/vídeo entre três usuários, microfone/câmera, compartilhamento de tela com fonte simulada, saída/retorno, encerramento para todos e layout móvel. Os dispositivos de captura são simulados; testes em aparelhos reais e redes Foz–Teixeira continuam necessários. Não houve envio a uma caixa de e-mail real.

Atualize os arquivos do programa mantendo data/, suas configurações locais e a chave integration.key. Faça backup antes. As migrações criam as tabelas e colunas novas automaticamente, sem apagar cadastros ou tarefas.
