"""
Asset Dagster pour la synchronisation des métadonnées des stations
Loader optimisé pour Hub'Eau vers TimescaleDB/PostGIS
"""

import io
import math
import datetime as dt
import pandas as pd
from dagster import (
    asset, 
    define_asset_job, 
    ScheduleDefinition, 
    AssetExecutionContext, 
    get_dagster_logger
)

PAGE_SIZE = 10000

def _fetch_all(http, base_url: str, params: dict):
    """Pagination standard Hub'Eau: fields page/size/totalPages."""
    rows, page = [], 1
    while True:
        resp = http.get(base_url, params={**params, "page": page, "size": PAGE_SIZE})
        resp.raise_for_status()
        data = resp.json() or {}
        rows.extend(data.get("data", []))
        if page >= int(data.get("totalPages", 1) or 1):
            break
        page += 1
    return rows

def _upsert_station_meta(pg, rows: list[dict]):
    """Upsert massif, avec calcul geom (WGS84 si lon/lat, sinon Lambert-93 -> WGS84)."""
    if not rows:
        return 0
    
    with pg.cursor() as cur:
        # Création table temporaire
        cur.execute("""
        CREATE TEMP TABLE stg_station_meta(
            station_code    TEXT,
            label           TEXT,
            type            TEXT,
            insee           TEXT,
            masse_eau_code  TEXT,
            lon             DOUBLE PRECISION,
            lat             DOUBLE PRECISION,
            x2154           DOUBLE PRECISION,
            y2154           DOUBLE PRECISION
        ) ON COMMIT DROP;
        """)
        
        # COPY en CSV optimisé
        with cur.copy("COPY stg_station_meta (station_code,label,type,insee,masse_eau_code,lon,lat,x2154,y2154) FROM STDIN WITH (FORMAT CSV)") as cp:
            for r in rows:
                cp.write_row([
                    r.get("station_code"),
                    r.get("label"),
                    r.get("type"),
                    r.get("insee"),
                    r.get("masse_eau_code"),
                    r.get("lon"),
                    r.get("lat"),
                    r.get("x2154"),
                    r.get("y2154"),
                ])
        
        # Merge -> station_meta (idempotent) avec transformation géographique
        cur.execute("""
        INSERT INTO station_meta (station_code, label, type, insee, masse_eau_code, geom)
        SELECT 
            s.station_code,
            NULLIF(s.label,''),
            s.type,
            NULLIF(s.insee,''),
            NULLIF(s.masse_eau_code,''),
            COALESCE(
                CASE WHEN s.lon IS NOT NULL AND s.lat IS NOT NULL 
                     THEN ST_SetSRID(ST_MakePoint(s.lon, s.lat), 4326)::geography
                END,
                CASE WHEN s.x2154 IS NOT NULL AND s.y2154 IS NOT NULL 
                     THEN ST_Transform(ST_SetSRID(ST_MakePoint(s.x2154, s.y2154), 2154), 4326)::geography
                END
            )
        FROM stg_station_meta s
        ON CONFLICT (station_code) DO UPDATE 
           SET label = EXCLUDED.label,
               type  = EXCLUDED.type,
               insee = EXCLUDED.insee,
               masse_eau_code = EXCLUDED.masse_eau_code,
               geom  = COALESCE(EXCLUDED.geom, station_meta.geom);
        """)
    
    return len(rows)

def _first_bdlisa(codes):
    """Extrait le premier code BDLISA d'une chaîne séparée par virgules."""
    if not codes:
        return None
    # codes_bdlisa peut être "A1,B2,..." -> on prend le premier
    return str(codes).split(",")[0].strip() or None

