"""
Assets Silver - Chargement optimisé vers TimescaleDB
Avec batch loading, upserts conditionnels et tables complètes
"""

from dagster import asset, DailyPartitionsDefinition, AssetExecutionContext, get_dagster_logger
from datetime import datetime
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from typing import Dict, List, Any
from dataclasses import dataclass

# Configuration des partitions journalières
DAILY_PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@dataclass
class TimescaleConfig:
    """Configuration TimescaleDB"""
    host: str = "timescaledb"
    port: int = 5432
    database: str = "water_timeseries"
    user: str = "postgres"
    password: str = "BrgmPostgres2024!"

class TimescaleDBService:
    """Service optimisé pour TimescaleDB"""
    
    def __init__(self, config: TimescaleConfig):
        self.config = config
        self.logger = get_dagster_logger()
        
    def get_connection(self):
        """Connexion à TimescaleDB"""
        return psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password
        )
    
    def create_hypertable_if_not_exists(self, conn, table_name: str, time_column: str = "timestamp"):
        """Création de l'hypertable TimescaleDB"""
        with conn.cursor() as cur:
            # Vérifier si l'hypertable existe déjà
            cur.execute("""
                SELECT 1 FROM timescaledb_information.hypertables 
                WHERE hypertable_name = %s
            """, (table_name,))
            
            if not cur.fetchone():
                cur.execute(f"""
                    SELECT create_hypertable('{table_name}', '{time_column}', 
                                            chunk_time_interval => INTERVAL '1 day',
                                            if_not_exists => TRUE)
                """)
                self.logger.info(f"✅ Created hypertable: {table_name}")
    
    def batch_upsert(self, conn, table_name: str, data: List[Dict], 
                     conflict_columns: List[str], batch_size: int = 1000):
        """Upsert par batch optimisé"""
        if not data:
            return 0
        
        # Préparation des colonnes
        columns = list(data[0].keys())
        placeholders = ", ".join(["%s"] * len(columns))
        
        # Construction de la requête UPSERT
        conflict_cols = ", ".join(conflict_columns)
        update_cols = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns if col not in conflict_columns])
        
        upsert_query = f"""
            INSERT INTO {table_name} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_cols}) 
            DO UPDATE SET {update_cols}
        """
        
        # Traitement par batch
        total_inserted = 0
        with conn.cursor() as cur:
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                batch_values = [[row[col] for col in columns] for row in batch]
                
                execute_batch(cur, upsert_query, batch_values, page_size=batch_size)
                total_inserted += len(batch)
                
                if i % (batch_size * 10) == 0:
                    self.logger.info(f"Processed {total_inserted}/{len(data)} records...")
        
        conn.commit()
        self.logger.info(f"✅ Upserted {total_inserted} records into {table_name}")
        return total_inserted

