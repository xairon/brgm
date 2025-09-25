"""
Jobs Dagster - Organisation optimisée par fonction métier
"""

from .ingestion import (
    hubeau_production_job, 
    bdlisa_production_job, 
    sandre_production_job,
    demo_showcase_job
)
from .analytics import analytics_production_job

# Jobs de production (données réelles)
production_jobs = [
    hubeau_production_job,
    bdlisa_production_job,
    sandre_production_job, 
    analytics_production_job
]

# Jobs de démonstration
demo_jobs = [
    demo_showcase_job
]

# Tous les jobs
all_jobs = production_jobs + demo_jobs

__all__ = [
    "all_jobs",
    "production_jobs",
    "demo_jobs"
]