"""Assets qualité - Version simplifiée"""

from dagster import asset

@asset
def quality_raw():
    return {"status": "placeholder"}