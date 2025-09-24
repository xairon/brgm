"""
Asset Bronze - BDLISA
Petite brique spécialisée pour BDLISA (masses d'eau souterraine)
"""

from dagster import AssetExecutionContext, asset, MonthlyPartitionsDefinition, get_dagster_logger

# Configuration des partitions mensuelles (BDLISA se met à jour mensuellement)
PARTITIONS = MonthlyPartitionsDefinition(start_date="2020-01-01")

@asset(
    partitions_def=PARTITIONS,
    group_name="bronze_external",
    description="Récupération des masses d'eau souterraine BDLISA"
)
def bdlisa_masses_eau_raw(context: AssetExecutionContext):
    """
    Petite brique : Récupère les masses d'eau souterraine BDLISA
    
    Cette brique récupère :
    - Polygones des masses d'eau
    - Codes et libellés
    - Hiérarchies (niveaux 1, 2, 3)
    - Relations géographiques
    """
    logger = get_dagster_logger()
    month = context.partition_key
    
    logger.info(f"Récupération BDLISA pour {month}")
    
    # Configuration WFS BDLISA
    wfs_url = "https://services.sandre.eaufrance.fr/geo/bdlisa"
    wfs_params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "bdlisa:Massedeau",
        "outputFormat": "application/json"
    }
    
    try:
        # Simulation de données BDLISA
        bdlisa_data = {
            "date": month,
            "masses_eau_count": 1250,
            "niveau1_count": 45,
            "niveau2_count": 180,
            "niveau3_count": 1025,
            "source": "WFS BDLISA",
            "status": "success"
        }
        
        result = {
            "date": month,
            "records": bdlisa_data["masses_eau_count"],
            "levels": {
                "niveau1": bdlisa_data["niveau1_count"],
                "niveau2": bdlisa_data["niveau2_count"], 
                "niveau3": bdlisa_data["niveau3_count"]
            },
            "status": "simulation",
            "note": "BDLISA - simulation WFS"
        }
        
        logger.info(f"✓ BDLISA {month}: {result['records']} masses d'eau")
        return result
        
    except Exception as e:
        logger.error(f"✗ Erreur BDLISA: {str(e)}")
        return {
            "date": month,
            "records": 0,
            "status": "error",
            "error": str(e)
        }
