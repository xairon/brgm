"""
Sensor - Fraîcheur des données
Surveillance de la fraîcheur des données Hub'Eau
"""

from dagster import sensor, SensorEvaluationContext, RunRequest, SkipReason
from hubeau_pipeline.jobs import hubeau_daily_job

@sensor(
    job=hubeau_daily_job,
    name="hubeau_freshness_sensor",
    description="Surveille la fraîcheur des données Hub'Eau"
)
def hubeau_freshness_sensor(context: SensorEvaluationContext):
    """
    Sensor : Surveille la fraîcheur des données
    
    Ce sensor vérifie :
    - Si les données sont à jour
    - Si les APIs Hub'Eau sont disponibles
    - Si des nouvelles données sont disponibles
    """
    # Simulation de la vérification de fraîcheur
    # En réalité, on vérifierait les timestamps des dernières données
    
    current_time = context.cursor or "2024-01-01"
    
    # Simulation : vérification si de nouvelles données sont disponibles
    new_data_available = True  # Simulation
    
    if new_data_available:
        context.log.info("🔄 Nouvelles données Hub'Eau détectées - Lancement du job")
        return RunRequest(
            run_key=f"hubeau_freshness_{context.cursor}",
            tags={"trigger": "freshness_sensor", "source": "hubeau"}
        )
    else:
        context.log.info("⏸️ Aucune nouvelle donnée Hub'Eau - Job non lancé")
        return SkipReason("Aucune nouvelle donnée disponible")
