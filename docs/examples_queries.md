# Exemples de requêtes avancées

Ce document présente des exemples de requêtes pour exploiter la plateforme Hub'Eau Data Integration.

## 🔍 Requêtes Neo4j (Graphe sémantique)

### Relations de proximité et corrélations

```cypher
// Stations piézométriques proches (< 5km) partageant la même masse d'eau
MATCH (s:Station {type: 'piezo'})-[:IN_MASSE]->(m:MasseEau)<-[:IN_MASSE]-(t:Station),
      (s)-[n:NEAR]-(t)
WHERE n.distance_km < 5
RETURN s.code, s.label, t.code, t.label, n.distance_km
ORDER BY n.distance_km ASC;

// Stations corrélées (rho>0.7) sur 90 jours
MATCH (:Station {code: $station_code})-[c:CORRELATED]-(t:Station)
WHERE c.rho > 0.7 AND c.window_days = 90
RETURN t.code, t.label, c.rho, c.station_type
ORDER BY c.rho DESC;

// Relations hydrologiques complexes
MATCH (piezo:Station {type: 'piezo'})-[:HYDROLOGICAL_RELATION]-(hydro:Station {type: 'hydro'})
WHERE piezo.masse_eau_code = hydro.masse_eau_code
RETURN piezo.code, hydro.code, piezo.masse_eau_code;
```

### Analyses d'impact anthropique

```cypher
// Stations affectées par des prélèvements importants
MATCH (p:Prelevement)-[:AFFECTS]->(s:Station)
WHERE p.pressure_level IN ['high_pressure', 'moderate_pressure']
RETURN s.code, s.label, p.total_volume_m3, p.pressure_level
ORDER BY p.total_volume_m3 DESC;

// Corrélation entre prélèvements et niveaux piézométriques
MATCH (s:Station {type: 'piezo'})-[r:AFFECTS]-(p:Prelevement)
WHERE s.avg_piezo_level IS NOT NULL
RETURN s.code, p.total_volume_m3, s.avg_piezo_level
ORDER BY p.total_volume_m3 DESC;
```

### Requêtes avec ontologies

```cypher
// Utilisation des nomenclatures Sandre
MATCH (s:Station)-[:MEASURES_PARAM]->(p:Parametre)
WHERE p.theme = 'quality'
RETURN s.code, p.libelle, p.unite;

// Relations de provenance (PROV-O)
MATCH (a:Activity)-[:GENERATED]->(ds:DataSource)
WHERE a.type = 'data_ingestion'
RETURN a.source, ds.name, ds.quality_rate_percent;
```

## 🗄️ Requêtes TimescaleDB (Analyses temporelles)

### Analyses de séries temporelles

```sql
-- Évolution des niveaux piézométriques par masse d'eau
SELECT 
    sm.masse_eau_code,
    time_bucket('1 month', m.ts) as month,
    AVG(m.value) as avg_level,
    MIN(m.value) as min_level,
    MAX(m.value) as max_level,
    COUNT(*) as nb_mesures
FROM measure m
JOIN station_meta sm ON m.station_code = sm.station_code
WHERE m.theme = 'piezo'
AND m.ts >= NOW() - INTERVAL '2 years'
GROUP BY sm.masse_eau_code, month
ORDER BY sm.masse_eau_code, month;

-- Corrélation entre hydrométrie et piézométrie
WITH monthly_piezo AS (
    SELECT 
        station_code,
        time_bucket('1 month', ts) as month,
        AVG(value) as piezo_level
    FROM measure 
    WHERE theme = 'piezo' AND ts >= NOW() - INTERVAL '1 year'
    GROUP BY station_code, month
),
monthly_hydro AS (
    SELECT 
        station_code,
        time_bucket('1 month', ts) as month,
        AVG(value) as hydro_level
    FROM measure 
    WHERE theme = 'hydro' AND ts >= NOW() - INTERVAL '1 year'
    GROUP BY station_code, month
)
SELECT 
    p.station_code,
    corr(p.piezo_level, h.hydro_level) as correlation
FROM monthly_piezo p
JOIN monthly_hydro h ON p.station_code = h.station_code AND p.month = h.month
WHERE p.piezo_level IS NOT NULL AND h.hydro_level IS NOT NULL
GROUP BY p.station_code
HAVING corr(p.piezo_level, h.hydro_level) > 0.5;
```

