"""
Assets Dagster pour la qualitÃ© v2 (Hub'Eau)
ModÃ¨le spÃ©cialisÃ© avec thÃ©saurus Sandre
"""

import io
import datetime as dt
import pandas as pd
from dagster import (
    asset, 
    DailyPartitionsDefinition, 
    AssetExecutionContext,
    FreshnessPolicy
)

PART_DAY = DailyPartitionsDefinition(start_date="2015-01-01")
FRESH_DAILY = FreshnessPolicy(maximum_lag_minutes=24*60)

def _fetch_all(http, base_url: str, params: dict):
    """Pagination standard Hub'Eau optimisÃ©e"""
    rows, page = [], 1
    while True:
        r = http.get(base_url, params={**params, "page": page, "size": 10000})
        r.raise_for_status()
        j = r.json() or {}
        rows += j.get("data", [])
        if page >= int(j.get("totalPages", 1) or 1):
            break
        page += 1
        # Rate limiting respectueux
        import time
        time.sleep(0.1)
    return rows

@asset(
    partitions_def=PART_DAY, 
    group_name="hubeau_bronze",
    description="Ingestion des donnÃ©es de qualitÃ© eaux de surface v2",
    freshness_policy=FRESH_DAILY
)
def quality_raw(context: AssetExecutionContext, http_client, s3):
    """Ingestion des donnÃ©es de qualitÃ© depuis Hub'Eau v2"""
    day = context.partition_key
    d0 = dt.datetime.fromisoformat(day)
    d1 = d0 + dt.timedelta(days=1)
    
    url = "https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface/analyse"
    params = {
        "date_debut_prelevement": d0.strftime("%Y-%m-%d"), 
        "date_fin_prelevement": d1.strftime("%Y-%m-%d")
    }
    
    rows = _fetch_all(http_client, url, params)
    
    df = pd.DataFrame([{
        "station_code": r.get("code_station"),
        "param_code":   r.get("code_parametre"),
        "ts":           pd.to_datetime(r.get("date_prelevement"), utc=True, errors="coerce"),
        "value":        r.get("resultat"),
        "unit":         r.get("code_unite"),
        "quality":      r.get("code_remarque"),
        "source":       "hubeau_quality_v2"
    } for r in rows]).dropna(subset=["station_code","param_code","ts"])
    
    key = f"hubeau/quality/raw/date={day}/quality_{day}.parquet"
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    s3["client"].put_object(Bucket=s3["bucket"], Key=key, Body=buf.getvalue())
    
    context.log.info(f"quality_raw: {len(df)} rows saved to s3://{s3['bucket']}/{key}")
    
    return {"count": len(df), "key": key}

@asset(
    partitions_def=PART_DAY, 
    deps=[quality_raw], 
    group_name="warehouse_silver",
    description="Chargement des donnÃ©es qualitÃ© vers TimescaleDB"
)
def quality_timescale(context: AssetExecutionContext, pg, s3, quality_raw):
    """Chargement des donnees qualite vers TimescaleDB (table specialisee)"""
    key = quality_raw["key"]
    obj = s3["client"].get_object(Bucket=s3["bucket"], Key=key)
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()))

    if df.empty:
        return {"loaded": 0}

    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    df = df.dropna(subset=["station_code", "param_code", "ts"]).copy()

    if df.empty:
        return {"loaded": 0}

    partition_day = context.partition_key
    if partition_day:
        start_ts = pd.Timestamp(partition_day).tz_localize("UTC")
    else:
        start_ts = pd.to_datetime(df["ts"].min())
    end_ts = start_ts + pd.Timedelta(days=1)

    with pg.cursor() as cur:
        cur.execute(
            "DELETE FROM measure_quality WHERE ts >= %s AND ts < %s AND source = %s",
            (start_ts.to_pydatetime(), end_ts.to_pydatetime(), "hubeau_quality_v2"),
        )

        with cur.copy("""
            COPY measure_quality (station_code,param_code,ts,value,unit,quality,source)
            FROM STDIN WITH (FORMAT CSV)
        """) as cp:
            for r in df.itertuples(index=False):
                cp.write_row([
                    r.station_code,
                    r.param_code,
                    pd.to_datetime(r.ts).isoformat(),
                    None if pd.isna(r.value) else r.value,
                    None if pd.isna(r.unit) else r.unit,
                    None if pd.isna(r.quality) else r.quality,
                    "hubeau_quality_v2",
                ])

    context.log.info(f"quality_timescale: {len(df)} records loaded to TimescaleDB")

    return {"loaded": len(df)}

