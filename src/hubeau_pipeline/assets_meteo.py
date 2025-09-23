"""
Assets Dagster pour les donnÃ©es mÃ©tÃ©o
Squelette pour intÃ©gration MÃ©tÃ©o-France, ERA5, etc.
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
    description="Ingestion des donnÃ©es mÃ©tÃ©o brutes (squelette)"
)
def meteo_raw(context: AssetExecutionContext, s3):
    """
    Squelette pour l'ingestion mÃ©tÃ©o
    Ã€ adapter selon la source : MÃ©tÃ©o-France, ERA5, NetCDF, etc.
    """
    day = context.partition_key
    
    # TODO: Adapter selon la source mÃ©tÃ©o
    # Exemples de sources possibles :
    # - MÃ©tÃ©o-France SAFRAN (nÃ©cessite partenariat)
    # - ERA5-Land via CDS API
    # - Fichiers NetCDF locaux
    # - API OpenWeatherMap
    # - Fichiers CSV/Parquet prÃ©-traitÃ©s
    
    # Pour l'exemple, on simule des donnÃ©es mÃ©tÃ©o
    context.log.info(f"meteo_raw: Squelette pour {day} - Ã€ implÃ©menter selon la source")
    
    # Structure attendue des donnÃ©es mÃ©tÃ©o :
    # columns: lon, lat, ts, prcp (mm), t2m (Â°C), etp (mm)
    
    key = f"meteo/raw/date={day}/meteo_{day}.parquet"
    
    # Simulation de donnÃ©es pour les tests
    sample_data = pd.DataFrame({
        'lon': [2.3522, 2.3522, 2.3522],  # Paris
        'lat': [48.8566, 48.8566, 48.8566],
        'ts': [pd.Timestamp(day) + pd.Timedelta(hours=h) for h in [0, 6, 12]],
        'prcp': [0.0, 2.5, 0.0],  # mm
        't2m': [15.0, 12.5, 18.0],  # Â°C
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
    
    context.log.info(f"meteo_raw: DonnÃ©es simulÃ©es sauvegardÃ©es pour {day}")
    
    return {"count": len(sample_data), "key": key}

@asset(
    partitions_def=PART_DAY, 
    deps=[meteo_raw], 
    group_name="warehouse_silver",
    description="Chargement des donnÃ©es mÃ©tÃ©o vers TimescaleDB"
)
def meteo_timescale(context: AssetExecutionContext, s3, pg, meteo_raw):
    """Chargement des donnees meteo vers TimescaleDB avec grille normalisee"""
    key = meteo_raw["key"]
    obj = s3["client"].get_object(Bucket=s3["bucket"], Key=key)
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()))

    if df.empty:
        return {"loaded": 0}

    df = df.dropna(subset=["lon", "lat", "ts"]).copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    df = df.dropna(subset=["ts"])  # filtre les timestamps invalides

    if df.empty:
        return {"loaded": 0}

    with pg.cursor() as cur:
        # Preparation des tables temporaires
        cur.execute("""
            CREATE TEMP TABLE IF NOT EXISTS stg_meteo_grid(
                lon DOUBLE PRECISION,
                lat DOUBLE PRECISION
            );
        """)
        cur.execute("TRUNCATE TABLE stg_meteo_grid;")

        with cur.copy("COPY stg_meteo_grid (lon,lat) FROM STDIN WITH (FORMAT CSV)") as cp:
            for row in df[["lon", "lat"]].drop_duplicates().itertuples(index=False):
                cp.write_row([row.lon, row.lat])

        cur.execute("""
            INSERT INTO meteo_grid(lon, lat, geom)
            SELECT DISTINCT
                lon,
                lat,
                ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography
            FROM stg_meteo_grid
            ON CONFLICT (lon, lat) DO NOTHING;
        """)

        cur.execute("""
            CREATE TEMP TABLE IF NOT EXISTS stg_meteo_series(
                lon DOUBLE PRECISION,
                lat DOUBLE PRECISION,
                ts TIMESTAMPTZ,
                prcp DOUBLE PRECISION,
                t2m DOUBLE PRECISION,
                etp DOUBLE PRECISION
            );
        """)
        cur.execute("TRUNCATE TABLE stg_meteo_series;")

        with cur.copy("COPY stg_meteo_series (lon,lat,ts,prcp,t2m,etp) FROM STDIN WITH (FORMAT CSV)") as cp:
            for row in df.itertuples(index=False):
                cp.write_row([
                    row.lon,
                    row.lat,
                    pd.to_datetime(row.ts).isoformat(),
                    None if pd.isna(row.prcp) else row.prcp,
                    None if pd.isna(row.t2m) else row.t2m,
                    None if pd.isna(row.etp) else row.etp,
                ])

        cur.execute("""
            INSERT INTO meteo_series (grid_id, ts, prcp, t2m, etp, source)
            SELECT
                g.grid_id,
                s.ts,
                s.prcp,
                s.t2m,
                s.etp,
                %s
            FROM stg_meteo_series s
            JOIN meteo_grid g ON g.lon = s.lon AND g.lat = s.lat
            ON CONFLICT (grid_id, ts) DO UPDATE
            SET prcp = EXCLUDED.prcp,
                t2m = EXCLUDED.t2m,
                etp = EXCLUDED.etp,
                source = EXCLUDED.source;
        """, ("meteo_simulated",))

        cur.execute("DROP TABLE IF EXISTS stg_meteo_series")
        cur.execute("DROP TABLE IF EXISTS stg_meteo_grid")

    context.log.info(f"meteo_timescale: {len(df)} enregistrements meteo charges")

    return {"loaded": len(df)}

@asset(
    group_name="warehouse_silver",
    description="Mise Ã  jour des liens station-grille mÃ©tÃ©o"
)
def station2grid_update(context: AssetExecutionContext, pg):
    """Mise Ã  jour de la table de correspondance station-grille mÃ©tÃ©o"""
    with pg.cursor() as cur:
        # Suppression et recrÃ©ation de la table de correspondance
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
    
    context.log.info(f"station2grid_update: {count} stations liÃ©es Ã  la grille mÃ©tÃ©o")
    
    return {"linked_stations": count}

@asset(
    group_name="meteo_gold",
    description="Vue agrÃ©gÃ©e mÃ©tÃ©o par station"
)
def meteo_station_summary(context: AssetExecutionContext, pg):
    """CrÃ©ation d'une vue agrÃ©gÃ©e des donnÃ©es mÃ©tÃ©o par station"""
    with pg.cursor() as cur:
        # CrÃ©ation d'une vue matÃ©rialisÃ©e pour les agrÃ©gats mÃ©tÃ©o par station
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
    
    context.log.info(f"meteo_station_summary: {count} enregistrements mÃ©tÃ©o agrÃ©gÃ©s par station")
    
    return {"aggregated_records": count}



