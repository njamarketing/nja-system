# 1.15 — Chats, contas, marca e interação social

## Checklist de uso
- Chats: altura limitada à área disponível, rolagem interna do histórico e compositor independente do tamanho das imagens. Regras específicas para teclado mobile e chat flutuante. Fotos/vídeos têm tamanho limitado.
- Fotos: clique na miniatura abre uma janela modal na mesma página, com download e fechamento. O modal conserva a página/diálogo de origem.
- Contas: ao editar perfil, somente master vê Alterar e-mail de login e Excluir perfil. E-mail é validado, duplicatas são bloqueadas e sessões/tokens de recuperação anteriores são revogados. Exclusão é lógica: o usuário perde acesso e sai da equipe; autoria e registros históricos são preservados. O master não pode ser excluído. Perfis excluídos não podem ser reativados por PATCH.
- Chamadas em grupo: uma aba inativa deixou de encerrar uma reunião aberta em outra aba. Falha em um candidato ICE não bloqueia os demais participantes. Sinalização tem nova tentativa e conexões falhas podem tentar renegociar ICE. Mantém limite de seis participantes.
- Clientes: abra o card e veja Marca do cliente. Adicione arquivos de logo (PNG, JPG, WebP, SVG ou PDF, até 8 MB por arquivo), baixe os originais, remova arquivos e cadastre cores #RRGGBB e link HTTPS do Google Drive. Miniaturas raster preservam transparência; SVG/PDF são apresentados como arquivos para baixar. Visualização depende de acesso à carteira; alteração exige Gerenciar clientes. O link não autoriza acesso ao Google: permissões do Drive continuam necessárias.
- Stories: imagem completa com object-fit contain e navegação manual enquanto responde. Comentários e reações são privados, enviados ao chat individual com o autor. Reutiliza a conversa existente, inclusive restaurando-a se arquivada, ou cria uma nova. Abre o chat após enviar. O autor não pode responder à própria história. Histórias expiradas bloqueiam novas respostas.
- Feed: o autor pode editar texto, substituir/adicionar/remover imagem. Curtidas e comentários permanecem. Exibe Editado.
- Comentários do feed: Responder seleciona o comentário de origem, mostra contexto e permite cancelar. O servidor impede vincular resposta a comentário de outra publicação.

## Atualização na VPS
Faça backup antes. Preserve .env, chaves, volume e pasta de dados existentes. Atualize o código na mesma pasta do projeto e execute `docker compose up -d --build`. Nunca use `docker compose down -v`. A inicialização cria as tabelas/colunas adicionais sem apagar os registros antigos. Atualize a página após o deploy. O ZIP não altera automaticamente a VPS nem o APK.

## Verificação e limites
A bateria de 109 testes Python passou, incluindo quatro casos novos para usuários, marcas, edição/respostas e stories. Testes JavaScript verificaram renderização e regressões de sinalização: segunda aba não encerra chamada e um candidato inválido não interrompe outro participante.
A validação automatizada não comprova áudio/vídeo entre redes reais. É necessário testar com três aparelhos após instalar na VPS, usando HTTPS, câmera/microfone autorizados e a configuração NJA_ICE_SERVERS. Redes que bloqueiam conexão direta podem precisar de TURN (o padrão do projeto fornece somente STUN). Nenhum servidor TURN foi contratado/configurado nesta entrega.
Layout, teclado e modal ainda precisam de conferência visual em desktop e celular real; não foi possível realizar essa validação neste ambiente.
