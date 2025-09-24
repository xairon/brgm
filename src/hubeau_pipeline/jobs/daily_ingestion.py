"""
Job Orchestré - Ingestion quotidienne Hub'Eau
Grosse brique qui orchestre toutes les petites briques d'ingestion
"""

from dagster import define_asset_job, AssetSelection
from hubeau_pipeline.assets.bronze import (
    piezo_raw, hydro_raw, quality_surface_raw, quality_groundwater_raw, meteo_raw
)
from hubeau_pipeline.assets.silver import (
    piezo_timescale, hydro_timescale, quality_timescale, station_metadata_sync, data_quality_checks
)

# Sélection des assets pour l'ingestion quotidienne
daily_ingestion_selection = AssetSelection.assets(
    # Bronze Layer - Récupération des données brutes
    piezo_raw,
    hydro_raw,
    quality_surface_raw,
    quality_groundwater_raw,
    meteo_raw,
    
    # Silver Layer - Nettoyage et chargement
    piezo_timescale,
    hydro_timescale,
    quality_timescale,
    station_metadata_sync,
    data_quality_checks
)

# Job orchestré : Ingestion quotidienne complète
hubeau_daily_job = define_asset_job(
    name="hubeau_daily_job",
    description="""
    🏗️ GROSSE BRIQUE : Orchestration de l'ingestion quotidienne Hub'Eau
    
    Ce job orchestre toutes les petites briques nécessaires pour :
    - Récupérer les données brutes depuis les APIs Hub'Eau (Bronze)
    - Nettoyer et charger les données dans TimescaleDB (Silver)
    - Synchroniser les métadonnées des stations
    - Effectuer les contrôles qualité
    
    Flux d'exécution :
    1. Bronze Layer : Récupération parallèle des APIs
    2. Silver Layer : Nettoyage et chargement séquentiel
    3. Quality Layer : Contrôles qualité finaux
    """,
    selection=daily_ingestion_selection,
    config={
        "execution": {
            "config": {
                "multiprocess": {
                    "max_concurrent": 3,  # Limite la concurrence pour respecter les APIs
                }
            }
        }
    }
)
