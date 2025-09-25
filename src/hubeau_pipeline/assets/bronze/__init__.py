"""
Assets Bronze - Ingestion optimisée des données brutes
"""

from .hubeau_ingestion import (
    hubeau_piezo_bronze,
    hubeau_hydro_bronze,
    hubeau_quality_surface_bronze,
    hubeau_quality_groundwater_bronze,
    hubeau_temperature_bronze
)
from .external_data import bdlisa_geographic_bronze, sandre_thesaurus_bronze

__all__ = [
    # Hub'Eau APIs
    "hubeau_piezo_bronze",
    "hubeau_hydro_bronze",
    "hubeau_quality_surface_bronze",
    "hubeau_quality_groundwater_bronze",
    "hubeau_temperature_bronze",
    
    # Données externes
    "bdlisa_geographic_bronze",
    "sandre_thesaurus_bronze"
]