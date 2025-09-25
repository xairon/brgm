# Architecture Optimisée - Hub'Eau Data Pipeline

## 🏗️ Structure Dagster Professionnelle

```
src/hubeau_pipeline/
├── __init__.py                    # Point d'entrée principal
├── definitions.py                 # Définitions Dagster centrales
├── resources.py                  # Resources partagées
├── assets/                       # Assets organisés par couche
│   ├── __init__.py
│   ├── bronze/                   # Ingestion optimisée
│   │   ├── hubeau_ingestion.py   # Hub'Eau avec retry/pagination
│   │   └── external_data.py      # BDLISA/Sandre réels
│   ├── silver/                   # Transformation optimisée
│   │   ├── timescale_optimized.py # TimescaleDB batch loading
│   │   └── postgis_neo4j.py      # PostGIS + Neo4j
│   └── gold/                     # Analyses
│       ├── production_analytics.py # Calculs réels
│       └── demo_showcase.py       # Démonstrations séparées
├── jobs/                         # Jobs par fonction métier
│   ├── ingestion.py             # Bronze → Silver
│   └── analytics.py             # Gold
├── schedules/
│   └── schedules.py             # Planification optimisée
└── sensors/
    └── sensors.py               # Monitoring
```

## 🚀 Fonctionnalités Professionnelles

### 1. Ingestion Hub'Eau Optimisée
- ✅ **Retry automatique** avec backoff exponentiel
- ✅ **Pagination complète** (jusqu'à 20K records/page)
- ✅ **Rate limiting** respectueux
- ✅ **Filtrage temporel** par partition
- ✅ **Gestion d'erreurs** robuste

```python
# Exemple: hubeau_piezo_bronze
- max_retries: 3
- backoff_factor: 2.0
- max_per_page: 20000
- timeout: 30s
```

### 2. Chargement TimescaleDB Optimisé
- ✅ **Batch loading** (1000 records/batch)
- ✅ **Upserts conditionnels** (ON CONFLICT)
- ✅ **Hypertables automatiques** 
- ✅ **Tables complètes** : `piezo_observations`, `measure_quality`, `piezo_quality_flags`

```python
# Tables TimescaleDB créées
- piezo_stations (référentiel)
- piezo_observations (hypertable)
- piezo_quality_flags (hypertable)
- measure_quality (hypertable) # Mentionné dans README
```

### 3. Données Réelles vs Démonstration
- ✅ **Production** : Calculs basés sur données effectives
- ✅ **Démonstration** : Assets séparés marqués `🎭 DEMO`
- ✅ **Isolation claire** : `production_assets` vs `demo_assets`

## 📊 Sources de Données Réelles

### Hub'Eau APIs (Production)
```
🌊 APIs intégrées avec retry/pagination:
- Piézométrie: /api/v1/niveaux_nappes
- Hydrométrie: /api/v1/hydrometrie  
- Qualité surface: /api/v1/qualite_eau_surface
- Qualité souterraine: /api/v1/qualite_eaux_souterraines
- Température: /api/v1/temperature
```

### BDLISA (Géographique)
```
🗺️ WFS Géographique → PostGIS:
- Source: https://bdlisa.eaufrance.fr/telechargement
- Masses d'eau souterraine
- Formations géologiques
- Limites administratives
```

### Sandre (Thésaurus)
```
📚 API Officielle → Neo4j:
- Source: https://api.sandre.eaufrance.fr/
- Paramètres physicochimiques
- Unités de mesure
- Méthodes d'analyse
- Supports et fractions
```

## 🎯 Jobs de Production

### 1. `hubeau_production_job`
- **Fréquence** : Quotidienne (6h)
- **Flow** : APIs → MinIO → TimescaleDB
- **Optimisations** : Retry, pagination, batch loading

### 2. `bdlisa_production_job`  
- **Fréquence** : Mensuelle (1er à 8h)
- **Flow** : WFS → MinIO → PostGIS
- **Optimisations** : Index spatial automatique

### 3. `sandre_production_job`
- **Fréquence** : Mensuelle (1er à 9h)  
- **Flow** : API → MinIO → Neo4j
- **Optimisations** : Graphe hiérarchique, index performance

### 4. `analytics_production_job`
- **Fréquence** : Quotidienne (10h)
- **Flow** : Ontologie SOSA + Analyses multi-sources
- **Base** : Données réelles des 3 sources

## 🔗 Ontologie SOSA (Production)

```cypher
# Mapping réel vers Neo4j
Stations Hub'Eau → sosa:Platform
Capteurs dérivés → sosa:Sensor  
Observations → sosa:Observation
Paramètres Sandre → sosa:ObservableProperty
Masses d'eau BDLISA → sosa:FeatureOfInterest
Méthodes → sosa:Procedure
```

## ⚠️ Assets de Démonstration

```python
# Clairement marqués pour éviter confusion
🎭 demo_quality_scores    # Scores simulés pour UI
🎭 demo_neo4j_showcase    # Graphe simulé pour visualisation
```

## 📈 Métriques de Performance

### Ingestion
- **Débit** : 20K records/page Hub'Eau
- **Resilience** : 3 retries avec backoff
- **Latence** : Rate limiting 0.1s entre appels

### Chargement  
- **TimescaleDB** : 1000 records/batch
- **PostGIS** : Index spatial automatique
- **Neo4j** : Relations hiérarchiques optimisées

### Monitoring
- Retry automatique sur échec
- Logs détaillés par étape
- Métriques de qualité intégrées

## 🚀 Prochaines Étapes

1. **MinIO réel** : Remplacer simulations stockage
2. **Connexions DB** : Config production 
3. **Monitoring avancé** : Sensors Dagster
4. **Tests d'intégration** : Validation end-to-end
5. **Documentation API** : Swagger/OpenAPI
