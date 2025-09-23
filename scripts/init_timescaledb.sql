-- Initialisation TimescaleDB + PostGIS pour Hub'Eau
-- À exécuter une seule fois après le premier démarrage de TimescaleDB

-- Extensions requises
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;

-- Table des chroniques génériques multi-thèmes
CREATE TABLE IF NOT EXISTS measure(
  station_code TEXT NOT NULL,
  theme TEXT NOT NULL,                -- 'piezo','hydro','temp','quality', ...
  ts TIMESTAMPTZ NOT NULL,
  value DOUBLE PRECISION,
  quality TEXT,
  source TEXT,
  PRIMARY KEY (station_code, theme, ts)
);

-- Conversion en hypertable TimescaleDB
SELECT create_hypertable('measure','ts', chunk_time_interval => interval '7 days', if_not_exists => true);

-- Index pour les requêtes fréquentes
CREATE INDEX IF NOT EXISTS measure_idx ON measure(station_code, theme, ts DESC);
CREATE INDEX IF NOT EXISTS measure_theme_ts ON measure(theme, ts DESC);

-- Métadonnées des stations (géospatiales)
CREATE TABLE IF NOT EXISTS station_meta(
  station_code TEXT PRIMARY KEY,
  label TEXT,
  type TEXT,                          -- 'piezo','hydro','temp',...
  insee TEXT,
  masse_eau_code TEXT,
  reseau TEXT,                        -- réseau de mesure
  geom GEOGRAPHY(POINT, 4326),
  altitude_mngf DOUBLE PRECISION,
  profondeur_m DOUBLE PRECISION,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index géospatial pour PostGIS
CREATE INDEX IF NOT EXISTS station_meta_gix ON station_meta USING GIST(geom);
CREATE INDEX IF NOT EXISTS station_meta_insee ON station_meta(insee);
CREATE INDEX IF NOT EXISTS station_meta_masse_eau ON station_meta(masse_eau_code);

-- Agrégat quotidien pour les dashboards
CREATE MATERIALIZED VIEW IF NOT EXISTS measure_daily
WITH (timescaledb.continuous) AS
SELECT 
  station_code, 
  theme, 
  time_bucket('1 day', ts) AS day,
  avg(value) AS avg_value, 
  min(value) AS min_value, 
  max(value) AS max_value, 
  count(*) AS count_points,
  stddev(value) AS stddev_value
FROM measure
GROUP BY station_code, theme, day;

-- Agrégat hebdomadaire pour les analyses long-terme
CREATE MATERIALIZED VIEW IF NOT EXISTS measure_weekly
WITH (timescaledb.continuous) AS
SELECT 
  station_code, 
  theme, 
  time_bucket('1 week', ts) AS week,
  avg(value) AS avg_value, 
  min(value) AS min_value, 
  max(value) AS max_value, 
  count(*) AS count_points
FROM measure
GROUP BY station_code, theme, week;

-- Agrégat mensuel pour les analyses saisonnières
CREATE MATERIALIZED VIEW IF NOT EXISTS measure_monthly
WITH (timescaledb.continuous) AS
SELECT 
  station_code, 
  theme, 
  time_bucket('1 month', ts) AS month,
  avg(value) AS avg_value, 
  min(value) AS min_value, 
  max(value) AS max_value, 
  count(*) AS count_points
FROM measure
GROUP BY station_code, theme, month;

-- Table pour les métadonnées des masses d'eau (BDLISA)
CREATE TABLE IF NOT EXISTS masse_eau_meta(
  code TEXT PRIMARY KEY,
  libelle TEXT,
  niveau TEXT,                        -- 'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7', 'N8', 'N9', 'N10'
  type_masse TEXT,                    -- 'libre', 'captif'
  aquifere TEXT,
  geometry GEOMETRY(MULTIPOLYGON, 4326),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS masse_eau_geom_gix ON masse_eau_meta USING GIST(geometry);
CREATE INDEX IF NOT EXISTS masse_eau_niveau ON masse_eau_meta(niveau);
CREATE INDEX IF NOT EXISTS masse_eau_aquifere ON masse_eau_meta(aquifere);

-- Table pour les prélèvements d'eau
CREATE TABLE IF NOT EXISTS prelevements_summary(
  id SERIAL PRIMARY KEY,
  code_commune TEXT,
  code_commune_insee TEXT,
  code_departement TEXT,
  code_region TEXT,
  volume_preleve DOUBLE PRECISION,
  date_prelevement DATE,
  type_prelevement TEXT,              -- 'AEP', 'irrigation', 'industriel', etc.
  source_prelevement TEXT,            -- 'eau_souterraine', 'eau_surface'
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS prelevements_commune ON prelevements_summary(code_commune_insee);
CREATE INDEX IF NOT EXISTS prelevements_date ON prelevements_summary(date_prelevement);
CREATE INDEX IF NOT EXISTS prelevements_type ON prelevements_summary(type_prelevement);

-- Table pour les paramètres Sandre
CREATE TABLE IF NOT EXISTS parametre_sandre(
  code TEXT PRIMARY KEY,
  libelle TEXT,
  description TEXT,
  theme TEXT,
  unite TEXT,
  symbole TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS parametre_theme ON parametre_sandre(theme);

-- Table pour les unités Sandre
CREATE TABLE IF NOT EXISTS unite_sandre(
  code TEXT PRIMARY KEY,
  libelle TEXT,
  description TEXT,
  symbole TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table pour les méthodes d'analyse Sandre
CREATE TABLE IF NOT EXISTS methode_sandre(
  code TEXT PRIMARY KEY,
  libelle TEXT,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table pour les forages InfoTerre
CREATE TABLE IF NOT EXISTS forage_infoterre(
  code_bss TEXT PRIMARY KEY,
  nom_forage TEXT,
  profondeur_investigation DOUBLE PRECISION,
  altitude_forage DOUBLE PRECISION,
  date_creation DATE,
  geometry GEOMETRY(POINT, 4326),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS forage_geom_gix ON forage_infoterre USING GIST(geometry);
CREATE INDEX IF NOT EXISTS forage_profondeur ON forage_infoterre(profondeur_investigation);

-- Table pour les données CarMen (chimie agrégée)
CREATE TABLE IF NOT EXISTS carmen_chimie(
  id SERIAL PRIMARY KEY,
  code_station TEXT,
  code_parametre TEXT,
  valeur DOUBLE PRECISION,
  unite TEXT,
  date_analyse DATE,
  type_eau TEXT,                      -- 'souterraine', 'surface'
  region TEXT,
  departement TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS carmen_station ON carmen_chimie(code_station);
CREATE INDEX IF NOT EXISTS carmen_parametre ON carmen_chimie(code_parametre);
CREATE INDEX IF NOT EXISTS carmen_date ON carmen_chimie(date_analyse);
CREATE INDEX IF NOT EXISTS carmen_type ON carmen_chimie(type_eau);

-- Table spécialisée pour la qualité (paramètre chimique par mesure)
CREATE TABLE IF NOT EXISTS measure_quality(
  station_code TEXT NOT NULL,
  param_code   TEXT NOT NULL,          -- Sandre
  ts           TIMESTAMPTZ NOT NULL,
  value        DOUBLE PRECISION,
  unit         TEXT,                   -- Sandre
  quality      TEXT,                   -- remarque/qualification
  source       TEXT,
  PRIMARY KEY (station_code, param_code, ts)
);

SELECT create_hypertable('measure_quality','ts', chunk_time_interval => interval '14 days', if_not_exists => true);
CREATE INDEX IF NOT EXISTS measure_quality_idx ON measure_quality(station_code, param_code, ts DESC);
CREATE INDEX IF NOT EXISTS measure_quality_param ON measure_quality(param_code, ts DESC);

-- Table thésaurus paramètres Sandre
CREATE TABLE IF NOT EXISTS quality_param(
  code_param TEXT PRIMARY KEY,
  label      TEXT,
  unit       TEXT,
  family     TEXT,                     -- famille de paramètres
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS quality_param_family ON quality_param(family);

-- Tables météo (grille + séries)
CREATE TABLE IF NOT EXISTS meteo_grid(
  grid_id SERIAL PRIMARY KEY,
  lon DOUBLE PRECISION NOT NULL,
  lat DOUBLE PRECISION NOT NULL,
  geom GEOGRAPHY(POINT,4326) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS meteo_grid_gix ON meteo_grid USING GIST(geom);
CREATE UNIQUE INDEX IF NOT EXISTS meteo_grid_lonlat ON meteo_grid(lon, lat);

CREATE TABLE IF NOT EXISTS meteo_series(
  grid_id INT NOT NULL REFERENCES meteo_grid(grid_id),
  ts TIMESTAMPTZ NOT NULL,
  prcp DOUBLE PRECISION,               -- mm
  t2m  DOUBLE PRECISION,               -- °C
  etp  DOUBLE PRECISION,               -- mm (si dispo)
  source TEXT,
  PRIMARY KEY (grid_id, ts)
);

SELECT create_hypertable('meteo_series','ts', chunk_time_interval => interval '30 days', if_not_exists => true);
CREATE INDEX IF NOT EXISTS meteo_series_grid_ts ON meteo_series(grid_id, ts DESC);

-- Lien station -> cellule météo la plus proche (matérialisé)
CREATE TABLE IF NOT EXISTS station2grid AS 
SELECT s.station_code, g.grid_id 
FROM station_meta s 
JOIN LATERAL (
  SELECT grid_id FROM meteo_grid
  ORDER BY s.geom <-> meteo_grid.geom
  LIMIT 1
) g ON TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS station2grid_pk ON station2grid(station_code);

-- Vue métriques station (KPIs quotidiens)
CREATE MATERIALIZED VIEW IF NOT EXISTS station_kpis_daily 
WITH (timescaledb.continuous) AS
SELECT 
  station_code,
  time_bucket('1 day', ts) AS day,
  COUNT(*) AS n_pts,
  AVG(value) FILTER (WHERE theme='piezo') AS piezo_avg,
  MIN(value) FILTER (WHERE theme='piezo') AS piezo_min,
  MAX(value) FILTER (WHERE theme='piezo') AS piezo_max,
  AVG(value) FILTER (WHERE theme='hydro') AS hydro_avg,
  AVG(value) FILTER (WHERE theme='temp') AS temp_avg
FROM measure 
GROUP BY station_code, day;

-- Vue pour les corrélations qualité
CREATE MATERIALIZED VIEW IF NOT EXISTS quality_correlations
WITH (timescaledb.continuous) AS
SELECT 
  param_code,
  time_bucket('1 month', ts) AS month,
  COUNT(DISTINCT station_code) AS nb_stations,
  COUNT(*) AS nb_mesures,
  AVG(value) AS avg_value,
  STDDEV(value) AS stddev_value,
  MIN(value) AS min_value,
  MAX(value) AS max_value
FROM measure_quality
GROUP BY param_code, month;

-- Table pour les communes (géolocalisation)
CREATE TABLE IF NOT EXISTS commune_meta(
  insee TEXT PRIMARY KEY,
  nom TEXT,
  code_departement TEXT,
  code_region TEXT,
  geometry GEOMETRY(MULTIPOLYGON, 4326),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS commune_geom_gix ON commune_meta USING GIST(geometry);
CREATE INDEX IF NOT EXISTS commune_departement ON commune_meta(code_departement);

-- Fonction pour mettre à jour le timestamp updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger pour station_meta
CREATE TRIGGER update_station_meta_updated_at 
    BEFORE UPDATE ON station_meta 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Vue pour les statistiques globales
CREATE OR REPLACE VIEW stats_globales AS
SELECT 
  theme,
  COUNT(DISTINCT station_code) as nb_stations,
  MIN(ts) as date_debut,
  MAX(ts) as date_fin,
  COUNT(*) as nb_mesures,
  AVG(value) as moyenne_globale
FROM measure 
GROUP BY theme;

-- Fonction utilitaire pour calculer les corrélations entre stations
CREATE OR REPLACE FUNCTION calculate_correlation(
  station1 TEXT, 
  station2 TEXT, 
  start_date TIMESTAMPTZ, 
  end_date TIMESTAMPTZ
) RETURNS DOUBLE PRECISION AS $$
DECLARE
  correlation DOUBLE PRECISION;
BEGIN
  WITH data AS (
    SELECT 
      m1.value as val1,
      m2.value as val2
    FROM measure m1
    JOIN measure m2 ON m1.ts = m2.ts
    WHERE m1.station_code = station1 
      AND m2.station_code = station2
      AND m1.theme = m2.theme
      AND m1.ts BETWEEN start_date AND end_date
      AND m1.value IS NOT NULL 
      AND m2.value IS NOT NULL
  )
  SELECT corr(val1, val2) INTO correlation FROM data;
  
  RETURN COALESCE(correlation, 0.0);
END;
$$ LANGUAGE plpgsql;
