# Hub'Eau Data Integration Pipeline

Pipeline d'intÃ©gration des donnÃ©es Hub'Eau vers une architecture de donnÃ©es moderne avec Dagster, Neo4j et TimescaleDB.

## ðŸŽ¯ Vue d'ensemble

Ce projet intÃ¨gre les donnÃ©es des APIs Hub'Eau (piÃ©zomÃ©trie, hydromÃ©trie, qualitÃ©, etc.) dans une architecture hybride :

- **Dagster** : Orchestration des pipelines de donnÃ©es
- **TimescaleDB + PostGIS** : Stockage des chroniques temporelles et donnÃ©es gÃ©ospatiales
- **Neo4j** : Graphe sÃ©mantique pour les relations mÃ©tier et ontologies
- **MinIO** : Data lake pour les donnÃ©es brutes (bronze layer)
- **Redis** : Cache et verrous distribuÃ©s

## ðŸ—ï¸ Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   Hub'Eau   â”‚â”€â”€â”€â–¶â”‚   MinIO     â”‚â”€â”€â”€â–¶â”‚ TimescaleDB â”‚
â”‚    APIs     â”‚    â”‚  (Bronze)   â”‚    â”‚   (Silver)  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                              â”‚
                                              â–¼
                                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                                    â”‚   Neo4j     â”‚
                                    â”‚  (Gold)     â”‚
                                    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## ðŸš€ DÃ©marrage rapide

### 1. Configuration de l'environnement

```bash
# Copier le fichier d'environnement
cp env.example .env

# Ã‰diter les mots de passe
nano .env
```

### 2. Demarrage des services

```bash
# Construire et lancer les conteneurs
docker compose up -d --build

# Verifier le statut
docker compose ps
```

### 3. Initialisation automatique

```bash
# Linux / macOS
./scripts/init_all.sh

# Windows
scripts\init_all.bat
```

### 4. Lancement du premier job

```bash
# Ouvrir Dagster UI puis materialiser le job de votre choix
# Exemple : piezo_daily_job depuis l'onglet Assets
```

### 5. Acces aux interfaces

- **Dagster UI** : http://localhost:3000
- **Neo4j Browser** : http://localhost:7474
- **Grafana** : http://localhost:3001
- **MinIO Console** : http://localhost:9001

## ðŸ“Š Sources de donnÃ©es intÃ©grÃ©es

### Hub'Eau APIs (IntÃ©grÃ©es)

| API | Description | FrÃ©quence | DonnÃ©es | Status |
|-----|-------------|-----------|---------|--------|
| **PiÃ©zomÃ©trie** | Niveaux d'eau souterraine | Quotidien | Stations, mesures, mÃ©tadonnÃ©es | âœ… |
| **HydromÃ©trie** | Hauteurs/dÃ©bits cours d'eau | 15min | Stations hydromÃ©triques | âœ… |
| **TempÃ©rature** | TempÃ©rature cours d'eau | 15min | Stations thermomÃ©triques | âœ… |
| **Ã‰coulement** | Ã‰tat d'Ã©coulement cours d'eau | Quotidien | Assecs, intermittence | âœ… |
| **Hydrobiologie** | Indices biologiques | Annuel | IBGN, IBD, I2M2 | âœ… |
| **QualitÃ© eaux surface v1** | Analyses physico-chimiques | Mensuel | ParamÃ¨tres, concentrations | âœ… |
| **QualitÃ© eaux surface v2** | Analyses physico-chimiques (nouveau) | Mensuel | ParamÃ¨tres Sandre, unitÃ©s | âœ… |
| **QualitÃ© eaux souterraines v1** | Analyses chimiques nappes | Semestriel | Nitrates, pesticides, DCE | âœ… |
| **QualitÃ© eaux souterraines v2** | Analyses chimiques nappes (nouveau) | Semestriel | ParamÃ¨tres Sandre, unitÃ©s | âœ… |
| **PrÃ©lÃ¨vements** | Volumes prÃ©levÃ©s | Annuel | DÃ©clarations usagers | âœ… |

### Sources externes (IntÃ©grÃ©es)

