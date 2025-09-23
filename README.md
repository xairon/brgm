# Hub'Eau Data Integration Pipeline

Pipeline d'intégration des données Hub'Eau vers une architecture de données moderne avec Dagster, Neo4j et TimescaleDB.

## 🎯 Vue d'ensemble

Ce projet intègre les données des APIs Hub'Eau (piézométrie, hydrométrie, qualité, etc.) dans une architecture hybride :

- **Dagster** : Orchestration des pipelines de données
- **TimescaleDB + PostGIS** : Stockage des chroniques temporelles et données géospatiales
- **Neo4j** : Graphe sémantique pour les relations métier et ontologies
- **MinIO** : Data lake pour les données brutes (bronze layer)
- **Redis** : Cache et verrous distribués

## 🏗️ Architecture

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
# Lancer tous les services
docker-compose up -d

# Vérifier le statut
docker-compose ps
```

### 3. Initialisation des bases de données

```bash
# Initialiser TimescaleDB
docker-compose exec timescaledb psql -U postgres -d water -f /scripts/init_timescaledb.sql

# Initialiser Neo4j
docker-compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD -f /scripts/init_neo4j.cypher
```

### 4. Lancement du premier job

```bash
# Option 1: Via l'interface Dagster
# Ouvrir http://localhost:3000 et exécuter station_meta_job

# Option 2: Via script d'initialisation automatique
# Linux/Mac :
./scripts/init_all.sh
# Windows :
scripts\init_all.bat
```

### 5. Accès aux interfaces

- **Dagster UI** : http://localhost:3000
- **Neo4j Browser** : http://localhost:7474
- **Grafana** : http://localhost:3001
- **MinIO Console** : http://localhost:9001

## 📊 Sources de données intégrées

### Hub'Eau APIs (Intégrées)

| API | Description | Fréquence | Données | Status |
|-----|-------------|-----------|---------|--------|
| **Piézométrie** | Niveaux d'eau souterraine | Quotidien | Stations, mesures, métadonnées | ✅ |
| **Hydrométrie** | Hauteurs/débits cours d'eau | 15min | Stations hydrométriques | ✅ |
| **Température** | Température cours d'eau | 15min | Stations thermométriques | ✅ |
| **Écoulement** | État d'écoulement cours d'eau | Quotidien | Assecs, intermittence | ✅ |
| **Hydrobiologie** | Indices biologiques | Annuel | IBGN, IBD, I2M2 | ✅ |
| **Qualité eaux surface v1** | Analyses physico-chimiques | Mensuel | Paramètres, concentrations | ✅ |
| **Qualité eaux surface v2** | Analyses physico-chimiques (nouveau) | Mensuel | Paramètres Sandre, unités | ✅ |
| **Qualité eaux souterraines v1** | Analyses chimiques nappes | Semestriel | Nitrates, pesticides, DCE | ✅ |
| **Qualité eaux souterraines v2** | Analyses chimiques nappes (nouveau) | Semestriel | Paramètres Sandre, unités | ✅ |
| **Prélèvements** | Volumes prélevés | Annuel | Déclarations usagers | ✅ |

### Sources externes (Intégrées)

| Source | Description | Type | Données | Status |
|--------|-------------|------|---------|--------|
| **Sandre** | Nomenclatures officielles | API REST | Paramètres, unités, méthodes | ✅ |
| **Sandre Thésaurus** | Thésaurus paramètres (nouveau) | API REST | Codes paramètres, familles, unités | ✅ |
| **BDLISA** | Masses d'eau souterraine | WFS | Polygones, niveaux hiérarchiques | ✅ |
| **InfoTerre** | Forages et géologie | WFS | Forages BSS, cartes géologiques | ✅ |
| **CarMen** | Chimie agrégée | API REST | Données DCE agrégées | ✅ |
| **Ontologies RDF** | SOSA/SSN, GeoSPARQL, QUDT, PROV-O | RDF/Turtle | Vocabulaires sémantiques | ✅ |
| **Météo (Squelette)** | Données météorologiques | Flexible | Précipitations, température, ETP | 🔄 |

### Sources externes (Préparées)

- **Météo-France SAFRAN** : Pluie, température, ETP (nécessite partenariat)
- **ERA5-Land** : Données climatiques globales
- **Sentinel-2** : NDVI, température de surface
- **GRACE-FO** : Anomalies masse d'eau
- **MétéEAU Nappes** : Prévisions piézométriques BRGM

## 🗄️ Modèle de données

### TimescaleDB (Chroniques temporelles)

```sql
-- Table principale des mesures
measure(
  station_code TEXT,
  theme TEXT,           -- 'piezo', 'hydro', 'temp', 'quality'
  ts TIMESTAMPTZ,
  value DOUBLE PRECISION,
  quality TEXT,
  source TEXT
)

