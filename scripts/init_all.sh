#!/bin/bash

# Script d'initialisation complète du projet Hub'Eau
# Ce script configure tous les services et initialise les bases de données

set -e

echo "🚀 Initialisation du projet Hub'Eau Data Integration Pipeline"

# Vérification des prérequis
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose n'est pas installé"
    exit 1
fi

# Vérification du fichier .env
if [ ! -f .env ]; then
    echo "⚠️  Fichier .env manquant, copie depuis env.example"
    cp env.example .env
    echo "📝 Veuillez éditer le fichier .env avec vos mots de passe"
    echo "   nano .env"
    echo ""
    read -p "Appuyez sur Entrée une fois le fichier .env configuré..."
fi

# Chargement des variables d'environnement
source .env

echo "📦 Démarrage des services Docker..."
docker-compose up -d

echo "⏳ Attente du démarrage des services..."
sleep 30

# Vérification de la santé des services
echo "🔍 Vérification de la santé des services..."

# TimescaleDB
echo "   - TimescaleDB..."
until docker-compose exec timescaledb pg_isready -U postgres -d water; do
    echo "     Attente de TimescaleDB..."
    sleep 5
done

# Neo4j
echo "   - Neo4j..."
until docker-compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD "RETURN 1"; do
    echo "     Attente de Neo4j..."
    sleep 5
done

# Redis
echo "   - Redis..."
until docker-compose exec redis redis-cli ping; do
    echo "     Attente de Redis..."
    sleep 5
done

echo "✅ Tous les services sont opérationnels"

# Initialisation des bases de données
echo "🗄️  Initialisation des bases de données..."

# TimescaleDB
echo "   - Configuration de TimescaleDB..."
docker-compose exec timescaledb psql -U postgres -d water -c "
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
"

# Copie et exécution du script d'initialisation TimescaleDB
echo "   - Exécution du schéma TimescaleDB..."
docker cp scripts/init_timescaledb.sql $(docker-compose ps -q timescaledb):/tmp/init_timescaledb.sql
docker-compose exec timescaledb psql -U postgres -d water -f /tmp/init_timescaledb.sql

# Neo4j
echo "   - Configuration de Neo4j..."
docker cp scripts/init_neo4j.cypher $(docker-compose ps -q neo4j):/tmp/init_neo4j.cypher
docker-compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD -f /tmp/init_neo4j.cypher

# Création du bucket MinIO
echo "   - Configuration de MinIO..."
docker-compose exec minio sh -c "
mc alias set local http://localhost:9000 $MINIO_USER $MINIO_PASS
mc mb local/bronze --ignore-existing
mc mb local/silver --ignore-existing
mc mb local/gold --ignore-existing
"

# Installation des dépendances Python pour Dagster
echo "🐍 Installation des dépendances Python..."
docker-compose exec dagster_webserver pip install -r /opt/dagster/app/requirements.txt

# Test de connexion Dagster
echo "🧪 Test de connexion Dagster..."
sleep 10
until curl -f http://localhost:3000/api/graphql -H "Content-Type: application/json" -d '{"query":"query { __typename }"}'; do
    echo "     Attente de Dagster..."
    sleep 5
done

echo ""
echo "🎉 Initialisation terminée avec succès !"
echo ""
echo "📊 Accès aux interfaces :"
echo "   - Dagster UI    : http://localhost:3000"
echo "   - Neo4j Browser : http://localhost:7474 (neo4j/$NEO4J_PASSWORD)"
echo "   - Grafana       : http://localhost:3001 (admin/admin)"
echo "   - MinIO Console : http://localhost:9001 ($MINIO_USER/$MINIO_PASS)"
echo ""
echo "🚀 Pour lancer le premier job :"
echo "   1. Ouvrir http://localhost:3000"
echo "   2. Aller dans 'Assets'"
echo "   3. Sélectionner 'piezo_daily_job'"
echo "   4. Cliquer sur 'Materialize'"
echo ""
echo "📚 Documentation : voir README.md"
echo ""
echo "🔧 Commandes utiles :"
echo "   - Voir les logs : docker-compose logs -f [service]"
echo "   - Redémarrer : docker-compose restart [service]"
echo "   - Arrêter tout : docker-compose down"
