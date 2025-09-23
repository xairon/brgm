"""
Assets Dagster pour l'intÃ©gration complÃ¨te des donnÃ©es Hub'Eau
Pipeline d'ingestion : Hub'Eau APIs -> MinIO -> TimescaleDB -> Neo4j
IntÃ©gration des ontologies RDF et sources externes
"""

import io
import json
import datetime as dt
import pandas as pd
from typing import Dict, Any, List, Optional
from dagster import (
    AssetExecutionContext, 
    asset, 
    DailyPartitionsDefinition, 
    define_asset_job, 
    ScheduleDefinition, 
    SensorEvaluationContext, 
    sensor, 
    RunRequest,
    get_dagster_logger,
    AssetMaterialization,
    MetadataValue,
    FreshnessPolicy
)
from dagster._core.definitions.asset_check_spec import AssetCheckSpec
from dagster._core.definitions.asset_checks import asset_check


# Configuration des partitions journaliÃ¨res
PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

# Freshness policies pour les assets critiques
FRESH_DAILY = FreshnessPolicy(maximum_lag_minutes=24*60)  # 24h

# Configuration des endpoints Hub'Eau
HUBEAU_ENDPOINTS = {
    "piezo": {
        "observations_tr": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/observations_tr",
        "chroniques": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques",
        "stations": "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/stations"
    },
    "hydro": {
        "observations_tr": "https://hubeau.eaufrance.fr/api/v1/hydrometrie/observations_tr",
        "chroniques": "https://hubeau.eaufrance.fr/api/v1/hydrometrie/chroniques",
        "stations": "https://hubeau.eaufrance.fr/api/v1/hydrometrie/stations"
    },
    "temperature": {
        "chroniques_tr": "https://hubeau.eaufrance.fr/api/v1/temperature/chroniques_tr",
        "stations": "https://hubeau.eaufrance.fr/api/v1/temperature/stations"
    },
    "ecoulement": {
        "chroniques": "https://hubeau.eaufrance.fr/api/v1/ecoulement_cours_eau/chroniques",
        "stations": "https://hubeau.eaufrance.fr/api/v1/ecoulement_cours_eau/stations"
    },
    "hydrobiologie": {
        "indicateurs": "https://hubeau.eaufrance.fr/api/v1/hydrobiologie/indicateurs",
        "stations": "https://hubeau.eaufrance.fr/api/v1/hydrobiologie/stations"
    },
    "quality_surface": {
        "analyse": "https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface/analyse",
        "stations": "https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface/stations"
    },
    "quality_groundwater": {
        "analyse": "https://hubeau.eaufrance.fr/api/v1/qualite_eaux_souterraines/analyse",
        "stations": "https://hubeau.eaufrance.fr/api/v1/qualite_eaux_souterraines/stations"
    },
    "prelevements": {
        "prelevements": "https://hubeau.eaufrance.fr/api/v1/prelevements_eau/prelevements"
    }
}


# ---------- Fonctions utilitaires ----------
def fetch_hubeau(http, base_url: str, params: dict):
    """Pagination standard Hub'Eau: fields page/size/totalPages."""
    rows, page = [], 1
    while True:
        resp = http.get(base_url, params={**params, "page": page, "size": 10000})
        resp.raise_for_status()
        data = resp.json() or {}
        rows.extend(data.get("data", []))
        if page >= int(data.get("totalPages", 1) or 1):
            break
        page += 1
        # Rate limiting respectueux
        import time
        time.sleep(0.1)
    return rows

def fetch_hubeau_data(http_client, endpoints: List[Dict], day: str) -> List[Dict]:
    """Fonction gÃ©nÃ©rique pour rÃ©cupÃ©rer les donnÃ©es Hub'Eau (version optimisÃ©e)"""
    log = get_dagster_logger()
    d0 = dt.datetime.fromisoformat(day)
    d1 = d0 + dt.timedelta(days=1)
    
    all_rows = []
    
    for endpoint_config in endpoints:
        url = endpoint_config["url"]
        source = endpoint_config["source"]
        
        # ParamÃ¨tres communs
        params = {
            "date_debut": d0.strftime("%Y-%m-%d"), 
            "date_fin": d1.strftime("%Y-%m-%d")
        }
        
        try:
            endpoint_rows = fetch_hubeau(http_client, url, params)
            all_rows.extend(endpoint_rows)
            log.info(f"Total records from {source}: {len(endpoint_rows)}")
        except Exception as e:
            log.error(f"Error fetching from {source}: {e}")
    
    return all_rows


