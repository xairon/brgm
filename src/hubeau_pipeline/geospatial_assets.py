"""
Assets Dagster pour les relations inter-sources et analyses géospatiales
Calculs de proximité, corrélations, et relations métier
"""

import json
import datetime as dt
import pandas as pd
from typing import Dict, Any, List, Optional
from dagster import (
    AssetExecutionContext, 
    asset, 
    define_asset_job, 
    ScheduleDefinition, 
    get_dagster_logger,
    AssetMaterialization,
    MetadataValue
)


# ---------- Assets pour les relations inter-sources ----------

@asset(
    group_name="graph_gold",
    description="Calcul des relations de proximité entre toutes les stations"
)
def all_stations_proximity(context: AssetExecutionContext, pg, neo4j):
    """Calcul des relations de proximité entre toutes les stations (tous types)"""
    log = get_dagster_logger()
    
    # Récupération de toutes les stations depuis TimescaleDB
    with pg.cursor() as cur:
        cur.execute("""
            SELECT 
                station_code, label, type, 
                ST_Y(ST_AsText(geom::geometry)) AS lat,
                ST_X(ST_AsText(geom::geometry)) AS lon,
                masse_eau_code, insee
            FROM station_meta
            WHERE geom IS NOT NULL
        """)
        stations = cur.fetchall()
    
    log.info(f"Calculating proximity relations for {len(stations)} stations")
    
    # Calcul des distances et création des relations dans Neo4j
    with neo4j.session() as sess:
        relations_created = 0
        
        for i, station1 in enumerate(stations):
            for j, station2 in enumerate(stations):
                if i >= j:  # Éviter les doublons
                    continue
                
                # Calcul de la distance géographique (formule de Haversine simplifiée)
                lat1, lon1 = float(station1[3]), float(station1[4])
                lat2, lon2 = float(station2[3]), float(station2[4])
                
                # Distance en km (approximation)
                import math
                R = 6371  # Rayon de la Terre en km
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = (math.sin(dlat/2) * math.sin(dlat/2) + 
                     math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
                     math.sin(dlon/2) * math.sin(dlon/2))
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                distance_km = R * c
                
                # Création de la relation si distance < 50km
                if distance_km <= 50.0:
                    cypher = """
                    MATCH (s1:Station {code: $code1})
                    MATCH (s2:Station {code: $code2})
                    MERGE (s1)-[r:NEAR]-(s2)
                    SET r.distance_km = $distance,
                        r.station1_type = $type1,
                        r.station2_type = $type2,
                        r.created_at = datetime()
                    RETURN r
                    """
                    
                    sess.run(cypher, {
                        "code1": station1[0],
                        "code2": station2[0],
                        "distance": distance_km,
                        "type1": station1[2],
                        "type2": station2[2]
                    })
                    relations_created += 1
    
    log.info(f"Created {relations_created} proximity relations")
    
    return {"proximity_relations": relations_created}


