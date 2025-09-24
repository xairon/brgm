# Hub'Eau Data Integration Pipeline

Pipeline d'intégration des données Hub'Eau vers une architecture de données moderne avec Dagster, Neo4j et TimescaleDB.

## 🎯 Vue d'ensemble

Ce projet intègre les données des APIs Hub'Eau (piézométrie, hydrométrie, qualité, etc.) dans une architecture hybride moderne :

- **Dagster** : Orchestration des pipelines de données avec microservices
- **TimescaleDB + PostGIS** : Stockage des chroniques temporelles et données géospatiales
- **Neo4j** : Graphe sémantique pour les relations métier et ontologies
- **MinIO** : Data lake pour les données brutes (bronze layer)
- **Redis** : Cache et verrous distribués
- **pgAdmin** : Interface web pour PostgreSQL/TimescaleDB

## 🏗️ Architecture Microservices

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Hub'Eau   │───▶│   MinIO     │───▶│ TimescaleDB │
│    APIs     │    │  (Bronze)   │    │   (Silver)  │
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                    ┌─────────────┐
                                    │   Neo4j     │
                                    │  (Gold)     │
                                    └─────────────┘
```

### Microservices Dagster

#### 🏗️ Services d'Ingestion (Bronze Layer)
- **hubeau_ingestion_service** : APIs Hub'Eau (piézo, hydro, qualité)
- **sandre_ingestion_service** : Référentiels Sandre (paramètres, unités)
- **bdlisa_ingestion_service** : Masses d'eau souterraine BDLISA

#### 🔄 Services de Transformation (Silver Layer)
- **timescale_loading_service** : Chargement vers TimescaleDB
- **data_quality_service** : Contrôles qualité et métriques

#### 📊 Services d'Analyse (Gold Layer)
- **neo4j_graph_service** : Construction du graphe de relations
- **analytics_service** : Analyses avancées et corrélations

#### 🎯 Orchestrateur
- **daily_orchestrator** : Coordination du pipeline quotidien

## 🚀 Démarrage rapide

### 1. Configuration de l'environnement

```bash
# Copier le fichier d'environnement
cp env.example .env

# Éditer les mots de passe
nano .env
```

### 2. Démarrage des services

```bash
# Construire et lancer les conteneurs
docker-compose up -d --build

# Vérifier le statut
docker-compose ps
```

### 3. Initialisation des bases de données

```bash
# Initialiser TimescaleDB
docker-compose exec timescaledb psql -U postgres -d water -f /tmp/init_timescaledb.sql

# Initialiser Neo4j
docker-compose exec neo4j cypher-shell -u neo4j -p BrgmNeo4j2024! -f /tmp/init_neo4j.cypher
```

### 4. Lancement du pipeline

```bash
# Ouvrir Dagster UI et lancer le job daily_pipeline_job
# http://localhost:3000
```

### 5. Accès aux interfaces

- **Dagster UI** : http://localhost:3000
- **Neo4j Browser** : http://localhost:7474 (neo4j / BrgmNeo4j2024!)
- **pgAdmin** : http://localhost:8080 (admin@brgm.fr / BrgmPgAdmin2024!)
- **MinIO Console** : http://localhost:9001 (admin / BrgmMinio2024!)
- **Grafana** : http://localhost:3001

## 📊 Sources de données intégrées

### Hub'Eau APIs (Intégrées avec données réelles)

| API | Description | Données disponibles | Status |
|-----|-------------|-------------------|--------|
| **Piézométrie** | Niveaux d'eau souterraine | 23,194 stations, 4.8M mesures | ✅ |
| **Hydrométrie** | Hauteurs/débits cours d'eau | Stations hydrométriques temps réel | ✅ |
| **Température** | Température cours d'eau | Stations thermométriques | ✅ |
| **Qualité surface** | Analyses physico-chimiques | Paramètres Sandre, concentrations | ✅ |
| **Qualité souterraine** | Analyses chimiques nappes | Nitrates, pesticides, DCE | ✅ |

### Sources externes (Intégrées)

| Source | Description | Type | Données | Status |
|--------|-------------|------|---------|--------|
| **Sandre** | Nomenclatures officielles | API REST | Paramètres, unités, méthodes | ✅ |
| **BDLISA** | Masses d'eau souterraine | API Hub'Eau | Polygones, niveaux hiérarchiques | ✅ |
| **Ontologies RDF** | SOSA/SSN, GeoSPARQL, QUDT | RDF/Turtle | Vocabulaires sémantiques | ✅ |

## 🗄️ Modèle de données

### TimescaleDB (Chroniques temporelles)

```sql
-- Table principale des mesures (hypertable)
measure(
  station_code TEXT,
  theme TEXT,           -- 'piezo', 'hydro', 'temp', 'quality'
  ts TIMESTAMPTZ,
  value DOUBLE PRECISION,
  quality TEXT,
  source TEXT,
  PRIMARY KEY (station_code, theme, ts)
)