def normalize_measure_data(rows: List[Dict], theme: str, source: str) -> List[Dict]:
    """Normalisation des donnÃ©es de mesure"""
    normalized_data = []
    
    for row in rows:
        # Normalisation des codes de station
        station_code = (row.get("bss_id") or 
                       row.get("code_bss") or 
                       row.get("code_station") or 
                       row.get("code_site") or
                       row.get("station"))
        
        if not station_code:
            continue
            
        # Normalisation des timestamps
        date_measure = (row.get("date_mesure") or 
                       row.get("date_time") or 
                       row.get("timestamp") or
                       row.get("date_observation"))
        
        if not date_measure:
            continue
            
        # Normalisation des valeurs selon le thÃ¨me
        if theme == "piezo":
            value = (row.get("niveau_nappe") or 
                    row.get("valeur") or 
                    row.get("niveau"))
        elif theme == "hydro":
            value = (row.get("hauteur_eau") or 
                    row.get("debit") or 
                    row.get("valeur"))
        elif theme == "temperature":
            value = (row.get("temperature") or 
                    row.get("valeur"))
        elif theme in ["quality_surface", "quality_groundwater"]:
            value = (row.get("resultat") or 
                    row.get("valeur") or
                    row.get("concentration"))
        else:
            value = row.get("valeur")
        
        normalized_data.append({
            "station_code": station_code,
            "theme": theme,
            "ts": pd.to_datetime(date_measure),
            "value": float(value) if value is not None else None,
            "quality": row.get("code_qualite") or row.get("qualite"),
            "source": source,
            "raw_data": json.dumps(row)
        })
    
    return normalized_data


# ---------- Assets pour chaque API Hub'Eau ----------

# 1. PiÃ©zomÃ©trie
@asset(
    partitions_def=PARTITIONS, 
    group_name="hubeau_bronze",
    description="Ingestion des donnÃ©es piÃ©zomÃ©triques brutes depuis Hub'Eau vers MinIO",
    freshness_policy=FRESH_DAILY
)
def piezo_raw(context: AssetExecutionContext, http_client, s3):
    """Ingestion des donnÃ©es piÃ©zomÃ©triques depuis Hub'Eau"""
    log = get_dagster_logger()
    day = context.asset_partition_key_for_output()
    
    log.info(f"Starting piezo_raw ingestion for {day}")
    
    # Configuration des endpoints piÃ©zomÃ©trie
    endpoints = [
        {
            "url": HUBEAU_ENDPOINTS["piezo"]["observations_tr"],
            "source": "hubeau_piezo_tr"
        },
        {
            "url": HUBEAU_ENDPOINTS["piezo"]["chroniques"],
            "source": "hubeau_piezo_chroniques"
        }
    ]
    
    # RÃ©cupÃ©ration des donnÃ©es
    all_rows = fetch_hubeau_data(http_client, endpoints, day)
    
    # Normalisation
    normalized_data = normalize_measure_data(all_rows, "piezo", "hubeau_piezo")
    
    if not normalized_data:
        log.warning(f"No piezo data found for {day}")
        return {"count": 0, "key": None}
    
    # Conversion et sauvegarde
    df = pd.DataFrame(normalized_data).dropna(subset=["station_code", "ts"])
    
    key = f"piezo/raw/date={day}/piezo_{day}.parquet"
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    
    s3["client"].put_object(
        Bucket=s3["bucket"], 
        Key=key, 
        Body=buf.getvalue(),
        ContentType="application/octet-stream"
    )
    
    log.info(f"piezo_raw: {len(df)} rows saved to s3://{s3['bucket']}/{key}")
    
    return {
        "count": len(df),
        "key": key,
        "date": day,
        "endpoints_processed": len(endpoints)
    }


# 2. HydromÃ©trie
@asset(
    partitions_def=PARTITIONS,
    group_name="hubeau_bronze",
    description="Ingestion des donnÃ©es hydromÃ©triques brutes depuis Hub'Eau",
    freshness_policy=FRESH_DAILY
)
def hydro_raw(context: AssetExecutionContext, http_client, s3):
    """Ingestion des donnÃ©es hydromÃ©triques depuis Hub'Eau"""
    log = get_dagster_logger()
    day = context.asset_partition_key_for_output()
    
    endpoints = [
        {
            "url": HUBEAU_ENDPOINTS["hydro"]["observations_tr"],
            "source": "hubeau_hydro_tr"
        },
        {
            "url": HUBEAU_ENDPOINTS["hydro"]["chroniques"],
            "source": "hubeau_hydro_chroniques"
        }
    ]
    
    all_rows = fetch_hubeau_data(http_client, endpoints, day)
    normalized_data = normalize_measure_data(all_rows, "hydro", "hubeau_hydro")
    
    if not normalized_data:
        log.warning(f"No hydro data found for {day}")
        return {"count": 0, "key": None}
    
    df = pd.DataFrame(normalized_data).dropna(subset=["station_code", "ts"])
    
    key = f"hydro/raw/date={day}/hydro_{day}.parquet"
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    
    s3["client"].put_object(
        Bucket=s3["bucket"], 
        Key=key, 
        Body=buf.getvalue(),
        ContentType="application/octet-stream"
    )
    
    log.info(f"hydro_raw: {len(df)} rows saved")
    
    return {
        "count": len(df),
        "key": key,
        "date": day
    }