@asset(
    group_name="graph_gold",
    description="Calcul des corrélations entre stations de même type"
)
def station_correlations(context: AssetExecutionContext, pg, neo4j):
    """Calcul des corrélations entre stations de même type sur 90 jours"""
    log = get_dagster_logger()
    
    # Types de stations à analyser
    station_types = ["piezo", "hydro", "temperature"]
    correlations_created = 0
    
    with neo4j.session() as sess:
        for station_type in station_types:
            log.info(f"Calculating correlations for {station_type} stations")
            
            # Récupération des stations de ce type depuis TimescaleDB
            with pg.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT station_code
                    FROM measure 
                    WHERE theme = %s
                    AND ts >= NOW() - INTERVAL '90 days'
                """, (station_type,))
                stations = [row[0] for row in cur.fetchall()]
            
            log.info(f"Found {len(stations)} {station_type} stations with recent data")
            
            # Calcul des corrélations par paires
            for i, station1 in enumerate(stations):
                for j, station2 in enumerate(stations):
                    if i >= j:
                        continue
                    
                    # Calcul de la corrélation depuis TimescaleDB
                    with pg.cursor() as cur:
                        cur.execute("""
                            SELECT corr(m1.value, m2.value) as correlation
                            FROM measure m1
                            JOIN measure m2 ON m1.ts = m2.ts
                            WHERE m1.station_code = %s 
                            AND m2.station_code = %s
                            AND m1.theme = %s AND m2.theme = %s
                            AND m1.ts >= NOW() - INTERVAL '90 days'
                            AND m1.value IS NOT NULL 
                            AND m2.value IS NOT NULL
                        """, (station1, station2, station_type, station_type))
                        
                        result = cur.fetchone()
                        if result and result[0] is not None:
                            correlation = float(result[0])
                            
                            # Création de la relation si corrélation > 0.7
                            if abs(correlation) > 0.7:
                                cypher = """
                                MATCH (s1:Station {code: $code1})
                                MATCH (s2:Station {code: $code2})
                                MERGE (s1)-[r:CORRELATED]-(s2)
                                SET r.rho = $correlation,
                                    r.window_days = 90,
                                    r.station_type = $type,
                                    r.created_at = datetime()
                                """
                                
                                sess.run(cypher, {
                                    "code1": station1,
                                    "code2": station2,
                                    "correlation": correlation,
                                    "type": station_type
                                })
                                correlations_created += 1
    
    log.info(f"Created {correlations_created} correlation relations")
    
    return {"correlation_relations": correlations_created}


@asset(
    group_name="graph_gold",
    description="Relations entre stations et cours d'eau (hydrométrie)"
)
def station_river_relations(context: AssetExecutionContext, pg, neo4j):
    """Création des relations entre stations piézométriques et cours d'eau"""
    log = get_dagster_logger()
    
    with neo4j.session() as sess:
        # Requête pour trouver les stations piézo proches des stations hydro
        cypher = """
        MATCH (piezo:Station {type: 'piezo'})-[near:NEAR]-(hydro:Station {type: 'hydro'})
        WHERE near.distance_km <= 10.0
        MERGE (piezo)-[r:NEAR_RIVER]->(hydro)
        SET r.distance_km = near.distance_km,
            r.relation_type = 'piezo_hydro_proximity',
            r.created_at = datetime()
        RETURN count(r) as relations_created
        """
        
        result = sess.run(cypher)
        relations_created = result.single()["relations_created"]
    
    log.info(f"Created {relations_created} station-river relations")
    
    return {"station_river_relations": relations_created}


@asset(
    group_name="graph_gold",
    description="Relations entre prélèvements et stations piézométriques"
)
def withdrawal_station_relations(context: AssetExecutionContext, pg, neo4j):
    """Création des relations entre prélèvements et stations piézométriques"""
    log = get_dagster_logger()
    
    with pg.cursor() as cur:
        # Récupération des prélèvements par commune
        cur.execute("""
            SELECT 
                commune_code,
                SUM(volume_preleve) as total_volume,
                COUNT(*) as nb_prelevements
            FROM (
                SELECT 
                    COALESCE(code_commune_insee, code_commune) as commune_code,
                    volume_preleve
                FROM prelevements_summary
                WHERE date_prelevement >= NOW() - INTERVAL '1 year'
            ) prelevements
            GROUP BY commune_code
            HAVING SUM(volume_preleve) > 0
        """)
        prelevements = cur.fetchall()
    
    relations_created = 0
    
    with neo4j.session() as sess:
        for commune_code, total_volume, nb_prelevements in prelevements:
            # Trouver les stations piézométriques dans cette commune
            cypher = """
            MATCH (s:Station {type: 'piezo'})-[:IN_COMMUNE]->(c:Commune {insee: $commune_code})
            MERGE (p:Prelevement {commune: $commune_code})
            SET p.total_volume_m3 = $volume,
                p.nb_prelevements = $count,
                p.updated_at = datetime()
            MERGE (p)-[r:AFFECTS]->(s)
            SET r.relation_type = 'withdrawal_pressure',
                r.created_at = datetime()
            RETURN count(r) as relations_created
            """
            
            result = sess.run(cypher, {
                "commune_code": commune_code,
                "volume": float(total_volume),
                "count": nb_prelevements
            })
            
            relations_created += result.single()["relations_created"]
    
    log.info(f"Created {relations_created} withdrawal-station relations")
    
    return {"withdrawal_relations": relations_created}


# ---------- Assets pour les analyses géospatiales avancées ----------

