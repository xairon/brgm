@echo off
setlocal enabledelayedexpansion

set "COMPOSE=docker compose"
%COMPOSE% version >nul 2>&1
if errorlevel 1 (
  docker-compose --version >nul 2>&1
  if errorlevel 1 (
    echo Docker Compose est requis
    exit /b 1
  )
  set "COMPOSE=docker-compose"
)

docker --version >nul 2>&1
if errorlevel 1 (
  echo Docker est requis
  exit /b 1
)

if not exist .env (
  echo Fichier .env manquant, copie depuis env.example
  copy /y env.example .env >nul
  echo Veuillez mettre a jour .env avant de relancer le script
  exit /b 1
)

call :load_env .env

echo Construction des images Docker
call %COMPOSE% build dagster_webserver dagster_daemon

echo Demarrage des services
call %COMPOSE% up -d --remove-orphans

echo Attente du demarrage des bases
call %COMPOSE% ps

echo   - TimescaleDB
:wait_timescaledb
call %COMPOSE% exec timescaledb pg_isready -U postgres -d water >nul 2>&1
if errorlevel 1 (
  timeout /t 5 /nobreak >nul
  goto wait_timescaledb
)

echo   - Neo4j
:wait_neo4j
call %COMPOSE% exec neo4j cypher-shell -u neo4j -p %NEO4J_PASSWORD% "RETURN 1" >nul 2>&1
if errorlevel 1 (
  timeout /t 5 /nobreak >nul
  goto wait_neo4j
)

echo   - Redis
:wait_redis
call %COMPOSE% exec redis redis-cli ping >nul 2>&1
if errorlevel 1 (
  timeout /t 5 /nobreak >nul
  goto wait_redis
)

echo Initialisation des schemas TimescaleDB
call %COMPOSE% exec timescaledb psql -U postgres -d water -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" >nul
call %COMPOSE% exec timescaledb psql -U postgres -d water -c "CREATE EXTENSION IF NOT EXISTS postgis;" >nul
call %COMPOSE% cp scripts/init_timescaledb.sql timescaledb:/tmp/init_timescaledb.sql >nul
call %COMPOSE% exec timescaledb psql -U postgres -d water -f /tmp/init_timescaledb.sql >nul

echo Initialisation des contraintes Neo4j
call %COMPOSE% cp scripts/init_neo4j.cypher neo4j:/tmp/init_neo4j.cypher >nul
call %COMPOSE% exec neo4j cypher-shell -u neo4j -p %NEO4J_PASSWORD% -f /tmp/init_neo4j.cypher >nul

echo Configuration des buckets MinIO
call %COMPOSE% exec dagster_webserver python /opt/dagster/scripts/bootstrap_minio.py

echo Verification de Dagster
for /l %%i in (1,1,12) do (
  curl -fs http://localhost:3000/api/graphql -H "Content-Type: application/json" -d "{\"query\":\"query { __typename }\"}" >nul 2>&1
  if not errorlevel 1 (
    goto dagster_ok
  )
  timeout /t 5 /nobreak >nul
)

echo Dagster n'est pas encore disponible. Consultez les logs.
exit /b 1

:dagster_ok
echo Dagster disponible sur http://localhost:3000

echo.
echo Initialisation terminee.
echo.
echo Dagster UI    : http://localhost:3000
echo Neo4j Browser : http://localhost:7474 (neo4j/%NEO4J_PASSWORD%)
echo Grafana       : http://localhost:3001
echo MinIO Console : http://localhost:9001 (%MINIO_USER%/%MINIO_PASS%)
echo.
echo Commandes utiles :
echo   %COMPOSE% logs -f dagster_webserver
echo   %COMPOSE% ps
echo   %COMPOSE% down

echo.
pause
exit /b 0

:load_env
for /f "usebackq tokens=*" %%i in (%1) do (
  for /f "tokens=1,2 delims==" %%a in ("%%i") do (
    if not "%%a"=="" (
      set "%%a=%%b"
    )
  )
)
exit /b 0
