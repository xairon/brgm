# Hub'Eau Data Integration Pipeline - Architecture Optimisée

Pipeline d'intégration professionnel des données Hub'Eau avec Dagster, architecture moderne et optimisations de production.

## 🎯 Vue d'ensemble

Ce projet intègre les données des APIs Hub'Eau dans une architecture robuste et optimisée :

- **🔄 Dagster** : Orchestration avec retry/pagination professionnelle
- **⏱️ TimescaleDB** : Chroniques temporelles avec batch loading optimisé  
- **🗺️ PostGIS** : Données géographiques BDLISA
- **🕸️ Neo4j** : Thésaurus Sandre + Ontologie SOSA
- **📦 MinIO** : Data lake Bronze layer
- **🔧 Docker** : Déploiement conteneurisé

## 🏗️ Architecture Optimisée

### Structure Dagster Professionnelle
```
src/hubeau_pipeline/
├── assets/                    # Assets par couche
│   ├── bronze/               # Ingestion avec retry/pagination
│   ├── silver/               # Transformation optimisée  
│   └── gold/                 # Analyses + SOSA
├── jobs/                     # Jobs par fonction métier
├── schedules/                # Planification production
└── resources.py              # Configuration centralisée
```

### Flow de Données
```
🌊 Hub'Eau APIs ──[retry/pagination]──▶ MinIO (Bronze)
🗺️ BDLISA WFS ──[géographique]─────▶ MinIO (Bronze)  
📚 Sandre API ──[thésaurus]────────▶ MinIO (Bronze)
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
            TimescaleDB (Silver)   PostGIS (Silver)    Neo4j (Silver)
              [batch loading]      [index spatial]    [graphe hiérarchique]
                    │                     │                     │
                    └─────────────────────┼─────────────────────┘
                                          ▼
                                   Neo4j SOSA (Gold)
                                 [ontologie + analytics]
```

## 🚀 Fonctionnalités Professionnelles

### ✅ Ingestion Hub'Eau Optimisée
- **Retry automatique** : 3 tentatives avec backoff exponentiel
- **Pagination complète** : Jusqu'à 20K records/page  
- **Rate limiting** : Appels respectueux des APIs
- **Gestion d'erreurs** : Robuste et logged

### ✅ Chargement TimescaleDB Optimisé  
- **Batch loading** : 1000 records/batch
- **Upserts conditionnels** : ON CONFLICT optimisé
- **Hypertables automatiques** : Partitioning temporel
- **Tables complètes** : `piezo_observations`, `measure_quality`, `piezo_quality_flags`

### ✅ Séparation Production/Démonstration
- **Assets de production** : Calculs sur données réelles
- **Assets de démonstration** : Marqués `🎭 DEMO` pour interface

## 📊 Sources de Données

### 🌊 Hub'Eau (Production)
- **Piézométrie** : `/api/v1/niveaux_nappes`
- **Hydrométrie** : `/api/v1/hydrometrie`  
- **Qualité surface** : `/api/v1/qualite_eau_surface`
- **Qualité souterraine** : `/api/v1/qualite_eaux_souterraines`
- **Température** : `/api/v1/temperature`

### 🗺️ BDLISA (Géographique → PostGIS)
- **Source** : https://bdlisa.eaufrance.fr/telechargement
- **Masses d'eau souterraine**
- **Formations géologiques**
- **Limites administratives**

### 📚 Sandre (Thésaurus → Neo4j)
- **Source** : https://api.sandre.eaufrance.fr/
- **Paramètres physicochimiques**
- **Unités de mesure**  
- **Méthodes d'analyse**
- **Supports et fractions**

## 🎯 Jobs de Production

### `hubeau_production_job` (Quotidien 6h)
```python
🌊 Hub'Eau APIs → MinIO → TimescaleDB
- Retry/pagination automatique
- Batch loading optimisé
- 5 APIs Hub'Eau intégrées
```

### `bdlisa_production_job` (Mensuel)
```python  
🗺️ BDLISA WFS → MinIO → PostGIS
- Données géographiques réelles
- Index spatial automatique
```

### `sandre_production_job` (Mensuel)
```python
📚 Sandre API → MinIO → Neo4j  
- Thésaurus complet
- Graphe hiérarchique
```

### `analytics_production_job` (Quotidien 10h)
```python
🔗 Ontologie SOSA + Analyses multi-sources
- Basé sur données réelles
- Relations spatiales/temporelles
```