@asset(
    partitions_def=PART_DAY,
    group_name="hubeau_bronze",
    description="Ingestion des donnÃ©es de qualitÃ© eaux souterraines v2"
)
def quality_groundwater_raw(context: AssetExecutionContext, http_client, s3):
    """Ingestion des donnÃ©es de qualitÃ© eaux souterraines depuis Hub'Eau"""
    day = context.partition_key
    d0 = dt.datetime.fromisoformat(day)
    d1 = d0 + dt.timedelta(days=1)
    
    url = "https://hubeau.eaufrance.fr/api/v1/qualite_eaux_souterraines/analyse"
    params = {
        "date_debut_prelevement": d0.strftime("%Y-%m-%d"), 
        "date_fin_prelevement": d1.strftime("%Y-%m-%d")
    }
    
    rows = _fetch_all(http_client, url, params)
    
    df = pd.DataFrame([{
        "station_code": r.get("code_bss") or r.get("code_station"),
        "param_code":   r.get("code_parametre"),
        "ts":           pd.to_datetime(r.get("date_prelevement"), utc=True, errors="coerce"),
        "value":        r.get("resultat"),
        "unit":         r.get("code_unite"),
        "quality":      r.get("code_remarque"),
        "source":       "hubeau_quality_groundwater_v2"
    } for r in rows]).dropna(subset=["station_code","param_code","ts"])
    
    key = f"hubeau/quality_groundwater/raw/date={day}/quality_groundwater_{day}.parquet"
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    s3["client"].put_object(Bucket=s3["bucket"], Key=key, Body=buf.getvalue())
    
    context.log.info(f"quality_groundwater_raw: {len(df)} rows saved")
    
    return {"count": len(df), "key": key}

@asset(
    partitions_def=PART_DAY, 
    deps=[quality_groundwater_raw], 
    group_name="warehouse_silver"
)
def quality_groundwater_timescale(context: AssetExecutionContext, pg, s3, quality_groundwater_raw):
    """Chargement des donnees qualite eaux souterraines vers TimescaleDB"""
    key = quality_groundwater_raw["key"]
    obj = s3["client"].get_object(Bucket=s3["bucket"], Key=key)
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()))

    if df.empty:
        return {"loaded": 0}

    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    df = df.dropna(subset=["station_code", "param_code", "ts"]).copy()

    if df.empty:
        return {"loaded": 0}

    partition_day = context.partition_key
    if partition_day:
        start_ts = pd.Timestamp(partition_day).tz_localize("UTC")
    else:
        start_ts = pd.to_datetime(df["ts"].min())
    end_ts = start_ts + pd.Timedelta(days=1)

    with pg.cursor() as cur:
        cur.execute(
            "DELETE FROM measure_quality WHERE ts >= %s AND ts < %s AND source = %s",
            (start_ts.to_pydatetime(), end_ts.to_pydatetime(), "hubeau_quality_groundwater_v2"),
        )

        with cur.copy("""
            COPY measure_quality (station_code,param_code,ts,value,unit,quality,source)
            FROM STDIN WITH (FORMAT CSV)
        """) as cp:
            for r in df.itertuples(index=False):
                cp.write_row([
                    r.station_code,
                    r.param_code,
                    pd.to_datetime(r.ts).isoformat(),
                    None if pd.isna(r.value) else r.value,
                    None if pd.isna(r.unit) else r.unit,
                    None if pd.isna(r.quality) else r.quality,
                    "hubeau_quality_groundwater_v2",
                ])

    context.log.info(f"quality_groundwater_timescale: {len(df)} records loaded")

    return {"loaded": len(df)}



