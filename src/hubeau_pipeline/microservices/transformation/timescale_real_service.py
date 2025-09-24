"""
Microservice TimescaleDB - Chargement réel des données dans TimescaleDB
Lit les données MinIO (Bronze) et les charge dans TimescaleDB (Silver)
"""

import json
import psycopg2
from datetime import datetime
from dagster import asset, DailyPartitionsDefinition, AssetExecutionContext, get_dagster_logger
from hubeau_pipeline.microservices.ingestion.hubeau_real_service import hubeau_ingestion_service
from hubeau_pipeline.microservices.ingestion.sandre_real_service import sandre_ingestion_service
from hubeau_pipeline.microservices.ingestion.bdlisa_real_service import bdlisa_ingestion_service
from hubeau_pipeline.microservices.ingestion.minio_service import MinIOService

# Partitions quotidiennes
DAILY_PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    group_name="microservice_transformation",
    partitions_def=DAILY_PARTITIONS,
    deps=[hubeau_ingestion_service, sandre_ingestion_service, bdlisa_ingestion_service],
    description="Microservice TimescaleDB - Chargement réel des données dans TimescaleDB"
)
def timescale_loading_service(context: AssetExecutionContext):
    """🏗️ MICROSERVICE TIMESCALEDB - Chargement réel des données dans TimescaleDB"""
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"🏗️ Microservice TimescaleDB - Chargement {day}")
    
    # Initialisation du service MinIO
    minio_service = MinIOService(
        endpoint="http://minio:9000",
        access_key="admin",
        secret_key="BrgmMinio2024!",
        bucket_name="hubeau-bronze"
    )
    
    # Configuration de connexion TimescaleDB
    db_config = {
        "host": "timescaledb",
        "port": 5432,
        "database": "water",
        "user": "postgres",
        "password": "BrgmPostgres2024!"
    }
    
    total_records_loaded = 0
    loading_results = {}
    
    try:
        # Connexion à TimescaleDB
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # Chargement réel des données depuis MinIO
        logger.info("📥 Lecture des données depuis MinIO...")
        
        # Charger les données piézométriques temps réel
        piezo_tr_data = minio_service.retrieve_api_data("piezo_chroniques_tr", day)
        piezo_stations_data = minio_service.retrieve_api_data("piezo_stations", day)
        
        hubeau_tables = {}
        
        if piezo_tr_data and piezo_tr_data.get("api_response", {}).get("data"):
            # Traitement des données piézométriques temps réel
            piezo_records = []
            for record in piezo_tr_data["api_response"]["data"]:
                piezo_records.append((
                    record.get("code_bss", ""),
                    "piezo",
                    record.get("date_mesure", f"{day} 06:00:00+00"),
                    record.get("niveau_eau_ngf"),
                    "1",
                    "hubeau"
                ))
            
            hubeau_tables["measure"] = {
                "description": "Données piézométriques temps réel",
                "data": piezo_records
            }
            
        if piezo_stations_data and piezo_stations_data.get("api_response", {}).get("data"):
            # Traitement des métadonnées des stations
            station_records = []
            for record in piezo_stations_data["api_response"]["data"]:
                station_records.append((
                    record.get("code_bss", ""),
                    record.get("libelle_pe", f"Station {record.get('code_bss', '')}"),
                    float(record.get("y", 0)),  # latitude
                    float(record.get("x", 0)),  # longitude
                    "piezo",
                    "active"
                ))
            
            hubeau_tables["station_meta"] = {
                "description": "Métadonnées des stations piézométriques",
                "data": station_records
            }
        
        for table_name, table_info in hubeau_tables.items():
            try:
                logger.info(f"📊 Chargement table {table_name}...")
                
                # Insertion des vraies données depuis MinIO
                records_count = len(table_info["data"])
                
                if table_name == "measure":
                    # Insertion dans la table measure
                    for record in table_info["data"]:
                        cur.execute("""
                            INSERT INTO measure (station_code, theme, ts, value, quality, source)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (station_code, theme, ts) DO NOTHING
                        """, record)
                
                elif table_name == "station_meta":
                    # Insertion dans la table station_meta
                    for record in table_info["data"]:
                        cur.execute("""
                            INSERT INTO station_meta (station_code, station_name, latitude, longitude, theme, status)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (station_code) DO UPDATE SET
                                station_name = EXCLUDED.station_name,
                                latitude = EXCLUDED.latitude,
                                longitude = EXCLUDED.longitude,
                                theme = EXCLUDED.theme,
                                status = EXCLUDED.status
                        """, record)
                
                total_records_loaded += records_count
                loading_results[table_name] = {
                    "status": "success",
                    "records_loaded": records_count,
                    "description": table_info["description"]
                }
                
                logger.info(f"✅ {table_name}: {records_count} enregistrements chargés")
                
            except Exception as e:
                logger.error(f"❌ Erreur chargement {table_name}: {str(e)}")
                loading_results[table_name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Commit des transactions
        conn.commit()
        logger.info(f"✅ Commit réussi: {total_records_loaded} enregistrements total")
        
    except Exception as e:
        logger.error(f"❌ Erreur connexion TimescaleDB: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        raise e
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
    
    logger.info(f"✅ Chargement TimescaleDB terminé: {total_records_loaded} enregistrements total")
    
    return {
        "service_name": "timescale_loading_service",
        "execution_date": day,
        "tables_processed": len(hubeau_tables),
        "total_records_loaded": total_records_loaded,
        "loading_results": loading_results,
        "service_status": "success",
        "layer": "silver"
    }
