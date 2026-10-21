#!/usr/bin/env bash
# NJA 1.17 — update code only, preserving the live Compose project and data volume.
set -euo pipefail
origem=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
destino=${1:-/www/wwwroot/nja-system}
cd -- "$destino"
destino=$(pwd)
if [ "$origem" = "$destino" ]; then
  echo 'Extraia o pacote em uma pasta separada antes de executar. Nada foi alterado.'
  exit 1
fi
for arquivo in app.py interaction_updates.py drive_gallery.py requirements.txt static/index.html static/interaction-updates.js static/interaction-updates.css static/celebrations.js; do
  test -f "$origem/$arquivo" || { echo "Pacote incompleto: $arquivo. Nada foi alterado."; exit 1; }
done
test -f compose.yaml && test -f .env || { echo 'Destino inválido: compose.yaml ou .env ausente.'; exit 1; }
docker compose config --quiet
if [ -z "$(docker compose ps -q web)" ]; then
  echo 'O serviço web não está ativo neste projeto. Confira o destino antes de atualizar.'
  exit 1
fi
backup_root=$(mktemp -d "${destino%/*}/nja-backup-v117-XXXXXXXX")
chmod 700 "$backup_root"
backup_interno="/tmp/$(basename "$backup_root")-dados"
echo '1/5 Criando backup consistente do banco, anexos e chave das integrações...'
docker compose exec -T web python manage.py backup --output "$backup_interno"
container_web=$(docker compose ps -q web)
docker cp "$container_web:$backup_interno" "$backup_root/dados"
test -s "$backup_root/dados/nja.sqlite3" || { echo 'Backup não encontrado. Atualização interrompida.'; exit 1; }
echo '2/5 Preservando o código atual e as configurações...'
tar --exclude='./data' --exclude='./.venv' --exclude='./__pycache__' --exclude='./tests/__pycache__' --exclude='./backups' -czf "$backup_root/codigo-e-configuracoes.tar.gz" -C "$destino" .
echo "BACKUP DA ATUALIZAÇÃO: $backup_root"
echo '3/5 Copiando o código. .env e arquivos Compose serão preservados...'
for arquivo in "$origem"/*.py; do cp -- "$arquivo" "$destino/$(basename "$arquivo")"; done
cp -- "$origem/requirements.txt" "$destino/requirements.txt"
cp -R -- "$origem/static/." "$destino/static/"
for arquivo in "$origem"/*.md; do cp -- "$arquivo" "$destino/$(basename "$arquivo")"; done
echo '4/5 Construindo as imagens atualizadas...'
docker compose build web scheduler
echo '5/5 Reiniciando web e scheduler com o mesmo volume de dados...'
docker compose up -d --no-build web scheduler
docker compose ps
echo "Backup preservado em: $backup_root"
echo 'Abra o sistema, pressione Ctrl+Shift+R e execute o checklist de validação do GUIA-ATUALIZACAO-VPS-v1.17.md.'
