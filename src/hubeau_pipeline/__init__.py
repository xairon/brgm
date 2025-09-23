from dagster import Definitions
from .assets import assets, schedules, sensors, checks
from .resources import RESOURCES

defs = Definitions(
    assets=assets, 
    schedules=schedules, 
    sensors=sensors, 
    resources=RESOURCES,
    asset_checks=checks
)
