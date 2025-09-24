"""
Job Orchestré - Analyses mensuelles
Grosse brique qui orchestre toutes les analyses avancées
"""

from dagster import define_asset_job, AssetSelection
from hubeau_pipeline.assets.gold import (
    stations_graph, correlations_graph, station_analytics, quality_analytics, proximity_relations
)

# Sélection des assets pour les analyses mensuelles
analytics_selection = AssetSelection.assets(
    # Gold Layer - Analyses avancées
    stations_graph,
    correlations_graph,
    station_analytics,
    quality_analytics,
    proximity_relations
)

# Job orchestré : Analyses mensuelles
analytics_monthly_job = define_asset_job(
    name="analytics_monthly_job",
    description="""
    🏗️ GROSSE BRIQUE : Orchestration des analyses mensuelles
    
    Ce job orchestre les petites briques pour :
    - Construire le graphe des stations dans Neo4j
    - Analyser les corrélations entre stations
    - Effectuer les analyses de performance
    - Calculer les relations géospatiales
    
    Exécution mensuelle car ces analyses sont coûteuses
    et les résultats sont stables sur cette période
    """,
    selection=analytics_selection,
    config={
        "execution": {
            "config": {
                "multiprocess": {
                    "max_concurrent": 4,  # Plus de concurrence pour les analyses
                }
            }
        }
    }
)
