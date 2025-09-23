"""
Tests d'intégration pour le pipeline Hub'Eau
Validation des composants critiques et des nouvelles fonctionnalités
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta


class TestHubEauIntegration:
    """Tests d'intégration pour valider le pipeline complet"""
    
    def test_endpoints_configuration(self):
        """Test que tous les endpoints Hub'Eau sont configurés"""
        from src.hubeau_pipeline.assets import HUBEAU_ENDPOINTS
        
        expected_apis = [
            "piezo", "hydro", "temperature", "ecoulement", 
            "hydrobiologie", "quality_surface", "quality_groundwater", "prelevements"
        ]
        
        for api in expected_apis:
            assert api in HUBEAU_ENDPOINTS, f"API {api} manquante dans la configuration"
            
        # Vérification des URLs
        for api, config in HUBEAU_ENDPOINTS.items():
            for endpoint_type, url in config.items():
                assert url.startswith("https://hubeau.eaufrance.fr/api/v1/"), \
                    f"URL invalide pour {api}.{endpoint_type}: {url}"
    
    def test_pagination_function(self):
        """Test de la fonction de pagination optimisée"""
        from src.hubeau_pipeline.assets import fetch_hubeau
        
        # Mock d'une réponse Hub'Eau typique
        class MockResponse:
            def __init__(self, data, total_pages=1):
                self.data = data
                self.total_pages = total_pages
            
            def json(self):
                return {
                    "data": self.data,
                    "totalPages": self.total_pages
                }
            
            def raise_for_status(self):
                pass
        
        class MockHTTP:
            def __init__(self, responses):
                self.responses = responses
                self.call_count = 0
            
            def get(self, url, params):
                response = self.responses[self.call_count]
                self.call_count += 1
                return response
        
        # Test avec une seule page
        mock_http = MockHTTP([
            MockResponse([{"id": 1, "value": 10}], total_pages=1)
        ])
        
        result = fetch_hubeau(mock_http, "http://test.com", {})
        assert len(result) == 1
        assert result[0]["id"] == 1
    
    def test_normalize_measure_data(self):
        """Test de la normalisation des données de mesure"""
        from src.hubeau_pipeline.assets import normalize_measure_data
        
        # Données piézométriques simulées
        rows = [
            {
                "bss_id": "12345",
                "date_mesure": "2024-01-01T10:00:00Z",
                "niveau_nappe": 15.5,
                "code_qualite": "2"
            }
        ]
        
        normalized = normalize_measure_data(rows, "piezo", "hubeau_piezo")
        
        assert len(normalized) == 1
        assert normalized[0]["station_code"] == "12345"
        assert normalized[0]["theme"] == "piezo"
        assert normalized[0]["value"] == 15.5
        assert normalized[0]["quality"] == "2"
        assert normalized[0]["source"] == "hubeau_piezo"
    
    def test_station_meta_structure(self):
        """Test de la structure des métadonnées des stations"""
        # Vérification que l'asset station_meta_sync existe
        from src.hubeau_pipeline.assets_station_meta import station_meta_sync
        
        assert station_meta_sync is not None
        assert hasattr(station_meta_sync, 'group_name')
        assert station_meta_sync.group_name == "meta"
    
    def test_neo4j_constraints(self):
        """Test des contraintes Neo4j"""
        # Lecture du fichier de contraintes
        with open("scripts/init_neo4j.cypher", "r") as f:
            content = f.read()
        
        expected_constraints = [
            "station_code", "masse_eau_code", "commune_insee", 
            "parametre_code", "reseau_code", "unite_code", "methode_code"
        ]
        
        for constraint in expected_constraints:
            assert f"CREATE CONSTRAINT {constraint}" in content, \
                f"Contrainte {constraint} manquante"
    
    def test_timescaledb_schema(self):
        """Test du schéma TimescaleDB"""
        with open("scripts/init_timescaledb.sql", "r") as f:
            content = f.read()
        
        # Vérification des extensions
        assert "CREATE EXTENSION IF NOT EXISTS timescaledb" in content
        assert "CREATE EXTENSION IF NOT EXISTS postgis" in content
        
        # Vérification des tables principales
        expected_tables = [
            "measure", "station_meta", "masse_eau_meta", 
            "prelevements_summary", "parametre_sandre", "forage_infoterre"
        ]
        
        for table in expected_tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in content, \
                f"Table {table} manquante"
    
    def test_dagster_definitions(self):
        """Test que toutes les définitions Dagster sont correctes"""
        from src.hubeau_pipeline import defs
        
        # Vérification des composants
        assert defs.assets is not None
        assert len(defs.assets) > 20, "Pas assez d'assets définis"
        
        assert defs.schedules is not None
        assert len(defs.schedules) >= 4, "Pas assez de schedules définis"
        
        assert defs.sensors is not None
        assert len(defs.sensors) >= 2, "Pas assez de sensors définis"
        
        assert defs.asset_checks is not None
        assert len(defs.asset_checks) >= 4, "Pas assez d'asset checks définis"
    
    def test_resources_configuration(self):
        """Test de la configuration des ressources"""
        from src.hubeau_pipeline.resources import RESOURCES
        
        expected_resources = [
            "http_client", "pg", "neo4j", "redis", "s3"
        ]
        
        for resource in expected_resources:
            assert resource in RESOURCES, f"Ressource {resource} manquante"
    
    def test_freshness_policies(self):
        """Test des politiques de fraîcheur"""
        from src.hubeau_pipeline.assets import FRESH_DAILY
        
        assert FRESH_DAILY is not None
        assert FRESH_DAILY.maximum_lag_minutes == 24 * 60  # 24h
    
    def test_job_definitions(self):
        """Test des définitions de jobs"""
        from src.hubeau_pipeline.assets import (
            hubeau_daily_job, external_weekly_job, full_integration_job
        )
        
        # Vérification que les jobs existent
        assert hubeau_daily_job is not None
        assert external_weekly_job is not None
        assert full_integration_job is not None
        
        # Vérification des sélections
        assert len(hubeau_daily_job.selection.resolve()) > 5
        assert len(external_weekly_job.selection.resolve()) > 5


