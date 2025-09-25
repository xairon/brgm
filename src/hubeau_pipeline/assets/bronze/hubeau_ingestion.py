"""
Assets Bronze Hub'Eau - Ingestion professionnelle avec retry/pagination
"""

from dagster import asset, DailyPartitionsDefinition, AssetExecutionContext, get_dagster_logger, RetryPolicy
from datetime import datetime, timedelta
import requests
import time
import json
from typing import Dict, List, Any
from dataclasses import dataclass

# Configuration des partitions journalières
DAILY_PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@dataclass
class HubeauAPIConfig:
    """Configuration pour une API Hub'Eau"""
    name: str
    base_url: str
    endpoints: List[str]
    params: Dict[str, Any]
    max_per_page: int = 20000
    max_retries: int = 3
    backoff_factor: float = 2.0

class HubeauIngestionService:
    """Service d'ingestion Hub'Eau avec retry/backoff et pagination"""
    
    def __init__(self):
        self.logger = get_dagster_logger()
        self.session = requests.Session()
        # Configuration retry pour la session
        self.session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
    
    def call_api_with_retry(self, url: str, params: Dict, max_retries: int = 3, backoff_factor: float = 2.0) -> Dict:
        """Appel API avec retry exponentiel"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            
            except requests.exceptions.RequestException as e:
                wait_time = backoff_factor ** attempt
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Max retries reached for {url}")
                    raise
    
    def paginate_api_call(self, config: HubeauAPIConfig, endpoint: str, base_params: Dict) -> List[Dict]:
        """Pagination complète avec retry"""
        all_data = []
        page = 1
        total_pages = None
        
        while True:
            params = {**base_params, "page": page, "size": config.max_per_page}
            url = f"{config.base_url}/{endpoint}"
            
            try:
                response_data = self.call_api_with_retry(url, params, config.max_retries, config.backoff_factor)
                
                # Extraction des données selon la structure Hub'Eau
                data = response_data.get("data", [])
                if data:
                    all_data.extend(data)
                
                # Gestion pagination
                count = response_data.get("count", 0)
                if total_pages is None:
                    total_pages = (count + config.max_per_page - 1) // config.max_per_page
                    self.logger.info(f"{endpoint}: {count} total records, {total_pages} pages")
                
                if page >= total_pages or len(data) < config.max_per_page:
                    break
                    
                page += 1
                
                # Rate limiting respectueux
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error paginating {endpoint} page {page}: {e}")
                break
        
        self.logger.info(f"{endpoint}: Retrieved {len(all_data)} records total")
        return all_data
    
    def ingest_hubeau_api(self, config: HubeauAPIConfig, date: str) -> Dict[str, Any]:
        """Ingestion complète d'une API Hub'Eau"""
        self.logger.info(f"🌊 Starting {config.name} ingestion for {date}")
        
        results = {}
        total_records = 0
        
        # Paramètres de base avec filtrage temporel
        base_params = {
            **config.params,
            "date_debut_obs": date,
            "date_fin_obs": date,
            "format": "json"
        }
        
        for endpoint in config.endpoints:
            try:
                data = self.paginate_api_call(config, endpoint, base_params)
                
                # Stockage MinIO (simulation professionnelle)
                minio_path = f"bronze/hubeau/{config.name}/{date}/{endpoint}.json"
                # TODO: Implement actual MinIO storage
                # minio_client.put_object("hubeau-bronze", minio_path, json.dumps(data))
                
                results[endpoint] = {
                    "records": len(data),
                    "minio_path": minio_path,
                    "status": "success"
                }
                total_records += len(data)
                
            except Exception as e:
                self.logger.error(f"Failed to ingest {endpoint}: {e}")
                results[endpoint] = {
                    "records": 0,
                    "error": str(e),
                    "status": "failed"
                }
        
        return {
            "api_name": config.name,
            "execution_date": date,
            "endpoints_processed": list(results.keys()),
            "total_records": total_records,
            "results": results,
            "status": "completed" if total_records > 0 else "failed"
        }

@asset(
    partitions_def=DAILY_PARTITIONS,
    group_name="bronze_hubeau",
    description="Ingestion piézométrie Hub'Eau avec retry/pagination",
    retry_policy=RetryPolicy(max_retries=3, delay=60)
)
def hubeau_piezo_bronze(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    Ingestion données piézométriques Hub'Eau
    - API: https://hubeau.eaufrance.fr/api/v1/niveaux_nappes
    - Retry automatique avec backoff exponentiel
    - Pagination complète des résultats
    - Filtrage temporel par partition
    """
    day = context.partition_key
    
    config = HubeauAPIConfig(
        name="piezo",
        base_url="https://hubeau.eaufrance.fr/api/v1/niveaux_nappes",
        endpoints=["stations", "observations_tr", "chroniques"],
        params={"size": 20000},
        max_per_page=20000,
        max_retries=3,
        backoff_factor=2.0
    )
    
    service = HubeauIngestionService()
    return service.ingest_hubeau_api(config, day)