@asset(group_name="meta")
def station_meta_sync(context: AssetExecutionContext, http_client, pg):
    """Récupère & unifie les métadonnées stations (Hub'Eau) -> station_meta (PG/PostGIS)."""
    log = get_dagster_logger()
    total = 0
    
    # 1) Piézométrie (niveaux nappes) — stations
    piezo_rows = _fetch_all(
        http_client,
        "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/stations",
        {}
    )
    
    piezo = []
    for r in piezo_rows:
        code = r.get("bss_id") or r.get("code_bss") or r.get("code_station")
        if not code:
            continue
        
        # Coordonnées: soit lon/lat via geometry.coordinates, soit X/Y Lambert-93 (x,y)
        lon = r.get("geometry", {}).get("coordinates", [None, None])[0] if isinstance(r.get("geometry",{}).get("coordinates"), (list,tuple)) else None
        lat = r.get("geometry", {}).get("coordinates", [None, None])[1] if isinstance(r.get("geometry",{}).get("coordinates"), (list,tuple)) else None
        x   = r.get("x")
        y   = r.get("y")
        
        piezo.append({
            "station_code": code,
            "label": r.get("libelle_pe") or r.get("nom_commune"),
            "type": "piezo",
            "insee": r.get("code_commune_insee"),
            "masse_eau_code": _first_bdlisa(r.get("codes_bdlisa")),
            "lon": lon,
            "lat": lat,
            "x2154": x,
            "y2154": y,
        })
    
    total += _upsert_station_meta(pg, piezo)
    log.info(f"Piézo: {len(piezo)} stations upsert.")
    
    # 2) Hydrométrie — stations
    hydro_rows = _fetch_all(
        http_client,
        "https://hubeau.eaufrance.fr/api/v1/hydrometrie/stations",
        {}
    )
    
    hydro = []
    for r in hydro_rows:
        code = r.get("code_station")
        if not code:
            continue
        
        lon = r.get("longitude_station") or r.get("longitude")
        lat = r.get("latitude_station") or r.get("latitude")
        x   = r.get("coordonnee_x_station") or None
        y   = r.get("coordonnee_y_station") or None
        
        hydro.append({
            "station_code": code,
            "label": r.get("libelle_station") or r.get("libelle_site"),
            "type": "hydro",
            "insee": r.get("code_commune_station") or r.get("code_commune_site"),
            "masse_eau_code": r.get("code_masse_eau"),
            "lon": lon,
            "lat": lat,
            "x2154": x,
            "y2154": y,
        })
    
    total += _upsert_station_meta(pg, hydro)
    log.info(f"Hydro: {len(hydro)} stations upsert.")
    
    # 3) Température — stations
    temp_rows = _fetch_all(
        http_client,
        "https://hubeau.eaufrance.fr/api/v1/temperature/stations",
        {}
    )
    
    temp = []
    for r in temp_rows:
        code = r.get("code_station")
        if not code:
            continue
        
        lon = r.get("longitude")
        lat = r.get("latitude")
        x   = r.get("coordonnee_x") or None
        y   = r.get("coordonnee_y") or None
        
        temp.append({
            "station_code": code,
            "label": r.get("libelle_station"),
            "type": "temp",
            "insee": r.get("code_commune"),
            "masse_eau_code": r.get("code_masse_eau"),
            "lon": lon,
            "lat": lat,
            "x2154": x,
            "y2154": y,
        })
    
    total += _upsert_station_meta(pg, temp)
    log.info(f"Température: {len(temp)} stations upsert.")
    
    # 4) Qualité eaux de surface v2 — stations
    quality_rows = _fetch_all(
        http_client,
        "https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface/stations",
        {}
    )
    
    quality = []
    for r in quality_rows:
        code = r.get("code_station")
        if not code:
            continue
        
        lon = r.get("longitude") or r.get("lon")
        lat = r.get("latitude") or r.get("lat")
        x   = r.get("coordonnee_x") or None
        y   = r.get("coordonnee_y") or None
        
        quality.append({
            "station_code": code,
            "label": r.get("libelle_station") or r.get("libelle"),
            "type": "quality",
            "insee": r.get("code_commune"),
            "masse_eau_code": r.get("code_masse_eau"),
            "lon": lon, 
            "lat": lat, 
            "x2154": x, 
            "y2154": y,
        })
    
    total += _upsert_station_meta(pg, quality)
    log.info(f"Qualité: {len(quality)} stations upsert.")
    
    return {"upserted": total}

# Job + Schedule (hebdo, 03:10 Europe/Paris)
station_meta_job = define_asset_job("station_meta_job", selection=["station_meta_sync"])
station_meta_schedule = ScheduleDefinition(
    job=station_meta_job, 
    cron_schedule="10 3 * * 1", 
    execution_timezone="Europe/Paris"
)
