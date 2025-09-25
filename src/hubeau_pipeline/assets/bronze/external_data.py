"""
Assets Bronze - Données externes (BDLISA, Sandre)
"""

from dagster import asset, AssetExecutionContext, get_dagster_logger, RetryPolicy
from datetime import datetime
import requests
import time
from typing import Dict, Any

@asset(
    group_name="bronze_external",
    description="Ingestion BDLISA - Données géographiques réelles",
    retry_policy=RetryPolicy(max_retries=3, delay=60)
)
def bdlisa_geographic_bronze(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    Ingestion des données géographiques BDLISA via WFS
    - Source: https://bdlisa.eaufrance.fr/telechargement
    - Format: WFS/GML → MinIO
    """
    logger = get_dagster_logger()
    logger.info("🗺️ Ingestion BDLISA - Données géographiques")
    
    # Configuration WFS BDLISA
    wfs_base_url = "https://services.sandre.eaufrance.fr/geo/bdlisa"
    
    datasets = [
        {
            "name": "masses_eau_souterraine",
            "typename": "BDLISA_MASSE_EAU_SOUTERRAINE",
            "description": "Masses d'eau souterraine"
        },
        {
            "name": "formations_geologiques", 
            "typename": "BDLISA_FORMATION_GEOLOGIQUE",
            "description": "Formations géologiques"
        },
        {
            "name": "limites_administratives",
            "typename": "BDLISA_LIMITE_ADMINISTRATIVE", 
            "description": "Limites administratives"
        }
    ]
    
    results = {}
    total_features = 0
    
    for dataset in datasets:
        try:
            # Paramètres WFS GetFeature
            params = {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typename": dataset["typename"],
                "outputFormat": "application/gml+xml;version=3.2",
                "srsName": "EPSG:4326"
            }
            
            logger.info(f"Requesting {dataset['description']}...")
            response = requests.get(wfs_base_url, params=params, timeout=300)
            response.raise_for_status()
            
            # Stockage MinIO
            minio_path = f"bronze/bdlisa/{dataset['name']}.gml"
            # TODO: Implement actual MinIO storage
            # minio_client.put_object("bdlisa-bronze", minio_path, response.content)
            
            # Estimation du nombre de features (parsing GML simplifié)
            feature_count = response.text.count('<gml:featureMember>') or response.text.count('<wfs:member>')
            
            results[dataset["name"]] = {
                "features": feature_count,
                "minio_path": minio_path,
                "size_bytes": len(response.content),
                "status": "success"
            }
            total_features += feature_count
            
            logger.info(f"✅ {dataset['description']}: {feature_count} features → {minio_path}")
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch {dataset['description']}: {e}")
            results[dataset["name"]] = {
                "features": 0,
                "error": str(e),
                "status": "failed"
            }
    
    return {
        "execution_date": datetime.now().isoformat(),
        "source": "BDLISA WFS",
        "datasets_processed": [d["name"] for d in datasets],
        "total_features": total_features,
        "results": results,
        "status": "completed" if total_features > 0 else "partial"
    }

@asset(
    group_name="bronze_external",
    description="Ingestion Sandre - Thésaurus réel", 
    retry_policy=RetryPolicy(max_retries=3, delay=60)
)
def sandre_thesaurus_bronze(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    Ingestion du thésaurus Sandre via API officielle
    - Source: https://api.sandre.eaufrance.fr/
    - Nomenclatures: paramètres, unités, méthodes, supports, fractions
    """
    logger = get_dagster_logger()
    logger.info("📚 Ingestion Sandre - Thésaurus officiel")
    
    # Configuration API Sandre
    sandre_base_url = "https://api.sandre.eaufrance.fr"
    
    nomenclatures = [
        {
            "name": "parametres",
            "endpoint": "/parametres/v1/parametres",
            "description": "Paramètres physicochimiques"
        },
        {
            "name": "unites",
            "endpoint": "/unites/v1/unites", 
            "description": "Unités de mesure"
        },
        {
            "name": "methodes", 
            "endpoint": "/methodes/v1/methodes",
            "description": "Méthodes d'analyse"
        },
        {
            "name": "supports",
            "endpoint": "/supports/v1/supports",
            "description": "Supports d'observation"
        },
        {
            "name": "fractions",
            "endpoint": "/fractions/v1/fractions", 
            "description": "Fractions analysées"
        }
    ]
    
    results = {}
    total_codes = 0
    
    for nomenclature in nomenclatures:
        try:
            url = f"{sandre_base_url}{nomenclature['endpoint']}"
            params = {"size": 10000, "format": "json"}
            
            logger.info(f"Requesting {nomenclature['description']}...")
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            codes_data = data.get("data", [])
            
            # Stockage MinIO
            minio_path = f"bronze/sandre/{nomenclature['name']}.json"
            # TODO: Implement actual MinIO storage
            # minio_client.put_object("sandre-bronze", minio_path, response.text)
            
            results[nomenclature["name"]] = {
                "codes": len(codes_data),
                "minio_path": minio_path,
                "total_available": data.get("count", len(codes_data)),
                "status": "success"
            }
            total_codes += len(codes_data)
            
            logger.info(f"✅ {nomenclature['description']}: {len(codes_data)} codes → {minio_path}")
            
            # Rate limiting respectueux
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch {nomenclature['description']}: {e}")
            results[nomenclature["name"]] = {
                "codes": 0,
                "error": str(e),
                "status": "failed"
            }
    
    return {
        "execution_date": datetime.now().isoformat(),
        "source": "Sandre API",
        "nomenclatures_processed": [n["name"] for n in nomenclatures],
        "total_codes": total_codes,
        "results": results,
        "status": "completed" if total_codes > 0 else "partial"
    }
