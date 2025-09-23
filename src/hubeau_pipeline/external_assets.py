"""
Assets Dagster pour les sources externes et ontologies
BDLISA, Sandre, InfoTerre, CarMen, Météo-France, etc.
"""

import io
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


# ---------- Assets pour les sources externes ----------

@asset(
    group_name="external_bronze",
    description="Import des ontologies RDF (SOSA/SSN, GeoSPARQL, QUDT, PROV-O)"
)
def ontologies_rdf(context: AssetExecutionContext, neo4j):
    """Import des ontologies RDF dans Neo4j via n10s"""
    log = get_dagster_logger()
    
    ontologies = [
        {
            "name": "SOSA/SSN",
            "url": "https://www.w3.org/ns/sosa",
            "format": "Turtle",
            "description": "Ontologie pour les capteurs et observations"
        },
        {
            "name": "GeoSPARQL",
            "url": "https://www.opengis.net/ont/geosparql#",
            "format": "RDF/XML",
            "description": "Ontologie géospatiale OGC"
        },
        {
            "name": "QUDT",
            "url": "https://qudt.org/vocab/unit/",
            "format": "Turtle",
            "description": "Vocabulaire des quantités et unités"
        },
        {
            "name": "PROV-O",
            "url": "https://www.w3.org/ns/prov-o",
            "format": "RDF/XML",
            "description": "Ontologie de provenance"
        }
    ]
    
    imported_count = 0
    
    with neo4j.session() as sess:
        for ontology in ontologies:
            try:
                log.info(f"Importing ontology: {ontology['name']}")
                
                # Import via n10s
                cypher = f"""
                CALL n10s.rdf.import.fetch(
                    '{ontology['url']}', 
                    '{ontology['format']}',
                    {{
                        handleVocabUris: 'SHORTEN',
                        handleMultival: 'ARRAY',
                        handleRDFTypes: 'LABELS_AND_NODES'
                    }}
                ) YIELD triplesLoaded, triplesParsed, namespaces
                RETURN triplesLoaded, triplesParsed, namespaces
                """
                
                result = sess.run(cypher)
                summary = result.single()
                
                if summary:
                    log.info(f"Successfully imported {ontology['name']}: "
                           f"{summary['triplesLoaded']} triples loaded")
                    imported_count += 1
                else:
                    log.warning(f"Failed to import {ontology['name']}")
                    
            except Exception as e:
                log.error(f"Error importing {ontology['name']}: {e}")
    
    log.info(f"Imported {imported_count}/{len(ontologies)} ontologies")
    
    return {
        "ontologies_imported": imported_count,
        "total_ontologies": len(ontologies)
    }


@asset(
    group_name="external_bronze",
    description="Import des nomenclatures Sandre"
)
def sandre_nomenclatures(context: AssetExecutionContext, http_client, s3):
    """Import des nomenclatures Sandre pour l'eau"""
    log = get_dagster_logger()
    
    sandre_endpoints = [
        {
            "name": "parametres",
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/par.json",
            "description": "Paramètres de mesure"
        },
        {
            "name": "unites",
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/uni.json",
            "description": "Unités de mesure"
        },
        {
            "name": "methodes",
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/met.json",
            "description": "Méthodes d'analyse"
        },
        {
            "name": "fractions",
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/fra.json",
            "description": "Fractions analysées"
        },
        {
            "name": "support",
            "url": "https://api.sandre.eaufrance.fr/referentiels/v1/sup.json",
            "description": "Supports d'analyse"
        }
    ]
    
    imported_data = {}
    
    for endpoint in sandre_endpoints:
        try:
            log.info(f"Fetching Sandre data: {endpoint['name']}")
            
            response = http_client.get(endpoint["url"])
            response.raise_for_status()
            data = response.json()
            
            # Sauvegarde dans MinIO
            key = f"sandre/{endpoint['name']}/{dt.date.today().isoformat()}.json"
            s3["client"].put_object(
                Bucket=s3["bucket"],
                Key=key,
                Body=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                ContentType="application/json"
            )
            
            imported_data[endpoint["name"]] = {
                "count": len(data.get("data", [])),
                "key": key
            }
            
            log.info(f"Saved {endpoint['name']}: {len(data.get('data', []))} items")
            
        except Exception as e:
            log.error(f"Error fetching Sandre {endpoint['name']}: {e}")
            imported_data[endpoint["name"]] = {"count": 0, "key": None}
    
    return imported_data


