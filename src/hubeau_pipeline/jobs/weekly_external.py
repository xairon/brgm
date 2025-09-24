"""
Job Orchestré - Sources externes hebdomadaires
Grosse brique qui orchestre les sources externes (Sandre, BDLISA, etc.)
"""

from dagster import define_asset_job, AssetSelection
from hubeau_pipeline.assets.bronze import (
    sandre_params_raw, sandre_units_raw, bdlisa_masses_eau_raw
)

# Sélection des assets Sandre (hebdomadaire)
sandre_selection = AssetSelection.assets(
    sandre_params_raw,
    sandre_units_raw
)

# Sélection des assets BDLISA (mensuel)
bdlisa_selection = AssetSelection.assets(
    bdlisa_masses_eau_raw
)

# Job orchestré : Sources Sandre hebdomadaires
sandre_weekly_job = define_asset_job(
    name="sandre_weekly_job",
    description="""
    🏗️ GROSSE BRIQUE : Orchestration des sources Sandre
    
    Ce job orchestre les petites briques pour :
    - Récupérer les nomenclatures Sandre (paramètres, unités)
    - Synchroniser les référentiels Sandre
    
    Exécution hebdomadaire car ces sources changent moins souvent
    """,
    selection=sandre_selection,
    config={
        "execution": {
            "config": {
                "multiprocess": {
                    "max_concurrent": 2,  # Limite pour les APIs externes
                }
            }
        }
    }
)

# Job orchestré : Sources BDLISA mensuelles
bdlisa_monthly_job = define_asset_job(
    name="bdlisa_monthly_job",
    description="""
    🏗️ GROSSE BRIQUE : Orchestration des sources BDLISA
    
    Ce job orchestre les petites briques pour :
    - Mettre à jour les masses d'eau BDLISA
    - Synchroniser les référentiels géographiques
    
    Exécution mensuelle car ces sources changent très peu
    """,
    selection=bdlisa_selection,
    config={
        "execution": {
            "config": {
                "multiprocess": {
                    "max_concurrent": 1,  # Limite pour les APIs externes
                }
            }
        }
    }
)
