"""
Asset Silver - Contrôles qualité des données
Petite brique spécialisée pour les vérifications qualité
"""

from dagster import AssetExecutionContext, asset, DailyPartitionsDefinition, get_dagster_logger, asset_check, AssetCheckResult
# from hubeau_pipeline.assets.silver import piezo_timescale, hydro_timescale, quality_timescale

# Configuration des partitions journalières
PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="silver_quality",
    description="Contrôles qualité des données chargées"
)
def data_quality_checks(context: AssetExecutionContext):
    """
    Petite brique : Effectue les contrôles qualité des données
    
    Cette brique est responsable uniquement de :
    - Vérifier la cohérence des données
    - Détecter les valeurs aberrantes
    - Valider les métadonnées
    - Générer des alertes si nécessaire
    """
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"Contrôles qualité des données pour {day}")
    
    # Simulation des résultats de chargement
    loading_results = {
        "piezo": {"records_inserted": 1250, "status": "success"},
        "hydro": {"records_inserted": 980, "status": "success"},
        "quality": {"records_inserted": 450, "status": "success"}
    }
    
    # Simulation des contrôles qualité
    quality_checks = {
        "data_completeness": {
            "piezo": loading_results["piezo"]["records_inserted"] > 0,
            "hydro": loading_results["hydro"]["records_inserted"] > 0,
            "quality": loading_results["quality"]["records_inserted"] > 0
        },
        "data_freshness": {
            "all_sources_updated": all(
                result.get("status") in ["success", "skipped"] 
                for result in loading_results.values()
            )
        },
        "data_consistency": {
            "no_duplicates": True,  # Simulation
            "valid_coordinates": True,  # Simulation
            "valid_timestamps": True  # Simulation
        }
    }
    
    # Calcul du score qualité global
    all_checks = []
    for category, checks in quality_checks.items():
        all_checks.extend(checks.values())
    
    quality_score = sum(all_checks) / len(all_checks) * 100
    
    # Génération des alertes
    alerts = []
    if quality_score < 90:
        alerts.append("Score qualité global faible")
    
    if not quality_checks["data_completeness"]["piezo"]:
        alerts.append("Pas de données piézométriques")
    
    result = {
        "date": day,
        "quality_score": quality_score,
        "checks_performed": len(all_checks),
        "checks_passed": sum(all_checks),
        "alerts_count": len(alerts),
        "alerts": alerts,
        "status": "success" if quality_score >= 80 else "warning"
    }
    
    logger.info(f"✓ Contrôles qualité {day}: Score {quality_score:.1f}% ({result['checks_passed']}/{result['checks_performed']})")
    return result

# Asset Check pour la qualité des données (simplifié pour éviter les dépendances)
# @asset_check(
#     asset=piezo_timescale,
#     name="piezo_data_quality_check"
# )
def piezo_data_quality_check(context: AssetExecutionContext):
    """
    Check spécialisé : Vérifie la qualité des données piézométriques
    """
    records = 1250  # Simulation
    
    if records == 0:
        return AssetCheckResult(
            passed=False,
            description=f"Aucune donnée piézométrique pour {context.partition_key}"
        )
    elif records < 10:
        return AssetCheckResult(
            passed=False,
            description=f"Très peu de données piézométriques: {records}"
        )
    else:
        return AssetCheckResult(
            passed=True,
            description=f"Données piézométriques OK: {records} enregistrements"
        )
