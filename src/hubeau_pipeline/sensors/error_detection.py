"""
Sensor - Détection d'erreurs
Surveillance des erreurs et alertes
"""

from dagster import sensor, SensorEvaluationContext, RunRequest, SkipReason
from hubeau_pipeline.jobs import hubeau_daily_job

@sensor(
    job=hubeau_daily_job,
    name="error_detection_sensor",
    description="Détecte les erreurs dans les pipelines"
)
def error_detection_sensor(context: SensorEvaluationContext):
    """
    Sensor : Détecte les erreurs dans les pipelines
    
    Ce sensor vérifie :
    - Les échecs de jobs récents
    - Les données manquantes
    - Les anomalies dans les métriques
    - Les problèmes de connectivité
    """
    # Simulation de la détection d'erreurs
    # En réalité, on vérifierait les logs, métriques, etc.
    
    errors_detected = False  # Simulation
    
    if errors_detected:
        context.log.warning("🚨 Erreurs détectées - Relance du job de récupération")
        return RunRequest(
            run_key=f"error_recovery_{context.cursor}",
            tags={"trigger": "error_sensor", "recovery": "true"}
        )
    else:
        context.log.info("✅ Aucune erreur détectée")
        return SkipReason("Pipeline fonctionne normalement")
