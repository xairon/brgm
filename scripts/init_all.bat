@echo off
REM Script d'initialisation complète du projet Hub'Eau pour Windows
REM Ce script configure tous les services et initialise les bases de données

echo 🚀 Initialisation du projet Hub'Eau Data Integration Pipeline

REM Vérification des prérequis
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker n'est pas installé
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose n'est pas installé
    exit /b 1
)

REM Vérification du fichier .env
if not exist .env (
    echo ⚠️  Fichier .env manquant, copie depuis env.example
    copy env.example .env
    echo 📝 Veuillez éditer le fichier .env avec vos mots de passe
    echo    notepad .env
    echo.
    pause
)

echo 📦 Démarrage des services Docker...
docker-compose up -d

echo ⏳ Attente du démarrage des services...
timeout /t 30 /nobreak >nul

REM Vérification de la santé des services
echo 🔍 Vérification de la santé des services...

echo    - TimescaleDB...
:wait_timescale
docker-compose exec timescaledb pg_isready -U postgres -d water >nul 2>&1
if errorlevel 1 (
    echo      Attente de TimescaleDB...
    timeout /t 5 /nobreak >nul
    goto wait_timescale
)

echo    - Neo4j...
:wait_neo4j
docker-compose exec neo4j cypher-shell -u neo4j -p %NEO4J_PASSWORD% "RETURN 1" >nul 2>&1
if errorlevel 1 (
    echo      Attente de Neo4j...
    timeout /t 5 /nobreak >nul
    goto wait_neo4j
)

echo    - Redis...
:wait_redis
docker-compose exec redis redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo      Attente de Redis...
    timeout /t 5 /nobreak >nul
    goto wait_redis
)

echo ✅ Tous les services sont opérationnels

REM Initialisation des bases de données
echo 🗄️  Initialisation des bases de données...

echo    - Configuration de TimescaleDB...
docker-compose exec timescaledb psql -U postgres -d water -c "CREATE EXTENSION IF NOT EXISTS timescaledb; CREATE EXTENSION IF NOT EXISTS postgis;"

echo    - Exécution du schéma TimescaleDB...
docker cp scripts\init_timescaledb.sql $(docker-compose ps -q timescaledb):/tmp/init_timescaledb.sql
docker-compose exec timescaledb psql -U postgres -d water -f /tmp/init_timescaledb.sql

echo    - Configuration de Neo4j...
docker cp scripts\init_neo4j.cypher $(docker-compose ps -q neo4j):/tmp/init_neo4j.cypher
docker-compose exec neo4j cypher-shell -u neo4j -p %NEO4J_PASSWORD% -f /tmp/init_neo4j.cypher

echo    - Configuration de MinIO...
docker-compose exec minio sh -c "mc alias set local http://localhost:9000 %MINIO_USER% %MINIO_PASS% && mc mb local/bronze --ignore-existing && mc mb local/silver --ignore-existing && mc mb local/gold --ignore-existing"

echo 🐍 Installation des dépendances Python...
docker-compose exec dagster_webserver pip install -r /opt/dagster/app/requirements.txt

echo 🧪 Test de connexion Dagster...
timeout /t 10 /nobreak >nul
:wait_dagster
curl -f http://localhost:3000/api/graphql -H "Content-Type: application/json" -d "{\"query\":\"query { __typename }\"}" >nul 2>&1
if errorlevel 1 (
    echo      Attente de Dagster...
    timeout /t 5 /nobreak >nul
    goto wait_dagster
)

echo.
echo 🎉 Initialisation terminée avec succès !
echo.
echo 📊 Accès aux interfaces :
echo    - Dagster UI    : http://localhost:3000
echo    - Neo4j Browser : http://localhost:7474 (neo4j/%NEO4J_PASSWORD%)
echo    - Grafana       : http://localhost:3001 (admin/admin)
echo    - MinIO Console : http://localhost:9001 (%MINIO_USER%/%MINIO_PASS%)
echo.
echo 🚀 Pour lancer le premier job :
echo    1. Ouvrir http://localhost:3000
echo    2. Aller dans 'Assets'
echo    3. Sélectionner 'piezo_daily_job'
echo    4. Cliquer sur 'Materialize'
echo.
echo 📚 Documentation : voir README.md
echo.
echo 🔧 Commandes utiles :
echo    - Voir les logs : docker-compose logs -f [service]
echo    - Redémarrer : docker-compose restart [service]
echo    - Arrêter tout : docker-compose down

pause
