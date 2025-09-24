"""
Asset Bronze - Piézométrie Hub'Eau
Petite brique spécialisée pour l'API piézométrie
"""

import httpx
from dagster import AssetExecutionContext, asset, DailyPartitionsDefinition, get_dagster_logger
from hubeau_pipeline.utils import get_with_backoff, RateLimiter

# Configuration des partitions journalières
PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="bronze_hubeau",
    description="Récupération des données piézométriques depuis l'API Hub'Eau"
)
def piezo_raw(context: AssetExecutionContext):
    """
    Petite brique : Récupère les données piézométriques brutes
    
    Cette brique est responsable uniquement de :
    - Appeler l'API Hub'Eau piézométrie
    - Récupérer les données brutes
    - Les stocker dans MinIO (bronze layer)
    """
    logger = get_dagster_logger()
    day = context.partition_key
    
    # Configuration des endpoints Hub'Eau piézométrie
    endpoints = [
        {
            "name": "stations",
            "url": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/stations",
            "params": {"size": 1000}
        },
        {
            "name": "observations", 
            "url": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/observations_tr",
            "params": {"date_debut_obs": day, "date_fin_obs": day, "size": 1000}
        },
        {
            "name": "chroniques",
            "url": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques", 
            "params": {"date_debut_mesure": day, "date_fin_mesure": day, "size": 1000}
        }
    ]
    
    # Rate limiter pour respecter les limites API
    rate_limiter = RateLimiter(calls_per_second=2)
    
    all_data = {}
    total_records = 0
    
    for endpoint in endpoints:
        logger.info(f"Récupération {endpoint['name']} pour {day}")
        
        try:
            # Récupération avec retry automatique
            data = get_with_backoff(
                endpoint["url"],
                params=endpoint["params"],
                rate_limiter=rate_limiter
            )
            
            all_data[endpoint["name"]] = data
            records_count = len(data.get("data", []))
            total_records += records_count
            
            logger.info(f"✓ {endpoint['name']}: {records_count} enregistrements")
            
        except Exception as e:
            logger.error(f"✗ Erreur {endpoint['name']}: {str(e)}")
            all_data[endpoint["name"]] = {"error": str(e)}
    
    # Stockage dans MinIO (simulation pour l'instant)
    result = {
        "date": day,
        "endpoints": list(all_data.keys()),
        "total_records": total_records,
        "status": "success" if total_records > 0 else "warning"
    }
    
    logger.info(f"✓ Piézométrie {day}: {total_records} enregistrements au total")
    return result