@asset(
    group_name="graph_gold",
    description="Analyse des bassins versants et relations hydrologiques"
)
def watershed_analysis(context: AssetExecutionContext, pg, neo4j):
    """Analyse des relations hydrologiques entre stations"""
    log = get_dagster_logger()
    
    with pg.cursor() as cur:
        # Requête PostGIS pour les analyses spatiales
        cur.execute("""
            WITH station_pairs AS (
                SELECT 
                    s1.station_code as station1,
                    s2.station_code as station2,
                    s1.type as type1,
                    s2.type as type2,
                    ST_Distance(s1.geom, s2.geom) as distance_m,
                    ST_Distance(s1.geom, s2.geom) / 1000.0 as distance_km,
                    s1.masse_eau_code = s2.masse_eau_code as same_aquifer
                FROM station_meta s1
                CROSS JOIN station_meta s2
                WHERE s1.station_code < s2.station_code
                AND s1.geom IS NOT NULL 
                AND s2.geom IS NOT NULL
                AND ST_DWithin(s1.geom, s2.geom, 50000)  -- 50km buffer
            )
            SELECT 
                station1, station2, type1, type2,
                distance_km, same_aquifer,
                CASE 
                    WHEN same_aquifer AND distance_km <= 10 THEN 'strong_hydrological_link'
                    WHEN same_aquifer AND distance_km <= 25 THEN 'moderate_hydrological_link'
                    WHEN distance_km <= 5 THEN 'spatial_proximity'
                    ELSE 'distant'
                END as relationship_type
            FROM station_pairs
            WHERE distance_km <= 50
            ORDER BY distance_km
        """)
        
        spatial_relations = cur.fetchall()
    
    log.info(f"Found {len(spatial_relations)} spatial relationships")
    
    # Synchronisation vers Neo4j
    with neo4j.session() as sess:
        relations_created = 0
        
        for relation in spatial_relations:
            station1, station2, type1, type2, distance_km, same_aquifer, relationship_type = relation
            
            if relationship_type != 'distant':
                cypher = """
                MATCH (s1:Station {code: $code1})
                MATCH (s2:Station {code: $code2})
                MERGE (s1)-[r:HYDROLOGICAL_RELATION]-(s2)
                SET r.distance_km = $distance,
                    r.relationship_type = $rel_type,
                    r.same_aquifer = $same_aquifer,
                    r.station1_type = $type1,
                    r.station2_type = $type2,
                    r.created_at = datetime()
                """
                
                sess.run(cypher, {
                    "code1": station1,
                    "code2": station2,
                    "distance": float(distance_km),
                    "rel_type": relationship_type,
                    "same_aquifer": same_aquifer,
                    "type1": type1,
                    "type2": type2
                })
                relations_created += 1
    
    log.info(f"Created {relations_created} hydrological relations")
    
    return {"hydrological_relations": relations_created}


