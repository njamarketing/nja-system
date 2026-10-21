# 1.14 — Atendimento no Portal do Cliente

## Como usar
1. Cadastre a empresa em Clientes e gere o convite em Aprovação de materiais > Convidar cliente.
2. O contato entra com o mesmo login do portal. Na página inicial aparece Converse com a NJA.
3. A equipe abre Chats (ou Clientes) > Chats com clientes e seleciona a empresa.
4. As mensagens são atualizadas a cada cinco segundos enquanto a conversa está aberta e a aba está visível. O histórico fica salvo; mensagens anteriores podem ser carregadas pelo botão.

## Acesso
Uma conversa de atendimento por empresa, compartilhada com TODOS os contatos ativos do portal dessa empresa. Não são mensagens privadas entre contatos. O envio independe da permissão de aprovação de materiais.
Na equipe, é necessária a permissão Chats e acesso à carteira/unidade/empresa segundo as regras existentes em Carteiras e acessos. Master e gestores com acesso global conservam seus privilégios. O cliente é determinado pela sessão do portal: informar outro cliente na requisição não altera o destinatário. Contatos desativados ou sessões expiradas perdem o acesso.
As conversas internas existentes não são compartilhadas, copiadas ou expostas ao portal.

## Escopo desta versão
Mensagens de texto até 5.000 caracteres, identificação do remetente, data e histórico paginado. Não inclui chamadas, áudio, anexos dentro da conversa, confirmação de leitura ou notificações push do chat do portal. O envio de materiais pela seção já existente do portal continua disponível, separado do chat.

## Instalação
Faça backup antes da atualização. Preserve .env, volume de dados e chaves. Substitua o código e execute `docker compose up -d --build` na pasta atual do projeto. A inicialização cria uma tabela e um índice novos sem apagar os dados existentes. Não use `docker compose down -v`. Reabra a página após atualizar. Este ZIP não instala automaticamente na VPS e não atualiza o APK.

## Validação
Três testes de atendimento verificam envio nos dois sentidos, separação entre empresas, bloqueio por carteira, revogação de contato, histórico/paginação e persistência após inicialização. Os testes existentes do portal também foram executados. A sintaxe JavaScript foi conferida. A interface ainda precisa de teste em navegador/celular real.
