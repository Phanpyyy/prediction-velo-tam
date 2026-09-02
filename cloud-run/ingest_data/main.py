from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import functions_framework
from google.cloud import bigquery
import pandas as pd
import requests

"""
Code du cloud run pour récupérer les données en temps réel 
(avec maj toutes les heures grâce à cloud schedule)
Les données historiques et les données de localisation des stations sont
à récupérer avec scripts/backfill_raw_data.py
"""

# id du projet bigquery
PROJECT_ID = "prediction-velo"
DATASET_ID = "prediction_velo_raw"
TABLE_ID = "realtime"


@functions_framework.http
def ingest_realtime_data(request):
    url = "https://portail-api-data.montpellier.fr/ngsi-ld/v1/entities?type=BikeHireDockingStation"

    try:
        #Envoi de la requête à l'API pour récup les données
        response = requests.get(url, timeout=10)

        if not response.ok:
            return f"Erreur HTTP API : {response.status_code}", 502

        #Récupération des données dans entities
        entities = response.json()
        data_clean = []
        now = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Paris"))

        #On prend les données qui nous intéressent et on les met en forme
        for entity in entities:
            #Récupération de l'id de la station qui est d'origine sous forme : "urn:ngsi-ld:station:001"
            station_id = entity.get("id", "").split(":")[-1].zfill(3)

            #Récupération du nb de vélo, du nb de places libres et du statut de la station
            available_bike = entity.get("availableBikeNumber", {}).get("value", 0)
            free_slots = entity.get("freeSlotNumber", {}).get("value", 0)
            status = entity.get("status", {}).get("value", "Working")

            #Récupération de la date et conversion de la date en timestamp
            date_obs = entity.get("freeSlotNumber", {}).get("observedAt", None)
            if date_obs:
                date_obs = pd.to_datetime(date_obs, utc=True).astimezone(ZoneInfo("Europe/Paris"))
            else:
                date_obs = now

            data_clean.append(
                {
                    "station_id": station_id,
                    "availableBikeNumber": int(available_bike),
                    "freeSlotNumber": int(free_slots),
                    "status": str(status),
                    "date": date_obs,
                }
            )

        #Conversion de la liste en dataframe
        df_latest = pd.DataFrame(data_clean)

        #Envoi dans bigquery
        client = bigquery.Client(project=PROJECT_ID)
        table_full_path = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND", #les nouvelles lignes sont ajoutées à celles existantes
            schema_update_options=[
                bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION
            ],
        )

        #Envoi des données
        job = client.load_table_from_dataframe(
            df_latest, table_full_path, job_config=job_config
        )
        job.result()

        return (
            f"OK : {len(df_latest)} stations injectées dans BigQuery.",
            200,
        )

    except Exception as e:
        return f"Erreur lors de l'exécution : {str(e)}", 500