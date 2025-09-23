# 📚 Guide des Backfills Hub'Eau

## 🎯 Vue d'ensemble

Ce guide explique comment effectuer des backfills efficaces sur le pipeline Hub'Eau, avec des exemples concrets et des bonnes pratiques.

## 🚀 Commandes de backfill

### 1. Backfill complet (toutes les données)

```bash
# Backfill sur une année complète (2024)
dagster asset materialize \
  --select "piezo_raw,piezo_timescale,hydro_raw,hydro_timescale,temp_raw,temp_timescale,quality_raw,quality_timescale,quality_groundwater_raw,quality_groundwater_timescale" \
  --start 2024-01-01 \
  --end 2024-12-31

# Backfill sur une plage personnalisée
dagster asset materialize \
  --select "piezo_raw,piezo_timescale,hydro_raw,hydro_timescale" \
  --start 2023-06-01 \
  --end 2023-08-31
```

### 2. Backfill par source de données

```bash
# Piézométrie uniquement
dagster asset materialize \
  --select "piezo_raw,piezo_timescale" \
  --start 2024-01-01 \
  --end 2024-12-31

# Hydrométrie uniquement
dagster asset materialize \
  --select "hydro_raw,hydro_timescale" \
  --start 2024-01-01 \
  --end 2024-12-31

# Qualité v2 uniquement
dagster asset materialize \
  --select "quality_raw,quality_timescale,quality_groundwater_raw,quality_groundwater_timescale" \
  --start 2024-01-01 \
  --end 2024-12-31
```

### 3. Backfill des métadonnées

```bash
# Synchronisation des métadonnées des stations
dagster asset materialize \
  --select "station_meta_sync" \
  --tags "force_refresh=true"

# Thésaurus Sandre
dagster asset materialize \
  --select "sandre_params_raw,sandre_params_pg,sandre_units_raw,sandre_units_pg"
```

### 4. Backfill des analyses graphe

```bash
# Relations et corrélations
dagster asset materialize \
  --select "stations_graph,proximity_relations,graph_params,graph_station_has_param,graph_quality_correlations" \
  --tags "force_recompute=true"
```

## 📊 Monitoring des backfills

### 1. Vérification des volumes de données

```sql
-- Vérification des données ingérées par jour
SELECT 
    DATE(ts) as jour,
    theme,
    COUNT(*) as nb_mesures,
    COUNT(DISTINCT station_code) as nb_stations
FROM measure 
WHERE ts >= '2024-01-01'
GROUP BY DATE(ts), theme
ORDER BY jour DESC, theme;

-- Vérification des données qualité
SELECT 
    DATE(ts) as jour,
    COUNT(*) as nb_mesures,
    COUNT(DISTINCT station_code) as nb_stations,
    COUNT(DISTINCT param_code) as nb_parametres
FROM measure_quality 
WHERE ts >= '2024-01-01'
GROUP BY DATE(ts)
ORDER BY jour DESC;
```

### 2. Vérification de la qualité des données

```sql
-- Stations avec peu de données
SELECT 
    station_code,
    theme,
    COUNT(*) as nb_mesures,
    MIN(ts) as premiere_mesure,
    MAX(ts) as derniere_mesure
FROM measure 
WHERE ts >= '2024-01-01'
GROUP BY station_code, theme
HAVING COUNT(*) < 100
ORDER BY nb_mesures ASC;

-- Paramètres de qualité rares
SELECT 
    param_code,
    COUNT(*) as nb_mesures,
    COUNT(DISTINCT station_code) as nb_stations
FROM measure_quality 
WHERE ts >= '2024-01-01'
GROUP BY param_code
ORDER BY nb_mesures ASC;
```

## 🔧 Gestion des erreurs et retry

### 1. Backfill avec retry automatique

```bash
# Backfill avec retry sur erreurs
dagster asset materialize \
  --select "piezo_raw,piezo_timescale" \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --tags "retry_on_failure=true,max_retries=3"
```

### 2. Backfill par chunks (pour gros volumes)

