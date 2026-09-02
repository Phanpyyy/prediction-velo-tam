# Prédiction Vélo Montpellier

Ce projet prend les données en temps réel sur les stations de vélos de Montpellier, les stocke dans Google BigQuery et les visualise sur un dashboard Power BI.

---

## Architecture

1. **Récupération des données :** Script Python ingest_data.py exécuté avec Cloud Run pour récupérer les données de l'API des vélos de Montpellier. (maj toutes les heures avec Cloud Schedule)
2. **Stockage Cloud :** Données stockées dans google BigQuery.
3. **Entraînement de notre modèle de prédictions et récupération du pipeline :** Script Python train.py. (exécution manuelle)
4. **Réalisation des prédictions :** Script Python run_predictions exécuté avec Cloud Run puis envoi de la table prédictions dans BigQuery. (maj toutes les heures avec Cloud Schedule)
5. **Visualisation :** Power BI - Récupération des données en mode **Import** et rafraîchissement des données 8 fois par jour (le max possible).

---

## Structure BigQuery (dataset `prediction_velo_raw`)
- `realtime` : relevés bruts des données en temps réel.
- `station_referentiel` : référentiel des stations (nom, lat/lon)
- `predictions` : prédictions brutes du modèle (sur 7 jours)
- `station_complet` (vue) : jointure realtime + référentiel
- `predictions_view` (vue) : jointure predictions + référentiel

---

## Modèle ML
Encore en cours de développement.

**Algorithme actuel** : Random Forest Regressor entraîné pour prédire le nombre de vélos disponibles (`availableBikeNumber`) par station et par heure.

**Features utilisées :**
- `station_id` (encodé via Target Encoding)
- `hour` 
- `dayOfWeek` 
- `isWeekend` 
- `isHolidays` 

**Méthodologie d'évaluation :**
- Validation croisée temporelle (`TimeSeriesSplit`, 5 folds) pour respecter la chronologie des données.
- Métriques suivies : MAE et RMSE.

**Pipeline** : le modèle final est ré-entraîné sur l'intégralité des données disponibles après validation.

**Améliorations futures envisagées :**
- Test d'autres modèles (par ex XGBoost)
- Optimisation des hyperparamètres (actuellement `random_state=42` par défaut, pas de recherche d'hyperparamètres)
- Ajout de features supplémentaires (météo)

---

## Visualisation Power BI
  - Cartographie interactive des stations.
  - Top 5 des stations avec le plus de vélos.
  - Nombre de vélos dispos global et par station.
  - Nombre de bornes disponibles et de stations actives.
  - Fréquentation dans la journée par station qui reprend les données en temps réel et les prédictions.

Lien vers la visualisation : https://app.powerbi.com/links/SGdx-gdNy9?ctid=67c313fc-3764-4c09-a4a1-81f35edcef53&pbi_source=linkShare 

