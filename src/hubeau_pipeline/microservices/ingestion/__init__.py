"""
Services d'ingestion - Bronze Layer
Microservices spécialisés pour l'ingestion des données
"""

from .hubeau_service import hubeau_ingestion_service
from .sandre_service import sandre_ingestion_service
from .bdlisa_service import bdlisa_ingestion_service

__all__ = [
    "hubeau_ingestion_service",
    "sandre_ingestion_service", 
    "bdlisa_ingestion_service"
]