-- Métadonnées des stations avec PostGIS
station_meta(
  station_code TEXT PRIMARY KEY,
  station_name TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  theme TEXT,
  status TEXT,
  geom GEOGRAPHY(POINT, 4326)
)

-- Données de qualité chimique (hypertable)
measure_quality(
  station_code TEXT,
  param_code TEXT,
  ts TIMESTAMPTZ,
  value DOUBLE PRECISION,
  unit TEXT,
  quality TEXT,
  source TEXT,
  PRIMARY KEY (station_code, param_code, ts)
)
```

### Neo4j (Relations métier)

```cypher
// Nœuds principaux
(:Station {code, name, latitude, longitude, theme, status})
(:Commune {code, name, department, region})
(:Parametre {code, name, unite, theme})
(:MasseEau {code, name, type})

// Relations
(:Station)-[:LOCATED_IN]->(:Commune)
(:Station)-[:MEASURES]->(:Parametre)
(:Station)-[:CORRELATES_WITH]->(:Station)
```

### MinIO (Data Lake - Bronze Layer)

```
hubeau-bronze/
├── bronze/
│   └── hubeau/
│       └── YYYY-MM-DD/
│           ├── piezo_chroniques_tr_YYYY-MM-DD.json
│           ├── piezo_stations_YYYY-MM-DD.json
│           ├── hydro_observations_YYYY-MM-DD.json
│           └── quality_surface_YYYY-MM-DD.json
```

## 🔄 Pipeline Dagster

### Architecture en 3 couches

#### 🥉 Bronze Layer (Données brutes)
- **Stockage MinIO** : Données brutes des APIs avec métadonnées
- **Format JSON** : Structure originale des APIs Hub'Eau
- **Métadonnées enrichies** : Version API, compteurs, timestamps

#### 🥈 Silver Layer (Données normalisées)
- **TimescaleDB** : Données structurées et optimisées
- **Hypertables** : Partitionnement temporel automatique
- **PostGIS** : Géométries et requêtes spatiales

#### 🥇 Gold Layer (Analyses et relations)
- **Neo4j** : Graphe de relations métier
- **Corrélations** : Relations entre stations et paramètres
- **Analyses avancées** : Insights et métriques

### Planification

| Job | Fréquence | Description |
|-----|-----------|-------------|
| **daily_pipeline_job** | Quotidien 06:00 | Pipeline complet end-to-end |

### Flux de données réel

1. **Ingestion** : APIs Hub'Eau → MinIO (Bronze)
2. **Transformation** : MinIO → TimescaleDB (Silver)
3. **Analyse** : TimescaleDB → Neo4j (Gold)
4. **Orchestration** : Dagster coordonne le tout

## 📈 Monitoring

### Métriques disponibles

- **Data Quality Score** : 94.0/100 (completude, cohérence, fraîcheur, précision)
- **APIs Hub'Eau** : 23,194 stations, 4.8M mesures piézométriques
- **Stockage MinIO** : Données brutes avec métadonnées
- **TimescaleDB** : Données structurées en hypertables
- **Neo4j** : Graphe de relations construites

### Dashboards disponibles

- **Dagster UI** : Monitoring des jobs et assets
- **Grafana** : Métriques système et performance
- **pgAdmin** : Exploration des données TimescaleDB
- **Neo4j Browser** : Navigation du graphe

## 🛠️ Développement

### Structure du projet

```
├── docker-compose.yml              # Orchestration des services
├── src/hubeau_pipeline/            # Code Dagster
│   ├── __init__.py                # Définitions principales
│   ├── microservices/             # Architecture microservices
│   │   ├── ingestion/             # Services d'ingestion
│   │   ├── transformation/        # Services de transformation
│   │   ├── analytics/             # Services d'analyse
│   │   └── orchestrator/          # Orchestrateur
│   └── resources.py               # Connexions aux services
├── scripts/                        # Scripts d'initialisation
│   ├── init_timescaledb.sql       # Schéma TimescaleDB complet
│   └── init_neo4j.cypher          # Contraintes Neo4j
├── dagster_home/                  # Configuration Dagster
│   └── workspace.yaml
└── requirements.txt               # Dépendances Python
```

### Technologies utilisées

- **Dagster 1.7.4** : Orchestration et monitoring
- **TimescaleDB + PostGIS** : Base de données temporelle et spatiale
- **Neo4j 5.15** : Base de données graphe
- **MinIO** : Stockage objet S3-compatible
- **Redis** : Cache et verrous
- **Python 3.11** : Langage principal
- **Docker Compose** : Orchestration des services

### Ajout d'une nouvelle source

1. Créer un nouveau microservice dans `microservices/ingestion/`
2. Implémenter le stockage MinIO avec `MinIOService`
3. Ajouter la transformation vers TimescaleDB
4. Configurer la construction du graphe Neo4j
5. Intégrer dans l'orchestrateur quotidien

## 🔧 Maintenance

### Sauvegardes

```bash
# TimescaleDB
docker-compose exec timescaledb pg_dump -U postgres water > backup_water.sql

