"""
Assets Dagster pour les données météo
Squelette pour intégration Météo-France, ERA5, etc.
"""

import io
import pandas as pd
import datetime as dt
from dagster import (
    asset, 
    DailyPartitionsDefinition, 
    AssetExecutionContext
)

PART_DAY = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PART_DAY, 
    group_name="meteo_bronze",
    description="Ingestion des données météo brutes (squelette)"
)
def meteo_raw(context: AssetExecutionContext, s3):
    """
    Squelette pour l'ingestion météo
    À adapter selon la source : Météo-France, ERA5, NetCDF, etc.
    """
    day = context.partition_key
    
    # TODO: Adapter selon la source météo
    # Exemples de sources possibles :
    # - Météo-France SAFRAN (nécessite partenariat)
    # - ERA5-Land via CDS API
    # - Fichiers NetCDF locaux
    # - API OpenWeatherMap
    # - Fichiers CSV/Parquet pré-traités
    
    # Pour l'exemple, on simule des données météo
    context.log.info(f"meteo_raw: Squelette pour {day} - À implémenter selon la source")
    
    # Structure attendue des données météo :
    # columns: lon, lat, ts, prcp (mm), t2m (°C), etp (mm)
    
    key = f"meteo/raw/date={day}/meteo_{day}.parquet"
    
    # Simulation de données pour les tests
    sample_data = pd.DataFrame({
        'lon': [2.3522, 2.3522, 2.3522],  # Paris
        'lat': [48.8566, 48.8566, 48.8566],
        'ts': [pd.Timestamp(day) + pd.Timedelta(hours=h) for h in [0, 6, 12]],
        'prcp': [0.0, 2.5, 0.0],  # mm
        't2m': [15.0, 12.5, 18.0],  # °C
        'etp': [1.0, 0.5, 2.0]  # mm
    })
    
    buf = io.BytesIO()
    sample_data.to_parquet(buf, index=False)
    s3["client"].put_object(
        Bucket=s3["bucket"], 
        Key=key, 
        Body=buf.getvalue(),
        ContentType="application/octet-stream"
    )
    
    context.log.info(f"meteo_raw: Données simulées sauvegardées pour {day}")
    
    return {"count": len(sample_data), "key": key}

@asset(
    partitions_def=PART_DAY, 
    deps=[meteo_raw], 
    group_name="warehouse_silver",
    description="Chargement des données météo vers TimescaleDB"
)
def meteo_timescale(context: AssetExecutionContext, s3, pg, meteo_raw):
    """Chargement des données météo vers TimescaleDB avec grille normalisée"""
    key = meteo_raw["key"]
    obj = s3["client"].get_object(Bucket=s3["bucket"], Key=key)
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()))
    
    if df.empty:
        return {"loaded": 0}
    
    with pg.cursor() as cur:
        # 1) Upsert grille météo (idempotent)
        cur.execute("""
            CREATE TEMP TABLE stg_meteo_grid(
                lon DOUBLE PRECISION, 
                lat DOUBLE PRECISION
            ) ON COMMIT DROP;
        """)
        
        with cur.copy("COPY stg_meteo_grid (lon,lat) FROM STDIN WITH (FORMAT CSV)") as cp:
            for row in df[["lon","lat"]].drop_duplicates().itertuples(index=False):
                cp.write_row([row.lon, row.lat])
        
        cur.execute("""
            INSERT INTO meteo_grid(lon, lat, geom)
            SELECT 
                lon, lat, 
                ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography
            FROM stg_meteo_grid
            ON CONFLICT (lon, lat) DO NOTHING;
        """)
        
        # 2) Récupération des grid_id pour les séries
        cur.execute("""
            CREATE TEMP TABLE stg_meteo_series AS
            SELECT 
                g.grid_id,
                d.ts,
                d.prcp,
                d.t2m,
                d.etp
            FROM (
                SELECT DISTINCT lon, lat, ts, prcp, t2m, etp
                FROM (VALUES %s) AS t(lon, lat, ts, prcp, t2m, etp)
            ) d
            JOIN meteo_grid g ON g.lon = d.lon AND g.lat = d.lat;
        """, [tuple(row) for row in df[["lon","lat","ts","prcp","t2m","etp"]].values])
        
        # 3) Chargement des séries météo
        with cur.copy("""
            COPY meteo_series (grid_id, ts, prcp, t2m, etp, source)
            FROM STDIN WITH (FORMAT CSV)
        """) as cp:
            for row in df.itertuples(index=False):
                # Récupération du grid_id (à optimiser avec un cache)
                cur.execute("""
                    SELECT grid_id FROM meteo_grid 
                    WHERE lon = %s AND lat = %s
                """, (row.lon, row.lat))
                grid_id = cur.fetchone()[0]
                
                cp.write_row([
                    grid_id,
                    pd.to_datetime(row.ts).strftime("%Y-%m-%d %H:%M:%S%z"),
                    None if pd.isna(row.prcp) else row.prcp,
                    None if pd.isna(row.t2m) else row.t2m,
                    None if pd.isna(row.etp) else row.etp,
                    "meteo_simulated"
                ])
    
    context.log.info(f"meteo_timescale: {len(df)} enregistrements météo chargés")
    
    return {"loaded": len(df)}

