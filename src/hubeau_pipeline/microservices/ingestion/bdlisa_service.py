"""
Microservice BDLISA - Ingestion des masses d'eau BDLISA
Service spécialisé pour l'ingestion des données géographiques BDLISA
"""

from dagster import asset, MonthlyPartitionsDefinition, get_dagster_logger, AssetExecutionContext

# Configuration des partitions mensuelles
PARTITIONS = MonthlyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="microservice_ingestion",
    description="Microservice BDLISA - Ingestion des masses d'eau BDLISA"
)
def bdlisa_ingestion_service(context: AssetExecutionContext):
    """
    🏗️ MICROSERVICE BDLISA
    
    Responsabilité unique : Ingestion des données BDLISA
    - Masses d'eau souterraine (polygones géographiques)
    - Hiérarchies des masses d'eau (niveaux 1, 2, 3)
    - Vérification des changements (logique intelligente)
    - Stockage dans MinIO (couche Bronze)
    - Fréquence mensuelle (1er du mois)
    """
    logger = get_dagster_logger()
    month = context.partition_key
    
    logger.info(f"🏗️ Microservice BDLISA - Ingestion {month}")
    
    # Configuration des sources BDLISA
    bdlisa_sources = {
        "masses_eau": {
            "wfs_url": "https://services.sandre.eaufrance.fr/geo/bdlisa",
            "layer": "bdlisa:Massedeau",
            "description": "Polygones des masses d'eau souterraine",
            "update_frequency": "monthly"
        },
        "hierarchies": {
            "wfs_url": "https://services.sandre.eaufrance.fr/geo/bdlisa",
            "layer": "bdlisa:Hierarchie",
            "description": "Hiérarchies des masses d'eau",
            "update_frequency": "monthly"
        },
        "communes": {
            "wfs_url": "https://services.sandre.eaufrance.fr/geo/bdlisa",
            "layer": "bdlisa:Commune",
            "description": "Relations communes-masses d'eau",
            "update_frequency": "monthly"
        }
    }
    
    # Simulation de la vérification des changements
    ingestion_results = {}
    total_records = 0
    
    for source_name, config in bdlisa_sources.items():
        logger.info(f"📡 Vérification {source_name} - {config['wfs_url']}")
        
        # Simulation de la vérification des changements
        # En réalité : comparaison avec la version précédente
        has_changes = (hash(f"{source_name}{month}") % 4) == 0  # 25% de chance de changement
        
        if has_changes:
            records_count = 1000 + (hash(f"{source_name}{month}") % 500)
            
            ingestion_results[source_name] = {
                "wfs_endpoint": config["wfs_url"],
                "layer": config["layer"],
                "description": config["description"],
                "has_changes": True,
                "records_ingested": records_count,
                "last_update": month,
                "storage_location": f"minio://bronze/bdlisa/{source_name}/{month}/",
                "status": "updated"
            }
            
            total_records += records_count
            logger.info(f"🔄 {source_name}: {records_count} enregistrements mis à jour")
        else:
            ingestion_results[source_name] = {
                "wfs_endpoint": config["wfs_url"],
                "layer": config["layer"],
                "description": config["description"],
                "has_changes": False,
                "records_ingested": 0,
                "last_update": month,
                "status": "no_changes"
            }
            logger.info(f"✅ {source_name}: Aucun changement détecté")
    
    # Résultat du microservice
    service_result = {
        "service_name": "bdlisa_ingestion_service",
        "execution_date": month,
        "sources_checked": len(bdlisa_sources),
        "sources_updated": sum(1 for r in ingestion_results.values() if r["has_changes"]),
        "total_records": total_records,
        "ingestion_results": ingestion_results,
        "service_status": "success",
        "layer": "bronze",
        "storage": "minio"
    }
    
    logger.info(f"🏗️ Microservice BDLISA terminé: {total_records} enregistrements mis à jour")
    return service_result