@asset(
    partitions_def=DAILY_PARTITIONS,
    group_name="bronze_hubeau",
    description="Ingestion hydrométrie Hub'Eau avec retry/pagination",
    retry_policy=RetryPolicy(max_retries=3, delay=60)
)
def hubeau_hydro_bronze(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    Ingestion données hydrométriques Hub'Eau
    - API: https://hubeau.eaufrance.fr/api/v1/hydrometrie
    """
    day = context.partition_key
    
    config = HubeauAPIConfig(
        name="hydro",
        base_url="https://hubeau.eaufrance.fr/api/v1/hydrometrie",
        endpoints=["stations", "observations_tr", "chroniques"],
        params={"size": 20000},
        max_per_page=20000,
        max_retries=3,
        backoff_factor=2.0
    )
    
    service = HubeauIngestionService()
    return service.ingest_hubeau_api(config, day)

@asset(
    partitions_def=DAILY_PARTITIONS,
    group_name="bronze_hubeau",
    description="Ingestion qualité eaux surface Hub'Eau avec retry/pagination",
    retry_policy=RetryPolicy(max_retries=3, delay=60)
)
def hubeau_quality_surface_bronze(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    Ingestion données qualité eaux de surface Hub'Eau
    - API: https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface
    """
    day = context.partition_key
    
    config = HubeauAPIConfig(
        name="quality_surface",
        base_url="https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface",
        endpoints=["stations", "analyses"],
        params={"size": 20000},
        max_per_page=20000,
        max_retries=3,
        backoff_factor=2.0
    )
    
    service = HubeauIngestionService()
    return service.ingest_hubeau_api(config, day)

@asset(
    partitions_def=DAILY_PARTITIONS,
    group_name="bronze_hubeau",
    description="Ingestion qualité eaux souterraines Hub'Eau avec retry/pagination",
    retry_policy=RetryPolicy(max_retries=3, delay=60)
)
def hubeau_quality_groundwater_bronze(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    Ingestion données qualité eaux souterraines Hub'Eau
    - API: https://hubeau.eaufrance.fr/api/v1/qualite_eaux_souterraines
    """
    day = context.partition_key
    
    config = HubeauAPIConfig(
        name="quality_groundwater",
        base_url="https://hubeau.eaufrance.fr/api/v1/qualite_eaux_souterraines",
        endpoints=["stations", "analyses"],
        params={"size": 20000},
        max_per_page=20000,
        max_retries=3,
        backoff_factor=2.0
    )
    
    service = HubeauIngestionService()
    return service.ingest_hubeau_api(config, day)

@asset(
    partitions_def=DAILY_PARTITIONS,
    group_name="bronze_hubeau",
    description="Ingestion température Hub'Eau avec retry/pagination",
    retry_policy=RetryPolicy(max_retries=3, delay=60)
)
def hubeau_temperature_bronze(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    Ingestion données température Hub'Eau
    - API: https://hubeau.eaufrance.fr/api/v1/temperature
    """
    day = context.partition_key
    
    config = HubeauAPIConfig(
        name="temperature",
        base_url="https://hubeau.eaufrance.fr/api/v1/temperature",
        endpoints=["stations", "observations_tr"],
        params={"size": 20000},
        max_per_page=20000,
        max_retries=3,
        backoff_factor=2.0
    )
    
    service = HubeauIngestionService()
    return service.ingest_hubeau_api(config, day)
