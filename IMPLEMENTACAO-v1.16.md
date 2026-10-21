# Atualização 1.16 — Google Drive em lista e miniaturas

- Botões Lista e Miniaturas na aba Google Drive; miniaturas como visualização inicial.
- Escolha lembrada por usuário neste navegador. Sem armazenamento de arquivos no localStorage.
- Grade responsiva (duas colunas no celular), imagens inteiras sem recorte e ícones para pastas, PDF, vídeo, planilhas e apresentações.
- Pastas, busca, caminho e paginação preservados. Alternar visualização mantém pasta, busca e página.
- Prévias carregadas conforme entram na tela, com no máximo quatro requisições simultâneas por renderização.
- Miniaturas usam a autorização Google do próprio usuário; o token e o link temporário não são enviados ao frontend. Não é necessário tornar arquivos públicos.
- Sem prévia disponível, o cartão mantém o ícone. Clique no arquivo para abrir o original no Google Drive.
- Corrigida pasta inicial vazia: GOOGLE_DRIVE_ROOT_ID vazio agora usa root automaticamente.

## Instalar na VPS existente

O pacote NÃO foi aplicado automaticamente à VPS.

1. Envie o ZIP atualizado para uma pasta separada, por exemplo /www/wwwroot/nja-update-v116, e extraia.
2. No terminal, entre na pasta extraída que contém app.py e ATUALIZAR-DRIVE.sh.
3. Execute: `bash ATUALIZAR-DRIVE.sh /www/wwwroot/nja-system`.
4. O script faz backup dos dados pelo comando do sistema e dos cinco arquivos substituídos, copia apenas integrations.py, drive_gallery.py, static/enterprise.js, static/enterprise.css e static/sw.js, valida o Compose e reconstrói web/scheduler.
5. O .env, compose.yaml, compose.override.yaml, dados e DNS da instalação existente são preservados.
6. Recarregue com Ctrl+Shift+R e abra Google Drive. A conexão existente é preservada. Confira Lista/Miniaturas, abertura de pasta, busca e próxima página.

Alternativa manual: com backup prévio, substitua somente os cinco arquivos listados acima e rode `docker compose up -d --build` na pasta da instalação. Nunca use `docker compose down -v`.

## Validação e limites

Quatro testes Python específicos passaram: pasta inicial vazia, autorização por usuário, resposta sem cache, imagem com transparência, rejeição de URLs externas e redirecionamentos inseguros. Dez testes existentes de integrações passaram. Teste JavaScript validou preferência por usuário, lista/grade, pastas e escape de nomes. Sintaxe Python e JavaScript e testes gerais de renderização passaram.

Não houve autorização Google real neste ambiente nem teste visual em navegador/celular físico. A disponibilidade de prévias depende do Google; alguns formatos podem mostrar apenas ícone. Referência oficial: https://developers.google.com/workspace/drive/api/reference/rest/v3/files (thumbnailLink).
