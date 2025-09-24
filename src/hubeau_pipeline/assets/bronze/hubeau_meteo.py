"""
Asset Bronze - Météo Hub'Eau
Petite brique spécialisée pour les données météorologiques
"""

from dagster import AssetExecutionContext, asset, DailyPartitionsDefinition, get_dagster_logger

# Configuration des partitions journalières
PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="bronze_hubeau",
    description="Récupération des données météorologiques (squelette pour extension future)"
)
def meteo_raw(context: AssetExecutionContext):
    """
    Petite brique : Récupère les données météorologiques brutes
    
    Cette brique est un squelette pour intégrer :
    - Météo-France SAFRAN (nécessite partenariat)
    - ERA5-Land (données climatiques globales)
    - Données locales
    """
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"Récupération données météo pour {day}")
    
    # Simulation de données météo (à remplacer par vraie API)
    meteo_data = {
        "date": day,
        "precipitation": 0.0,
        "temperature": 15.0,
        "humidity": 70.0,
        "source": "simulation",
        "grid_points": 100
    }
    
    result = {
        "date": day,
        "records": 1,
        "status": "simulation",
        "note": "Données simulées - intégration API météo à venir"
    }
    
    logger.info(f"✓ Météo {day}: {result['records']} enregistrement (simulation)")
    return result