@asset(
    group_name="external_bronze",
    description="Import des données BDLISA (masses d'eau souterraine)"
)
def bdlisa_masses_eau(context: AssetExecutionContext, http_client, s3):
    """Import des données BDLISA depuis les services WFS"""
    log = get_dagster_logger()
    
    # Endpoints BDLISA WFS
    bdlisa_endpoints = [
        {
            "name": "niveau1",
            "url": "https://bdlisa.eaufrance.fr/geoserver/bdlisa/wfs",
            "typename": "bdlisa:niveau1",
            "description": "Niveau 1 - Systèmes aquifères"
        },
        {
            "name": "niveau2", 
            "url": "https://bdlisa.eaufrance.fr/geoserver/bdlisa/wfs",
            "typename": "bdlisa:niveau2",
            "description": "Niveau 2 - Entités hydrogéologiques"
        },
        {
            "name": "niveau3",
            "url": "https://bdlisa.eaufrance.fr/geoserver/bdlisa/wfs", 
            "typename": "bdlisa:niveau3",
            "description": "Niveau 3 - Masses d'eau"
        }
    ]
    
    imported_data = {}
    
    for endpoint in bdlisa_endpoints:
        try:
            log.info(f"Fetching BDLISA data: {endpoint['name']}")
            
            # Requête WFS GetFeature
            params = {
                "service": "WFS",
                "version": "1.1.0",
                "request": "GetFeature",
                "typeName": endpoint["typename"],
                "outputFormat": "application/json"
            }
            
            response = http_client.get(endpoint["url"], params=params)
            response.raise_for_status()
            data = response.json()
            
            # Sauvegarde dans MinIO
            key = f"bdlisa/{endpoint['name']}/{dt.date.today().isoformat()}.geojson"
            s3["client"].put_object(
                Bucket=s3["bucket"],
                Key=key,
                Body=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                ContentType="application/geo+json"
            )
            
            feature_count = len(data.get("features", []))
            imported_data[endpoint["name"]] = {
                "count": feature_count,
                "key": key
            }
            
            log.info(f"Saved BDLISA {endpoint['name']}: {feature_count} features")
            
        except Exception as e:
            log.error(f"Error fetching BDLISA {endpoint['name']}: {e}")
            imported_data[endpoint["name"]] = {"count": 0, "key": None}
    
    return imported_data


@asset(
    group_name="external_bronze",
    description="Import des données InfoTerre (forages et géologie)"
)
def infoterre_forages(context: AssetExecutionContext, http_client, s3):
    """Import des données InfoTerre pour les forages et géologie"""
    log = get_dagster_logger()
    
    infoterre_endpoints = [
        {
            "name": "forages_bss",
            "url": "https://inspire.brgm.fr/geoserver/bss/wfs",
            "typename": "bss:Forage",
            "description": "Forages BSS"
        },
        {
            "name": "geologie_1_50k",
            "url": "https://inspire.brgm.fr/geoserver/geologie/wfs",
            "typename": "geologie:Geologie_1_50k",
            "description": "Cartes géologiques 1:50 000"
        }
    ]
    
    imported_data = {}
    
    for endpoint in infoterre_endpoints:
        try:
            log.info(f"Fetching InfoTerre data: {endpoint['name']}")
            
            params = {
                "service": "WFS",
                "version": "1.1.0",
                "request": "GetFeature",
                "typeName": endpoint["typename"],
                "outputFormat": "application/json",
                "maxFeatures": 10000  # Limite pour éviter les timeouts
            }
            
            response = http_client.get(endpoint["url"], params=params)
            response.raise_for_status()
            data = response.json()
            
            # Sauvegarde dans MinIO
            key = f"infoterre/{endpoint['name']}/{dt.date.today().isoformat()}.geojson"
            s3["client"].put_object(
                Bucket=s3["bucket"],
                Key=key,
                Body=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                ContentType="application/geo+json"
            )
            
            feature_count = len(data.get("features", []))
            imported_data[endpoint["name"]] = {
                "count": feature_count,
                "key": key
            }
            
            log.info(f"Saved InfoTerre {endpoint['name']}: {feature_count} features")
            
        except Exception as e:
            log.error(f"Error fetching InfoTerre {endpoint['name']}: {e}")
            imported_data[endpoint["name"]] = {"count": 0, "key": None}
    
    return imported_data


