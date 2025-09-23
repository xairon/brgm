// Initialisation Neo4j pour Hub'Eau
// Contraintes et configuration

// Contraintes d'unicité (complètes selon bonnes pratiques)
CREATE CONSTRAINT station_code IF NOT EXISTS FOR (s:Station) REQUIRE s.code IS UNIQUE;
CREATE CONSTRAINT masse_eau_code IF NOT EXISTS FOR (m:MasseEau) REQUIRE m.code IS UNIQUE;
CREATE CONSTRAINT commune_insee IF NOT EXISTS FOR (c:Commune) REQUIRE c.insee IS UNIQUE;
CREATE CONSTRAINT parametre_code IF NOT EXISTS FOR (p:Parametre) REQUIRE p.code IS UNIQUE;
CREATE CONSTRAINT reseau_code IF NOT EXISTS FOR (r:Reseau) REQUIRE r.code IS UNIQUE;
CREATE CONSTRAINT unite_code IF NOT EXISTS FOR (u:Unite) REQUIRE u.code IS UNIQUE;
CREATE CONSTRAINT methode_code IF NOT EXISTS FOR (m:Methode) REQUIRE m.code IS UNIQUE;

// Configuration n10s pour les ontologies RDF
CALL n10s.graphconfig.init({ 
  handleVocabUris: "SHORTEN", 
  handleMultival: "ARRAY",
  handleRDFTypes: "LABELS_AND_NODES",
  keepCustomDataTypes: true,
  keepLangTag: true
});

// Index géospatial pour les coordonnées
CREATE INDEX station_geom IF NOT EXISTS FOR (s:Station) ON (s.lat, s.lon);

// Index pour les performances de requêtes
CREATE INDEX station_type IF NOT EXISTS FOR (s:Station) ON (s.type);
CREATE INDEX station_reseau IF NOT EXISTS FOR (s:Station) ON (s.reseau);
CREATE INDEX mesure_date IF NOT EXISTS FOR (m:Mesure) ON (m.date_mesure);

// Labels et propriétés de base pour les stations
// Les stations peuvent être de différents types : piézométriques, hydrométriques, etc.
MERGE (s:Station {code: "EXAMPLE"}) 
SET s.label = "Station exemple",
    s.type = "piezo",
    s.lat = 48.8566,
    s.lon = 2.3522,
    s.reseau = "BRGM",
    s.altitude_mngf = 35.0,
    s.profondeur_m = 15.0;

// Structure des masses d'eau (BDLISA)
MERGE (me:MasseEau {code: "EXAMPLE_ME"})
SET me.libelle = "Masse d'eau exemple",
    me.niveau = "N1",
    me.type_masse = "libre";

// Communes
MERGE (c:Commune {insee: "75056"})
SET c.nom = "Paris",
    c.code_departement = "75",
    c.code_region = "11";

// Relations de base
MATCH (s:Station {code: "EXAMPLE"})
MATCH (me:MasseEau {code: "EXAMPLE_ME"})
MATCH (c:Commune {insee: "75056"})
MERGE (s)-[:IN_MASSE]->(me)
MERGE (s)-[:IN_COMMUNE]->(c);

// Suppression de l'exemple
MATCH (s:Station {code: "EXAMPLE"}) DELETE s;
MATCH (me:MasseEau {code: "EXAMPLE_ME"}) DELETE me;

// Fonction pour calculer les distances géographiques
// (sera utilisée pour créer les relations NEAR)
CALL apoc.custom.asFunction(
  'geoDistance',
  'point1, point2',
  'RETURN point({latitude: point1.lat, longitude: point1.lon}) <-> point({latitude: point2.lat, longitude: point2.lon}) / 1000 AS distance_km',
  'DOUBLE',
  'Calcule la distance en km entre deux points géographiques'
);

// Procédure pour créer les relations de proximité entre stations
CALL apoc.custom.asProcedure(
  'createNearRelations',
  'distance_km',
  'PROCEDURE',
  'CALL apoc.periodic.iterate(
    "MATCH (s1:Station), (s2:Station) WHERE s1.code < s2.code RETURN s1, s2",
    "WITH s1, s2, custom.geoDistance(s1, s2) AS dist WHERE dist <= $distance_km MERGE (s1)-[:NEAR {distance_km: dist}]-(s2)",
    {batchSize: 100, iterateList: true, parallel: false, params: {distance_km: $distance_km}}
  )',
  'VOID',
  'Crée les relations NEAR entre stations dans un rayon donné'
);

// Procédure pour importer les ontologies Sandre (SKOS)
CALL apoc.custom.asProcedure(
  'importSOSA',
  '',
  'PROCEDURE',
  'CALL n10s.rdf.import.fetch("https://www.w3.org/ns/sosa", "Turtle")',
  'VOID',
  'Importe l\'ontologie SOSA/SSN pour les capteurs et observations'
);

