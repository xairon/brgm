"""
Assets Gold - Analyses et ontologie
"""

from .production_analytics import sosa_ontology_production, integrated_analytics_production
from .demo_showcase import demo_quality_scores, demo_neo4j_showcase

__all__ = [
    # Production - Calculs réels
    "sosa_ontology_production",
    "integrated_analytics_production",
    
    # Démonstration - Simulations
    "demo_quality_scores", 
    "demo_neo4j_showcase"
]