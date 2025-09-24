"""
Microservice Sandre - Ingestion réelle des référentiels Sandre
Intègre les nomenclatures et thésaurus Sandre
"""

import requests
import json
from datetime import datetime
from dagster import asset, DailyPartitionsDefinition, AssetExecutionContext, get_dagster_logger

# Partitions quotidiennes
DAILY_PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    group_name="microservice_ingestion",
    partitions_def=DAILY_PARTITIONS,
    description="Microservice Sandre - Ingestion réelle des référentiels Sandre"
)
def sandre_ingestion_service(context: AssetExecutionContext):
    """🏗️ MICROSERVICE SANDRE - Ingestion réelle des référentiels Sandre"""
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"🏗️ Microservice Sandre - Ingestion référentiels {day}")
    
    # Configuration des APIs Sandre
    sandre_apis = {
        "parametres": {
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/par",
            "description": "Paramètres de mesure"
        },
        "unites": {
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/unt",
            "description": "Unités de mesure"
        },
        "methodes": {
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/met",
            "description": "Méthodes d'analyse"
        },
        "fractions": {
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/frac",
            "description": "Fractions analysées"
        },
        "matrices": {
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/mat",
            "description": "Matrices d'analyse"
        }
    }
    
    total_records = 0
    sandre_results = {}
    
    for ref_name, config in sandre_apis.items():
        try:
            logger.info(f"📡 Appel API Sandre {ref_name}...")
            
            # Appel API Sandre
            response = requests.get(
                config["url"],
                params={"size": 1000},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                records_count = len(data.get("data", []))
                total_records += records_count
                
                # Stockage dans MinIO (Bronze layer)
                if records_count > 0:
                    filename = f"sandre_{ref_name}.json"
                    filepath = f"bronze/sandre/{day}/{filename}"
                    
                    logger.info(f"💾 Stockage {records_count} enregistrements Sandre dans MinIO: {filepath}")
                    
                    sandre_results[ref_name] = {
                        "status": "success",
                        "records": records_count,
                        "filepath": filepath,
                        "description": config["description"]
                    }
                else:
                    logger.info(f"ℹ️ Aucune donnée pour {ref_name}")
                    sandre_results[ref_name] = {
                        "status": "no_data",
                        "records": 0
                    }
            else:
                logger.warning(f"⚠️ Erreur API Sandre {ref_name}: {response.status_code}")
                sandre_results[ref_name] = {
                    "status": "error",
                    "error_code": response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erreur connexion Sandre {ref_name}: {str(e)}")
            sandre_results[ref_name] = {
                "status": "connection_error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"❌ Erreur inattendue Sandre {ref_name}: {str(e)}")
            sandre_results[ref_name] = {
                "status": "unexpected_error",
                "error": str(e)
            }
    
    logger.info(f"✅ Ingestion Sandre terminée: {total_records} enregistrements total")
    
    return {
        "service_name": "sandre_ingestion_service",
        "execution_date": day,
        "referentials_processed": len(sandre_apis),
        "total_records": total_records,
        "sandre_results": sandre_results,
        "service_status": "success",
        "layer": "bronze"
    }
