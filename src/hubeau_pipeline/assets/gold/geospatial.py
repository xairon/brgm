"""
Asset Gold - Relations géospatiales
Petite brique spécialisée pour les analyses géospatiales
"""

from dagster import AssetExecutionContext, asset, DailyPartitionsDefinition, get_dagster_logger
# from hubeau_pipeline.assets.silver import station_metadata_sync

# Configuration des partitions journalières
PARTITIONS = DailyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="gold_geospatial",
    description="Analyse des relations de proximité entre stations"
)
def proximity_relations(context: AssetExecutionContext):
    """
    Petite brique : Analyse les relations de proximité entre stations
    
    Cette brique est responsable uniquement de :
    - Calculer les distances entre stations
    - Identifier les clusters géographiques
    - Créer les relations de proximité
    - Analyser les bassins versants
    """
    logger = get_dagster_logger()
    day = context.partition_key
    
    logger.info(f"Analyse proximité stations pour {day}")
    
    stations_count = 350  # Simulation
    
    if stations_count < 2:
        logger.warning(f"⚠ Proximité {day}: Pas assez de stations pour l'analyse")
        return {
            "date": day,
            "relations_created": 0,
            "status": "insufficient_data"
        }
    
    # Simulation de l'analyse géospatiale
    proximity_analysis = {
        "stations_analyzed": stations_count,
        "distance_matrix_computed": True,
        "clusters_identified": min(stations_count // 3, 5),  # Simulation
        "watersheds_analyzed": 3,  # Simulation
        "relations_created": stations_count * (stations_count - 1) // 2,  # Combinaisons
        "max_distance_km": 50.0,  # Rayon d'analyse
        "spatial_metrics": {
            "average_distance": 25.5,  # Simulation
            "closest_pair_distance": 2.3,  # Simulation
            "farthest_pair_distance": 48.7  # Simulation
        }
    }
    
    # Simulation des relations créées
    relations = []
    for i in range(min(stations_count, 10)):  # Limite pour la simulation
        for j in range(i + 1, min(stations_count, 10)):
            distance = 2.0 + (i * j * 1.5) % 30.0  # Simulation de distance
            if distance <= proximity_analysis["max_distance_km"]:
                relations.append({
                    "station1": f"BSS{i:03d}",
                    "station2": f"BSS{j:03d}",
                    "distance_km": distance,
                    "relationship_type": "nearby" if distance < 10 else "regional"
                })
    
    result = {
        "date": day,
        "relations_analyzed": len(relations),
        "relations_created": len(relations),
        "clusters_identified": proximity_analysis["clusters_identified"],
        "average_distance_km": proximity_analysis["spatial_metrics"]["average_distance"],
        "status": "success"
    }
    
    logger.info(f"✓ Proximité {day}: {result['relations_created']} relations créées, {result['clusters_identified']} clusters")
    return result