// Labels pour les différentes sources de données
CREATE (:DataSource {name: "Hub'Eau Piézométrie", url: "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes", type: "piezo"});
CREATE (:DataSource {name: "Hub'Eau Hydrométrie", url: "https://hubeau.eaufrance.fr/api/v1/hydrometrie", type: "hydro"});
CREATE (:DataSource {name: "Hub'Eau Température", url: "https://hubeau.eaufrance.fr/api/v1/temperature", type: "temp"});
CREATE (:DataSource {name: "Hub'Eau Qualité", url: "https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface", type: "quality"});

// Structure pour les paramètres de qualité (Sandre)
CREATE (:Parametre {code: "1301", libelle: "Température de l'eau", unite: "°C", theme: "quality"});
CREATE (:Parametre {code: "1303", libelle: "pH", unite: "", theme: "quality"});
CREATE (:Parametre {code: "1340", libelle: "Oxygène dissous", unite: "mg/L", theme: "quality"});
CREATE (:Parametre {code: "1335", libelle: "Nitrates", unite: "mg/L", theme: "quality"});

// Relations pour lier les mesures aux paramètres
// (:Mesure)-[:MEASURES_PARAM]->(:Parametre)

// Structure pour les réseaux de mesure
CREATE (:Reseau {code: "BRGM", libelle: "Réseau piézométrique BRGM", type: "piezo"});
CREATE (:Reseau {code: "HYDRO", libelle: "Réseau hydrométrique", type: "hydro"});
CREATE (:Reseau {code: "QUALITE", libelle: "Réseau qualité eau", type: "quality"});
CREATE (:Reseau {code: "TEMP", libelle: "Réseau température", type: "temperature"});
CREATE (:Reseau {code: "ECOULEMENT", libelle: "Réseau écoulement", type: "ecoulement"});
CREATE (:Reseau {code: "HYDROBIO", libelle: "Réseau hydrobiologie", type: "hydrobiologie"});

// Relations pour lier les stations aux réseaux
// (:Station)-[:BELONGS_TO]->(:Reseau)

// Structure pour les impacts anthropiques
CREATE (:Impact {type: "anthropogenic", description: "Impact des activités humaines"});
CREATE (:Impact {type: "climatic", description: "Impact climatique"});
CREATE (:Impact {type: "hydrological", description: "Impact hydrologique"});

// Relations pour les impacts
// (:Impact)-[:IMPACTS]->(:Station)

// Structure pour les activités (PROV-O)
CREATE (:Activity {type: "data_ingestion", description: "Ingestion de données"});
CREATE (:Activity {type: "data_processing", description: "Traitement de données"});
CREATE (:Activity {type: "analysis", description: "Analyse des données"});

// Relations de provenance (PROV-O)
// (:Activity)-[:GENERATED]->(:DataSource)
// (:Activity)-[:USED]->(:DataSource)

// Structure pour les sources de données
CREATE (:DataSource {name: "Hub'Eau Piézométrie", url: "https://hubeau.eaufrance.fr/api/v1/niveaux_nappes", type: "piezo"});
CREATE (:DataSource {name: "Hub'Eau Hydrométrie", url: "https://hubeau.eaufrance.fr/api/v1/hydrometrie", type: "hydro"});
CREATE (:DataSource {name: "Hub'Eau Température", url: "https://hubeau.eaufrance.fr/api/v1/temperature", type: "temp"});
CREATE (:DataSource {name: "Hub'Eau Qualité", url: "https://hubeau.eaufrance.fr/api/v1/qualite_eau_surface", type: "quality"});
CREATE (:DataSource {name: "Sandre", url: "https://api.sandre.eaufrance.fr", type: "nomenclature"});
CREATE (:DataSource {name: "BDLISA", url: "https://bdlisa.eaufrance.fr", type: "hydrogeology"});
CREATE (:DataSource {name: "InfoTerre", url: "https://inspire.brgm.fr", type: "geology"});
CREATE (:DataSource {name: "CarMen", url: "https://services.carmen.developpement-durable.gouv.fr", type: "chemistry"});

// Structure pour les prélèvements
CREATE (:Prelevement {type: "withdrawal", description: "Prélèvement d'eau"});

// Relations pour les prélèvements
// (:Prelevement)-[:AFFECTS]->(:Station)

// Structure pour les relations hydrologiques
CREATE (:HydrologicalRelation {type: "upstream_downstream", description: "Relation amont-aval"});
CREATE (:HydrologicalRelation {type: "piezo_hydro", description: "Relation nappe-rivière"});
CREATE (:HydrologicalRelation {type: "aquifer_connection", description: "Connexion aquifère"});

// Relations hydrologiques
// (:Station)-[:HYDROLOGICAL_RELATION]->(:Station)

// Exemple de requête pour trouver les stations proches d'une masse d'eau
// MATCH (s:Station)-[:IN_MASSE]->(me:MasseEau {code: $masse_eau_code})
// MATCH (s)-[n:NEAR]-(s2:Station)
// WHERE n.distance_km <= $distance_km
// RETURN s.code, s2.code, n.distance_km
// ORDER BY n.distance_km;

// Exemple de requête pour les corrélations entre stations
// MATCH (s1:Station {code: $station1})-[c:CORRELATED]->(s2:Station)
// WHERE c.rho >= $min_correlation AND c.window = $window_days
// RETURN s2.code, c.rho, c.p_value
// ORDER BY c.rho DESC;
