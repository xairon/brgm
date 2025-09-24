"""
Assets Bronze - Sources externes Sandre
Petites briques spécialisées pour les APIs Sandre
"""

import httpx
from dagster import AssetExecutionContext, asset, WeeklyPartitionsDefinition, get_dagster_logger
from hubeau_pipeline.utils import get_with_backoff, RateLimiter

# Configuration des partitions hebdomadaires (Sandre se met à jour moins souvent)
PARTITIONS = WeeklyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="bronze_external",
    description="Récupération des paramètres Sandre depuis l'API officielle"
)
def sandre_params_raw(context: AssetExecutionContext):
    """
    Petite brique : Récupère les paramètres Sandre bruts
    
    Cette brique récupère :
    - Codes paramètres
    - Libellés
    - Unités de mesure
    - Familles de paramètres
    """
    logger = get_dagster_logger()
    week = context.partition_key
    
    # Configuration des endpoints Sandre
    endpoints = [
        {
            "name": "parametres",
            "url": "https://api.sandre.eaufrance.fr/parametres/v1/parametres",
            "params": {"size": 1000}
        },
        {
            "name": "unites",
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/unites",
            "params": {"size": 1000}
        }
    ]
    
    rate_limiter = RateLimiter(calls_per_second=1)  # Sandre plus restrictif
    all_data = {}
    total_records = 0
    
    for endpoint in endpoints:
        logger.info(f"Récupération Sandre {endpoint['name']} pour {week}")
        
        try:
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
            logger.error(f"✗ Erreur Sandre {endpoint['name']}: {str(e)}")
            all_data[endpoint["name"]] = {"error": str(e)}
    
    result = {
        "date": week,
        "endpoints": list(all_data.keys()),
        "total_records": total_records,
        "status": "success" if total_records > 0 else "warning"
    }
    
    logger.info(f"✓ Sandre {week}: {total_records} enregistrements")
    return result

@asset(
    partitions_def=PARTITIONS,
    group_name="bronze_external",
    description="Récupération des unités Sandre depuis l'API officielle"
)
def sandre_units_raw(context: AssetExecutionContext):
    """
    Petite brique : Récupère les unités Sandre brutes
    """
    logger = get_dagster_logger()
    week = context.partition_key
    
    logger.info(f"Récupération unités Sandre pour {week}")
    
    # Simulation pour l'instant
    result = {
        "date": week,
        "records": 150,
        "status": "simulation",
        "note": "Unités Sandre - simulation"
    }
    
    logger.info(f"✓ Unités Sandre {week}: {result['records']} enregistrements")
    return result