# 3. TempÃ©rature des cours d'eau
@asset(
    partitions_def=PARTITIONS,
    group_name="hubeau_bronze",
    description="Ingestion des donnÃ©es de tempÃ©rature des cours d'eau"
)
def temperature_raw(context: AssetExecutionContext, http_client, s3):
    """Ingestion des donnÃ©es de tempÃ©rature depuis Hub'Eau"""
    log = get_dagster_logger()
    day = context.asset_partition_key_for_output()
    
    endpoints = [{
        "url": HUBEAU_ENDPOINTS["temperature"]["chroniques_tr"],
        "source": "hubeau_temperature"
    }]
    
    all_rows = fetch_hubeau_data(http_client, endpoints, day)
    normalized_data = normalize_measure_data(all_rows, "temperature", "hubeau_temperature")
    
    if not normalized_data:
        log.warning(f"No temperature data found for {day}")
        return {"count": 0, "key": None}
    
    df = pd.DataFrame(normalized_data).dropna(subset=["station_code", "ts"])
    
    key = f"temperature/raw/date={day}/temperature_{day}.parquet"
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    
    s3["client"].put_object(
        Bucket=s3["bucket"], 
        Key=key, 
        Body=buf.getvalue(),
        ContentType="application/octet-stream"
    )
    
    log.info(f"temperature_raw: {len(df)} rows saved")
    
    return {
        "count": len(df),
        "key": key,
        "date": day
    }


# 4. Ã‰coulement des cours d'eau
@asset(
    partitions_def=PARTITIONS,
    group_name="hubeau_bronze",
    description="Ingestion des donnÃ©es d'Ã©coulement des cours d'eau"
)
def ecoulement_raw(context: AssetExecutionContext, http_client, s3):
    """Ingestion des donnÃ©es d'Ã©coulement depuis Hub'Eau"""
    log = get_dagster_logger()
    day = context.asset_partition_key_for_output()
    
    endpoints = [{
        "url": HUBEAU_ENDPOINTS["ecoulement"]["chroniques"],
        "source": "hubeau_ecoulement"
    }]
    
    all_rows = fetch_hubeau_data(http_client, endpoints, day)
    normalized_data = normalize_measure_data(all_rows, "ecoulement", "hubeau_ecoulement")
    
    if not normalized_data:
        log.warning(f"No ecoulement data found for {day}")
        return {"count": 0, "key": None}
    
    df = pd.DataFrame(normalized_data).dropna(subset=["station_code", "ts"])
    
    key = f"ecoulement/raw/date={day}/ecoulement_{day}.parquet"
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    
    s3["client"].put_object(
        Bucket=s3["bucket"], 
        Key=key, 
        Body=buf.getvalue(),
        ContentType="application/octet-stream"
    )
    
    log.info(f"ecoulement_raw: {len(df)} rows saved")
    
    return {
        "count": len(df),
        "key": key,
        "date": day
    }


# 5. Hydrobiologie
@asset(
    partitions_def=PARTITIONS,
    group_name="hubeau_bronze",
    description="Ingestion des donnÃ©es hydrobiologiques"
)
def hydrobiologie_raw(context: AssetExecutionContext, http_client, s3):
    """Ingestion des donnÃ©es hydrobiologiques depuis Hub'Eau"""
    log = get_dagster_logger()
    day = context.asset_partition_key_for_output()
    
    endpoints = [{
        "url": HUBEAU_ENDPOINTS["hydrobiologie"]["indicateurs"],
        "source": "hubeau_hydrobiologie"
    }]
    
    all_rows = fetch_hubeau_data(http_client, endpoints, day)
    normalized_data = normalize_measure_data(all_rows, "hydrobiologie", "hubeau_hydrobiologie")
    
    if not normalized_data:
        log.warning(f"No hydrobiologie data found for {day}")
        return {"count": 0, "key": None}
    
    df = pd.DataFrame(normalized_data).dropna(subset=["station_code", "ts"])
    
    key = f"hydrobiologie/raw/date={day}/hydrobiologie_{day}.parquet"
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    
    s3["client"].put_object(
        Bucket=s3["bucket"], 
        Key=key, 
        Body=buf.getvalue(),
        ContentType="application/octet-stream"
    )
    
    log.info(f"hydrobiologie_raw: {len(df)} rows saved")
    
    return {
        "count": len(df),
        "key": key,
        "date": day
    }


