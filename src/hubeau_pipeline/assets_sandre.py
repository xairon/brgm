"""Assets Sandre - Version simplifiée"""

from dagster import asset

@asset
def sandre_params_raw():
    return {"status": "placeholder"}