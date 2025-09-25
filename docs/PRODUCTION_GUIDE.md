# Guide de Production - Hub'Eau Pipeline

## 🔧 Configuration Production

### 1. Variables d'Environnement
```env
# MinIO (Bronze Layer)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=BrgmMinio2024!
MINIO_BUCKET_BRONZE=hubeau-bronze

# TimescaleDB (Silver Layer)
TIMESCALE_HOST=timescaledb
TIMESCALE_PORT=5432
TIMESCALE_DB=water_timeseries
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=BrgmPostgres2024!

# PostGIS (Silver Layer - Geographic)
POSTGIS_HOST=postgis
POSTGIS_PORT=5432
POSTGIS_DB=water_geo
POSTGIS_USER=postgres
POSTGIS_PASSWORD=BrgmPostgres2024!

# Neo4j (Silver/Gold Layer)
NEO4J_HOST=neo4j
NEO4J_PORT=7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=BrgmNeo4j2024!
```

### 2. Configuration APIs
```python
# Hub'Eau Configuration
HUBEAU_BASE_URLS = {
    "piezo": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes",
    "hydro": "https://hubeau.eaufrance.fr/api/v1/hydrometrie",
    "quality_surface": "https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface",
    "quality_groundwater": "https://hubeau.eaufrance.fr/api/v1/qualite_eaux_souterraines",
    "temperature": "https://hubeau.eaufrance.fr/api/v1/temperature"
}

# Retry Configuration
RETRY_CONFIG = {
    "max_retries": 3,
    "backoff_factor": 2.0,
    "timeout": 30
}

# Pagination Configuration  
PAGINATION_CONFIG = {
    "max_per_page": 20000,
    "rate_limit_seconds": 0.1
}
```

## 🗄️ Schémas de Base de Données

### TimescaleDB Tables

#### 1. piezo_stations (Référentiel)
```sql
CREATE TABLE piezo_stations (
    station_id VARCHAR(50) PRIMARY KEY,
    station_name VARCHAR(200),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude INTEGER,
    aquifer_name VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 2. piezo_observations (Hypertable)
```sql
CREATE TABLE piezo_observations (
    station_id VARCHAR(50),
    timestamp TIMESTAMP NOT NULL,
    water_level DOUBLE PRECISION,
    measurement_method VARCHAR(50),
    quality_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (station_id, timestamp)
);

-- Hypertable
SELECT create_hypertable('piezo_observations', 'timestamp', 
                        chunk_time_interval => INTERVAL '1 day');
```

#### 3. measure_quality (Hypertable)
```sql
CREATE TABLE measure_quality (
    station_id VARCHAR(50),
    timestamp TIMESTAMP NOT NULL,
    parameter_code VARCHAR(50),
    parameter_name VARCHAR(200),
    value DOUBLE PRECISION,
    unit VARCHAR(50),
    detection_limit DOUBLE PRECISION,
    quantification_limit DOUBLE PRECISION,
    measurement_method VARCHAR(100),
    laboratory VARCHAR(100),
    quality_code VARCHAR(10),
    validation_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (station_id, timestamp, parameter_code)
);

-- Hypertable
SELECT create_hypertable('measure_quality', 'timestamp',
                        chunk_time_interval => INTERVAL '1 day');
```

### PostGIS Tables

#### BDLISA Géographique
```sql
-- Masses d'eau souterraine
CREATE TABLE bdlisa_masses_eau_souterraine (
    id VARCHAR(50) PRIMARY KEY,
    nom VARCHAR(200),
    type_masse_eau VARCHAR(100),
    bassin_district VARCHAR(100),
    geom GEOMETRY(MULTIPOLYGON, 4326)
);

CREATE INDEX idx_masses_eau_geom ON bdlisa_masses_eau_souterraine USING GIST(geom);

-- Formations géologiques
CREATE TABLE bdlisa_formations_geologiques (
    id VARCHAR(50) PRIMARY KEY,
    formation_name VARCHAR(200),
    age_geologique VARCHAR(100),
    lithologie VARCHAR(200),
    geom GEOMETRY(MULTIPOLYGON, 4326)
);
```

### Neo4j Schema

#### Sandre Thésaurus
```cypher
// Paramètres
CREATE (p:SandreParametres {
    code: "1340",
    libelle: "Nitrates",
    definition: "Concentration en nitrates",
    unite_defaut: "mg/L",
    fraction_defaut: "Dissoute"
});