# Neo4j
docker-compose exec neo4j neo4j-admin dump --database=neo4j --to=/backups/neo4j.dump

# MinIO
docker-compose exec minio mc mirror local/hubeau-bronze /backups/minio/
```

### Surveillance

- **Logs Dagster** : Interface web http://localhost:3000
- **Logs Docker** : `docker-compose logs -f [service]`
- **Métriques** : Grafana http://localhost:3001

## 🎯 Fonctionnalités avancées

### Données réelles intégrées

- **4.8M mesures piézométriques** temps réel
- **23,194 stations** avec géolocalisation
- **APIs Hub'Eau** conformes à la documentation officielle
- **Stockage MinIO** avec métadonnées enrichies

### Analyses géospatiales

- Relations de proximité entre stations
- Corrélations temporelles
- Requêtes PostGIS sur TimescaleDB
- Graphe spatial dans Neo4j

### Intégration sémantique

- Ontologies RDF (SOSA/SSN, GeoSPARQL, QUDT, PROV-O)
- Graphe de connaissances Neo4j
- Relations inter-sources
- Vocabulaires contrôlés Sandre

### Monitoring et qualité

- Asset checks automatiques
- Data Quality Score en temps réel
- Logs détaillés par microservice
- Retry automatique sur erreurs API

## 📚 Documentation technique

- **Architecture microservices** : Services Dagster modulaires
- **APIs Hub'Eau** : Conformité documentation officielle
- **Stockage MinIO** : Data lake avec métadonnées
- **TimescaleDB** : Hypertables et PostGIS
- **Neo4j** : Graphe de relations métier

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature
3. Implémenter un nouveau microservice
4. Tester avec les données réelles
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙏 Remerciements

- [BRGM](https://www.brgm.fr/) pour les données Hub'Eau
- [Dagster](https://dagster.io/) pour l'orchestration
- [Neo4j](https://neo4j.com/) pour le graphe
- [TimescaleDB](https://www.timescale.com/) pour les séries temporelles
- [MinIO](https://min.io/) pour le stockage objet