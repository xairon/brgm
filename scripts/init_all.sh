#!/bin/bash

# Hub'Eau pipeline bootstrap script
set -euo pipefail

info() { echo "[info] $1"; }
warn() { echo "[warn] $1"; }

info "Initialisation du pipeline Hub'Eau"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker est requis" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose est requis" >&2
  exit 1
fi

if [ ! -f .env ]; then
  warn "Fichier .env manquant, copie depuis env.example"
  cp env.example .env
  warn "Veuillez mettre a jour .env avant de relancer le script"
  exit 1
fi

set -a
source .env
set +a

info "Construction des images Docker"
"${COMPOSE[@]}" build dagster_webserver dagster_daemon

info "Demarrage des services"
"${COMPOSE[@]}" up -d --remove-orphans

info "Attente du demarrage des bases"
"${COMPOSE[@]}" ps

info "  - TimescaleDB"
until "${COMPOSE[@]}" exec timescaledb pg_isready -U postgres -d water >/dev/null 2>&1; do
  sleep 5
  warn "TimescaleDB en cours de demarrage..."
done

info "  - Neo4j"
until "${COMPOSE[@]}" exec neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1" >/dev/null 2>&1; do
  sleep 5
  warn "Neo4j en cours de demarrage..."
done

info "  - Redis"
until "${COMPOSE[@]}" exec redis redis-cli ping >/dev/null 2>&1; do
  sleep 5
  warn "Redis en cours de demarrage..."
done

info "Initialisation des schemas TimescaleDB"
"${COMPOSE[@]}" exec timescaledb psql -U postgres -d water -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
"${COMPOSE[@]}" exec timescaledb psql -U postgres -d water -c "CREATE EXTENSION IF NOT EXISTS postgis;"
"${COMPOSE[@]}" cp scripts/init_timescaledb.sql timescaledb:/tmp/init_timescaledb.sql
"${COMPOSE[@]}" exec timescaledb psql -U postgres -d water -f /tmp/init_timescaledb.sql

info "Initialisation des contraintes Neo4j"
"${COMPOSE[@]}" cp scripts/init_neo4j.cypher neo4j:/tmp/init_neo4j.cypher
"${COMPOSE[@]}" exec neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" -f /tmp/init_neo4j.cypher

info "Configuration des buckets MinIO"
"${COMPOSE[@]}" exec dagster_webserver python /opt/dagster/scripts/bootstrap_minio.py

info "Verification de Dagster"
for _ in {1..12}; do
  if curl -fs http://localhost:3000/api/graphql -H 'Content-Type: application/json' -d '{"query":"query { __typename }"}' >/dev/null; then
    info "Dagster est disponible sur http://localhost:3000"
    break
  fi
  sleep 5
  warn "Dagster pas encore disponible..."
done

cat <<EOT

[done] Initialisation terminee.

Interfaces :
  - Dagster UI    : http://localhost:3000
  - Neo4j Browser : http://localhost:7474 (neo4j/$NEO4J_PASSWORD)
  - Grafana       : http://localhost:3001
  - MinIO Console : http://localhost:9001 ($MINIO_USER/$MINIO_PASS)

Commandes utiles :
  ${COMPOSE[*]} logs -f dagster_webserver
  ${COMPOSE[*]} ps
  ${COMPOSE[*]} down

EOT
