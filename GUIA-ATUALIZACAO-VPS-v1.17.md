# NJA System 1.17 — atualização da VPS com os dados existentes

Instalação identificada: `/www/wwwroot/nja-system`. Endereço: https://njasystem.com.br.
Este pacote contém as melhorias 1.16 e 1.17 e pode atualizar a instalação 1.15 usada nesta conversa.

## 1. Preparar o pacote em uma pasta separada

1. Baixe o ZIP atualizado fornecido nesta conversa.
2. No painel da VPS, clique em **Files**.
3. Navegue até **Root dir → www → wwwroot**.
4. Clique em **New → Directory** e crie `nja-update-v117`.
5. Abra essa pasta e clique em **Upload** para enviar o ZIP atualizado.
6. Use a opção **Unzip/Extract** do arquivo para extrair dentro dessa pasta.
7. Abra a pasta `nja-system` que veio dentro do ZIP. Confira se existe `ATUALIZAR-NJA.sh`.
8. O caminho esperado do script é `/www/wwwroot/nja-update-v117/nja-system/ATUALIZAR-NJA.sh`. Se a extração tiver criado outra estrutura, confira o caminho antes de executar.

Não extraia o ZIP diretamente sobre a instalação em uso. Isso poderia substituir arquivos de configuração que você personalizou. O instalador abaixo preserva esses arquivos.

## 2. Aplicar a atualização

Escolha um horário de menor uso e avise a equipe. Clique em **Terminal** no painel e cole:

```bash
bash /www/wwwroot/nja-update-v117/nja-system/ATUALIZAR-NJA.sh /www/wwwroot/nja-system
```

O script:

1. Confere os arquivos e valida o Compose existente.
2. Faz backup SQLite pelo mecanismo do sistema, com anexos e `integration.key`, e copia esse backup do contêiner para uma pasta na VPS.
3. Faz uma cópia do código e das configurações atuais, incluindo `.env` e os arquivos Compose, em arquivo compactado.
4. Mostra o caminho `BACKUP DA ATUALIZAÇÃO: /www/wwwroot/nja-backup-v117-XXXXXXXX`.
5. Copia os arquivos Python, arquivos da interface, dependências e documentação.
6. Mantém `.env`, `compose.yaml`, `compose.override.yaml`, Dockerfile, volume de dados, DNS `1.1.1.1` configurado anteriormente, contas, mensagens e anexos da instalação.
7. Constrói as imagens e reinicia os serviços usando o mesmo projeto e volume.
8. As quatro tabelas adicionais são criadas automaticamente; registros antigos não são apagados.

A construção pode levar alguns minutos. O reinício pode causar uma breve indisponibilidade. Se aparecer erro, pare e envie a mensagem: não execute comandos de limpeza ou recrie a conta master.

O backup fica no mesmo servidor; baixe uma cópia para outro dispositivo/local seguro antes de considerar o backup protegido contra perda da VPS. Ele contém dados privados e configurações: não o publique.

## 3. Verificar os serviços

Depois do script terminar, execute:

```bash
cd /www/wwwroot/nja-system && docker compose ps
```

`web` e `scheduler` devem mostrar `Up`/`running`. Depois:

```bash
cd /www/wwwroot/nja-system && docker compose logs --tail=60 web scheduler
```

Se houver erro, envie a parte correspondente, ocultando informações privadas. Não envie o `.env`.

## 4. Atualizar o navegador e testar

1. Acesse https://njasystem.com.br e pressione **Ctrl + Shift + R**.
2. Confira clientes, tarefas e mensagens antigas. Abra um anexo antigo.
3. Abra Google Drive e confirme que a conta continua conectada, com Lista/Miniaturas.
4. Entre com duas contas em navegadores/dispositivos diferentes. Abra o chat individual flutuante; confira online e botões de voz/vídeo. A presença se atualiza por atividade com intervalo de aproximadamente 30 segundos, não representa conexão instantânea permanente.
5. Reaja a uma mensagem e a um arquivo; confirme na outra conta. Clique novamente no mesmo emoji para remover. Responda a uma mensagem e confira a citação no chat completo e no flutuante.
6. Abra um grupo com envio restrito: usuários sem envio não devem responder nem reagir.
7. Publique um story de teste e abra com outra conta. No perfil autor, abra o próprio story e clique **Quem visualizou**. Um mesmo usuário conta uma vez; o próprio autor não conta. As visualizações começam nesta versão, sem reconstrução de acessos antigos. Mesmo o master não lê a lista de outro autor.
8. Abra o menu **✦ Escolher animação** do Ninja e experimente os movimentos.
9. Abra o balão da IA e confira o campo de texto ampliado, inclusive com teclado mobile. A resposta da IA continua dependendo da chave OpenAI da instalação.
10. Para a comemoração, mantenha duas contas conectadas por pelo menos cinco segundos antes de registrar uma venda real/autorizada no fluxo comercial: lead convertido → Registrar venda. Ela aparece para colaboradores conectados em até cerca de cinco segundos. A conversão de lead sozinha não registra uma venda.
11. A tela informa vendedor, posição nacional e, quando ocorre a troca de líder, a conquista do primeiro lugar. O cálculo usa o ranking mensal existente por valor, com os mesmos desempates. Para venda com data de mês anterior, o aviso identifica aquele mês.
12. O evento não revela cliente nem valor para a equipe. Clientes do portal não recebem esse evento. Não cadastre vendas fictícias em produção para testar ranking real.

## 5. Cuidados para preservar os dados

- Mantenha o projeto na pasta `/www/wwwroot/nja-system`.
- Não use `docker compose down -v`, `docker volume prune` ou exclusão de volumes.
- Não substitua `.env` por `.env.example`.
- Não execute `init-master` para atualizar.
- Preserve `integration.key`, ou `NJA_TOKEN_KEY` caso configurada no ambiente; ela protege as conexões Google e outras integrações.
- O script não atualiza Dockerfile/proxy/Compose. Ele mantém as configurações usadas na sua VPS.

## 6. Se precisar voltar ao código anterior

Guarde o caminho do backup mostrado pelo script. Primeiro envie o erro para diagnóstico. Para voltar somente ao código anterior, com o projeto parado, a cópia `codigo-e-configuracoes.tar.gz` pode ser extraída de volta sobre a mesma instalação e as imagens reconstruídas. As novas tabelas são adicionais e podem permanecer no banco; voltar ao código não exige apagar o banco.

Restaurar o banco é uma operação separada e perde alterações posteriores ao backup: faça isso somente se necessário, com web e scheduler parados, preservando antes uma cópia da situação atual. A pasta `dados` contém `nja.sqlite3`, `uploads` e, quando usada, `integration.key` do mesmo backup. Nunca misture banco e anexos de backups diferentes. Confira o caminho real de dados/volume da sua instalação antes de restaurar.
