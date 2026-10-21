# NJA System · Atualização 1.10

## Checklist da solicitação
- [x] Caminhada com 36 recortes distintos, ciclo de 1,44 s, transparência preservada e alinhamento dos pés. São 30 quadros principais e seis complementares selecionados de uma segunda folha; o laboratório permite inspecionar todos. A naturalidade final depende da conferência visual no navegador.
- [x] Tutorial guiado por permissões, com avançar/voltar/pular e botão Tutorial para rever. Conclusão salva por usuário no servidor.
- [x] Tela de carregamento preta, ninja subindo na ampulheta e alternando poses sentado com os pés em movimento. Não cria espera artificial; desaparece quando o aplicativo termina de carregar.
- [x] Configurações dentro do grupo: nome, foto, descrição, integrantes, gestores, políticas de envio e convite (todos, gestores ou selecionados).
- [x] Permissões de grupo verificadas no servidor também para anexos, áudio e solicitações de IA que publicam na conversa.
- [x] Visual dos grupos com fundo delicado, cores, entrada animada das mensagens e reações com destaque. Respeita movimento reduzido do dispositivo.
- [x] Ranking comercial mensal, nacional inicialmente, com filtros locais e pódio dos três primeiros. Fotos de perfil ou iniciais quando não houver foto.
- [x] Cascavel/PR nas unidades, seleção de gestores, perfis, clima e filtros comerciais.

## Vendas e permissões
O ranking usa o valor de vendas confirmadas registradas na seção Vendas · Ranking, nunca o orçamento disponível do lead. Converta o lead em cliente e registre valor/data efetivos. Cada lead convertido permite um registro de venda. Cancelar/restaurar fica restrito a sales_manage e registrado na auditoria. A unidade é uma fotografia da unidade do vendedor no cadastro da venda; mudança posterior do perfil não transfere vendas antigas.

O papel Comercial ganha sales_ranking pela migração. Papéis personalizados precisam receber essa permissão. Gestores de grupos podem ser escolhidos sem receber administração global de chats. Administradores globais continuam com acesso administrativo. Quem perde o envio continua podendo ler. O grupo Geral conserva os integrantes definidos pelo cadastro da equipe.

## Conferência visual
Use /ninja-lab.html para conferir a caminhada e cada movimento. Use /loading-preview.html para observar a tela de carregamento sem depender da velocidade da conexão. As imagens foram geradas com a ferramenta integrada de imagens e mantidas como PNG com transparência. Prompts: caminhada lateral do ninja NJA em quadros sequenciais com braços e pernas articulados; quadros complementares da caminhada; sequência subir na ampulheta, sentar e balançar os pés.

Validação: 74 testes Python passaram, incluindo delegação/revogação de gestores, bloqueio de mensagens/anexos/áudio, persistência do tutorial, filtros e cancelamento de vendas. Testes JavaScript verificam renderização, escape de texto, permissões e linha do tempo do ninja. A fluidez final ainda precisa ser conferida no navegador; não foi realizado teste visual de ponta a ponta nesta sessão.

## Atualizar
Faça backup da pasta data antes de substituir os arquivos do programa. Preserve data e as configurações locais. Reinicie o servidor; as novas colunas e tabelas são migradas automaticamente. Recarregue o aplicativo para atualizar o cache. Nenhum dado de demonstração foi adicionado ao banco da instalação.