### Analyses géospatiales avec PostGIS

```sql
-- Stations dans un rayon de 10km d'un point
SELECT 
    station_code,
    label,
    ST_Distance(
        ST_GeogFromText('POINT(2.3522 48.8566)'),  -- Paris
        geom
    ) / 1000 as distance_km
FROM station_meta
WHERE ST_DWithin(
    ST_GeogFromText('POINT(2.3522 48.8566)'),
    geom,
    10000  -- 10km
)
ORDER BY distance_km;

-- Intersection avec masses d'eau
SELECT 
    s.station_code,
    s.label,
    me.libelle as masse_eau,
    ST_Area(me.geometry::geography) / 1000000 as area_km2
FROM station_meta s
JOIN masse_eau_meta me ON ST_Intersects(s.geom::geometry, me.geometry)
WHERE s.type = 'piezo';
```

### Analyses de qualité des données

```sql
-- Statistiques de qualité par source
SELECT 
    source,
    theme,
    COUNT(*) as total_mesures,
    COUNT(CASE WHEN value IS NOT NULL THEN 1 END) as mesures_valides,
    COUNT(CASE WHEN quality IS NOT NULL THEN 1 END) as avec_qualite,
    ROUND(
        COUNT(CASE WHEN value IS NOT NULL THEN 1 END)::numeric / COUNT(*) * 100, 2
    ) as taux_validite_pct,
    MIN(ts) as premiere_mesure,
    MAX(ts) as derniere_mesure
FROM measure
GROUP BY source, theme
ORDER BY taux_validite_pct DESC;

-- Détection des anomalies (valeurs aberrantes)
WITH stats AS (
    SELECT 
        station_code,
        AVG(value) as mean_val,
        STDDEV(value) as std_val
    FROM measure 
    WHERE theme = 'piezo' AND ts >= NOW() - INTERVAL '1 year'
    GROUP BY station_code
)
SELECT 
    m.station_code,
    m.ts,
    m.value,
    s.mean_val,
    s.std_val,
    ABS(m.value - s.mean_val) / s.std_val as z_score
FROM measure m
JOIN stats s ON m.station_code = s.station_code
WHERE m.theme = 'piezo' 
AND ABS(m.value - s.mean_val) / s.std_val > 3  -- Anomalies > 3σ
ORDER BY z_score DESC;
```

## 🔗 Requêtes inter-sources (Neo4j + TimescaleDB)

### Analyses combinées

```cypher
// Stations avec données complètes (piézo + hydro + qualité)
MATCH (s:Station)
WHERE s.type = 'piezo'
WITH s
MATCH (s)-[:NEAR]-(h:Station {type: 'hydro'})
WHERE h.type = 'hydro'
WITH s, h
MATCH (s)-[:MEASURES_PARAM]->(p:Parametre)
WHERE p.theme = 'quality'
RETURN s.code, s.label, h.code as station_hydro, COUNT(p) as nb_parametres_qualite;
```

### Requêtes de diagnostic

```sql
-- Stations avec données récentes et métadonnées complètes
SELECT 
    s.station_code,
    s.label,
    s.type,
    s.masse_eau_code,
    s.insee,
    MAX(m.ts) as derniere_mesure,
    COUNT(m.value) as nb_mesures_30j
FROM station_meta s
LEFT JOIN measure m ON s.station_code = m.station_code 
    AND m.ts >= NOW() - INTERVAL '30 days'
WHERE s.geom IS NOT NULL
GROUP BY s.station_code, s.label, s.type, s.masse_eau_code, s.insee
HAVING MAX(m.ts) >= NOW() - INTERVAL '7 days'
ORDER BY nb_mesures_30j DESC;
```

## 📊 Requêtes pour dashboards

### Métriques de performance

```sql
-- Vue d'ensemble des données par thème
SELECT 
    theme,
    COUNT(DISTINCT station_code) as nb_stations,
    COUNT(*) as nb_mesures,
    MIN(ts) as debut,
    MAX(ts) as fin,
    ROUND(AVG(value), 2) as moyenne
FROM measure
GROUP BY theme
ORDER BY nb_mesures DESC;

-- Évolution des données par mois
SELECT 
    theme,
    DATE_TRUNC('month', ts) as mois,
    COUNT(*) as nb_mesures,
    COUNT(DISTINCT station_code) as nb_stations
FROM measure
WHERE ts >= NOW() - INTERVAL '1 year'
GROUP BY theme, mois
ORDER BY theme, mois;
```

