"""
Asset Silver - Métadonnées des stations
Petite brique spécialisée pour la synchronisation des métadonnées
"""

from dagster import AssetExecutionContext, asset, DailyPartitionsDefinition, get_dagster_logger
# from hubeau_pipeline.assets.bronze import piezo_raw, hydro_raw, quality_surface_raw

# Configuration des partitions journalières
PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="silver_metadata",
    description="Synchronisation des métadonnées des stations"
)
def station_metadata_sync(context: AssetExecutionContext):
    """
    Petite brique : Synchronise les métadonnées des stations
    
    Cette brique est responsable uniquement de :
    - Récupérer les métadonnées des stations depuis les APIs
    - Unifier les données (coordonnées, libellés, etc.)
    - Transformer les coordonnées (Lambert-93 -> WGS84)
    - Charger dans TimescaleDB avec gestion des conflits
    """
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"Synchronisation métadonnées stations pour {day}")
    
    # Simulation de la récupération des métadonnées
    stations_data = {
        "piezo_stations": 150,
        "hydro_stations": 120, 
        "quality_stations": 80
    }
    
    # Simulation de l'unification et transformation
    unified_stations = []
    
    # Simulation des stations piézométriques
    if stations_data["piezo_stations"] > 0:
        unified_stations.append({
            "station_code": "BSS001",
            "type": "piezometrique",
            "libelle": "Station Piézométrique Test",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "commune": "Paris",
            "insee": "75101"
        })
    
    # Simulation des stations hydrométriques
    if stations_data["hydro_stations"] > 0:
        unified_stations.append({
            "station_code": "HYD001", 
            "type": "hydrometrique",
            "libelle": "Station Hydrométrique Test",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "commune": "Paris",
            "insee": "75101"
        })
    
    # Simulation du chargement en base
    result = {
        "date": day,
        "stations_processed": len(unified_stations),
        "stations_created": len(unified_stations),
        "stations_updated": 0,
        "coordinate_transformations": len(unified_stations),
        "status": "success"
    }
    
    logger.info(f"✓ Métadonnées stations {day}: {result['stations_processed']} stations")
    return result
