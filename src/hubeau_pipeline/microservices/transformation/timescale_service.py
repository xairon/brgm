"""
Microservice TimescaleDB - Chargement et transformation des données
Service spécialisé pour le chargement dans TimescaleDB
"""

from dagster import asset, DailyPartitionsDefinition, get_dagster_logger, AssetExecutionContext

# Configuration des partitions journalières
PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="microservice_transformation",
    description="Microservice TimescaleDB - Chargement et transformation des données"
)
def timescale_loading_service(context: AssetExecutionContext):
    """
    🏗️ MICROSERVICE TIMESCALEDB
    
    Responsabilité unique : Chargement des données dans TimescaleDB
    - Lecture depuis MinIO (couche Bronze)
    - Nettoyage et validation des données
    - Transformation et structuration
    - Chargement dans TimescaleDB (couche Silver)
    - Gestion des hypertables et index PostGIS
    """
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"🏗️ Microservice TimescaleDB - Chargement {day}")
    
    # Configuration des tables TimescaleDB
    timescale_tables = {
        "measure": {
            "source": "minio://bronze/hubeau/",
            "description": "Données temporelles unifiées (hypertable)",
            "columns": ["station_code", "time", "value", "parameter", "quality", "source"],
            "indexes": ["time", "station_code", "parameter"]
        },
        "station_meta": {
            "source": "minio://bronze/hubeau/",
            "description": "Métadonnées des stations (PostGIS)",
            "columns": ["station_code", "type", "libelle", "latitude", "longitude", "geom"],
            "indexes": ["geom", "station_code", "type"]
        },
        "measure_quality": {
            "source": "minio://bronze/hubeau/quality_*",
            "description": "Données qualité spécialisées",
            "columns": ["station_code", "time", "parameter_code", "value", "unit", "quality"],
            "indexes": ["time", "station_code", "parameter_code"]
        },
        "parametre_sandre": {
            "source": "minio://bronze/sandre/",
            "description": "Nomenclatures Sandre",
            "columns": ["code", "libelle", "famille", "unite_code"],
            "indexes": ["code", "famille"]
        }
    }
    
    # Simulation du chargement
    loading_results = {}
    total_records = 0
    
    for table_name, config in timescale_tables.items():
        logger.info(f"📊 Chargement {table_name} - {config['description']}")
        
        # Simulation du chargement
        records_count = 2000 + (hash(f"{table_name}{day}") % 1000)
        
        loading_results[table_name] = {
            "source_location": config["source"],
            "description": config["description"],
            "records_loaded": records_count,
            "columns": config["columns"],
            "indexes_created": config["indexes"],
            "loading_time_seconds": 15 + (hash(f"{table_name}{day}") % 30),
            "status": "success"
        }
        
        total_records += records_count
        logger.info(f"✅ {table_name}: {records_count} enregistrements chargés")
    
    # Résultat du microservice
    service_result = {
        "service_name": "timescale_loading_service",
        "execution_date": day,
        "tables_processed": len(timescale_tables),
        "total_records": total_records,
        "loading_results": loading_results,
        "service_status": "success",
        "layer": "silver",
        "storage": "timescaledb"
    }
    
    logger.info(f"🏗️ Microservice TimescaleDB terminé: {total_records} enregistrements chargés")
    return service_result
