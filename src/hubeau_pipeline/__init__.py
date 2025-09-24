"""
Hub'Eau Data Integration Pipeline
Architecture microservices avec orchestration Dagster
"""

from dagster import Definitions

# Import des microservices RÉELS
from hubeau_pipeline.microservices.ingestion.hubeau_real_service import hubeau_ingestion_service
from hubeau_pipeline.microservices.ingestion.sandre_real_service import sandre_ingestion_service
from hubeau_pipeline.microservices.ingestion.bdlisa_real_service import bdlisa_ingestion_service

from hubeau_pipeline.microservices.transformation.timescale_real_service import timescale_loading_service
from hubeau_pipeline.microservices.transformation.quality_service import data_quality_service

from hubeau_pipeline.microservices.analytics.neo4j_real_service import neo4j_graph_service
from hubeau_pipeline.microservices.analytics.analytics_service import analytics_service

from hubeau_pipeline.microservices.orchestrator.daily_orchestrator import daily_orchestrator

# Import des ressources partagées
from hubeau_pipeline.resources import RESOURCES

# Import du job et schedule
from hubeau_pipeline.simple_microservices import daily_pipeline_job, daily_pipeline_schedule

# Définitions Dagster
defs = Definitions(
    # 🏗️ Microservices spécialisés
    assets=[
        # Services d'ingestion
        hubeau_ingestion_service,
        sandre_ingestion_service,
        bdlisa_ingestion_service,
        
        # Services de transformation
        timescale_loading_service,
        data_quality_service,
        
        # Services d'analyse
        neo4j_graph_service,
        analytics_service,
        
        # Orchestrateur
        daily_orchestrator
    ],
    
    # 🚀 Jobs et Schedules
    jobs=[daily_pipeline_job],
    schedules=[daily_pipeline_schedule],
    
    # 🔧 Ressources partagées
    resources=RESOURCES
)