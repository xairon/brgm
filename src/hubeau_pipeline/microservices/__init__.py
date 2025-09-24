"""
Microservices Hub'Eau
Architecture microservices avec services spécialisés
"""

# Services d'ingestion (Bronze Layer)
from .ingestion.hubeau_service import hubeau_ingestion_service
from .ingestion.sandre_service import sandre_ingestion_service  
from .ingestion.bdlisa_service import bdlisa_ingestion_service

# Services de transformation (Silver Layer)
from .transformation.timescale_service import timescale_loading_service
from .transformation.quality_service import data_quality_service

# Services d'analyse (Gold Layer)
from .analytics.neo4j_service import neo4j_graph_service
from .analytics.analytics_service import analytics_service

# Orchestrateur
from .orchestrator.daily_orchestrator import daily_orchestrator

__all__ = [
    # Services d'ingestion
    "hubeau_ingestion_service",
    "sandre_ingestion_service", 
    "bdlisa_ingestion_service",
    
    # Services de transformation
    "timescale_loading_service",
    "data_quality_service",
    
    # Services d'analyse
    "neo4j_graph_service",
    "analytics_service",
    
    # Orchestrateur
    "daily_orchestrator"
]
