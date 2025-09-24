"""
Service MinIO - Stockage réel des données brutes (Bronze Layer)
Interface pour stocker et récupérer les données des APIs Hub'Eau
"""

import json
import boto3
from datetime import datetime
from typing import Dict, Any, Optional
from dagster import get_dagster_logger

class MinIOService:
    """Service MinIO pour le stockage des données brutes"""
    
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket_name: str = "hubeau-bronze"):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.logger = get_dagster_logger()
        
        # Configuration S3/MinIO
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='us-east-1'
        )
        
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """S'assurer que le bucket existe"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            self.logger.info(f"✅ Bucket {self.bucket_name} existe déjà")
        except:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
                self.logger.info(f"✅ Bucket {self.bucket_name} créé")
            except Exception as e:
                self.logger.error(f"❌ Erreur création bucket: {str(e)}")
                raise e
    
    def store_api_data(self, data: Dict[str, Any], api_name: str, date: str) -> str:
        """Stocker les données d'une API dans MinIO"""
        try:
            # Structure du chemin: bronze/{source}/{date}/{api_name}_{date}.json
            filepath = f"bronze/hubeau/{date}/{api_name}_{date}.json"
            
            # Ajouter des métadonnées
            metadata = {
                "api_name": api_name,
                "date": date,
                "stored_at": datetime.now().isoformat(),
                "record_count": len(data.get("data", [])),
                "api_version": data.get("api_version", "unknown"),
                "total_count": data.get("count", 0)
            }
            
            # Préparer les données avec métadonnées
            enriched_data = {
                "metadata": metadata,
                "api_response": data
            }
            
            # Stocker dans MinIO
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filepath,
                Body=json.dumps(enriched_data, indent=2, ensure_ascii=False),
                ContentType='application/json',
                Metadata={
                    'api_name': api_name,
                    'date': date,
                    'record_count': str(metadata["record_count"])
                }
            )
            
            self.logger.info(f"💾 Données stockées dans MinIO: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"❌ Erreur stockage MinIO: {str(e)}")
            raise e
    
    def retrieve_api_data(self, api_name: str, date: str) -> Optional[Dict[str, Any]]:
        """Récupérer les données d'une API depuis MinIO"""
        try:
            filepath = f"bronze/hubeau/{date}/{api_name}_{date}.json"
            
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=filepath
            )
            
            data = json.loads(response['Body'].read().decode('utf-8'))
            self.logger.info(f"📥 Données récupérées depuis MinIO: {filepath}")
            return data
            
        except Exception as e:
            self.logger.error(f"❌ Erreur récupération MinIO: {str(e)}")
            return None
    
    def list_stored_dates(self) -> list:
        """Lister les dates pour lesquelles des données sont stockées"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix="bronze/hubeau/"
            )
            
            dates = set()
            for obj in response.get('Contents', []):
                # Extraire la date du chemin: bronze/hubeau/YYYY-MM-DD/...
                path_parts = obj['Key'].split('/')
                if len(path_parts) >= 3:
                    dates.add(path_parts[2])
            
            return sorted(list(dates))
            
        except Exception as e:
            self.logger.error(f"❌ Erreur listing MinIO: {str(e)}")
            return []
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Obtenir les statistiques de stockage"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix="bronze/hubeau/"
            )
            
            total_files = len(response.get('Contents', []))
            total_size = sum(obj['Size'] for obj in response.get('Contents', []))
            
            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Erreur stats MinIO: {str(e)}")
            return {"total_files": 0, "total_size_bytes": 0, "total_size_mb": 0}
