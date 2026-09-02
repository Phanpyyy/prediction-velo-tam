import os
from google.cloud import bigquery
import pandas as pd
import requests
from datetime import datetime
from datetime import timezone

"""
A lancer une seule fois pour :
- initialiser la table realtime avec l'historique des données.
- créer la table station_referentiel.
"""


#Récupère l'historique des données
def load_historical_data_to_bigquery(project_id, dataset_id, table_id, force=False):
    client = bigquery.Client(project=project_id)
    table_full_path = f"{project_id}.{dataset_id}.{table_id}"

    # --- Vérifie si la table contient déjà des données ---
    if not force:
        try:
            table = client.get_table(table_full_path)
            if table.num_rows > 0:
                print(
                    f" Historique déjà chargé ({table.num_rows} lignes) — étape ignorée. "
                    f"Utilise force=True pour forcer le rechargement."
                )
                return None
        except Exception:
            # La table n'existe pas encore, on continue normalement
            pass

    url = (
        "https://portail-api-data.montpellier.fr/ngsi-ld/v1/temporal/entities"
        "?type=BikeHireDockingStation"
        "&format=temporalValues"
        "&timerel=after"
        "&timeAt=2025-12-31T23%3A59%3A59Z"
    )

    response = requests.get(url, timeout=15)

    if response.status_code in [200, 206]:
        entities = response.json()
        data_clean = []

        for entity in entities:
            full_id = entity.get("id", "")
            station_id = full_id.split(":")[-1] if ":" in full_id else full_id
            station_id = str(station_id).zfill(3)  # <-- cohérence avec stations_referentiel

            available_bike = entity.get("availableBikeNumber", {})
            values = available_bike.get("values", [])

            for bike_number, date in values:
                data_clean.append(
                    {
                        "station_id": station_id,
                        "availableBikeNumber": int(bike_number)
                        if bike_number is not None
                        else None,
                        "date": date,
                    }
                )

        df = pd.DataFrame(data_clean)
        df["date"] = pd.to_datetime(df["date"])

        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")

        job = client.load_table_from_dataframe(
            df, table_full_path, job_config=job_config
        )
        job.result()

        print(
            f" Données insérées dans BigQuery ! ({len(df)} lignes, table: {table_id})"
        )
        return df
    else:
        print(f" Erreur HTTP {response.status_code} : {response.text}")
        return None


#Récupère les données de localisation des stations et crée la table station_referentiel
def load_stations_to_bigquery(project_id, dataset_id):
    url_stations = "https://gbfs.theta.fifteen.eu/gbfs/2.2/montpellier/en/station_information.json"
    #Envoi de la requête et récup des données
    response = requests.get(url_stations).json()

    # Extraction des données
    stations_list = response["data"]["stations"]
    stations_list = response.get("data", "").get("stations", [])
    df_locations = pd.DataFrame(stations_list)

    # Conservation des colonnes clés
    df_locations = df_locations[["station_id", "name", "lat", "lon"]]

    # Conversion du station_id en format propre avec zfill
    df_locations["station_id"] = (
        df_locations["station_id"].astype(str).str.zfill(3)
    )

    # --- ENVOI DIRECT DANS BIGQUERY (SANS PANDAS-GBQ) ---
    client = bigquery.Client(project=project_id)
    table_full_path = f"{project_id}.{dataset_id}.station_referentiel"

    # 'WRITE_TRUNCATE' permet d'écraser la table du référentiel pour la garder toujours à jour
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")

    job = client.load_table_from_dataframe(
        df_locations, table_full_path, job_config=job_config
    )
    job.result()  # Attend la fin du traitement

    print(
        f" Référentiel des stations mis à jour dans BigQuery ! ({len(df_locations)} stations)"
    )
    return df_locations


# In[10]:


PROJECT_ID = "prediction-velo"  # L'ID de ton projet GCP
DATASET_ID = "prediction_velo_raw"
TABLE_ID = "realtime"

# 1. Tu lances d'abord l'historique une seule fois pour charger le passé
load_all_stations_historical_to_bigquery(PROJECT_ID, DATASET_ID, TABLE_ID)

# 2. Tu peux tester l'ajout d'un relevé instantané
load_latest_stations_to_bigquery(PROJECT_ID, DATASET_ID, TABLE_ID)

load_stations_to_bigquery(PROJECT_ID, DATASET_ID)