| Source | Description | Type | DonnÃ©es | Status |
|--------|-------------|------|---------|--------|
| **Sandre** | Nomenclatures officielles | API REST | ParamÃ¨tres, unitÃ©s, mÃ©thodes | âœ… |
| **Sandre ThÃ©saurus** | ThÃ©saurus paramÃ¨tres (nouveau) | API REST | Codes paramÃ¨tres, familles, unitÃ©s | âœ… |
| **BDLISA** | Masses d'eau souterraine | WFS | Polygones, niveaux hiÃ©rarchiques | âœ… |
| **InfoTerre** | Forages et gÃ©ologie | WFS | Forages BSS, cartes gÃ©ologiques | âœ… |
| **CarMen** | Chimie agrÃ©gÃ©e | API REST | DonnÃ©es DCE agrÃ©gÃ©es | âœ… |
| **Ontologies RDF** | SOSA/SSN, GeoSPARQL, QUDT, PROV-O | RDF/Turtle | Vocabulaires sÃ©mantiques | âœ… |
| **MÃ©tÃ©o (Squelette)** | DonnÃ©es mÃ©tÃ©orologiques | Flexible | PrÃ©cipitations, tempÃ©rature, ETP | ðŸ”„ |

### Sources externes (PrÃ©parÃ©es)

- **MÃ©tÃ©o-France SAFRAN** : Pluie, tempÃ©rature, ETP (nÃ©cessite partenariat)
- **ERA5-Land** : DonnÃ©es climatiques globales
- **Sentinel-2** : NDVI, tempÃ©rature de surface
- **GRACE-FO** : Anomalies masse d'eau
- **MÃ©tÃ©EAU Nappes** : PrÃ©visions piÃ©zomÃ©triques BRGM

## ðŸ—„ï¸ ModÃ¨le de donnÃ©es

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

-- MÃ©tadonnÃ©es des stations
station_meta(
  station_code TEXT PRIMARY KEY,
  label TEXT,
  type TEXT,
  geom GEOGRAPHY(POINT, 4326),
  masse_eau_code TEXT
)
```

### Neo4j (Relations mÃ©tier)

```cypher
// NÅ“uds principaux
(:Station {code, label, type, lat, lon})
(:MasseEau {code, libelle, niveau})
(:Commune {insee, nom})
(:Parametre {code, libelle, unite})

