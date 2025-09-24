"""
Jobs Orchestrés - Grosses briques
Orchestration des petites briques en workflows cohérents
"""

from .daily_ingestion import hubeau_daily_job
from .weekly_external import sandre_weekly_job, bdlisa_monthly_job
from .monthly_analytics import analytics_monthly_job

__all__ = [
    "hubeau_daily_job",
    "sandre_weekly_job",
    "bdlisa_monthly_job", 
    "analytics_monthly_job"
]