-- Métadonnées des stations
station_meta(
  station_code TEXT PRIMARY KEY,
  label TEXT,
  type TEXT,
  geom GEOGRAPHY(POINT, 4326),
  masse_eau_code TEXT
)
```

### Neo4j (Relations métier)

```cypher
// Nœuds principaux
(:Station {code, label, type, lat, lon})
(:MasseEau {code, libelle, niveau})
(:Commune {insee, nom})
(:Parametre {code, libelle, unite})

// Relations
(:Station)-[:IN_MASSE]->(:MasseEau)
(:Station)-[:IN_COMMUNE]->(:Commune)
(:Station)-[:NEAR {distance_km}]->(:Station)
```

## 🔄 Pipeline Dagster

### Architecture en 3 couches

#### 🥉 Bronze Layer (Données brutes)
- **piezo_raw** : Piézométrie Hub'Eau
- **hydro_raw** : Hydrométrie Hub'Eau
- **temperature_raw** : Température cours d'eau
- **ecoulement_raw** : Écoulement cours d'eau
- **hydrobiologie_raw** : Indices biologiques
- **quality_surface_raw** : Qualité eaux de surface v1
- **quality_groundwater_raw** : Qualité eaux souterraines v1
- **quality_raw** : Qualité eaux de surface v2 (nouveau)
- **quality_groundwater_raw** : Qualité eaux souterraines v2 (nouveau)
- **prelevements_raw** : Prélèvements d'eau
- **sandre_nomenclatures** : Nomenclatures Sandre
- **sandre_params_raw** : Thésaurus paramètres Sandre (nouveau)
- **sandre_units_raw** : Thésaurus unités Sandre (nouveau)
- **bdlisa_masses_eau** : Masses d'eau BDLISA
- **infoterre_forages** : Forages InfoTerre
- **carmen_chimie** : Chimie agrégée CarMen
- **ontologies_rdf** : Ontologies RDF
- **meteo_raw** : Données météo (squelette)

#### 🥈 Silver Layer (Données normalisées)
- **piezo_timescale** : Chargement vers TimescaleDB
- **quality_timescale** : Chargement qualité v2 vers TimescaleDB (nouveau)
- **quality_groundwater_timescale** : Chargement qualité souterraine v2 (nouveau)
- **stations_metadata** : Métadonnées des stations
- **sandre_params_pg** : Thésaurus paramètres → TimescaleDB (nouveau)
- **sandre_units_pg** : Thésaurus unités → TimescaleDB (nouveau)
- **meteo_timescale** : Chargement météo → TimescaleDB (nouveau)
- **sandre_to_neo4j** : Synchronisation Sandre → Neo4j
- **bdlisa_to_neo4j** : Synchronisation BDLISA → Neo4j

#### 🥇 Gold Layer (Analyses et relations)
- **stations_graph** : Construction du graphe Neo4j
- **all_stations_proximity** : Relations de proximité
- **station_correlations** : Corrélations entre stations
- **station_river_relations** : Relations nappe-rivière
- **withdrawal_station_relations** : Relations prélèvements-stations
- **watershed_analysis** : Analyses de bassins versants
- **anthropogenic_impact_analysis** : Impacts anthropiques
- **data_quality_metadata** : Métadonnées de qualité
- **graph_params** : Nœuds paramètres dans Neo4j (nouveau)
- **graph_station_has_param** : Relations station-paramètre (nouveau)
- **graph_quality_correlations** : Corrélations paramètres qualité (nouveau)
- **graph_quality_profiles** : Profils de qualité par station (nouveau)
- **station2grid_update** : Liens station-grille météo (nouveau)
- **meteo_station_summary** : Agrégats météo par station (nouveau)

### Planification

| Job | Fréquence | Description |
|-----|-----------|-------------|
| **hubeau_daily_job** | Quotidien 02:30 | Intégration toutes les APIs Hub'Eau |
| **external_weekly_job** | Hebdomadaire (Lundi 03:00) | Sources externes et analyses avancées |
| **full_integration_job** | Mensuel (1er à 04:00) | Intégration complète et maintenance |

### Sensors et Checks

- **Sensors** : Détection automatique des données manquantes
- **Asset Checks** : Validation de la qualité des données
- **Data Quality** : Métriques de complétude et cohérence

## 📈 Monitoring

### Métriques disponibles

- Nombre de records ingérés par source
- Latence des APIs Hub'Eau
- Taux de succès des jobs Dagster
- Utilisation des ressources

### Dashboards Grafana

- Vue d'ensemble du pipeline
- Santé des bases de données
- Métriques de performance
- Alertes sur les erreurs

## 🛠️ Développement

### Structure du projet

```
├── docker-compose.yml              # Orchestration des services
├── src/hubeau_pipeline/            # Code Dagster
│   ├── __init__.py                # Définitions principales
│   ├── assets.py                  # Assets Hub'Eau principaux
│   ├── external_assets.py         # Sources externes et ontologies
│   ├── geospatial_assets.py       # Analyses géospatiales
│   ├── assets_station_meta.py     # Métadonnées des stations (CRITIQUE)
│   └── resources.py               # Connexions aux services
├── scripts/                        # Scripts d'initialisation
│   ├── init_timescaledb.sql       # Schéma TimescaleDB complet
│   ├── init_neo4j.cypher          # Contraintes Neo4j
│   ├── init_all.sh               # Script Linux/Mac
│   └── init_all.bat              # Script Windows
├── tests/                          # Tests d'intégration
│   └── test_integration.py        # Validation du pipeline
├── docs/                          # Documentation
│   ├── examples_queries.md        # Requêtes avancées
│   ├── REVIEW_CORRECTIONS.md      # Revue et corrections
│   └── BACKFILL_GUIDE.md          # Guide des backfills
└── dagster_home/                  # Configuration Dagster
    └── workspace.yaml
