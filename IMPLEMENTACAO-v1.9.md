# NJA System 1.9 — Animações do ninja

## Checklist solicitado
- [x] Caminhada com pelo menos 10 frames: atlas novo com 12 imagens sequenciais, ciclo de 900 ms (75 ms/frame), alinhamento dos pés, altura corrigida entre as linhas, balanço discreto e deslocamento proporcional à distância. Espelhamento para andar à esquerda.
- [x] Cruzar os braços: braços relaxados, aproximação, cruzamento parcial, braços cruzados e retorno. Sequência de 4,8 segundos.
- [x] Abrir notebook e digitar: notebook fechado, tampa levantando, notebook aberto, alternância das mãos a cada 160 ms, fechamento ao terminar. Sequência de 10,5 segundos.
- [x] Cambalhota: agachamento, corpo recolhido, giro completo com deslocamento e pequena trajetória aérea, aterrissagem e retorno. Sequência de 1,8 segundo.
- [x] Pular entre lados: preparação, pose aérea, arco parabólico, compressão de aterrissagem e retorno. Sequência de 2,2 segundos. Respeita limites da área útil; não passa por outras janelas do computador.
- [x] Jutsu: sequência de selos, energia ciano, fumaça na origem, desaparecimento, deslocamento invisível, fumaça no destino e reaparecimento. Sequência de 3,1 segundos.
- [x] Movimento entre ações: respiração e inclinação sutis durante os intervalos de 8–14 segundos, substituindo os 65 segundos parados da versão anterior. Alterna braços, caminhada, notebook, cambalhota, salto e jutsu.
- [x] Interrupções: abrir o balão, recolher, ocultar, pausar, redimensionar, sair da conta ou ocultar a aba interrompe a sequência com restauração da visibilidade. Movimento reduzido mantém pose estática e não produz fumaça.
- [x] Página de conferência com botões para cada ação e exposição dos 12 frames de caminhada.

## Como conferir
Inicie o NJA normalmente e abra http://localhost:8000/ninja-lab.html (ou /ninja-lab.html no endereço onde o sistema está instalado). Essa página usa os mesmos atlas e o mesmo motor do assistente. É uma página pública de demonstração de animação; não mostra dados, agenda, contas ou conversas.

O ciclo também roda no assistente normal. Avisos e chat têm prioridade: enquanto o balão estiver aberto, ele não pula nem atravessa a tela. O botão de pausa também suspende os movimentos. A opção de movimento reduzido do dispositivo é respeitada, inclusive no laboratório.

## Arquivos de arte
- static/ninja-walk-v19.png: atlas transparente com 12 frames (4 colunas × 3 linhas).
- static/ninja-actions-v19.png: atlas transparente com 16 poses (braços, notebook, acrobacias, jutsu).
- static/ninja-atlas-v19.js: janelas de recorte dos frames e dimensões das imagens. Imagens geradas preservadas sem regravação.
- static/ninja-motion-v19.js e .css: cronogramas de frames, deslocamento, giro, arco, transparência e partículas de fumaça.
- static/ninja-lab.html, .js e .css: demonstração interativa.

As imagens foram geradas pelo recurso integrado de geração de imagens, usando o ninja da versão 1.7 como referência da identidade. Não foi utilizada a API/CLI com chave pessoal. As partículas de fumaça são CSS, combinadas à pose ilustrada do jutsu.

## Prompts utilizados
1. Atlas de caminhada: ninja 3D preto NJA, máscara prateada e olhos ciano, câmera de três quartos lateral para direita, fundo transparente, 4 colunas e 3 linhas, 12 fases distintas e sequenciais de um ciclo de caminhada, alternância entre contato do calcanhar, apoio, passagem e elevação do joelho, pernas opostas nas duas metades, braços em contramovimento, cabeça e escala consistentes, pés alinhados, margem transparente, sem texto ou cenário.
2. Atlas de ações: mesma identidade, fundo transparente, 4 colunas e 4 linhas. Primeira linha: braços relaxados, antebraços elevados, cruzamento parcial e completo. Segunda: sentado com notebook fechado, abertura da tampa, digitação pela mão esquerda e direita. Terceira: agachamento, salto estendido, cambalhota com corpo recolhido e aterrissagem. Quarta: mãos subindo, selo, selo com energia ciano e energia com fumaça. Personagens inteiros, escala e câmera consistentes, sem textos ou divisórias.

## Validação
Inspeção das duas imagens geradas; testes JavaScript do ciclo de 12 frames, transições, notebook, cambalhota, salto, duas fases de fumaça, transparência, limites dos recortes, cancelamento e movimento reduzido. Testes existentes do relógio e da estrutura da interface continuam aprovados.

A renderização animada não foi validada em navegador neste ambiente: a ferramenta de navegador exigida pela skill Sites estava indisponível. O laboratório permite conferir visualmente no navegador instalado. Não apresentamos essa validação pendente como concluída.

## Atualização
Faça backup de data e preserve configuracao-local.bat/credenciais. Substitua os arquivos do sistema e reinicie. O cache da PWA foi atualizado; se a versão anterior continuar aparecendo, recarregue a página após reiniciar o servidor. Não houve mudança no banco de dados nesta versão. Os módulos e limites da versão 1.8 permanecem válidos.
