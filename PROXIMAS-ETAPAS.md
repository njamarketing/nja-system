# Situação consolidada — 1.12

O código dos módulos de carteira, produção mensal, portal/aprovações, editorial, propostas/metas/comissões e gestão financeira/relatórios está implementado e testado localmente. Leia `IMPLEMENTACAO-v1.12.md` para limites e configuração. O sistema **não foi colocado em produção**.

## Bloqueios externos para implantação

- Endereço e acesso autorizado à hospedagem Python/WSGI, HTTPS, armazenamento persistente e rotina do scheduler.
- Instalação existente e backup para validar atualização sem perda de dados.
- Contas reais Meta/Google/WhatsApp/Cora, permissões dos provedores e homologação.
- API contratada/habilitada do Itaú e documentação de consulta geral disponível para a conta InfinitePay. Controle manual e PDFs já existem; sincronização desses dois bancos ainda não está implementada.
- Conferência visual em navegador/celular e teste de restauração na infraestrutura de destino.

## Ampliações ainda não implementadas

- WhatsApp: templates com cabeçalhos/botões/parâmetros nomeados, áudio enviado pelo próprio sistema e arquivos acima dos limites internos. Histórico paginado, templates de texto e JPEG/PNG/MP4/PDF já foram implementados, sujeitos à homologação.
- Meta Ads: criação de conjuntos/segmentação/criativos/anúncios completos dentro do NJA e edição de orçamento fora de BRL. Campanhas pausadas, alteração de estado/orçamento em BRL e indicadores por cliente estão implementados; finalize conjuntos e anúncios no Gerenciador da Meta.
- OAuth Meta para descoberta automática de contas: nesta versão, o gestor cadastra os IDs/tokens autorizados.
- Google Calendar: sincronização bidirecional e recorrência. A versão atual cria eventos únicos/links Meet e consulta o processamento.
- Assinatura eletrônica, emissão fiscal e conciliação bancária automática não estão implementadas.

Não há operação bancária de pagamento. Não confundir testes simulados com homologação de serviços externos. Estas pendências impedem classificar todo o escopo de integrações como concluído.