@asset(
    group_name="external_bronze",
    description="Import des données CarMen (chimie agrégée)"
)
def carmen_chimie(context: AssetExecutionContext, http_client, s3):
    """Import des données CarMen pour la chimie agrégée"""
    log = get_dagster_logger()
    
    carmen_endpoints = [
        {
            "name": "chimie_nappes",
            "url": "https://services.carmen.developpement-durable.gouv.fr/exws/services/rest/DataDownload/export",
            "params": {
                "service": "DataDownload",
                "version": "2.0",
                "request": "GetData",
                "type": "nappes",
                "format": "json"
            },
            "description": "Données chimiques nappes phréatiques"
        },
        {
            "name": "chimie_rivieres",
            "url": "https://services.carmen.developpement-durable.gouv.fr/exws/services/rest/DataDownload/export",
            "params": {
                "service": "DataDownload",
                "version": "2.0",
                "request": "GetData", 
                "type": "rivieres",
                "format": "json"
            },
            "description": "Données chimiques rivières"
        }
    ]
    
    imported_data = {}
    
    for endpoint in carmen_endpoints:
        try:
            log.info(f"Fetching CarMen data: {endpoint['name']}")
            
            response = http_client.get(endpoint["url"], params=endpoint["params"])
            response.raise_for_status()
            data = response.json()
            
            # Sauvegarde dans MinIO
            key = f"carmen/{endpoint['name']}/{dt.date.today().isoformat()}.json"
            s3["client"].put_object(
                Bucket=s3["bucket"],
                Key=key,
                Body=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                ContentType="application/json"
            )
            
            record_count = len(data.get("data", []))
            imported_data[endpoint["name"]] = {
                "count": record_count,
                "key": key
            }
            
            log.info(f"Saved CarMen {endpoint['name']}: {record_count} records")
            
        except Exception as e:
            log.error(f"Error fetching CarMen {endpoint['name']}: {e}")
            imported_data[endpoint["name"]] = {"count": 0, "key": None}
    
    return imported_data


@asset(
    group_name="external_bronze",
    description="Import des données Météo-France SAFRAN"
)
def meteo_france_safran(context: AssetExecutionContext, http_client, s3):
    """Import des données Météo-France SAFRAN (pluie, température, ETP)"""
    log = get_dagster_logger()
    
    # Note: SAFRAN nécessite une authentification et un accès spécial
    # Ceci est un exemple de structure pour l'intégration future
    
    safran_variables = [
        {
            "name": "precipitation",
            "description": "Précipitations (mm)"
        },
        {
            "name": "temperature",
            "description": "Température (°C)"
        },
        {
            "name": "etp",
            "description": "Évapotranspiration potentielle (mm)"
        }
    ]
    
    log.info("SAFRAN integration structure prepared (requires special access)")
    
    return {
        "status": "prepared",
        "variables": len(safran_variables),
        "note": "Requires Météo-France partnership for actual data access"
    }


# ---------- Asset pour la synchronisation des ontologies vers Neo4j ----------

