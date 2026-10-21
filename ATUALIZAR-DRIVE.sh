#!/usr/bin/env bash
set -euo pipefail
origem=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
destino=${1:-/www/wwwroot/nja-system}
cd -- "$destino"
destino=$(pwd)
arquivos=(integrations.py drive_gallery.py static/enterprise.js static/enterprise.css static/sw.js)
for arquivo in "${arquivos[@]}"; do
  test -f "$origem/$arquivo" || { echo "Arquivo da atualização ausente: $arquivo"; exit 1; }
done
test -f compose.yaml && test -f .env || { echo 'A pasta de destino precisa conter compose.yaml e .env.'; exit 1; }
if [ "$origem" = "$destino" ]; then
  echo 'Extraia a atualização em uma pasta separada da instalação antes de executar.'
  exit 1
fi
docker compose config --quiet
echo 'Criando backup do banco e dos anexos...'
docker compose exec -T web python manage.py backup
backup_codigo=$(mktemp -d "${destino%/*}/nja-backup-drive-XXXXXXXX")
for arquivo in "${arquivos[@]}"; do
  if [ -f "$destino/$arquivo" ]; then
    mkdir -p -- "$backup_codigo/$(dirname -- "$arquivo")"
    cp -p -- "$destino/$arquivo" "$backup_codigo/$arquivo"
  fi
done
for arquivo in "${arquivos[@]}"; do cp -- "$origem/$arquivo" "$destino/$arquivo"; done
echo "Backup do código: $backup_codigo"
echo 'Aplicando a atualização. Pode haver uma breve interrupção...'
docker compose up -d --build
docker compose ps
echo 'Atualização aplicada. Recarregue a página com Ctrl+Shift+R e teste Google Drive > Miniaturas.'
