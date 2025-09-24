"""
Microservice BDLISA - Ingestion réelle des données BDLISA
Intègre les masses d'eau souterraine et leurs caractéristiques
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
    description="Microservice BDLISA - Ingestion réelle des données BDLISA"
)
def bdlisa_ingestion_service(context: AssetExecutionContext):
    """🏗️ MICROSERVICE BDLISA - Ingestion réelle des données BDLISA"""
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"🏗️ Microservice BDLISA - Ingestion masses d'eau {day}")
    
    # Configuration des APIs BDLISA
    bdlisa_apis = {
        "masses_eau": {
            "url": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/masses_eau",
            "params": {"size": 1000},
            "description": "Masses d'eau souterraine"
        },
        "stations": {
            "url": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/stations",
            "params": {"size": 1000},
            "description": "Stations de mesure piézométriques"
        },
        "communes": {
            "url": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/communes",
            "params": {"size": 1000},
            "description": "Communes avec stations"
        }
    }
    
    total_records = 0
    bdlisa_results = {}
    
    for api_name, config in bdlisa_apis.items():
        try:
            logger.info(f"📡 Appel API BDLISA {api_name}...")
            
            # Appel API BDLISA
            response = requests.get(
                config["url"],
                params=config["params"],
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                records_count = len(data.get("data", []))
                total_records += records_count
                
                # Stockage dans MinIO (Bronze layer)
                if records_count > 0:
                    filename = f"bdlisa_{api_name}.json"
                    filepath = f"bronze/bdlisa/{day}/{filename}"
                    
                    logger.info(f"💾 Stockage {records_count} enregistrements BDLISA dans MinIO: {filepath}")
                    
                    bdlisa_results[api_name] = {
                        "status": "success",
                        "records": records_count,
                        "filepath": filepath,
                        "description": config["description"]
                    }
                else:
                    logger.info(f"ℹ️ Aucune donnée pour {api_name}")
                    bdlisa_results[api_name] = {
                        "status": "no_data",
                        "records": 0
                    }
            else:
                logger.warning(f"⚠️ Erreur API BDLISA {api_name}: {response.status_code}")
                bdlisa_results[api_name] = {
                    "status": "error",
                    "error_code": response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erreur connexion BDLISA {api_name}: {str(e)}")
            bdlisa_results[api_name] = {
                "status": "connection_error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"❌ Erreur inattendue BDLISA {api_name}: {str(e)}")
            bdlisa_results[api_name] = {
                "status": "unexpected_error",
                "error": str(e)
            }
    
    logger.info(f"✅ Ingestion BDLISA terminée: {total_records} enregistrements total")
    
    return {
        "service_name": "bdlisa_ingestion_service",
        "execution_date": day,
        "apis_processed": len(bdlisa_apis),
        "total_records": total_records,
        "bdlisa_results": bdlisa_results,
        "service_status": "success",
        "layer": "bronze"
    }