```bash
# Backfill par mois pour éviter les timeouts
for month in 01 02 03 04 05 06 07 08 09 10 11 12; do
  dagster asset materialize \
    --select "piezo_raw,piezo_timescale,hydro_raw,hydro_timescale" \
    --start "2024-${month}-01" \
    --end "2024-${month}-31" \
    --tags "chunk=month_${month}"
done
```

### 3. Gestion des rate limits

```bash
# Backfill avec rate limiting respectueux
dagster asset materialize \
  --select "quality_raw,quality_timescale" \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --tags "rate_limit=true,delay_between_requests=0.5"
```

## 📈 Optimisation des performances

### 1. Backfill parallèle par région

```bash
# Backfill par région géographique (si partitionné)
dagster asset materialize \
  --select "piezo_raw,piezo_timescale" \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --tags "region=north"

dagster asset materialize \
  --select "piezo_raw,piezo_timescale" \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --tags "region=south"
```

### 2. Backfill sélectif par type de station

```bash
# Backfill uniquement les stations prioritaires
dagster asset materialize \
  --select "piezo_raw,piezo_timescale" \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --tags "station_type=priority,network=BRGM"
```

## 🚨 Dépannage

### 1. Problèmes courants

**Erreur 429 (Rate Limit)**
```bash
# Solution : Augmenter les délais
export HUBEAU_RATE_LIMIT_DELAY=1.0
dagster asset materialize --select "piezo_raw" --start 2024-01-01 --end 2024-01-31
```

**Timeout sur gros volumes**
```bash
# Solution : Réduire la taille des chunks
dagster asset materialize \
  --select "piezo_raw,piezo_timescale" \
  --start 2024-01-01 \
  --end 2024-01-15 \
  --tags "chunk_size=small"
```

**Données manquantes**
```bash
# Solution : Vérifier les logs et relancer
dagster asset materialize \
  --select "piezo_raw" \
  --start 2024-01-15 \
  --end 2024-01-15 \
  --tags "debug=true,verbose_logging=true"
```

### 2. Validation des backfills

```sql
-- Validation complète des données
WITH daily_counts AS (
    SELECT 
        DATE(ts) as jour,
        theme,
        COUNT(*) as nb_mesures,
        COUNT(DISTINCT station_code) as nb_stations
    FROM measure 
    WHERE ts >= '2024-01-01' AND ts < '2025-01-01'
    GROUP BY DATE(ts), theme
)
SELECT 
    theme,
    COUNT(*) as nb_jours_avec_donnees,
    AVG(nb_mesures) as moyenne_mesures_par_jour,
    AVG(nb_stations) as moyenne_stations_par_jour
FROM daily_counts
GROUP BY theme
ORDER BY theme;
```

## 📋 Checklist de backfill

### Avant le backfill
- [ ] Vérifier l'espace disque disponible
- [ ] S'assurer que les services sont opérationnels
- [ ] Configurer les logs de debug si nécessaire
- [ ] Planifier les créneaux horaires (éviter les heures de pointe)

### Pendant le backfill
- [ ] Monitorer les logs Dagster
- [ ] Vérifier les métriques de performance
- [ ] Surveiller l'utilisation des ressources
- [ ] Contrôler les rate limits Hub'Eau

### Après le backfill
- [ ] Valider les volumes de données ingérées
- [ ] Vérifier la qualité des données
- [ ] Tester quelques requêtes de validation
- [ ] Mettre à jour la documentation si nécessaire

## 🎯 Exemples de backfills typiques

### 1. Remise à niveau complète (annuelle)
```bash
# Backfill complet d'une année
./scripts/backfill_year.sh 2024
```

### 2. Rattrapage mensuel
```bash
# Backfill du mois précédent
./scripts/backfill_month.sh $(date -d "last month" +%Y-%m)
```

### 3. Correction ponctuelle
```bash
# Backfill d'une journée spécifique
./scripts/backfill_day.sh 2024-03-15
```

## 📊 Métriques de succès

Un backfill réussi doit respecter ces seuils :

- **Couverture temporelle** : > 95% des jours avec données
- **Volume de données** : > 80% du volume attendu
- **Qualité** : < 5% de données invalides
- **Performance** : < 24h pour une année complète

---

**Note** : Ce guide est évolutif et sera mis à jour selon les retours d'expérience et les nouvelles fonctionnalités.