# 6. Qualite des eaux de surface
@asset(
    partitions_def=PARTITIONS,
    group_name="hubeau_bronze",
    description="Ingestion des donnees de qualite des eaux de surface"
)
def quality_surface_raw(context: AssetExecutionContext, http_client, s3):
    """Ingestion des donnees de qualite des eaux de surface depuis Hub'Eau"""
    log = get_dagster_logger()
    day = context.asset_partition_key_for_output()

    endpoints = [{
        "url": HUBEAU_ENDPOINTS["quality_surface"]["analyse"],
        "source": "hubeau_quality_surface"
    }]

    all_rows = fetch_hubeau_data(http_client, endpoints, day)
    normalized_data = normalize_measure_data(all_rows, "quality_surface", "hubeau_quality_surface")

    if not normalized_data:
        log.warning(f"No quality_surface data found for {day}")
        return {"count": 0, "key": None}

    df = pd.DataFrame(normalized_data).dropna(subset=["station_code", "ts"])

    key = f"quality_surface/raw/date={day}/quality_surface_{day}.parquet"
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)

    s3["client"].put_object(
        Bucket=s3["bucket"],
        Key=key,
        Body=buf.getvalue(),
        ContentType="application/octet-stream"
    )

    log.info(f"quality_surface_raw: {len(df)} rows saved")

    return {
        "count": len(df),
        "key": key,
        "date": day
    }


# 7. Prelevements d'eau
@asset(
    partitions_def=PARTITIONS,
    group_name="hubeau_bronze",
    description="Ingestion des donnÃ©es de prÃ©lÃ¨vements d'eau"
)
def prelevements_raw(context: AssetExecutionContext, http_client, s3):
    """Ingestion des donnÃ©es de prÃ©lÃ¨vements depuis Hub'Eau"""
    log = get_dagster_logger()
    day = context.asset_partition_key_for_output()
    
    endpoints = [{
        "url": HUBEAU_ENDPOINTS["prelevements"]["prelevements"],
        "source": "hubeau_prelevements"
    }]
    
    all_rows = fetch_hubeau_data(http_client, endpoints, day)
    normalized_data = normalize_measure_data(all_rows, "prelevements", "hubeau_prelevements")
    
    if not normalized_data:
        log.warning(f"No prelevements data found for {day}")
        return {"count": 0, "key": None}
    
    df = pd.DataFrame(normalized_data).dropna(subset=["station_code", "ts"])
    
    key = f"prelevements/raw/date={day}/prelevements_{day}.parquet"
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    
    s3["client"].put_object(
        Bucket=s3["bucket"], 
        Key=key, 
        Body=buf.getvalue(),
        ContentType="application/octet-stream"
    )
    
    log.info(f"prelevements_raw: {len(df)} rows saved")
    
    return {
        "count": len(df),
        "key": key,
        "date": day
    }


# ---------- Asset 2 : Chargement TimescaleDB (Silver Layer) ----------
@asset(
    partitions_def=PARTITIONS, 
    deps=[piezo_raw], 
    group_name="warehouse_silver",
    description="Chargement des donnÃ©es piÃ©zomÃ©triques vers TimescaleDB"
)
def piezo_timescale(context: AssetExecutionContext, pg, s3, piezo_raw):
    """Chargement des donnÃ©es normalisÃ©es vers TimescaleDB"""
    log = get_dagster_logger()
    
    if not piezo_raw["key"]:
        log.warning("No data to load to TimescaleDB")
        return {"loaded": 0}
    
    # RÃ©cupÃ©ration des donnÃ©es depuis MinIO
    key = piezo_raw["key"]
    obj = s3["client"].get_object(Bucket=s3["bucket"], Key=key)
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()))
    
    log.info(f"Loading {len(df)} records to TimescaleDB")
    
    # Upsert idempotent vers TimescaleDB avec COPY optimisÃ©
    with pg.cursor() as cur:
        with cur.copy("COPY measure (station_code, theme, ts, value, quality, source) FROM STDIN WITH (FORMAT CSV)") as cp:
            for r in df.itertuples(index=False):
                cp.write_row([
                    r.station_code, 
                    "piezo",
                    pd.to_datetime(r.ts).strftime("%Y-%m-%d %H:%M:%S%z"),
                    None if pd.isna(r.value) else r.value,
                    None if pd.isna(r.quality) else r.quality,
                    "hubeau_piezo"
                ])
        
        # DÃ©duplication par clÃ© primaire (si nÃ©cessaire)
        cur.execute("""
            DELETE FROM measure a USING measure b 
            WHERE a.station_code = b.station_code 
            AND a.theme = b.theme 
            AND a.ts = b.ts 
            AND a.ctid < b.ctid
        """)
    
    log.info(f"Successfully loaded {len(df)} records to TimescaleDB")
    
    return {
        "loaded": len(df),
        "date": piezo_raw["date"]
    }


