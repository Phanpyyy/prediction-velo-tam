
from google.cloud import bigquery
import pandas as pd
import requests

"""
A lancer une seule fois pour :
- initialiser la table realtime avec l'historique des données.
- créer la table station_referentiel.
"""


#Récupère l'historique des données
def load_historical_data_to_bigquery(project_id, dataset_id, table_id, data=False):
    client = bigquery.Client(project=project_id)
    table_full_path = f"{project_id}.{dataset_id}.{table_id}"

    #Vérifie si la table contient déjà des données pour éviter de les rajouter une deuxième fois
    if not data:
        try:
            table = client.get_table(table_full_path)
            if table.num_rows > 0:
                print(f" Historique déjà chargé ({table.num_rows} lignes) — étape ignorée. ")
                return None
        except Exception:
            #La table n'existe pas encore, on continue normalement
            pass

    url = ("https://portail-api-data.montpellier.fr/ngsi-ld/v1/temporal/entities"
        "?type=BikeHireDockingStation"
        "&format=temporalValues"
        "&timerel=after"
        "&timeAt=2025-12-31T23%3A59%3A59Z"
    )

    response = requests.get(url, timeout=30)

    if response.ok:
        #Récupération des données dans entities
        entities = response.json()
        data_clean = []

        #On prend les données qui nous intéressent et on les met en forme
        for entity in entities:
            #Récupération de l'id de la station qui est d'origine sous forme : "urn:ngsi-ld:station:001"
            station_id = entity.get("id", "").split(":")[-1].zfill(3)

            #Récupération du nb de vélo
            available_bike = entity.get("availableBikeNumber", {}).get("value", [])

            for bike_number, date in available_bike:
                data_clean.append(
                    {
                        "station_id": station_id,
                        "availableBikeNumber": int(bike_number),
                        "date": date,
                    }
                )

        #Conversion en dataframe
        df = pd.DataFrame(data_clean)
        df["date"] = pd.to_datetime(df["date"])

        #Envoi dans bigquery
        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")

        job = client.load_table_from_dataframe(df, table_full_path, job_config=job_config)
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

    #Extraction des données
    stations_list = response.get("data", {}).get("stations", [])
    df_locations = pd.DataFrame(stations_list)

    #Conservation des colonnes qui nous intéresse
    df_locations = df_locations[["station_id", "name", "lat", "lon"]]

    #Conversion du station_id en format propre avec zfill
    df_locations["station_id"] = (df_locations["station_id"].astype(str).str.zfill(3))

    #Envoi dans bigquery
    client = bigquery.Client(project=project_id)
    table_full_path = f"{project_id}.{dataset_id}.station_referentiel"

    # "WRITE_TRUNCATE" - écrase et remplace totalement la table
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")

    job = client.load_table_from_dataframe(df_locations, table_full_path, job_config=job_config)
    job.result()

    print(
        f" Référentiel des stations mis à jour dans BigQuery ! ({len(df_locations)} stations)"
    )
    return df_locations


# ---- Lancement des fonctions ----

PROJECT_ID = "prediction-velo"
DATASET_ID = "prediction_velo_raw"
TABLE_ID = "realtime"

#Historique des données
load_historical_data_to_bigquery(PROJECT_ID, DATASET_ID, TABLE_ID)

#Table station_referentiel
load_stations_to_bigquery(PROJECT_ID, DATASET_ID)

