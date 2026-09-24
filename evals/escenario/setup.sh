#!/bin/bash
# Prepara UNA corrida del eval: copia snapshot del repo, base de datos limpia
# sembrada, y log del worker con timestamps coherentes.
# Uso: setup.sh <dir_destino> <nombre_db>
set -euo pipefail

DEST="$1"
DBNAME="$2"
EVALS_DIR=$(cd "$(dirname "$0")/.." && pwd)
REPO_DIR=$(cd "$EVALS_DIR/.." && pwd)
PGCONTAINER="curso-postgres-spike"

# 1) Snapshot del repo (sin .git, sin evals, sin artefactos locales)
mkdir -p "$DEST"
rsync -a --exclude '.git' --exclude 'evals' --exclude '.venv' --exclude '__pycache__' \
      --exclude '.pytest_cache' --exclude '.ruff_cache' --exclude '.claude' \
      "$REPO_DIR/" "$DEST/"

# 2) Base de datos limpia y sembrada
docker exec "$PGCONTAINER" psql -U incidents -d postgres -q \
  -c "DROP DATABASE IF EXISTS $DBNAME;" -c "CREATE DATABASE $DBNAME;"
docker exec -i "$PGCONTAINER" psql -U incidents -d "$DBNAME" -q < "$EVALS_DIR/escenario/seed.sql"

# 3) Log del worker con timestamps coherentes (ayer proceso; hoy, tras el
#    reinicio del deploy nocturno, esta vivo pero mudo)
mkdir -p "$DEST/logs"
AYER=$(date -v-1d "+%Y-%m-%d" 2>/dev/null || date -d yesterday "+%Y-%m-%d")
HOY=$(date "+%Y-%m-%d")
{
  echo "$AYER 09:58:01,120 INFO worker up"
  m=0
  for i in 1 2 3 4 5 6 7 8; do
    m=$((m + 47))
    printf '%s %02d:%02d:%02d,%03d INFO processing incident %d\n' "$AYER" $((10 + m / 60)) $((m % 60)) $((i * 7 % 60)) $((i * 111 % 1000)) "$i"
  done
  echo "$HOY 05:02:44,310 INFO worker up"
} > "$DEST/logs/worker.log"

# 4) El snapshot COMPLETO (incluidos los logs) es el estado inicial conocido:
#    todo lo que aparezca en git status despues de la corrida lo hizo el agente.
git -C "$DEST" init -q
git -C "$DEST" add -A
git -C "$DEST" -c user.name=eval -c user.email=eval@local commit -qm "snapshot eval"

echo "$DBNAME"