@asset(
    group_name="graph_gold",
    deps=[sandre_nomenclatures],
    description="Synchronisation des nomenclatures Sandre vers Neo4j"
)
def sandre_to_neo4j(context: AssetExecutionContext, s3, neo4j):
    """Synchronisation des nomenclatures Sandre vers le graphe Neo4j"""
    log = get_dagster_logger()
    
    # Récupération des données Sandre depuis MinIO
    sandre_data = {}
    
    try:
        # Import des paramètres
        param_key = f"sandre/parametres/{dt.date.today().isoformat()}.json"
        obj = s3["client"].get_object(Bucket=s3["bucket"], Key=param_key)
        param_data = json.loads(obj["Body"].read().decode('utf-8'))
        sandre_data["parametres"] = param_data.get("data", [])
        
        # Import des unités
        uni_key = f"sandre/unites/{dt.date.today().isoformat()}.json"
        obj = s3["client"].get_object(Bucket=s3["bucket"], Key=uni_key)
        uni_data = json.loads(obj["Body"].read().decode('utf-8'))
        sandre_data["unites"] = uni_data.get("data", [])
        
    except Exception as e:
        log.error(f"Error loading Sandre data from MinIO: {e}")
        return {"synced": 0}
    
    # Synchronisation vers Neo4j
    with neo4j.session() as sess:
        synced_count = 0
        
        # Import des paramètres
        for param in sandre_data["parametres"]:
            cypher = """
            MERGE (p:Parametre {code: $code})
            SET p.libelle = $libelle,
                p.description = $description,
                p.theme = $theme,
                p.unite = $unite,
                p.updated_at = datetime()
            """
            sess.run(cypher, {
                "code": param.get("CdParametre"),
                "libelle": param.get("NomParametre"),
                "description": param.get("DescriptionParametre"),
                "theme": param.get("ThemeParametre"),
                "unite": param.get("UniteParametre")
            })
            synced_count += 1
        
        # Import des unités
        for unite in sandre_data["unites"]:
            cypher = """
            MERGE (u:Unite {code: $code})
            SET u.libelle = $libelle,
                u.description = $description,
                u.symbole = $symbole,
                u.updated_at = datetime()
            """
            sess.run(cypher, {
                "code": unite.get("CdUniteMesure"),
                "libelle": unite.get("SymboleUniteMesure"),
                "description": unite.get("LblUniteMesure"),
                "symbole": unite.get("SymboleUniteMesure")
            })
            synced_count += 1
    
    log.info(f"Synchronized {synced_count} Sandre items to Neo4j")
    
    return {"synced": synced_count}


@asset(
    group_name="graph_gold", 
    deps=[bdlisa_masses_eau],
    description="Synchronisation des masses d'eau BDLISA vers Neo4j"
)
def bdlisa_to_neo4j(context: AssetExecutionContext, s3, neo4j):
    """Synchronisation des masses d'eau BDLISA vers le graphe Neo4j"""
    log = get_dagster_logger()
    
    synced_count = 0
    
    with neo4j.session() as sess:
        # Import des masses d'eau niveau 3 (le plus détaillé)
        try:
            bdlisa_key = f"bdlisa/niveau3/{dt.date.today().isoformat()}.geojson"
            obj = s3["client"].get_object(Bucket=s3["bucket"], Key=bdlisa_key)
            bdlisa_data = json.loads(obj["Body"].read().decode('utf-8'))
            
            for feature in bdlisa_data.get("features", []):
                props = feature.get("properties", {})
                geometry = feature.get("geometry")
                
                cypher = """
                MERGE (me:MasseEau {code: $code})
                SET me.libelle = $libelle,
                    me.niveau = $niveau,
                    me.type_masse = $type_masse,
                    me.aquifere = $aquifere,
                    me.geometry = $geometry,
                    me.updated_at = datetime()
                """
                
                sess.run(cypher, {
                    "code": props.get("CodeMasseDEau"),
                    "libelle": props.get("LibelleMasseDEau"),
                    "niveau": "N3",
                    "type_masse": props.get("TypeMasseDEau"),
                    "aquifere": props.get("NomAquifere"),
                    "geometry": json.dumps(geometry) if geometry else None
                })
                synced_count += 1
                
        except Exception as e:
            log.error(f"Error syncing BDLISA to Neo4j: {e}")
    
    log.info(f"Synchronized {synced_count} BDLISA masses d'eau to Neo4j")
    
    return {"synced": synced_count}
