"""Assets météo - Version simplifiée"""

from dagster import asset

@asset
def meteo_raw():
    return {"status": "placeholder"}