// Relations
(:Station)-[:IN_MASSE]->(:MasseEau)
(:Station)-[:IN_COMMUNE]->(:Commune)
(:Station)-[:NEAR {distance_km}]->(:Station)
```

## ðŸ”„ Pipeline Dagster

### Architecture en 3 couches

#### ðŸ¥‰ Bronze Layer (DonnÃ©es brutes)
- **piezo_raw** : PiÃ©zomÃ©trie Hub'Eau
- **hydro_raw** : HydromÃ©trie Hub'Eau
- **temperature_raw** : TempÃ©rature cours d'eau
- **ecoulement_raw** : Ã‰coulement cours d'eau
- **hydrobiologie_raw** : Indices biologiques
- **quality_surface_raw** : QualitÃ© eaux de surface v1
- **quality_groundwater_raw** : QualitÃ© eaux souterraines v1
- **quality_raw** : QualitÃ© eaux de surface v2 (nouveau)
- **quality_groundwater_raw** : QualitÃ© eaux souterraines v2 (nouveau)
- **prelevements_raw** : PrÃ©lÃ¨vements d'eau
- **sandre_nomenclatures** : Nomenclatures Sandre
- **sandre_params_raw** : ThÃ©saurus paramÃ¨tres Sandre (nouveau)
- **sandre_units_raw** : ThÃ©saurus unitÃ©s Sandre (nouveau)
- **bdlisa_masses_eau** : Masses d'eau BDLISA
- **infoterre_forages** : Forages InfoTerre
- **carmen_chimie** : Chimie agrÃ©gÃ©e CarMen
- **ontologies_rdf** : Ontologies RDF
- **meteo_raw** : DonnÃ©es mÃ©tÃ©o (squelette)

#### ðŸ¥ˆ Silver Layer (DonnÃ©es normalisÃ©es)
- **piezo_timescale** : Chargement vers TimescaleDB
- **quality_timescale** : Chargement qualitÃ© v2 vers TimescaleDB (nouveau)
- **quality_groundwater_timescale** : Chargement qualitÃ© souterraine v2 (nouveau)
- **stations_metadata** : MÃ©tadonnÃ©es des stations
- **sandre_params_pg** : ThÃ©saurus paramÃ¨tres â†’ TimescaleDB (nouveau)
- **sandre_units_pg** : ThÃ©saurus unitÃ©s â†’ TimescaleDB (nouveau)
- **meteo_timescale** : Chargement mÃ©tÃ©o â†’ TimescaleDB (nouveau)
- **sandre_to_neo4j** : Synchronisation Sandre â†’ Neo4j
- **bdlisa_to_neo4j** : Synchronisation BDLISA â†’ Neo4j

#### ðŸ¥‡ Gold Layer (Analyses et relations)
- **stations_graph** : Construction du graphe Neo4j
- **all_stations_proximity** : Relations de proximitÃ©
- **station_correlations** : CorrÃ©lations entre stations
- **station_river_relations** : Relations nappe-riviÃ¨re
- **withdrawal_station_relations** : Relations prÃ©lÃ¨vements-stations
- **watershed_analysis** : Analyses de bassins versants
- **anthropogenic_impact_analysis** : Impacts anthropiques
- **data_quality_metadata** : MÃ©tadonnÃ©es de qualitÃ©
- **graph_params** : NÅ“uds paramÃ¨tres dans Neo4j (nouveau)
- **graph_station_has_param** : Relations station-paramÃ¨tre (nouveau)
- **graph_quality_correlations** : CorrÃ©lations paramÃ¨tres qualitÃ© (nouveau)
- **graph_quality_profiles** : Profils de qualitÃ© par station (nouveau)
- **station2grid_update** : Liens station-grille mÃ©tÃ©o (nouveau)
- **meteo_station_summary** : AgrÃ©gats mÃ©tÃ©o par station (nouveau)

### Planification

| Job | FrÃ©quence | Description |
|-----|-----------|-------------|
| **hubeau_daily_job** | Quotidien 02:30 | IntÃ©gration toutes les APIs Hub'Eau |
| **external_weekly_job** | Hebdomadaire (Lundi 03:00) | Sources externes et analyses avancÃ©es |
| **full_integration_job** | Mensuel (1er Ã  04:00) | IntÃ©gration complÃ¨te et maintenance |

### Sensors et Checks

- **Sensors** : DÃ©tection automatique des donnÃ©es manquantes
- **Asset Checks** : Validation de la qualitÃ© des donnÃ©es
- **Data Quality** : MÃ©triques de complÃ©tude et cohÃ©rence

## ðŸ“ˆ Monitoring

### MÃ©triques disponibles

- Nombre de records ingÃ©rÃ©s par source
- Latence des APIs Hub'Eau
- Taux de succÃ¨s des jobs Dagster
- Utilisation des ressources

### Dashboards Grafana

- Vue d'ensemble du pipeline
- SantÃ© des bases de donnÃ©es
- MÃ©triques de performance
- Alertes sur les erreurs

## ðŸ› ï¸ DÃ©veloppement

### Structure du projet

```
â”œâ”€â”€ docker-compose.yml              # Orchestration des services
â”œâ”€â”€ src/hubeau_pipeline/            # Code Dagster
â”‚   â”œâ”€â”€ __init__.py                # DÃ©finitions principales
â”‚   â”œâ”€â”€ assets.py                  # Assets Hub'Eau principaux
â”‚   â”œâ”€â”€ external_assets.py         # Sources externes et ontologies
â”‚   â”œâ”€â”€ geospatial_assets.py       # Analyses gÃ©ospatiales
â”‚   â”œâ”€â”€ assets_station_meta.py     # MÃ©tadonnÃ©es des stations (CRITIQUE)
â”‚   â””â”€â”€ resources.py               # Connexions aux services
â”œâ”€â”€ scripts/                        # Scripts d'initialisation
â”‚   â”œâ”€â”€ init_timescaledb.sql       # SchÃ©ma TimescaleDB complet
â”‚   â”œâ”€â”€ init_neo4j.cypher          # Contraintes Neo4j
â”‚   â”œâ”€â”€ init_all.sh               # Script Linux/Mac
â”‚   â””â”€â”€ init_all.bat              # Script Windows
â”œâ”€â”€ tests/                          # Tests d'intÃ©gration
â”‚   â””â”€â”€ test_integration.py        # Validation du pipeline
â”œâ”€â”€ docs/                          # Documentation
â”‚   â”œâ”€â”€ examples_queries.md        # RequÃªtes avancÃ©es
â”‚   â”œâ”€â”€ REVIEW_CORRECTIONS.md      # Revue et corrections
â”‚   â””â”€â”€ BACKFILL_GUIDE.md          # Guide des backfills
â””â”€â”€ dagster_home/                  # Configuration Dagster
    â””â”€â”€ workspace.yaml