# ---------- Asset 3 : MÃ©tadonnÃ©es des stations ----------
@asset(
    partitions_def=PARTITIONS,
    deps=[piezo_timescale],
    group_name="warehouse_silver",
    description="Synchronisation des mÃ©tadonnÃ©es des stations depuis Hub'Eau"
)
def stations_metadata(context: AssetExecutionContext, http_client, pg):
    """RÃ©cupÃ©ration et synchronisation des mÃ©tadonnÃ©es des stations"""
    log = get_dagster_logger()
    
    # RÃ©cupÃ©ration des stations depuis Hub'Eau
    url = "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/stations"
    params = {"size": 10000}
    
    stations_data = []
    page = 1
    
    while True:
        try:
            response = http_client.get(url, params={**params, "page": page})
            response.raise_for_status()
            data = response.json()
            
            stations = data.get("data", [])
            stations_data.extend(stations)
            
            if page >= data.get("totalPages", 1):
                break
            page += 1
            
            import time
            time.sleep(0.1)
            
        except Exception as e:
            log.error(f"Error fetching stations metadata: {e}")
            break
    
    log.info(f"Fetched {len(stations_data)} stations metadata")
    
    # Upsert vers TimescaleDB
    with pg.cursor() as cur:
        for station in stations_data:
            station_code = station.get("code_bss") or station.get("code_station")
            if not station_code:
                continue
                
            # Insertion/MAJ des mÃ©tadonnÃ©es
            cur.execute("""
                INSERT INTO station_meta (
                    station_code, label, type, insee, masse_eau_code, 
                    reseau, geom, altitude_mngf, profondeur_m
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, 
                    ST_GeogFromText('POINT(' || %s || ' ' || %s || ')'), 
                    %s, %s
                )
                ON CONFLICT (station_code) 
                DO UPDATE SET
                    label = EXCLUDED.label,
                    type = EXCLUDED.type,
                    insee = EXCLUDED.insee,
                    masse_eau_code = EXCLUDED.masse_eau_code,
                    reseau = EXCLUDED.reseau,
                    geom = EXCLUDED.geom,
                    altitude_mngf = EXCLUDED.altitude_mngf,
                    profondeur_m = EXCLUDED.profondeur_m,
                    updated_at = NOW()
            """, (
                station_code,
                station.get("libelle_station"),
                "piezo",
                station.get("code_commune_insee"),
                station.get("code_masse_eau"),
                station.get("code_entite"),
                station.get("longitude"),
                station.get("latitude"),
                station.get("altitude_station"),
                station.get("profondeur_investigation")
            ))
    
    return {"stations_synced": len(stations_data)}


