"""Assets géospatiaux - Version simplifiée"""

from dagster import asset

@asset
def station_correlations():
    return {"status": "placeholder"}