@asset(
    group_name="graph_gold",
    description="Analyse des impacts anthropiques (prélèvements, pollutions)"
)
def anthropogenic_impact_analysis(context: AssetExecutionContext, pg, neo4j):
    """Analyse des impacts anthropiques sur les ressources en eau"""
    log = get_dagster_logger()
    
    with pg.cursor() as cur:
        # Analyse des corrélations entre prélèvements et niveaux piézométriques
        cur.execute("""
            WITH monthly_data AS (
                SELECT 
                    DATE_TRUNC('month', ts) as month,
                    station_code,
                    AVG(value) as avg_level
                FROM measure 
                WHERE theme = 'piezo'
                AND ts >= NOW() - INTERVAL '2 years'
                GROUP BY DATE_TRUNC('month', ts), station_code
            ),
            withdrawal_impact AS (
                SELECT 
                    s.station_code,
                    s.insee,
                    COUNT(p.id) as nb_prelevements,
                    SUM(p.volume_preleve) as total_volume,
                    AVG(md.avg_level) as avg_piezo_level
                FROM station_meta s
                LEFT JOIN prelevements_summary p ON s.insee = p.code_commune
                LEFT JOIN monthly_data md ON s.station_code = md.station_code
                WHERE s.type = 'piezo'
                GROUP BY s.station_code, s.insee
            )
            SELECT 
                station_code,
                nb_prelevements,
                total_volume,
                avg_piezo_level,
                CASE 
                    WHEN total_volume > 100000 THEN 'high_pressure'
                    WHEN total_volume > 10000 THEN 'moderate_pressure'
                    WHEN total_volume > 0 THEN 'low_pressure'
                    ELSE 'no_pressure'
                END as pressure_level
            FROM withdrawal_impact
            WHERE total_volume > 0
        """)
        
        impact_data = cur.fetchall()
    
    # Synchronisation vers Neo4j
    with neo4j.session() as sess:
        impacts_created = 0
        
        for impact in impact_data:
            station_code, nb_prelevements, total_volume, avg_level, pressure_level = impact
            
            cypher = """
            MATCH (s:Station {code: $code})
            MERGE (i:Impact {type: 'anthropogenic'})
            SET i.nb_prelevements = $nb_prelevements,
                i.total_volume_m3 = $volume,
                i.avg_piezo_level = $level,
                i.pressure_level = $pressure,
                i.updated_at = datetime()
            MERGE (i)-[r:IMPACTS]->(s)
            SET r.impact_type = 'withdrawal_pressure',
                r.created_at = datetime()
            """
            
            sess.run(cypher, {
                "code": station_code,
                "nb_prelevements": nb_prelevements,
                "volume": float(total_volume) if total_volume else 0,
                "level": float(avg_level) if avg_level else None,
                "pressure": pressure_level
            })
            impacts_created += 1
    
    log.info(f"Created {impacts_created} anthropogenic impact relations")
    
    return {"anthropogenic_impacts": impacts_created}


# ---------- Asset pour la qualité des données et métadonnées ----------

@asset(
    group_name="graph_gold",
    description="Métadonnées de qualité et provenance des données"
)
def data_quality_metadata(context: AssetExecutionContext, pg, neo4j):
    """Création des métadonnées de qualité et provenance des données"""
    log = get_dagster_logger()
    
    with pg.cursor() as cur:
        # Statistiques de qualité par source
        cur.execute("""
            SELECT 
                source,
                theme,
                COUNT(*) as total_measurements,
                COUNT(CASE WHEN value IS NOT NULL THEN 1 END) as valid_measurements,
                COUNT(CASE WHEN quality IS NOT NULL THEN 1 END) as quality_flagged,
                MIN(ts) as first_measurement,
                MAX(ts) as last_measurement,
                AVG(value) as avg_value,
                STDDEV(value) as stddev_value
            FROM measure
            GROUP BY source, theme
            ORDER BY source, theme
        """)
        
        quality_stats = cur.fetchall()
    
    # Synchronisation vers Neo4j avec PROV-O
    with neo4j.session() as sess:
        metadata_created = 0
        
        for stats in quality_stats:
            source, theme, total, valid, quality_flagged, first_ts, last_ts, avg_val, stddev = stats
            
            # Calcul du taux de qualité
            quality_rate = (valid / total * 100) if total > 0 else 0
            
            cypher = """
            MERGE (ds:DataSource {name: $source, theme: $theme})
            SET ds.total_measurements = $total,
                ds.valid_measurements = $valid,
                ds.quality_rate_percent = $quality_rate,
                ds.quality_flagged_count = $quality_flagged,
                ds.first_measurement = datetime($first_ts),
                ds.last_measurement = datetime($last_ts),
                ds.avg_value = $avg_val,
                ds.stddev_value = $stddev,
                ds.updated_at = datetime()
            
            MERGE (a:Activity {type: 'data_ingestion', source: $source})
            SET a.theme = $theme,
                a.executed_at = datetime()
            
            MERGE (a)-[:GENERATED]->(ds)
            """
            
            sess.run(cypher, {
                "source": source,
                "theme": theme,
                "total": total,
                "valid": valid,
                "quality_rate": quality_rate,
                "quality_flagged": quality_flagged,
                "first_ts": first_ts.isoformat() if first_ts else None,
                "last_ts": last_ts.isoformat() if last_ts else None,
                "avg_val": float(avg_val) if avg_val else None,
                "stddev": float(stddev) if stddev else None
            })
            metadata_created += 1
    
    log.info(f"Created {metadata_created} data quality metadata entries")
    
    return {"quality_metadata": metadata_created}
