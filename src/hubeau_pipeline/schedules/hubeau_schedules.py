"""
Schedules - Planification des jobs Hub'Eau
Orchestration temporelle des grosses briques
"""

from dagster import ScheduleDefinition
from hubeau_pipeline.jobs import hubeau_daily_job, sandre_weekly_job, bdlisa_monthly_job, analytics_monthly_job

# Schedule quotidien - Ingestion Hub'Eau
hubeau_daily_schedule = ScheduleDefinition(
    job=hubeau_daily_job,
    cron_schedule="0 6 * * *",  # 6h du matin chaque jour
    execution_timezone="Europe/Paris",
    name="hubeau_daily_schedule",
    description="""
    ⏰ SCHEDULE QUOTIDIEN : Ingestion Hub'Eau
    
    Exécute tous les jours à 6h du matin :
    - Récupération des données Hub'Eau (Bronze)
    - Nettoyage et chargement TimescaleDB (Silver)
    - Synchronisation métadonnées
    - Contrôles qualité
    
    Horaire choisi pour éviter la charge des APIs en journée
    """
)

# Schedule hebdomadaire - Sources Sandre
sandre_weekly_schedule = ScheduleDefinition(
    job=sandre_weekly_job,
    cron_schedule="0 2 * * 1",  # 2h du matin chaque lundi
    execution_timezone="Europe/Paris",
    name="sandre_weekly_schedule",
    description="""
    ⏰ SCHEDULE HEBDOMADAIRE : Sources Sandre
    
    Exécute chaque lundi à 2h du matin :
    - Mise à jour nomenclatures Sandre
    - Actualisation référentiels Sandre
    
    Fréquence hebdomadaire car ces sources changent peu
    """
)

# Schedule mensuel - Sources BDLISA
bdlisa_monthly_schedule = ScheduleDefinition(
    job=bdlisa_monthly_job,
    cron_schedule="0 1 1 * *",  # 1h du matin le 1er de chaque mois
    execution_timezone="Europe/Paris",
    name="bdlisa_monthly_schedule",
    description="""
    ⏰ SCHEDULE MENSUEL : Sources BDLISA
    
    Exécute le 1er de chaque mois à 1h du matin :
    - Synchronisation masses d'eau BDLISA
    - Actualisation référentiels géographiques
    
    Fréquence mensuelle car ces sources changent très peu
    """
)

# Schedule mensuel - Analyses avancées
analytics_monthly_schedule = ScheduleDefinition(
    job=analytics_monthly_job,
    cron_schedule="0 1 1 * *",  # 1h du matin le 1er de chaque mois
    execution_timezone="Europe/Paris",
    name="analytics_monthly_schedule",
    description="""
    ⏰ SCHEDULE MENSUEL : Analyses avancées
    
    Exécute le 1er de chaque mois à 1h du matin :
    - Construction graphe Neo4j
    - Analyses de corrélation
    - Calculs géospatiaux
    - Rapports de performance
    
    Fréquence mensuelle car analyses coûteuses et résultats stables
    """
)