```

### Ajout d'une nouvelle source

1. Créer un nouvel asset dans `assets.py`
2. Définir les partitions et dépendances
3. Ajouter les ressources nécessaires
4. Configurer la planification

### Tests

```bash
# Tests d'intégration
pytest tests/test_integration.py -v

# Validation complète du pipeline
python -m pytest tests/ --tb=short
```

## 🔧 Maintenance

### Sauvegardes

```bash
# TimescaleDB
docker-compose exec timescaledb pg_dump -U postgres water > backup_water.sql

# Neo4j
docker-compose exec neo4j neo4j-admin dump --database=neo4j --to=/backups/neo4j.dump
```

### Surveillance

- Logs Dagster : Interface web
- Logs Docker : `docker-compose logs -f [service]`
- Métriques Prometheus : Port 9090

## 🎯 Fonctionnalités avancées

### Analyses géospatiales
- Relations de proximité entre stations
- Corrélations temporelles
- Relations hydrologiques (nappe-rivière)
- Analyses de bassins versants
- Impacts anthropiques

### Analyses de qualité avancées (Nouveau)
- Relations station-paramètre dans le graphe
- Corrélations entre paramètres de qualité
- Profils de qualité par station
- Thésaurus Sandre intégré
- Métadonnées enrichies

### Données météo (Squelette)
- Grille météo normalisée
- Liens station-cellule météo
- Agrégats météo par station
- Support pour multiples sources (ERA5, SAFRAN, etc.)

### Monitoring et qualité
- Asset checks automatiques
- Sensors de fraîcheur
- Métadonnées de qualité
- Logs détaillés
- Backoff/retry automatique

### Intégration sémantique
- Ontologies RDF (SOSA/SSN, GeoSPARQL, QUDT, PROV-O)
- Graphe de connaissances Neo4j
- Relations inter-sources
- Vocabulaires contrôlés
- Thésaurus officiels Sandre

## 📚 Documentation technique

- [Guide des backfills](docs/BACKFILL_GUIDE.md) - Guide complet pour les backfills
- [Exemples de requêtes](docs/examples_queries.md) - Requêtes avancées
- [Revue et corrections](docs/REVIEW_CORRECTIONS.md) - Détails des améliorations

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature
3. Commiter les changements
4. Pousser vers la branche
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙏 Remerciements

- [BRGM](https://www.brgm.fr/) pour les données Hub'Eau
- [Dagster](https://dagster.io/) pour l'orchestration
- [Neo4j](https://neo4j.com/) pour le graphe
- [TimescaleDB](https://www.timescale.com/) pour les séries temporelles