# ---------- Asset 4 : Contexte graphe (Gold Layer) ----------
@asset(
    group_name="graph_gold", 
    deps=[stations_metadata],
    description="Synchronisation du contexte mÃ©tier vers Neo4j"
)
def stations_graph(context: AssetExecutionContext, pg, neo4j):
    """Synchronisation des mÃ©tadonnÃ©es vers le graphe Neo4j"""
    log = get_dagster_logger()
    
    # RÃ©cupÃ©ration des mÃ©tadonnÃ©es depuis TimescaleDB
    with pg.cursor() as cur:
        cur.execute("""
            SELECT 
                station_code, label, type, insee, masse_eau_code, reseau,
                ST_Y(ST_AsText(geom::geometry)) AS lat,
                ST_X(ST_AsText(geom::geometry)) AS lon,
                altitude_mngf, profondeur_m
            FROM station_meta
            WHERE station_code IS NOT NULL
        """)
        rows = cur.fetchall()
    
    log.info(f"Syncing {len(rows)} stations to Neo4j")
    
    # RequÃªte Cypher pour la synchronisation
    cypher = """
        UNWIND $rows AS r
        MERGE (s:Station {code: r.code})
        SET s.label = r.label,
            s.type = r.type,
            s.lat = r.lat,
            s.lon = r.lon,
            s.altitude_mngf = r.altitude_mngf,
            s.profondeur_m = r.profondeur_m,
            s.reseau = r.reseau,
            s.updated_at = datetime()
        
        WITH s, r
        WHERE r.me_code IS NOT NULL
        MERGE (me:MasseEau {code: r.me_code})
        MERGE (s)-[:IN_MASSE]->(me)
        
        WITH s, r
        WHERE r.insee IS NOT NULL
        MERGE (c:Commune {insee: r.insee})
        MERGE (s)-[:IN_COMMUNE]->(c)
        
        WITH s, r
        WHERE r.reseau IS NOT NULL
        MERGE (res:Reseau {code: r.reseau})
        MERGE (s)-[:BELONGS_TO]->(res)
    """
    
    # PrÃ©paration des donnÃ©es pour Neo4j
    neo4j_rows = [{
        "code": r[0],
        "label": r[1], 
        "type": r[2],
        "insee": r[3],
        "me_code": r[4],
        "reseau": r[5],
        "lat": float(r[6]) if r[6] else None,
        "lon": float(r[7]) if r[7] else None,
        "altitude_mngf": float(r[8]) if r[8] else None,
        "profondeur_m": float(r[9]) if r[9] else None
    } for r in rows]
    
    # ExÃ©cution de la synchronisation
    with neo4j.session() as sess:
        result = sess.run(cypher, rows=neo4j_rows)
        summary = result.consume()
    
    log.info(f"Successfully synced {summary.counters.nodes_created} nodes to Neo4j")
    
    return {
        "nodes_synced": len(rows),
        "nodes_created": summary.counters.nodes_created,
        "relationships_created": summary.counters.relationships_created
    }


# ---------- Asset 5 : Relations de proximitÃ© ----------
@asset(
    group_name="graph_gold",
    deps=[stations_graph],
    description="Calcul des relations de proximitÃ© gÃ©ographique entre stations"
)
def proximity_relations(context: AssetExecutionContext, neo4j):
    """Calcul des relations de proximitÃ© entre stations"""
    log = get_dagster_logger()
    
    # Calcul des distances et crÃ©ation des relations NEAR
    cypher = """
        MATCH (s1:Station), (s2:Station)
        WHERE s1.code < s2.code 
        AND s1.lat IS NOT NULL AND s1.lon IS NOT NULL
        AND s2.lat IS NOT NULL AND s2.lon IS NOT NULL
        
        WITH s1, s2, 
             point({latitude: s1.lat, longitude: s1.lon}) <-> 
             point({latitude: s2.lat, longitude: s2.lon}) / 1000 AS distance_km
        
        WHERE distance_km <= 50.0  // Rayon de 50km
        
        MERGE (s1)-[r:NEAR]-(s2)
        SET r.distance_km = distance_km,
            r.created_at = datetime()
        
        RETURN count(r) as relations_created
    """
    
    with neo4j.session() as sess:
        result = sess.run(cypher)
        relations_created = result.single()["relations_created"]
    
    log.info(f"Created {relations_created} proximity relations")
    
    return {"proximity_relations": relations_created}


# ---------- Jobs et Schedules ----------
piezo_daily_job = define_asset_job(
    "piezo_daily_job", 
    selection=[
        "piezo_raw", 
        "piezo_timescale", 
        "stations_metadata",
        "stations_graph",
        "proximity_relations"
    ],
    description="Job quotidien d'intÃ©gration des donnÃ©es piÃ©zomÃ©triques"
)

schedules = [
    ScheduleDefinition(
        job=piezo_daily_job, 
        cron_schedule="30 2 * * *",  # 02:30 Europe/Paris
        name="piezo_daily_schedule"
    )
]


# ---------- Sensors ----------
@sensor(job=piezo_daily_job)
def freshness_sensor(context: SensorEvaluationContext):
    """Sensor pour dÃ©tecter les donnÃ©es manquantes"""
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    
    # VÃ©rifier si la partition d'hier existe
    # Dans un vrai cas, on pourrait vÃ©rifier l'Ã©tat des assets
    
    yield RunRequest(
        partition_key=yesterday,
        tags={"trigger": "freshness_sensor"}
    )


# ---------- Asset Checks ----------
@asset_check(
    asset=piezo_raw,
    spec=AssetCheckSpec(name="data_quality_check")
)
def piezo_data_quality_check(piezo_raw):
    """VÃ©rification de la qualitÃ© des donnÃ©es piÃ©zomÃ©triques"""
    if piezo_raw["count"] == 0:
        return False, "No data ingested"
    
    if piezo_raw["count"] < 100:  # Seuil arbitraire
        return False, f"Low data count: {piezo_raw['count']}"
    
    return True, f"Data quality OK: {piezo_raw['count']} records"


