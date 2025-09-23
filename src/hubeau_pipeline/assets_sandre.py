"""
Assets Dagster pour le thésaurus Sandre
Import et synchronisation des nomenclatures officielles
"""

import io
import pandas as pd
from dagster import asset

@asset(
    group_name="thesaurus_bronze",
    description="Import du thésaurus paramètres Sandre depuis l'API"
)
def sandre_params_raw(context, http_client, s3):
    """Récupération du thésaurus paramètres Sandre depuis l'API"""
    url = "https://api.sandre.eaufrance.fr/referentiels/v1/par.json"
    
    try:
        response = http_client.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Sauvegarde dans MinIO
        key = f"sandre/params/{pd.Timestamp.now().strftime('%Y-%m-%d')}.json"
        s3["client"].put_object(
            Bucket=s3["bucket"],
            Key=key,
            Body=response.content,
            ContentType="application/json"
        )
        
        context.log.info(f"sandre_params_raw: {len(data.get('data', []))} paramètres sauvegardés")
        
        return {"count": len(data.get("data", [])), "key": key}
        
    except Exception as e:
        context.log.error(f"Error fetching Sandre params: {e}")
        return {"count": 0, "key": None}

@asset(
    group_name="thesaurus_silver",
    deps=[sandre_params_raw],
    description="Chargement du thésaurus Sandre vers TimescaleDB"
)
def sandre_params_pg(context, s3, pg, sandre_params_raw):
    """Chargement du thésaurus paramètres Sandre vers TimescaleDB"""
    if not sandre_params_raw["key"]:
        return {"loaded": 0}
    
    key = sandre_params_raw["key"]
    obj = s3["client"].get_object(Bucket=s3["bucket"], Key=key)
    data = obj["Body"].read().decode('utf-8')
    
    import json
    sandre_data = json.loads(data)
    
    params = []
    for item in sandre_data.get("data", []):
        params.append({
            "code_param": item.get("CdParametre"),
            "label": item.get("NomParametre"),
            "unit": item.get("SymboleUniteMesure"),
            "family": item.get("ThemeParametre")
        })
    
    if not params:
        return {"loaded": 0}
    
    with pg.cursor() as cur:
        with cur.copy("COPY quality_param (code_param,label,unit,family) FROM STDIN WITH (FORMAT CSV)") as cp:
            for param in params:
                cp.write_row([
                    param["code_param"],
                    param["label"],
                    param["unit"],
                    param["family"]
                ])
    
    context.log.info(f"sandre_params_pg: {len(params)} paramètres chargés vers TimescaleDB")
    
    return {"loaded": len(params)}

@asset(
    group_name="thesaurus_bronze",
    description="Import du thésaurus unités Sandre"
)
def sandre_units_raw(context, http_client, s3):
    """Récupération du thésaurus unités Sandre"""
    url = "https://api.sandre.eaufrance.fr/referentiels/v1/uni.json"
    
    try:
        response = http_client.get(url)
        response.raise_for_status()
        data = response.json()
        
        key = f"sandre/units/{pd.Timestamp.now().strftime('%Y-%m-%d')}.json"
        s3["client"].put_object(
            Bucket=s3["bucket"],
            Key=key,
            Body=response.content,
            ContentType="application/json"
        )
        
        context.log.info(f"sandre_units_raw: {len(data.get('data', []))} unités sauvegardées")
        
        return {"count": len(data.get("data", [])), "key": key}
        
    except Exception as e:
        context.log.error(f"Error fetching Sandre units: {e}")
        return {"count": 0, "key": None}

@asset(
    group_name="thesaurus_silver",
    deps=[sandre_units_raw],
    description="Chargement du thésaurus unités Sandre vers TimescaleDB"
)
def sandre_units_pg(context, s3, pg, sandre_units_raw):
    """Chargement du thésaurus unités Sandre vers TimescaleDB"""
    if not sandre_units_raw["key"]:
        return {"loaded": 0}
    
    key = sandre_units_raw["key"]
    obj = s3["client"].get_object(Bucket=s3["bucket"], Key=key)
    data = obj["Body"].read().decode('utf-8')
    
    import json
    sandre_data = json.loads(data)
    
    units = []
    for item in sandre_data.get("data", []):
        units.append({
            "code": item.get("CdUniteMesure"),
            "label": item.get("SymboleUniteMesure"),
            "description": item.get("LblUniteMesure")
        })
    
    if not units:
        return {"loaded": 0}
    
    with pg.cursor() as cur:
        with cur.copy("COPY unite_sandre (code,libelle,description) FROM STDIN WITH (FORMAT CSV)") as cp:
            for unit in units:
                cp.write_row([
                    unit["code"],
                    unit["label"],
                    unit["description"]
                ])
    
    context.log.info(f"sandre_units_pg: {len(units)} unités chargées vers TimescaleDB")
    
    return {"loaded": len(units)}
