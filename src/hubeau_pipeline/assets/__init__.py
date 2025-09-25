"""
Assets Hub'Eau - Architecture Dagster professionnelle
Bronze → Silver → Gold avec optimisations
"""

# Import des assets par couche
from .bronze import (
    hubeau_piezo_bronze, hubeau_hydro_bronze, hubeau_quality_surface_bronze,
    hubeau_quality_groundwater_bronze, hubeau_temperature_bronze,
    bdlisa_geographic_bronze, sandre_thesaurus_bronze
)
from .silver import (
    piezo_timescale_optimized, quality_timescale_optimized,
    bdlisa_postgis_silver, sandre_neo4j_silver
)
from .gold import (
    sosa_ontology_production, integrated_analytics_production,
    demo_quality_scores, demo_neo4j_showcase
)

# Assets de production (calculs réels)
production_assets = [
    # Bronze
    hubeau_piezo_bronze,
    hubeau_hydro_bronze,
    hubeau_quality_surface_bronze,
    hubeau_quality_groundwater_bronze,
    hubeau_temperature_bronze,
    bdlisa_geographic_bronze,
    sandre_thesaurus_bronze,
    
    # Silver
    piezo_timescale_optimized,
    quality_timescale_optimized,
    bdlisa_postgis_silver,
    sandre_neo4j_silver,
    
    # Gold - Production
    sosa_ontology_production,
    integrated_analytics_production
]

# Assets de démonstration (simulations)
demo_assets = [
    demo_quality_scores,
    demo_neo4j_showcase
]

# Tous les assets
all_assets = production_assets + demo_assets

__all__ = [
    "all_assets",
    "production_assets", 
    "demo_assets"
]