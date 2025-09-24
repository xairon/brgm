"""
Assets Bronze - Données brutes depuis les APIs
Petites briques spécialisées par source de données
"""

from .hubeau_piezo import piezo_raw
from .hubeau_hydro import hydro_raw
from .hubeau_quality import quality_surface_raw, quality_groundwater_raw
from .hubeau_meteo import meteo_raw
from .external_sandre import sandre_params_raw, sandre_units_raw
from .external_bdlisa import bdlisa_masses_eau_raw

__all__ = [
    "piezo_raw",
    "hydro_raw", 
    "quality_surface_raw",
    "quality_groundwater_raw",
    "meteo_raw",
    "sandre_params_raw",
    "sandre_units_raw",
    "bdlisa_masses_eau_raw"
]
