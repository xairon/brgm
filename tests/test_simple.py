"""
Tests simplifiés pour le pipeline Hub'Eau
Version de base qui fonctionne
"""

import pytest
from dagster import materialize


class TestHubEauSimple:
    """Tests pour la version simplifiée du pipeline"""
    
    def test_assets_exist(self):
        """Test que les assets existent"""
        from hubeau_pipeline.assets_simple import assets
        
        assert len(assets) == 2
        assert assets[0].key.to_user_string() == "piezo_raw"
        assert assets[1].key.to_user_string() == "piezo_timescale"
    
    def test_jobs_exist(self):
        """Test que les jobs existent"""
        from hubeau_pipeline.assets_simple import jobs
        
        assert len(jobs) == 1
        assert jobs[0].name == "hubeau_daily_job"
    
    def test_schedules_exist(self):
        """Test que les schedules existent"""
        from hubeau_pipeline.assets_simple import schedules
        
        assert len(schedules) == 1
        assert schedules[0].name == "hubeau_daily_schedule"
    
    def test_definitions_load(self):
        """Test que les définitions se chargent"""
        from hubeau_pipeline import defs
        
        assert defs is not None
        assert len(defs.assets) == 2
        assert len(defs.jobs) == 1
        assert len(defs.schedules) == 1