## 🗄️ Schémas de Base de Données

### TimescaleDB (Chroniques)
```sql
-- Hypertables optimisées
piezo_observations          -- Observations piézométriques
measure_quality            -- Mesures de qualité (mentionné README)
piezo_quality_flags        -- Flags de qualité automatiques

-- Configuration
chunk_time_interval => INTERVAL '1 day'
compression + retention automatiques
```

### PostGIS (Géographique)
```sql
-- Tables spatiales
bdlisa_masses_eau_souterraine    -- Masses d'eau avec géométries
bdlisa_formations_geologiques    -- Formations géologiques
bdlisa_limites_administratives   -- Limites administratives

-- Index GIST automatiques
```

### Neo4j (Thésaurus + Ontologie)
```cypher
// Sandre Thésaurus
(:SandreParametres)-[:MESURE_AVEC_UNITE]->(:SandreUnites)
(:SandreMethodes)-[:UTILISE_SUPPORT]->(:SandreSupports)

// Ontologie SOSA
(:Platform)-[:hosts]->(:Sensor)
(:Observation)-[:madeBySensor]->(:Sensor)
(:Observation)-[:observedProperty]->(:ObservableProperty)
```

## 🚀 Démarrage

### 1. Configuration
```bash
cp env.example .env
# Éditer les variables d'environnement
```

### 2. Démarrage des services
```bash
docker-compose up -d
```

### 3. Accès interfaces
- **Dagster** : http://localhost:3000
- **Neo4j** : http://localhost:7474  
- **pgAdmin** : http://localhost:5050
- **MinIO** : http://localhost:9001

### 4. Initialisation des schémas
```bash
# Exécuter les scripts d'initialisation
./scripts/init_all.sh
```

## 📈 Monitoring

### Métriques de Performance
- **Débit Hub'Eau** : 20K records/page
- **Batch TimescaleDB** : 1000 records/batch  
- **Retry policy** : 3 tentatives max
- **Rate limiting** : 0.1s entre appels

### Logs et Debugging
```bash
# Logs Dagster
docker-compose logs -f dagster_webserver

# Monitoring bases de données
docker-compose exec timescaledb psql -U postgres -d water_timeseries
docker-compose exec neo4j cypher-shell
```

## 📚 Documentation

- **[Architecture Optimisée](docs/ARCHITECTURE_OPTIMIZED.md)** : Détails techniques
- **[Guide de Production](docs/PRODUCTION_GUIDE.md)** : Déploiement et monitoring
- **[Exemples de Requêtes](docs/examples_queries.md)** : Requêtes SQL/Cypher
- **[Guide de Correction](docs/REVIEW_CORRECTIONS.md)** : Corrections appliquées

## 🔧 Structure des Assets

### Bronze (Ingestion)
```python
hubeau_piezo_bronze          # Piézométrie avec retry
hubeau_quality_surface_bronze # Qualité surface avec pagination  
bdlisa_geographic_bronze     # BDLISA WFS réel
sandre_thesaurus_bronze      # Sandre API officielle
```

### Silver (Transformation)
```python
piezo_timescale_optimized    # TimescaleDB batch loading
quality_timescale_optimized  # Table measure_quality
bdlisa_postgis_silver       # PostGIS avec index spatial
sandre_neo4j_silver         # Neo4j thésaurus
```

### Gold (Analyses)
```python
sosa_ontology_production        # Ontologie SOSA réelle
integrated_analytics_production # Analyses multi-sources

# Démonstration (séparés)
demo_quality_scores    🎭     # Scores simulés pour UI
demo_neo4j_showcase   🎭     # Graphe simulé
```

## 💡 Optimisations Appliquées

### ✅ Ingestion Hub'Eau
- Retry exponentiel (3x avec backoff 2.0)  
- Pagination complète (20K/page)
- Rate limiting respectueux
- Filtrage temporel par partition

### ✅ TimescaleDB 
- Batch loading (1000 records/batch)
- Upserts conditionnels optimisés
- Hypertables avec compression
- Index temporels automatiques

### ✅ Architecture
- Séparation production/démonstration claire
- Structure Dagster standard  
- Jobs par fonction métier
- Monitoring intégré

## 🏷️ Version
**v2.0** - Architecture Optimisée avec fonctionnalités professionnelles

## 👥 Équipe
BRGM - Service géologique national