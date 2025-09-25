"""
Définition des schedules pour l'orchestration
"""

from dagster import ScheduleDefinition
from hubeau_pipeline.jobs import (
    hubeau_production_job, 
    bdlisa_production_job, 
    sandre_production_job,
    analytics_production_job
)

# Schedule quotidien Hub'Eau Production
hubeau_schedule = ScheduleDefinition(
    job=hubeau_production_job,
    cron_schedule="0 6 * * *",  # Quotidien 6h
    execution_timezone="Europe/Paris",
    name="hubeau_production_schedule",
    description="Ingestion Hub'Eau optimisée avec retry/pagination"
)

# Schedule mensuel BDLISA Production
bdlisa_schedule = ScheduleDefinition(
    job=bdlisa_production_job,
    cron_schedule="0 8 1 * *",  # Mensuel 1er à 8h
    execution_timezone="Europe/Paris", 
    name="bdlisa_production_schedule",
    description="Ingestion BDLISA → PostGIS"
)

# Schedule mensuel Sandre Production
sandre_schedule = ScheduleDefinition(
    job=sandre_production_job,
    cron_schedule="0 9 1 * *",  # Mensuel 1er à 9h
    execution_timezone="Europe/Paris",
    name="sandre_production_schedule",
    description="Ingestion Sandre → Neo4j"
)

# Schedule quotidien Analytics Production
analytics_schedule = ScheduleDefinition(
    job=analytics_production_job,
    cron_schedule="0 10 * * *",  # Quotidien 10h (après Hub'Eau)
    execution_timezone="Europe/Paris",
    name="analytics_production_schedule", 
    description="Analyses SOSA et intégrées basées sur données réelles"
)

# Liste de tous les schedules
all_schedules = [
    hubeau_schedule,
    bdlisa_schedule,
    sandre_schedule,
    analytics_schedule
]