class TestQualityV2:
    """Tests pour la qualité v2 et le thésaurus Sandre"""
    
    def test_quality_assets_exist(self):
        """Test que les assets qualité v2 existent"""
        from src.hubeau_pipeline.assets_quality import (
            quality_raw, quality_timescale, 
            quality_groundwater_raw, quality_groundwater_timescale
        )
        
        assert quality_raw is not None
        assert quality_timescale is not None
        assert quality_groundwater_raw is not None
        assert quality_groundwater_timescale is not None
    
    def test_sandre_assets_exist(self):
        """Test que les assets Sandre existent"""
        from src.hubeau_pipeline.assets_sandre import (
            sandre_params_raw, sandre_params_pg,
            sandre_units_raw, sandre_units_pg
        )
        
        assert sandre_params_raw is not None
        assert sandre_params_pg is not None
        assert sandre_units_raw is not None
        assert sandre_units_pg is not None
    
    def test_graph_quality_assets_exist(self):
        """Test que les assets graphe qualité existent"""
        from src.hubeau_pipeline.assets_graph_quality import (
            graph_params, graph_station_has_param,
            graph_quality_correlations, graph_quality_profiles
        )
        
        assert graph_params is not None
        assert graph_station_has_param is not None
        assert graph_quality_correlations is not None
        assert graph_quality_profiles is not None

class TestMeteoAssets:
    """Tests pour les assets météo"""
    
    def test_meteo_assets_exist(self):
        """Test que les assets météo existent"""
        from src.hubeau_pipeline.assets_meteo import (
            meteo_raw, meteo_timescale,
            station2grid_update, meteo_station_summary
        )
        
        assert meteo_raw is not None
        assert meteo_timescale is not None
        assert station2grid_update is not None
        assert meteo_station_summary is not None

