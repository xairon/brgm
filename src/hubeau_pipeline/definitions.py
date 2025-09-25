"""
Définitions Dagster centrales - Point d'entrée de l'application
"""

from dagster import Definitions

# Import des assets
from hubeau_pipeline.assets import all_assets

# Import des jobs  
from hubeau_pipeline.jobs import all_jobs

# Import des schedules
from hubeau_pipeline.schedules import all_schedules

# Import des resources
from hubeau_pipeline.resources import RESOURCES

# Définitions centrales
defs = Definitions(
    assets=all_assets,
    jobs=all_jobs, 
    schedules=all_schedules,
    resources=RESOURCES
)
