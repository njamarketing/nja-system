# NJA Systems 1.6 — um espaço mais vivo

- [x] Títulos e destaques com Oxanium; textos com Space Grotesk.
- [x] Fontes locais com acentos em português e licenças OFL incluídas.
- [x] Cores, cartões, navegação e botões com novos efeitos suaves.
- [x] Dia inteiro do calendário clicável e acessível pelo teclado.
- [x] Pop-up central de compromisso com data preenchida; atalhos também na semana/dia.
- [x] Mini ninja em SVG/CSS: caminhada, passos articulados, cambalhota e trabalhando no computador.
- [x] Placa com frases distintas para cada hora e incentivo a pausas.
- [x] Contador diário local por usuário com pausa, recolher e ocultar/restaurar.
- [x] Respeito à preferência de redução de movimento do dispositivo.

## Atualização
Faça backup antes de atualizar. Preserve `data`, `.env` (se utilizado) e `configuracao-local.bat`. Feche o servidor; copie o código novo para a instalação e mantenha os dados e configurações locais. Execute `iniciar-windows.bat`. Não substitua sua pasta de dados por outra. Para testar do zero, extraia em uma pasta nova.

## Mini ninja
Surge após o login, no rodapé à direita. Caminha para o canto, trabalha no computador, dá cambalhotas e passeia periodicamente. Ao completar cada hora, mostra uma nova frase na placa. `Ⅱ` pausa o contador; `◇` recolhe o personagem e mantém somente o painel; `×` oculta; o botão do ninja restaura. As preferências são individuais neste navegador. A preferência de movimento reduzido do sistema operacional desativa movimentos.

O contador é de **uso ativo neste navegador**. Só avança com a aba visível e em foco, até cinco minutos após a última interação com mouse, teclado, toque ou rolagem. Não conta o tempo em segundo plano, não recupera horas de suspensão do computador, e reinicia a cada dia de São Paulo. Compartilha o progresso entre abas do mesmo navegador/usuário; somente a aba em foco conta. Em modo privado ou com armazenamento bloqueado, vale apenas durante a sessão. Não sincroniza entre dispositivos. Não mede produtividade real, não é ponto e não altera as horas das tarefas no perfil.

## Calendário
Clique no espaço livre de qualquer dia ou no número do dia: o formulário surge em pop-up com início às 09h e término às 10h, editáveis. Enter/Espaço na célula também abre. Nas visões semanal e diária, clique no cabeçalho com “+ Compromisso”. Eventos e tarefas existentes continuam abrindo seus próprios detalhes. Salvar só confirma depois da resposta do servidor. As permissões atuais continuam aplicadas.

## Verificação
49 testes de integração existentes aprovados; verificações de renderização estrutural e testes do contador/hora aprovados. As fontes incluem os caracteres acentuados utilizados em português. Conferência visual em navegador real realizada em 1440×1000 e 390×844: abertura/salvamento/detalhe de compromisso, teclado, semana, fontes, controles do ninja, marco de uma hora com tempo preparado para teste, ausência de rolagem horizontal e redução de movimento. Testes em aparelhos físicos permanecem pendentes.
