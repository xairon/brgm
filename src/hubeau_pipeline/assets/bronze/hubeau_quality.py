"""
Assets Bronze - Qualité Hub'Eau
Petites briques spécialisées pour les APIs qualité
"""

import httpx
from dagster import AssetExecutionContext, asset, DailyPartitionsDefinition, get_dagster_logger
from hubeau_pipeline.utils import get_with_backoff, RateLimiter

# Configuration des partitions journalières
PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="bronze_hubeau",
    description="Récupération des données qualité eaux surface depuis l'API Hub'Eau"
)
def quality_surface_raw(context: AssetExecutionContext):
    """
    Petite brique : Récupère les données qualité eaux surface brutes
    """
    logger = get_dagster_logger()
    day = context.partition_key
    
    # Configuration des endpoints Hub'Eau qualité surface
    endpoints = [
        {
            "name": "stations",
            "url": "https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface/stations",
            "params": {"size": 1000}
        },
        {
            "name": "analyse", 
            "url": "https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface/analyse",
            "params": {"date_debut_prelevement": day, "date_fin_prelevement": day, "size": 1000}
        }
    ]
    
    rate_limiter = RateLimiter(calls_per_second=2)
    all_data = {}
    total_records = 0
    
    for endpoint in endpoints:
        logger.info(f"Récupération qualité surface {endpoint['name']} pour {day}")
        
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
            logger.error(f"✗ Erreur {endpoint['name']}: {str(e)}")
            all_data[endpoint["name"]] = {"error": str(e)}
    
    result = {
        "date": day,
        "endpoints": list(all_data.keys()),
        "total_records": total_records,
        "status": "success" if total_records > 0 else "warning"
    }
    
    logger.info(f"✓ Qualité surface {day}: {total_records} enregistrements")
    return result

@asset(
    partitions_def=PARTITIONS,
    group_name="bronze_hubeau", 
    description="Récupération des données qualité eaux souterraines depuis l'API Hub'Eau"
)
def quality_groundwater_raw(context: AssetExecutionContext):
    """
    Petite brique : Récupère les données qualité eaux souterraines brutes
    """
    logger = get_dagster_logger()
    day = context.partition_key
    
    # Configuration des endpoints Hub'Eau qualité souterraine
    endpoints = [
        {
            "name": "stations",
            "url": "https://hubeau.eaufrance.fr/api/v1/qualite_eaux_souterraines/stations",
            "params": {"size": 1000}
        },
        {
            "name": "analyse", 
            "url": "https://hubeau.eaufrance.fr/api/v1/qualite_eaux_souterraines/analyse",
            "params": {"date_debut_prelevement": day, "date_fin_prelevement": day, "size": 1000}
        }
    ]
    
    rate_limiter = RateLimiter(calls_per_second=2)
    all_data = {}
    total_records = 0
    
    for endpoint in endpoints:
        logger.info(f"Récupération qualité souterraine {endpoint['name']} pour {day}")
        
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
            logger.error(f"✗ Erreur {endpoint['name']}: {str(e)}")
            all_data[endpoint["name"]] = {"error": str(e)}
    
    result = {
        "date": day,
        "endpoints": list(all_data.keys()),
        "total_records": total_records,
        "status": "success" if total_records > 0 else "warning"
    }
    
    logger.info(f"✓ Qualité souterraine {day}: {total_records} enregistrements")
    return result