@asset(
    group_name="warehouse_silver",
    description="Mise à jour des liens station-grille météo"
)
def station2grid_update(context: AssetExecutionContext, pg):
    """Mise à jour de la table de correspondance station-grille météo"""
    with pg.cursor() as cur:
        # Suppression et recréation de la table de correspondance
        cur.execute("DROP TABLE IF EXISTS station2grid")
        
        cur.execute("""
            CREATE TABLE station2grid AS 
            SELECT s.station_code, g.grid_id 
            FROM station_meta s 
            JOIN LATERAL (
                SELECT grid_id FROM meteo_grid
                ORDER BY s.geom <-> meteo_grid.geom
                LIMIT 1
            ) g ON TRUE;
        """)
        
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS station2grid_pk ON station2grid(station_code)")
        
        # Statistiques
        cur.execute("SELECT COUNT(*) FROM station2grid")
        count = cur.fetchone()[0]
    
    context.log.info(f"station2grid_update: {count} stations liées à la grille météo")
    
    return {"linked_stations": count}

@asset(
    group_name="meteo_gold",
    description="Vue agrégée météo par station"
)
def meteo_station_summary(context: AssetExecutionContext, pg):
    """Création d'une vue agrégée des données météo par station"""
    with pg.cursor() as cur:
        # Création d'une vue matérialisée pour les agrégats météo par station
        cur.execute("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS meteo_station_daily AS
            SELECT 
                s.station_code,
                time_bucket('1 day', ms.ts) AS day,
                AVG(ms.prcp) AS avg_precipitation_mm,
                SUM(ms.prcp) AS total_precipitation_mm,
                AVG(ms.t2m) AS avg_temperature_c,
                MIN(ms.t2m) AS min_temperature_c,
                MAX(ms.t2m) AS max_temperature_c,
                AVG(ms.etp) AS avg_etp_mm,
                SUM(ms.etp) AS total_etp_mm
            FROM station2grid s2g
            JOIN meteo_series ms ON s2g.grid_id = ms.grid_id
            JOIN station_meta s ON s2g.station_code = s.station_code
            WHERE ms.ts >= NOW() - INTERVAL '1 year'
            GROUP BY s.station_code, time_bucket('1 day', ms.ts)
            ORDER BY s.station_code, day;
        """)
        
        cur.execute("SELECT COUNT(*) FROM meteo_station_daily")
        count = cur.fetchone()[0]
    
    context.log.info(f"meteo_station_summary: {count} enregistrements météo agrégés par station")
    
    return {"aggregated_records": count}