# ---------- Imports des autres modules ----------
from .external_assets import (
    ontologies_rdf,
    sandre_nomenclatures,
    bdlisa_masses_eau,
    infoterre_forages,
    carmen_chimie,
    meteo_france_safran,
    sandre_to_neo4j,
    bdlisa_to_neo4j
)

from .geospatial_assets import (
    all_stations_proximity,
    station_correlations,
    station_river_relations,
    withdrawal_station_relations,
    watershed_analysis,
    anthropogenic_impact_analysis,
    data_quality_metadata
)

from .assets_station_meta import (
    station_meta_sync,
    station_meta_job,
    station_meta_schedule
)

from .assets_quality import (
    quality_raw,
    quality_timescale,
    quality_groundwater_timescale
)

from .assets_sandre import (
    sandre_params_raw,
    sandre_params_pg,
    sandre_units_raw,
    sandre_units_pg
)

from .assets_graph_quality import (
    graph_params,
    graph_station_has_param,
    graph_quality_correlations,
    graph_quality_profiles
)

from .assets_meteo import (
    meteo_raw,
    meteo_timescale,
    station2grid_update,
    meteo_station_summary
)


# ---------- Jobs et Schedules Ã©tendus ----------

# Job quotidien pour toutes les APIs Hub'Eau
hubeau_daily_job = define_asset_job(
    "hubeau_daily_job",
    selection=[
        # Bronze layer - toutes les APIs Hub'Eau
        "piezo_raw",
        "hydro_raw",
        "temperature_raw",
        "ecoulement_raw",
        "hydrobiologie_raw",
        "quality_surface_raw",
        "prelevements_raw",
        
        # QualitÃ© v2 (nouveau)
        "quality_raw",
        "quality_groundwater_raw",
        
        # Silver layer - chargement vers TimescaleDB
        "piezo_timescale",
        "stations_metadata",
        "quality_timescale",
        "quality_groundwater_timescale",
        
        # Gold layer - graphe et relations
        "stations_graph",
        "proximity_relations",
        "graph_params",
        "graph_station_has_param"
    ],
    description="Job quotidien d'intÃ©gration de toutes les APIs Hub'Eau + qualitÃ© v2"
)

# Job hebdomadaire pour les sources externes et analyses avancÃ©es
external_weekly_job = define_asset_job(
    "external_weekly_job",
    selection=[
        # Sources externes
        "ontologies_rdf",
        "sandre_nomenclatures",
        "bdlisa_masses_eau",
        "infoterre_forages",
        "carmen_chimie",
        "meteo_france_safran",
        
        # ThÃ©saurus Sandre (nouveau)
        "sandre_params_raw",
        "sandre_params_pg",
        "sandre_units_raw",
        "sandre_units_pg",
        
        # Synchronisation vers Neo4j
        "sandre_to_neo4j",
        "bdlisa_to_neo4j",
        
        # Analyses gÃ©ospatiales et relations
        "all_stations_proximity",
        "station_correlations",
        "station_river_relations",
        "withdrawal_station_relations",
        "watershed_analysis",
        "anthropogenic_impact_analysis",
        "data_quality_metadata",
        
        # Analyses qualitÃ© avancÃ©es (nouveau)
        "graph_quality_correlations",
        "graph_quality_profiles"
    ],
    description="Job hebdomadaire pour les sources externes, thÃ©saurus et analyses avancÃ©es"
)

# Job complet (mensuel)
full_integration_job = define_asset_job(
    "full_integration_job",
    selection="*",  # Tous les assets
    description="Job d'intÃ©gration complÃ¨te mensuelle"
)

schedules = [
    ScheduleDefinition(
        job=hubeau_daily_job, 
        cron_schedule="30 2 * * *",  # 02:30 Europe/Paris
        name="hubeau_daily_schedule",
        execution_timezone="Europe/Paris"
    ),
    ScheduleDefinition(
        job=external_weekly_job,
        cron_schedule="0 3 * * 1",  # Lundi 03:00
        name="external_weekly_schedule",
        execution_timezone="Europe/Paris"
    ),
    ScheduleDefinition(
        job=full_integration_job,
        cron_schedule="0 4 1 * *",  # 1er du mois 04:00
        name="full_monthly_schedule",
        execution_timezone="Europe/Paris"
    ),
    station_meta_schedule  # Ajout du schedule pour station_meta
]


