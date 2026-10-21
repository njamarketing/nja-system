# Atualização 1.13 — escrita e navegação mobile

- Menu lateral: botão Fechar, fechamento com Escape, seleção de página e toque fora do menu.
- Comentários de tarefas: campo de cinco linhas, altura mínima de 150 px, fonte de 16 px e botão Enviar comentário em largura total no celular.
- Barra compartilhada: emojis, botão para retornar ao teclado nativo e seleção de pessoas com busca. Disponível nos campos de texto longo e nas mensagens/comentários do sistema, incluindo feed, histórias e chats.
- Digitar @ abre sugestões; escolher uma pessoa insere @Nome. Nos chats internos, a lista limita-se aos participantes. As menções preservam o texto simples e não criam links de perfil.
- Menções selecionadas geram notificações no feed, histórias, comentários e notas internas do CRM. Tarefas e chats mantêm suas notificações existentes, sem duplicá-las. O servidor verifica o acesso ao conteúdo antes de notificar. Marcar alguém não concede acesso.
- Mensagens destinadas ao WhatsApp externo recebem o nome como texto; isto não implementa marcação nativa de participantes em grupos do WhatsApp. No chat da IA, o nome também é apenas texto.
- Não há teclado virtual próprio: o botão Teclado dá foco ao campo e usa o teclado do dispositivo.

## Instalação / atualização
Faça backup dos dados. Substitua o código, conservando .env e o volume de dados existente. Na pasta do projeto, execute `docker compose up -d --build`. Não execute `docker compose down -v`: essa opção remove o volume de dados. Reabra a página para carregar a nova interface. Não é necessária alteração do esquema do banco.

## Validação
10 testes sociais e 2 testes de menções passaram, incluindo bloqueio de notificações para quem não tem acesso a tarefas/chats. A verificação estrutural das telas e a sintaxe Python/JavaScript passaram. A instalação do navegador de teste não pôde ser concluída neste ambiente, portanto ainda é necessário conferir o layout e o teclado em um celular real. Este pacote não atualiza automaticamente a VPS nem o APK.