@asset(
    partitions_def=DAILY_PARTITIONS,
    group_name="silver_timescale",
    description="Chargement optimisé piézométrie → TimescaleDB"
)
def piezo_timescale_optimized(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    Chargement optimisé des données piézométriques vers TimescaleDB
    - Batch loading avec upserts conditionnels
    - Hypertables TimescaleDB
    - Tables: piezo_stations, piezo_observations, piezo_quality_flags
    """
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"🏗️ Chargement optimisé piézométrie {day} → TimescaleDB")
    
    config = TimescaleConfig()
    service = TimescaleDBService(config)
    
    # Simulation de lecture des données depuis MinIO
    # TODO: Implement actual MinIO reading
    # minio_data = minio_client.get_object("hubeau-bronze", f"bronze/hubeau/piezo/{day}/observations_tr.json")
    
    # Données simulées pour démonstration de la structure
    demo_stations = [
        {
            "station_id": f"BSS{i:08d}",
            "station_name": f"Station Piézo {i}",
            "latitude": 46.0 + (i * 0.01),
            "longitude": 2.0 + (i * 0.01),
            "altitude": 100 + i,
            "aquifer_name": f"Aquifère {i // 10}",
            "created_at": datetime.now()
        }
        for i in range(1, 101)  # 100 stations
    ]
    
    demo_observations = [
        {
            "station_id": f"BSS{(i % 100) + 1:08d}",
            "timestamp": datetime.fromisoformat(f"{day}T{(i % 24):02d}:00:00"),
            "water_level": 10.0 + (i % 50) * 0.5,
            "measurement_method": "auto" if i % 2 == 0 else "manual",
            "quality_code": "good" if i % 10 != 0 else "suspect",
            "created_at": datetime.now()
        }
        for i in range(1, 2401)  # 2400 observations (100 stations * 24h)
    ]
    
    demo_quality_flags = [
        {
            "station_id": f"BSS{(i % 100) + 1:08d}",
            "timestamp": datetime.fromisoformat(f"{day}T{(i % 24):02d}:00:00"),
            "flag_type": "outlier" if i % 100 == 0 else "normal",
            "flag_description": "Valeur aberrante détectée" if i % 100 == 0 else "Mesure normale",
            "confidence_score": 0.95 if i % 100 != 0 else 0.30,
            "created_at": datetime.now()
        }
        for i in range(1, 2401)
    ]
    
    total_records = 0
    tables_processed = []
    
    try:
        with service.get_connection() as conn:
            # Création des tables et hypertables
            with conn.cursor() as cur:
                # Table stations (pas d'hypertable, données référentielles)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS piezo_stations (
                        station_id VARCHAR(50) PRIMARY KEY,
                        station_name VARCHAR(200),
                        latitude DOUBLE PRECISION,
                        longitude DOUBLE PRECISION,
                        altitude INTEGER,
                        aquifer_name VARCHAR(200),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Table observations (hypertable)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS piezo_observations (
                        station_id VARCHAR(50),
                        timestamp TIMESTAMP NOT NULL,
                        water_level DOUBLE PRECISION,
                        measurement_method VARCHAR(50),
                        quality_code VARCHAR(50),
                        created_at TIMESTAMP DEFAULT NOW(),
                        PRIMARY KEY (station_id, timestamp)
                    )
                """)
                
                # Table quality flags (hypertable)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS piezo_quality_flags (
                        station_id VARCHAR(50),
                        timestamp TIMESTAMP NOT NULL,
                        flag_type VARCHAR(50),
                        flag_description TEXT,
                        confidence_score DOUBLE PRECISION,
                        created_at TIMESTAMP DEFAULT NOW(),
                        PRIMARY KEY (station_id, timestamp, flag_type)
                    )
                """)
                
                conn.commit()
            
            # Création des hypertables
            service.create_hypertable_if_not_exists(conn, "piezo_observations", "timestamp")
            service.create_hypertable_if_not_exists(conn, "piezo_quality_flags", "timestamp")
            
            # Chargement par batch avec upsert
            stations_loaded = service.batch_upsert(
                conn, "piezo_stations", demo_stations, ["station_id"]
            )
            tables_processed.append("piezo_stations")
            total_records += stations_loaded
            
            observations_loaded = service.batch_upsert(
                conn, "piezo_observations", demo_observations, ["station_id", "timestamp"]
            )
            tables_processed.append("piezo_observations")
            total_records += observations_loaded
            
            quality_flags_loaded = service.batch_upsert(
                conn, "piezo_quality_flags", demo_quality_flags, ["station_id", "timestamp", "flag_type"]
            )
            tables_processed.append("piezo_quality_flags")
            total_records += quality_flags_loaded
            
    except Exception as e:
        logger.error(f"❌ Error loading piézométrie data: {e}")
        raise
    
    return {
        "execution_date": day,
        "source": "hubeau_piezo_bronze",
        "destination": "timescaledb",
        "tables_processed": tables_processed,
        "total_records_loaded": total_records,
        "batch_size_used": 1000,
        "hypertables_created": ["piezo_observations", "piezo_quality_flags"],
        "status": "success"
    }

@asset(
    partitions_def=DAILY_PARTITIONS,
    group_name="silver_timescale",
    description="Chargement optimisé qualité → TimescaleDB avec measure_quality"
)
def quality_timescale_optimized(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    Chargement optimisé des données qualité vers TimescaleDB
    - Table measure_quality comme mentionné dans le README
    - Optimisations TimescaleDB spécifiques
    """
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"🏗️ Chargement optimisé qualité {day} → TimescaleDB")
    
    config = TimescaleConfig()
    service = TimescaleDBService(config)
    
    # Données simulées pour measure_quality
    demo_quality_measures = [
        {
            "station_id": f"QUAL{i:06d}",
            "timestamp": datetime.fromisoformat(f"{day}T{(i % 24):02d}:00:00"),
            "parameter_code": f"1340",  # Code Sandre pour Nitrates
            "parameter_name": "Nitrates",
            "value": 10.0 + (i % 100) * 0.5,
            "unit": "mg/L",
            "detection_limit": 0.1,
            "quantification_limit": 0.5,
            "measurement_method": f"METH{(i % 10) + 1}",
            "laboratory": f"LAB{(i % 5) + 1}",
            "quality_code": "1" if i % 20 != 0 else "2",
            "validation_status": "validated" if i % 10 == 0 else "raw",
            "created_at": datetime.now()
        }
        for i in range(1, 1201)  # 1200 mesures qualité
    ]
    
    total_records = 0
    
    try:
        with service.get_connection() as conn:
            # Table measure_quality (hypertable)
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS measure_quality (
                        station_id VARCHAR(50),
                        timestamp TIMESTAMP NOT NULL,
                        parameter_code VARCHAR(50),
                        parameter_name VARCHAR(200),
                        value DOUBLE PRECISION,
                        unit VARCHAR(50),
                        detection_limit DOUBLE PRECISION,
                        quantification_limit DOUBLE PRECISION,
                        measurement_method VARCHAR(100),
                        laboratory VARCHAR(100),
                        quality_code VARCHAR(10),
                        validation_status VARCHAR(50),
                        created_at TIMESTAMP DEFAULT NOW(),
                        PRIMARY KEY (station_id, timestamp, parameter_code)
                    )
                """)
                conn.commit()
            
            # Création de l'hypertable
            service.create_hypertable_if_not_exists(conn, "measure_quality", "timestamp")
            
            # Chargement optimisé
            total_records = service.batch_upsert(
                conn, "measure_quality", demo_quality_measures, 
                ["station_id", "timestamp", "parameter_code"]
            )
            
    except Exception as e:
        logger.error(f"❌ Error loading quality data: {e}")
        raise
    
    return {
        "execution_date": day,
        "source": "hubeau_quality_bronze",
        "destination": "timescaledb",
        "tables_processed": ["measure_quality"],
        "total_records_loaded": total_records,
        "batch_size_used": 1000,
        "hypertables_created": ["measure_quality"],
        "status": "success"
    }