### Alertes et monitoring

```sql
-- Stations sans données récentes
SELECT 
    s.station_code,
    s.label,
    s.type,
    MAX(m.ts) as derniere_mesure,
    NOW() - MAX(m.ts) as delai_sans_donnees
FROM station_meta s
LEFT JOIN measure m ON s.station_code = m.station_code
GROUP BY s.station_code, s.label, s.type
HAVING MAX(m.ts) < NOW() - INTERVAL '7 days'
   OR MAX(m.ts) IS NULL
ORDER BY delai_sans_donnees DESC;

-- Qualité des données par région
SELECT 
    c.code_region,
    COUNT(DISTINCT s.station_code) as nb_stations,
    ROUND(
        AVG(CASE WHEN m.value IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 2
    ) as taux_validite_pct
FROM station_meta s
JOIN commune_meta c ON s.insee = c.insee
LEFT JOIN measure m ON s.station_code = m.station_code 
    AND m.ts >= NOW() - INTERVAL '30 days'
GROUP BY c.code_region
ORDER BY taux_validite_pct DESC;
```

## 🎯 Cas d'usage métier

### 1. Surveillance des nappes en période de sécheresse

```sql
-- Nappes avec niveaux critiques
WITH niveaux_actuels AS (
    SELECT 
        sm.station_code,
        sm.masse_eau_code,
        AVG(m.value) as niveau_actuel,
        AVG(m_hist.value) as niveau_historique
    FROM station_meta sm
    JOIN measure m ON sm.station_code = m.station_code
    JOIN measure m_hist ON sm.station_code = m_hist.station_code
    WHERE m.theme = 'piezo' 
    AND m.ts >= NOW() - INTERVAL '7 days'
    AND m_hist.theme = 'piezo'
    AND m_hist.ts >= NOW() - INTERVAL '1 year'
    AND m_hist.ts < NOW() - INTERVAL '30 days'
    GROUP BY sm.station_code, sm.masse_eau_code
)
SELECT 
    masse_eau_code,
    COUNT(*) as nb_stations,
    AVG(niveau_actuel - niveau_historique) as baisse_moyenne,
    MIN(niveau_actuel - niveau_historique) as baisse_max
FROM niveaux_actuels
WHERE (niveau_actuel - niveau_historique) < -1.0  -- Baisse > 1m
GROUP BY masse_eau_code
ORDER BY baisse_moyenne ASC;
```

### 2. Impact des prélèvements sur les nappes

```cypher
// Stations piézométriques impactées par des prélèvements
MATCH (s:Station {type: 'piezo'})-[r:AFFECTS]-(p:Prelevement)
WHERE p.pressure_level IN ['high_pressure', 'moderate_pressure']
RETURN s.code, s.label, s.masse_eau_code, 
       p.total_volume_m3, p.pressure_level,
       s.avg_piezo_level
ORDER BY p.total_volume_m3 DESC;
```

### 3. Corrélations climatiques

```sql
-- Corrélation entre température et niveaux piézométriques
WITH temp_monthly AS (
    SELECT 
        station_code,
        DATE_TRUNC('month', ts) as month,
        AVG(value) as temp_moyenne
    FROM measure 
    WHERE theme = 'temperature'
    AND ts >= NOW() - INTERVAL '2 years'
    GROUP BY station_code, month
),
piezo_monthly AS (
    SELECT 
        station_code,
        DATE_TRUNC('month', ts) as month,
        AVG(value) as niveau_moyen
    FROM measure 
    WHERE theme = 'piezo'
    AND ts >= NOW() - INTERVAL '2 years'
    GROUP BY station_code, month
)
SELECT 
    p.station_code,
    corr(t.temp_moyenne, p.niveau_moyen) as correlation_temp_piezo
FROM temp_monthly t
JOIN piezo_monthly p ON t.station_code = p.station_code AND t.month = p.month
GROUP BY p.station_code
HAVING corr(t.temp_moyenne, p.niveau_moyen) IS NOT NULL
ORDER BY ABS(corr(t.temp_moyenne, p.niveau_moyen)) DESC;
```

Ces exemples montrent la puissance de la plateforme pour des analyses complexes combinant données temporelles, géospatiales et relationnelles.
