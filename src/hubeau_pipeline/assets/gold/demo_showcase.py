"""
Assets Gold - Démonstration et showcase
ATTENTION: Assets de démonstration uniquement - Ne pas utiliser en production
"""

from dagster import asset, AssetExecutionContext, get_dagster_logger
from datetime import datetime
from typing import Dict, Any

@asset(
    group_name="gold_demo",
    description="🎭 DÉMONSTRATION - Simulation de scores qualité (NON-PRODUCTION)"
)
def demo_quality_scores(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    ⚠️ ASSET DE DÉMONSTRATION UNIQUEMENT ⚠️
    
    Simulation de scores qualité pour démonstration
    - Scores générés aléatoirement
    - Interface utilisateur uniquement
    - NE PAS UTILISER EN PRODUCTION
    """
    logger = get_dagster_logger()
    logger.warning("🎭 Exécution d'un asset de DÉMONSTRATION - Données simulées")
    
    # Scores simulés pour démonstration
    simulated_scores = {
        "water_quality_index": {
            "excellent": 25,      # % de mesures excellentes
            "good": 45,          # % de mesures bonnes  
            "moderate": 25,      # % de mesures modérées
            "poor": 5           # % de mesures pauvres
        },
        "data_completeness_score": 87.5,    # % de complétude
        "temporal_consistency_score": 92.1,  # % de cohérence temporelle
        "spatial_coverage_score": 78.3,      # % de couverture spatiale
        "laboratory_reliability_score": 95.7  # % de fiabilité labo
    }
    
    # Alertes simulées
    simulated_alerts = [
        {
            "type": "quality_exceedance",
            "parameter": "Nitrates",
            "station": "BSS00123456", 
            "value": 52.3,
            "threshold": 50.0,
            "severity": "moderate"
        },
        {
            "type": "data_gap",
            "station": "BSS00789012",
            "duration_hours": 6,
            "last_observation": "2024-01-15T14:00:00Z",
            "severity": "low"
        }
    ]
    
    return {
        "execution_date": datetime.now().isoformat(),
        "asset_type": "DEMONSTRATION",
        "warning": "⚠️ DONNÉES SIMULÉES - NE PAS UTILISER EN PRODUCTION ⚠️",
        "simulated_scores": simulated_scores,
        "simulated_alerts": simulated_alerts,
        "purpose": "Interface utilisateur et démonstration uniquement",
        "status": "demo_completed"
    }

@asset(
    group_name="gold_demo", 
    description="🎭 DÉMONSTRATION - Simulation graphe Neo4j (NON-PRODUCTION)"
)
def demo_neo4j_showcase(context: AssetExecutionContext) -> Dict[str, Any]:
    """
    ⚠️ ASSET DE DÉMONSTRATION UNIQUEMENT ⚠️
    
    Simulation d'un graphe Neo4j pour démonstration
    - Données générées pour l'interface
    - Visualisation uniquement
    - NE PAS UTILISER EN PRODUCTION
    """
    logger = get_dagster_logger()
    logger.warning("🎭 Exécution d'un asset de DÉMONSTRATION - Graphe simulé")
    
    # Simulation d'un graphe pour l'interface
    simulated_graph = {
        "nodes": {
            "stations": 156,
            "parameters": 45,
            "geographic_areas": 23,
            "laboratories": 8,
            "methods": 67
        },
        "relationships": {
            "station_in_area": 156,
            "measures_parameter": 2340,
            "uses_method": 1890,
            "analyzed_by_lab": 1245,
            "spatially_adjacent": 234
        },
        "graph_metrics": {
            "density": 0.023,
            "clustering_coefficient": 0.456,
            "average_path_length": 3.2,
            "connected_components": 1
        }
    }
    
    # Requêtes simulées pour démonstration
    simulated_queries = [
        {
            "query": "Stations dans un rayon de 10km",
            "result_count": 12,
            "execution_time_ms": 45
        },
        {
            "query": "Paramètres mesurés par laboratoire",
            "result_count": 234,
            "execution_time_ms": 78
        },
        {
            "query": "Corrélations spatiales Nitrates",
            "result_count": 89,
            "execution_time_ms": 156
        }
    ]
    
    return {
        "execution_date": datetime.now().isoformat(),
        "asset_type": "DEMONSTRATION",
        "warning": "⚠️ GRAPHE SIMULÉ - NE PAS UTILISER EN PRODUCTION ⚠️",
        "simulated_graph": simulated_graph,
        "simulated_queries": simulated_queries,
        "purpose": "Démonstration capacités Neo4j uniquement",
        "status": "demo_completed"
    }