```

### Ajout d'une nouvelle source

1. CrÃ©er un nouvel asset dans `assets.py`
2. DÃ©finir les partitions et dÃ©pendances
3. Ajouter les ressources nÃ©cessaires
4. Configurer la planification

### Tests

```bash
# Tests d'intÃ©gration
pytest tests/test_integration.py -v

# Validation complÃ¨te du pipeline
python -m pytest tests/ --tb=short
```

## ðŸ”§ Maintenance

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
- MÃ©triques Prometheus : Port 9090

## ðŸŽ¯ FonctionnalitÃ©s avancÃ©es

### Analyses gÃ©ospatiales
- Relations de proximitÃ© entre stations
- CorrÃ©lations temporelles
- Relations hydrologiques (nappe-riviÃ¨re)
- Analyses de bassins versants
- Impacts anthropiques

### Analyses de qualitÃ© avancÃ©es (Nouveau)
- Relations station-paramÃ¨tre dans le graphe
- CorrÃ©lations entre paramÃ¨tres de qualitÃ©
- Profils de qualitÃ© par station
- ThÃ©saurus Sandre intÃ©grÃ©
- MÃ©tadonnÃ©es enrichies

### DonnÃ©es mÃ©tÃ©o (Squelette)
- Grille mÃ©tÃ©o normalisÃ©e
- Liens station-cellule mÃ©tÃ©o
- AgrÃ©gats mÃ©tÃ©o par station
- Support pour multiples sources (ERA5, SAFRAN, etc.)

### Monitoring et qualitÃ©
- Asset checks automatiques
- Sensors de fraÃ®cheur
- MÃ©tadonnÃ©es de qualitÃ©
- Logs dÃ©taillÃ©s
- Backoff/retry automatique

### IntÃ©gration sÃ©mantique
- Ontologies RDF (SOSA/SSN, GeoSPARQL, QUDT, PROV-O)
- Graphe de connaissances Neo4j
- Relations inter-sources
- Vocabulaires contrÃ´lÃ©s
- ThÃ©saurus officiels Sandre

## ðŸ“š Documentation technique

- [Guide des backfills](docs/BACKFILL_GUIDE.md) - Guide complet pour les backfills
- [Exemples de requÃªtes](docs/examples_queries.md) - RequÃªtes avancÃ©es
- [Revue et corrections](docs/REVIEW_CORRECTIONS.md) - DÃ©tails des amÃ©liorations

## ðŸ¤ Contribution

1. Fork le projet
2. CrÃ©er une branche feature
3. Commiter les changements
4. Pousser vers la branche
5. Ouvrir une Pull Request

## ðŸ“„ Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de dÃ©tails.

## ðŸ™ Remerciements

- [BRGM](https://www.brgm.fr/) pour les donnÃ©es Hub'Eau
- [Dagster](https://dagster.io/) pour l'orchestration
- [Neo4j](https://neo4j.com/) pour le graphe
- [TimescaleDB](https://www.timescale.com/) pour les sÃ©ries temporelles


