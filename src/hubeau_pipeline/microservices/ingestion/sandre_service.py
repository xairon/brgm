"""
Microservice Sandre - Ingestion des nomenclatures Sandre
Service spécialisé pour l'ingestion des référentiels Sandre
"""

from dagster import asset, WeeklyPartitionsDefinition, get_dagster_logger, AssetExecutionContext

# Configuration des partitions hebdomadaires
PARTITIONS = WeeklyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="microservice_ingestion",
    description="Microservice Sandre - Ingestion des nomenclatures Sandre"
)
def sandre_ingestion_service(context: AssetExecutionContext):
    """
    🏗️ MICROSERVICE SANDRE
    
    Responsabilité unique : Ingestion des référentiels Sandre
    - Nomenclatures paramètres et unités
    - Vérification des changements (logique intelligente)
    - Stockage dans MinIO (couche Bronze)
    - Fréquence hebdomadaire (lundi)
    """
    logger = get_dagster_logger()
    week = context.partition_key
    
    logger.info(f"🏗️ Microservice Sandre - Ingestion {week}")
    
    # Configuration des APIs Sandre
    sandre_apis = {
        "parametres": {
            "url": "https://api.sandre.eaufrance.fr/parametres/v1/parametres",
            "description": "Nomenclatures des paramètres de mesure",
            "update_frequency": "weekly"
        },
        "unites": {
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/unites",
            "description": "Nomenclatures des unités de mesure",
            "update_frequency": "weekly"
        },
        "methodes": {
            "url": "https://api.sandre.eaufrance.fr/methodes/v1/methodes",
            "description": "Nomenclatures des méthodes d'analyse",
            "update_frequency": "weekly"
        }
    }
    
    # Simulation de la vérification des changements
    ingestion_results = {}
    total_records = 0
    
    for api_name, config in sandre_apis.items():
        logger.info(f"📡 Vérification {api_name} - {config['url']}")
        
        # Simulation de la vérification des changements
        # En réalité : comparaison avec la version précédente
        has_changes = (hash(f"{api_name}{week}") % 3) == 0  # 33% de chance de changement
        
        if has_changes:
            records_count = 500 + (hash(f"{api_name}{week}") % 200)
            
            ingestion_results[api_name] = {
                "endpoint": config["url"],
                "description": config["description"],
                "has_changes": True,
                "records_ingested": records_count,
                "last_update": week,
                "storage_location": f"minio://bronze/sandre/{api_name}/{week}/",
                "status": "updated"
            }
            
            total_records += records_count
            logger.info(f"🔄 {api_name}: {records_count} enregistrements mis à jour")
        else:
            ingestion_results[api_name] = {
                "endpoint": config["url"],
                "description": config["description"],
                "has_changes": False,
                "records_ingested": 0,
                "last_update": week,
                "status": "no_changes"
            }
            logger.info(f"✅ {api_name}: Aucun changement détecté")
    
    # Résultat du microservice
    service_result = {
        "service_name": "sandre_ingestion_service",
        "execution_date": week,
        "apis_checked": len(sandre_apis),
        "apis_updated": sum(1 for r in ingestion_results.values() if r["has_changes"]),
        "total_records": total_records,
        "ingestion_results": ingestion_results,
        "service_status": "success",
        "layer": "bronze",
        "storage": "minio"
    }
    
    logger.info(f"🏗️ Microservice Sandre terminé: {total_records} enregistrements mis à jour")
    return service_result
