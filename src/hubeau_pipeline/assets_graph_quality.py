"""Assets graph qualité - Version simplifiée"""

from dagster import asset

@asset
def graph_params():
    return {"status": "placeholder"}