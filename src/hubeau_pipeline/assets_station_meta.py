"""Assets métadonnées stations - Version simplifiée"""

from dagster import asset

@asset
def station_meta_sync():
    return {"status": "placeholder"}