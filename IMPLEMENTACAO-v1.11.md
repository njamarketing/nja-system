# NJA 1.11 · Movimento a 60 fps

- Reprodução amostrada em 60 imagens por segundo, comandada pelo relógio da animação. A taxa real depende do navegador, tela e carga do aparelho.
- Caminhada com 72 imagens por ciclo de 1,2 s: 36 poses-base e 36 imagens intermediárias calculadas com compensação de movimento bidirecional. Não são 72 novas poses desenhadas individualmente.
- Posição horizontal da cabeça estabilizada antes da interpolação. Pés alinhados, fundo transparente e mistura de cores ponderada pelo alfa para reduzir bordas escuras.
- As transições de braços, notebook, salto, cambalhota e selos também recebem imagens intermediárias. 146 imagens de transição são preparadas inicialmente; outras são calculadas sob demanda, com cache limitado.
- Jutsu mantém a fumaça branca/azulada e ganha preparação com aura crescente nos selos antes de desaparecer. Fumaça mais ampla na saída e na chegada.
- Pausas, respiração, botão de reduzir movimento e cancelamento de ações continuam funcionando. Processamento das imagens em Worker, fora da interface principal. Se ele falhar, usa os sprites originais.

## Conferir
Abra /ninja-lab.html no mesmo servidor. Caminhada reproduz o ciclo completo; o painel inferior mostra as 72 imagens após o processamento inicial. Teste também jutsu, notebook, salto e cambalhota.

Validação nesta atualização: testes da linha do tempo, 60 amostras distintas por segundo, fechamento do ciclo, interrupção de movimento, interpolação com transparência, extremos exatos da interpolação e fila/cache de 146 imagens. Sintaxe dos quatro scripts conferida. Não houve teste visual em navegador nesta sessão; anatomia, naturalidade e desempenho final precisam dessa conferência. A interpolação melhora a continuidade temporal, mas não substitui uma animação artística articulada e revisada quadro a quadro.

## Instalação
Faça backup da pasta data, preserve seus dados e configurações locais, substitua os arquivos do programa e reinicie. Recarregue o aplicativo para receber o novo cache. Esta atualização não altera o banco de dados nem permissões.