// Unités
CREATE (u:SandreUnites {
    code: "133",
    libelle: "mg/L",
    symbole: "mg/L",
    definition: "Milligramme par litre"
});

// Relations
CREATE (p)-[:MESURE_AVEC_UNITE]->(u);
```

#### Ontologie SOSA
```cypher
// Platform (Stations)
CREATE (platform:Platform {
    id: "BSS00123456",
    name: "Station Piézo X",
    latitude: 46.1234,
    longitude: 2.5678
});

// Sensor
CREATE (sensor:Sensor {
    id: "SENSOR_PIEZO_001",
    type: "Piézomètre automatique"
});

// Relations SOSA
CREATE (platform)-[:hosts]->(sensor);
```

## 📋 Processus de Déploiement

### 1. Préparation
```bash
# Build des images
docker-compose build --no-cache

# Vérification des volumes
docker volume ls | grep brgm

# Initialisation des bases
docker-compose up -d postgres timescaledb neo4j minio
```

### 2. Initialisation des Schémas
```bash
# TimescaleDB
docker exec -it brgm-timescaledb-1 psql -U postgres -d water_timeseries -f /init/timescale_schema.sql

# PostGIS  
docker exec -it brgm-postgis-1 psql -U postgres -d water_geo -f /init/postgis_schema.sql

# Neo4j
docker exec -it brgm-neo4j-1 cypher-shell -u neo4j -p BrgmNeo4j2024! -f /init/neo4j_schema.cypher
```

### 3. Démarrage Dagster
```bash
# Démarrage orchestrateur
docker-compose up -d dagster_webserver dagster_daemon

# Vérification
curl http://localhost:3000/health
```

## 🔍 Monitoring et Debugging

### 1. Logs Dagster
```bash
# Logs webserver
docker-compose logs -f dagster_webserver

# Logs daemon  
docker-compose logs -f dagster_daemon

# Logs par asset
docker-compose exec dagster_webserver dagster asset materialize --select hubeau_piezo_bronze
```

### 2. Monitoring Base de Données
```sql
-- TimescaleDB - Chunks et compression
SELECT * FROM timescaledb_information.chunks;
SELECT * FROM timescaledb_information.compression_settings;

-- Statistiques ingestion
SELECT 
    DATE(timestamp) as day,
    COUNT(*) as observations,
    COUNT(DISTINCT station_id) as stations
FROM piezo_observations 
GROUP BY DATE(timestamp)
ORDER BY day DESC;
```

### 3. Monitoring Neo4j
```cypher
// Statistiques nœuds
MATCH (n) RETURN labels(n), count(n);

// Performance requêtes
:queries;

// Index usage
CALL db.indexes();
```

## ⚡ Optimisations Performance

### 1. TimescaleDB
```sql
-- Compression automatique
ALTER TABLE piezo_observations SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'station_id'
);

-- Politique rétention
SELECT add_retention_policy('piezo_observations', INTERVAL '2 years');

-- Index additionnels
CREATE INDEX idx_piezo_station_time ON piezo_observations (station_id, timestamp DESC);
```

### 2. PostGIS
```sql
-- Index spatiaux additionnels
CREATE INDEX idx_masses_eau_bbox ON bdlisa_masses_eau_souterraine USING GIST(ST_Envelope(geom));

-- Clustering spatial
CLUSTER bdlisa_masses_eau_souterraine USING idx_masses_eau_geom;
```

### 3. Neo4j
```cypher
// Index sur propriétés fréquentes
CREATE INDEX FOR (p:SandreParametres) ON (p.code);
CREATE INDEX FOR (s:Station) ON (s.station_id);
CREATE INDEX FOR (o:Observation) ON (o.timestamp);

// Contraintes unicité
CREATE CONSTRAINT FOR (p:SandreParametres) REQUIRE p.code IS UNIQUE;
```

## 🚨 Gestion des Erreurs

### 1. Retry Policies
```python
# Configuration par asset
@asset(retry_policy=RetryPolicy(max_retries=3, delay=60))
def hubeau_piezo_bronze(context):
    # Logique avec gestion d'erreur
    pass
```

### 2. Monitoring d'Échecs
```python
# Sensors de surveillance
@sensor(job=hubeau_production_job)
def hubeau_failure_sensor(context):
    # Notification sur échec
    pass
```

### 3. Alertes
- **Échec ingestion** : Email + Slack
- **Données manquantes** : Dashboard Grafana
- **Performance dégradée** : Métriques Prometheus