class TestUtils:
    """Tests pour les utilitaires"""
    
    def test_coordinate_validation(self):
        """Test de validation des coordonnées"""
        from src.hubeau_pipeline.utils import validate_coordinates
        
        # Coordonnées valides
        assert validate_coordinates(2.3522, 48.8566) == True  # Paris
        assert validate_coordinates(-74.0059, 40.7128) == True  # New York
        
        # Coordonnées invalides
        assert validate_coordinates(None, 48.8566) == False
        assert validate_coordinates(2.3522, None) == False
        assert validate_coordinates(200, 48.8566) == False  # Longitude > 180
        assert validate_coordinates(2.3522, 200) == False  # Latitude > 90
    
    def test_station_code_normalization(self):
        """Test de normalisation des codes de station"""
        from src.hubeau_pipeline.utils import normalize_station_code
        
        # Codes valides
        assert normalize_station_code("12345") == "12345"
        assert normalize_station_code("  12345  ") == "12345"
        assert normalize_station_code("abc123") == "ABC123"
        
        # Codes invalides
        assert normalize_station_code("") == None
        assert normalize_station_code("12") == None  # Trop court
        assert normalize_station_code(None) == None
    
    def test_rate_limiter(self):
        """Test du rate limiter"""
        from src.hubeau_pipeline.utils import RateLimiter
        
        limiter = RateLimiter(max_requests=2, time_window=1)
        
        # Premières requêtes autorisées
        assert limiter.can_make_request() == True
        limiter.record_request()
        assert limiter.can_make_request() == True
        limiter.record_request()
        
        # Troisième requête bloquée
        assert limiter.can_make_request() == False

class TestBackfills:
    """Tests pour les fonctionnalités de backfill"""
    
    def test_partition_date_validation(self):
        """Test de validation des dates de partition"""
        from dagster import DailyPartitionsDefinition
        
        partitions = DailyPartitionsDefinition(start_date="2020-01-01")
        
        # Dates valides
        assert "2024-01-01" in partitions.get_partition_keys()
        assert "2024-12-31" in partitions.get_partition_keys()
        
        # Date future (hors partition)
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        assert future_date not in partitions.get_partition_keys()

class TestDatabaseSchema:
    """Tests pour la validation du schéma de base de données"""
    
    def test_measure_quality_table(self):
        """Test que la table measure_quality est définie"""
        with open("scripts/init_timescaledb.sql", "r") as f:
            content = f.read()
        
        assert "CREATE TABLE IF NOT EXISTS measure_quality" in content
        assert "station_code TEXT NOT NULL" in content
        assert "param_code TEXT NOT NULL" in content
        assert "PRIMARY KEY (station_code, param_code, ts)" in content
    
    def test_meteo_tables(self):
        """Test que les tables météo sont définies"""
        with open("scripts/init_timescaledb.sql", "r") as f:
            content = f.read()
        
        assert "CREATE TABLE IF NOT EXISTS meteo_grid" in content
        assert "CREATE TABLE IF NOT EXISTS meteo_series" in content
        assert "CREATE TABLE IF NOT EXISTS station2grid" in content
    
    def test_quality_param_table(self):
        """Test que la table quality_param est définie"""
        with open("scripts/init_timescaledb.sql", "r") as f:
            content = f.read()
        
        assert "CREATE TABLE IF NOT EXISTS quality_param" in content
        assert "code_param TEXT PRIMARY KEY" in content
    
    def test_materialized_views(self):
        """Test que les vues matérialisées sont définies"""
        with open("scripts/init_timescaledb.sql", "r") as f:
            content = f.read()
        
        assert "CREATE MATERIALIZED VIEW IF NOT EXISTS station_kpis_daily" in content
        assert "CREATE MATERIALIZED VIEW IF NOT EXISTS quality_correlations" in content
        assert "CREATE MATERIALIZED VIEW IF NOT EXISTS meteo_station_daily" in content

class TestIdempotence:
    """Tests d'idempotence pour les opérations critiques"""
    
    def test_upsert_queries(self):
        """Test que les requêtes d'upsert sont bien formées"""
        from src.hubeau_pipeline.utils import create_upsert_sql
        
        # Test d'upsert pour station_meta
        sql = create_upsert_sql(
            "station_meta",
            ["station_code", "label", "type", "geom"],
            ["station_code"]
        )
        
        assert "INSERT INTO station_meta" in sql
        assert "ON CONFLICT (station_code)" in sql
        assert "DO UPDATE SET" in sql
    
    def test_primary_keys_unique(self):
        """Test que les clés primaires sont bien définies"""
        with open("scripts/init_timescaledb.sql", "r") as f:
            content = f.read()
        
        # Tables avec clés primaires composées
        assert "PRIMARY KEY (station_code, theme, ts)" in content  # measure
        assert "PRIMARY KEY (station_code, param_code, ts)" in content  # measure_quality
        assert "PRIMARY KEY (grid_id, ts)" in content  # meteo_series


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
