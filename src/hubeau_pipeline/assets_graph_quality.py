"""
Assets Dagster pour les liens graphe qualité
Relations station-paramètre et analyses de corrélations
"""

from dagster import asset

@asset(
    group_name="graph_gold", 
    deps=["sandre_params_pg"],
    description="Création des nœuds Parametre dans le graphe Neo4j"
)
def graph_params(context, pg, neo4j):
    """Création des nœuds Parametre depuis le thésaurus Sandre"""
    with pg.cursor() as cur:
        cur.execute("SELECT code_param, label, unit, family FROM quality_param")
        params = cur.fetchall()
    
    cypher = """
        UNWIND $rows AS r
        MERGE (p:Parametre {code: r.code})
        SET p.label = r.label, 
            p.unit = r.unit,
            p.family = r.family,
            p.updated_at = datetime()
    """
    
    with neo4j.session() as sess:
        result = sess.run(cypher, rows=[{
            "code": r[0],
            "label": r[1], 
            "unit": r[2],
            "family": r[3]
        } for r in params])
        summary = result.consume()
    
    context.log.info(f"graph_params: {len(params)} paramètres créés dans Neo4j")
    
    return {"params": len(params)}

@asset(
    group_name="graph_gold", 
    deps=["quality_timescale", "graph_params"],
    description="Relations HAS_PARAM entre stations et paramètres"
)
def graph_station_has_param(context, pg, neo4j):
    """Création des relations HAS_PARAM entre stations et paramètres"""
    # Stations qui ont au moins une mesure de ce paramètre
    with pg.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT station_code, param_code
            FROM measure_quality
            WHERE station_code IS NOT NULL AND param_code IS NOT NULL
        """)
        pairs = cur.fetchall()
    
    if not pairs:
        return {"links": 0}
    
    cypher = """
        UNWIND $pairs AS r
        MATCH (s:Station {code: r.station})
        MATCH (p:Parametre {code: r.param})
        MERGE (s)-[:HAS_PARAM]->(p)
        SET p.updated_at = datetime()
    """
    
    with neo4j.session() as sess:
        result = sess.run(cypher, pairs=[{
            "station": r[0],
            "param": r[1]
        } for r in pairs])
        summary = result.consume()
    
    context.log.info(f"graph_station_has_param: {len(pairs)} relations HAS_PARAM créées")
    
    return {"links": len(pairs)}

@asset(
    group_name="graph_gold",
    deps=["quality_timescale"],
    description="Corrélations entre paramètres de qualité co-mesurés"
)
def graph_quality_correlations(context, pg, neo4j):
    """Calcul des corrélations entre paramètres de qualité"""
    with pg.cursor() as cur:
        # Paires de paramètres co-mesurés sur les mêmes stations
        cur.execute("""
            WITH param_pairs AS (
                SELECT DISTINCT 
                    m1.param_code as param1,
                    m2.param_code as param2,
                    m1.station_code
                FROM measure_quality m1
                JOIN measure_quality m2 ON m1.station_code = m2.station_code
                WHERE m1.param_code < m2.param_code
                AND m1.ts >= NOW() - INTERVAL '1 year'
                AND m2.ts >= NOW() - INTERVAL '1 year'
            )
            SELECT 
                param1, param2,
                COUNT(DISTINCT station_code) as nb_stations,
                AVG(
                    CASE WHEN m1.value IS NOT NULL AND m2.value IS NOT NULL 
                         THEN m1.value * m2.value 
                         ELSE NULL END
                ) as correlation_estimate
            FROM param_pairs pp
            JOIN measure_quality m1 ON pp.station_code = m1.station_code AND pp.param1 = m1.param_code
            JOIN measure_quality m2 ON pp.station_code = m2.station_code AND pp.param2 = m2.param_code
            WHERE m1.ts = m2.ts
            GROUP BY param1, param2
            HAVING COUNT(DISTINCT station_code) >= 3
            ORDER BY nb_stations DESC
        """)
        
        correlations = cur.fetchall()
    
    if not correlations:
        return {"correlations": 0}
    
    cypher = """
        UNWIND $correlations AS c
        MATCH (p1:Parametre {code: c.param1})
        MATCH (p2:Parametre {code: c.param2})
        MERGE (p1)-[r:CORRELATED_WITH]->(p2)
        SET r.nb_stations = c.nb_stations,
            r.correlation_estimate = c.correlation_estimate,
            r.created_at = datetime()
    """
    
    with neo4j.session() as sess:
        result = sess.run(cypher, correlations=[{
            "param1": r[0],
            "param2": r[1],
            "nb_stations": r[2],
            "correlation_estimate": float(r[3]) if r[3] else 0.0
        } for r in correlations])
        summary = result.consume()
    
    context.log.info(f"graph_quality_correlations: {len(correlations)} corrélations créées")
    
    return {"correlations": len(correlations)}

@asset(
    group_name="graph_gold",
    deps=["graph_station_has_param"],
    description="Analyse des profils de qualité par station"
)
def graph_quality_profiles(context, pg, neo4j):
    """Création des profils de qualité par station"""
    with pg.cursor() as cur:
        # Profils de qualité par station (paramètres mesurés)
        cur.execute("""
            SELECT 
                station_code,
                COUNT(DISTINCT param_code) as nb_parametres,
                COUNT(*) as nb_mesures,
                MIN(ts) as premiere_mesure,
                MAX(ts) as derniere_mesure,
                AVG(value) as valeur_moyenne
            FROM measure_quality
            WHERE ts >= NOW() - INTERVAL '2 years'
            GROUP BY station_code
            HAVING COUNT(DISTINCT param_code) >= 2
        """)
        
        profiles = cur.fetchall()
    
    if not profiles:
        return {"profiles": 0}
    
    cypher = """
        UNWIND $profiles AS p
        MATCH (s:Station {code: p.station_code})
        MERGE (s)-[:HAS_QUALITY_PROFILE]->(qp:QualityProfile)
        SET qp.nb_parametres = p.nb_parametres,
            qp.nb_mesures = p.nb_mesures,
            qp.valeur_moyenne = p.valeur_moyenne,
            qp.premiere_mesure = datetime(p.premiere_mesure),
            qp.derniere_mesure = datetime(p.derniere_mesure),
            qp.updated_at = datetime()
    """
    
    with neo4j.session() as sess:
        result = sess.run(cypher, profiles=[{
            "station_code": r[0],
            "nb_parametres": r[1],
            "nb_mesures": r[2],
            "premiere_mesure": r[3].isoformat() if r[3] else None,
            "derniere_mesure": r[4].isoformat() if r[4] else None,
            "valeur_moyenne": float(r[5]) if r[5] else None
        } for r in profiles])
        summary = result.consume()
    
    context.log.info(f"graph_quality_profiles: {len(profiles)} profils de qualité créés")
    
    return {"profiles": len(profiles)}
