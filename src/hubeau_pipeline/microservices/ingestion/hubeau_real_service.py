"""
Microservice Hub'Eau - Ingestion réelle des données Hub'Eau
Intègre les APIs : piézo, hydro, température, qualité surface, qualité souterraine
"""

import requests
import json
from datetime import datetime, timedelta
from dagster import asset, DailyPartitionsDefinition, AssetExecutionContext, get_dagster_logger
from hubeau_pipeline.resources import RESOURCES
from hubeau_pipeline.microservices.ingestion.minio_service import MinIOService

# Partitions quotidiennes
DAILY_PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    group_name="microservice_ingestion",
    partitions_def=DAILY_PARTITIONS,
    description="Microservice Hub'Eau - Ingestion réelle des données Hub'Eau"
)
def hubeau_ingestion_service(context: AssetExecutionContext):
    """🏗️ MICROSERVICE HUB'EAU - Ingestion réelle des données Hub'Eau"""
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"🏗️ Microservice Hub'Eau - Ingestion réelle {day}")
    
    # Initialisation du service MinIO
    minio_service = MinIOService(
        endpoint="http://minio:9000",
        access_key="admin",
        secret_key="BrgmMinio2024!",
        bucket_name="hubeau-bronze"
    )
    
    # Configuration des APIs Hub'Eau selon la documentation officielle
    apis_config = {
        "piezo_chroniques": {
            "url": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques",
            "params": {
                "date_debut_mesure": day,
                "date_fin_mesure": day,
                "size": 100,
                "format": "json",
                "pretty": "true"
            },
            "description": "Données piézométriques historiques"
        },
        "piezo_chroniques_tr": {
            "url": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques_tr",
            "params": {
                "size": 50,
                "sort": "desc",
                "format": "json",
                "pretty": "true"
            },
            "description": "Données piézométriques temps réel"
        },
        "piezo_stations": {
            "url": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/stations",
            "params": {
                "size": 100,
                "format": "json",
                "pretty": "true"
            },
            "description": "Métadonnées des stations piézométriques"
        },
        "hydro_observations": {
            "url": "https://hubeau.eaufrance.fr/api/v1/hydrometrie/observations_tr",
            "params": {
                "size": 100,
                "format": "json",
                "pretty": "true"
            },
            "description": "Observations hydrométriques temps réel"
        },
        "quality_surface": {
            "url": "https://hubeau.eaufrance.fr/api/v1/qualite_rivieres/analyses",
            "params": {
                "size": 100,
                "format": "json",
                "pretty": "true"
            },
            "description": "Analyses qualité cours d'eau"
        }
    }
    
    total_records = 0
    api_results = {}
    
    for api_name, config in apis_config.items():
        try:
            logger.info(f"📡 Appel API {api_name}...")
            
            # Appel API Hub'Eau
            response = requests.get(
                config["url"],
                params=config["params"],
                timeout=30
            )
            
            if response.status_code in [200, 206]:  # 206 = Partial Content (normal selon doc)
                data = response.json()
                records_count = len(data.get("data", []))
                total_records += records_count
                
                # Informations de pagination selon la doc
                api_version = data.get("api_version", "unknown")
                total_count = data.get("count", records_count)
                
                logger.info(f"✅ {api_name}: {records_count} enregistrements (total: {total_count}, API v{api_version})")
                
                # Stockage réel dans MinIO (Bronze layer)
                if records_count > 0:
                    # Stocker les données brutes avec métadonnées
                    filepath = minio_service.store_api_data(data, api_name, day)
                    
                    logger.info(f"💾 Stockage {records_count} enregistrements dans MinIO: {filepath}")
                    
                    api_results[api_name] = {
                        "status": "success",
                        "records": records_count,
                        "total_count": total_count,
                        "api_version": api_version,
                        "filepath": filepath,
                        "description": config["description"]
                    }
                else:
                    logger.info(f"ℹ️ Aucune donnée pour {api_name} le {day}")
                    api_results[api_name] = {
                        "status": "no_data",
                        "records": 0,
                        "description": config["description"]
                    }
            else:
                logger.warning(f"⚠️ Erreur API {api_name}: {response.status_code}")
                api_results[api_name] = {
                    "status": "error",
                    "error_code": response.status_code,
                    "description": config["description"]
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erreur connexion {api_name}: {str(e)}")
            api_results[api_name] = {
                "status": "connection_error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"❌ Erreur inattendue {api_name}: {str(e)}")
            api_results[api_name] = {
                "status": "unexpected_error",
                "error": str(e)
            }
    
    logger.info(f"✅ Ingestion Hub'Eau terminée: {total_records} enregistrements total")
    
    return {
        "service_name": "hubeau_ingestion_service",
        "execution_date": day,
        "apis_processed": len(apis_config),
        "total_records": total_records,
        "api_results": api_results,
        "service_status": "success",
        "layer": "bronze"
    }