# ---------- Sensors Ã©tendus ----------
@sensor(job=hubeau_daily_job)
def hubeau_freshness_sensor(context: SensorEvaluationContext):
    """Sensor pour dÃ©tecter les donnÃ©es Hub'Eau manquantes"""
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    
    yield RunRequest(
        partition_key=yesterday,
        tags={"trigger": "hubeau_freshness_sensor"}
    )


@sensor(job=external_weekly_job)
def external_data_sensor(context: SensorEvaluationContext):
    """Sensor pour dÃ©clencher l'import des sources externes"""
    yield RunRequest(
        tags={"trigger": "external_data_sensor"}
    )


# ---------- Asset Checks Ã©tendus ----------
@asset_check(
    asset=piezo_raw,
    spec=AssetCheckSpec(name="piezo_data_quality_check")
)
def piezo_data_quality_check(piezo_raw):
    """VÃ©rification de la qualitÃ© des donnÃ©es piÃ©zomÃ©triques"""
    if piezo_raw["count"] == 0:
        return False, "No piezo data ingested"
    
    if piezo_raw["count"] < 100:
        return False, f"Low piezo data count: {piezo_raw['count']}"
    
    return True, f"Piezo data quality OK: {piezo_raw['count']} records"


@asset_check(
    asset=hydro_raw,
    spec=AssetCheckSpec(name="hydro_data_quality_check")
)
def hydro_data_quality_check(hydro_raw):
    """VÃ©rification de la qualitÃ© des donnÃ©es hydromÃ©triques"""
    if hydro_raw["count"] == 0:
        return False, "No hydro data ingested"
    
    return True, f"Hydro data quality OK: {hydro_raw['count']} records"


@asset_check(
    asset=station_meta_sync,
    spec=AssetCheckSpec(name="station_meta_quality_check")
)
def station_meta_quality_check(station_meta_sync):
    """VÃ©rification de la qualitÃ© des mÃ©tadonnÃ©es des stations"""
    if station_meta_sync["upserted"] == 0:
        return False, "No station metadata synced"
    
    if station_meta_sync["upserted"] < 1000:  # Seuil minimal
        return False, f"Low station count: {station_meta_sync['upserted']}"
    
    return True, f"Station metadata quality OK: {station_meta_sync['upserted']} stations"


@asset_check(
    asset=piezo_timescale,
    spec=AssetCheckSpec(name="piezo_timescale_check")
)
def piezo_timescale_check(piezo_timescale):
    """VÃ©rification du chargement TimescaleDB"""
    if piezo_timescale["loaded"] == 0:
        return False, "No data loaded to TimescaleDB"
    
    return True, f"TimescaleDB load OK: {piezo_timescale['loaded']} records"


# ---------- Exports complets ----------
assets = [
    # Hub'Eau APIs (Bronze)
    piezo_raw,
    hydro_raw,
    temperature_raw,
    ecoulement_raw,
    hydrobiologie_raw,
    quality_surface_raw,
    prelevements_raw,
    
    # QualitÃ© v2 (nouveau)
    quality_raw,
    quality_groundwater_raw,
    
    # TimescaleDB (Silver)
    piezo_timescale,
    stations_metadata,
    quality_timescale,
    quality_groundwater_timescale,
    
    # Neo4j (Gold)
    stations_graph,
    proximity_relations,
    
    # Sources externes
    ontologies_rdf,
    sandre_nomenclatures,
    bdlisa_masses_eau,
    infoterre_forages,
    carmen_chimie,
    meteo_france_safran,
    sandre_to_neo4j,
    bdlisa_to_neo4j,
    
    # ThÃ©saurus Sandre (nouveau)
    sandre_params_raw,
    sandre_params_pg,
    sandre_units_raw,
    sandre_units_pg,
    
    # Analyses gÃ©ospatiales
    all_stations_proximity,
    station_correlations,
    station_river_relations,
    withdrawal_station_relations,
    watershed_analysis,
    anthropogenic_impact_analysis,
    data_quality_metadata,
    
    # Analyses qualitÃ© avancÃ©es (nouveau)
    graph_params,
    graph_station_has_param,
    graph_quality_correlations,
    graph_quality_profiles,
    
    # MÃ©tÃ©o (nouveau)
    meteo_raw,
    meteo_timescale,
    station2grid_update,
    meteo_station_summary,
    
    # MÃ©tadonnÃ©es des stations (CRITIQUE)
    station_meta_sync
]

sensors = [
    hubeau_freshness_sensor,
    external_data_sensor
]

checks = [
    piezo_data_quality_check,
    hydro_data_quality_check,
    station_meta_quality_check,
    piezo_timescale_check
]








