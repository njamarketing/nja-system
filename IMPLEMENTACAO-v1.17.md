# Checklist de implementação — NJA System 1.17

## 1. Online e chamadas no chat flutuante

- [x] Nome e estado online/último acesso no cabeçalho da conversa individual flutuante.
- [x] Botões de voz e vídeo com ícones já usados no chat completo.
- Como: reutiliza dados de presença e o mesmo fluxo de chamadas WebRTC existente. Atualiza a indicação durante as consultas do chat e de presença. Não cria um segundo sistema de chamadas.
- Verificação: sintaxe e teste de integração de frontend; chamadas reais e presença em aparelhos precisam de validação na VPS. TURN continua necessário em redes que bloqueiam conexão direta.

## 2. Reações e respostas a mensagens

- [x] Controles visíveis Responder/Reagir em chat completo e flutuante.
- [x] Reações a textos e anexos; uma reação por pessoa, trocável ou removível ao clicar novamente.
- [x] Responder mostra a mensagem/arquivo original no envio e uma citação na resposta salva. Clique na citação para localizar o original entre os itens carregados.
- [x] Cancelamento da resposta antes do envio e preservação em caso de erro.
- Como: tabelas adicionais message_replies e file_reactions, com validação de sala e das permissões de envio. Reações de texto reaproveitam a tabela existente. Não se permite responder a mensagem de outra sala ou reagir em grupo com envio bloqueado.
- Verificação: testes de isolamento de sala, resposta a anexo, toggle de reações e política de grupo passaram.

## 3. Logo do menu lateral

- [x] Fundo branco removido na apresentação do PNG oficial, que já tem transparência.
- [x] Contorno claro seguindo a transparência, brilho azul e moldura discreta no fundo escuro.
- Como: CSS aplicado somente ao logo do menu lateral. Nenhum redesenho do arquivo original.
- Verificação: seletores e regras revisados; acabamento visual precisa ser conferido no navegador real.

## 4. Quem visualizou meus stories

- [x] Registro único por pessoa ao exibir um story ativo. Não conta o próprio autor.
- [x] Botão Quem visualizou no próprio story, com nome, avatar e horário da primeira visualização.
- [x] Lista privada ao autor; o master não tem exceção para ler listas de outros perfis.
- Como: tabela story_views; permissão verificada no servidor. Stories com imagem são registrados após o carregamento, enquanto a página está visível. Não há histórico retroativo anterior à atualização.
- Verificação: privacidade entre contas, negação ao master, duplicidade, expiração e exclusão em cascata passaram nos testes.

## 5. Comemoração das vendas

- [x] Venda confirmada pelo fluxo existente gera um evento para todos os colaboradores conectados.
- [x] Aviso com nome, posição no ranking nacional mensal e indicação de novo primeiro colocado.
- [x] Fogos decorativos e Ninja comemorando com shurikens em várias direções.
- [x] Evento não contém cliente, valor ou comissão. Portal de clientes não participa.
- Como: registro transacional em sale_celebrations no cadastro de venda, reutilizando exatamente a ordenação do ranking: valor, quantidade, nome e identificador. Consulta a cada cinco segundos enquanto o sistema está aberto e visível. A troca de liderança compara a posição anterior e posterior à venda. Vendas canceladas não são entregues. Eventos antigos não são reproduzidos ao entrar; janela de entrega de dois minutos.
- Os efeitos duram cerca de 6,5 segundos, têm botão de fechar e não bloqueiam o restante da tela. Preferência de movimento reduzido mantém o aviso sem partículas. Ninja oculto/recolhido/pausado permanece respeitando sua preferência.
- Verificação: eventos entre contas, cursor, confidencialidade, liderança inicial/nova, manutenção de liderança e cancelamento passaram nos testes. Não houve simulação de venda real na VPS.

## 6. Escolher animação do Ninja

- [x] Botão ✦ no controle do avatar com 12 opções: descansar, caminhar, cruzar braços, notebook, cambalhota, pulo, jutsu, acenar, saudar, alongar, meditar e comemorar.
- Como: o menu aciona o player existente e mantém limites da tela e efeito de fumaça. Após o movimento, volta à rotina com pausas. Escolher movimento retoma a atividade/recolhimento do personagem; movimento reduzido do dispositivo é respeitado.
- Verificação: sintaxe e estados do player existente testados; não foram criados novos sprites neste lote.

## 7. Campo da IA

- [x] Campo multiline ampliado: 104 px no desktop, 88 px no celular, fonte 16 px e redimensionamento vertical.
- [x] Envio alinhado ao campo; ferramentas de escrita em linha própria, sem roubar sua largura.
- [x] Ajuste do balão à área visível quando o teclado mobile reduz a tela.
- Como: grid e flex com dimensões mínimas explícitas e visualViewport; histórico rolável separado do formulário.
- Verificação: regras de layout e sintaxe conferidas; teclado e navegação visual em dispositivos físicos ainda precisam ser testados.

## Entrega e atualização

O pacote inclui as melhorias do Drive da 1.16, guia detalhado `GUIA-ATUALIZACAO-VPS-v1.17.md` e script `ATUALIZAR-NJA.sh`. Não foi instalado automaticamente na VPS nem gerado novo APK.

Os testes Python e de frontend são executados localmente. A instalação de Chromium falhou por download incompleto no ambiente, portanto não se declara validação visual de navegador real neste lote.

Resultado final: bateria geral de 119 testes Python aprovada; mais dois testes do atualizador aprovados, verificando preservação de .env/Compose/Dockerfile, backup dos dados e interrupção antes da cópia se o backup falhar. Testes JavaScript de frontend, flutuante, eventos, ranking, contador e animação passaram. Os serviços Docker reais da VPS não foram operados por este ambiente.
