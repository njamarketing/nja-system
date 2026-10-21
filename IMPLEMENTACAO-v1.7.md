# NJA System 1.7 — Ninja assistente

## Entregue
- Ninja 3D inspirado nas referências NJA enviadas, com atlas transparente de 12 poses. Repousa sem animação contínua; alterna breves gestos, trabalho, meditação, alongamento, saudação e cambalhota, com intervalos de aproximadamente 65 segundos.
- Caminha entre lados da interface ao navegar pelas telas do sistema. Não atravessa outras janelas do computador. Respeita preferência de movimento reduzido e pausa em abas ocultas.
- Botão abre balão com Meu dia, Clima e Conversar com IA. Chat utiliza a conversa pessoal e a integração OpenAI existente, com histórico persistido e indicação de falha.
- Ao entrar no painel, informa tarefas pessoais abertas e compromissos do dia que o usuário pode acessar. Tarefas pessoais incluem responsabilidade e participação; não representa o total de toda a empresa para o master.
- Alertas de agenda a 60, 30 e 15 minutos, com deduplicação persistida e suporte a recorrência. Ao entrar atrasado, entrega apenas o marco mais próximo aplicável, sem despejar todos os anteriores. Preferências de notificações e permissões continuam aplicadas.
- Voz opcional pelo navegador, ativada por clique em cada sessão; depende das vozes disponíveis no aparelho. Não exige serviço de voz OpenAI.
- Clima por unidade: Foz do Iguaçu e Teixeira de Freitas, temperatura atual, sensação e previsão em intervalos de três horas. Cache de 15 minutos; dados antigos são sinalizados e falhas não viram previsão fictícia.
- Mantidos calendário com criação por popup, fontes da versão anterior e mensagens por hora de uso ativo. Tempo ocioso e aba oculta não contam como produtividade.

## Configuração
Preserve a pasta de dados e configurações existentes antes de substituir os arquivos. Faça backup pelo procedimento do LEIA-ME. Não substitua dados de produção por diretórios de teste.

A IA requer as credenciais da integração OpenAI já documentada. Para clima, configure OPENWEATHER_API_KEY no ambiente do servidor (ou no arquivo de configuração local usado pelo iniciador Windows), conforme os exemplos incluídos, e reinicie. A chave fica no servidor. Sem chave, o balão informa que o clima não está configurado.

Documentação do provedor: https://openweathermap.org/current e https://openweathermap.org/forecast5 . Não há chave incluída no pacote.

Mantenha scheduler.py em execução para notificações do servidor. Com o sistema aberto, a verificação do ninja ocorre aproximadamente a cada 30 segundos na aba visível e em foco. Com o aplicativo fechado, notificações dependem do worker, da configuração push e da autorização do navegador; o personagem e a voz não funcionam com a página fechada.

## Validação e limites
58 testes Python de integração aprovados, testes JavaScript do relógio e estrutura aprovados. Verificado em navegador: resumo pessoal, repouso real, caminhada, alerta, chat persistido, clima, abertura de compromisso, balão no celular, movimento reduzido e ocultar/restaurar. Serviços OpenAI e clima foram simulados nos testes, sem chamadas reais ou credenciais de produção. Voz e notificações em aparelhos físicos ainda precisam de validação no ambiente de uso.

## Próximos módulos
Meta, financeiro Itaú/Cora/InfinitePay somente consulta e download, contratos e CRM estão descritos em PROXIMAS-ETAPAS.md. Não foram implementados nesta versão. A disponibilidade de cada integração oficial ainda precisa ser verificada. Cada novo módulo deverá aplicar permissões no servidor, por usuário e escopo dos dados.

## Asset do personagem
static/ninja-poses-v17.png foi gerado com imagegen a partir das referências fornecidas: ninja 3D preto, máscara prateada, olhos e contorno ciano, fundo transparente, 12 poses em quatro colunas e três linhas (repouso, saudação, continência, alongamento, quatro passos, meditação, trabalho, pensamento e comemoração). Os recortes são feitos em CSS; a imagem original gerada foi preservada no atlas.
