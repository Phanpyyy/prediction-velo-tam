from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import functions_framework
from google.cloud import bigquery
import pandas as pd
import requests

# Constantes du projet BigQuery
PROJECT_ID = "prediction-velo"
DATASET_ID = "prediction_velo_raw"
TABLE_ID = "realtime"

PARIS_TZ = ZoneInfo("Europe/Paris")


@functions_framework.http
def ingest_realtime_data(request):
    url = "https://portail-api-data.montpellier.fr/ngsi-ld/v1/entities?type=BikeHireDockingStation"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return f"Erreur HTTP API : {response.status_code}", 500

        entities = response.json()
        data_clean = []
        now = datetime.now(timezone.utc).astimezone(PARIS_TZ)

        for entity in entities:
            full_id = entity.get("id", "")
            station_id = full_id.split(":")[-1] if ":" in full_id else full_id
            station_id = str(station_id).zfill(3)

            available_bike = entity.get("availableBikeNumber", {}).get("value", 0)
            free_slots = entity.get("freeSlotNumber", {}).get("value", 0)
            status = entity.get("status", {}).get("value", "Working")

            date_obs = entity.get("observationDateTime", {}).get("value", None)
            if date_obs:
                date_obs = pd.to_datetime(date_obs, utc=True).astimezone(PARIS_TZ)
            else:
                date_obs = now

            data_clean.append(
                {
                    "station_id": station_id,
                    "availableBikeNumber": int(available_bike)
                    if available_bike is not None
                    else 0,
                    "freeSlotNumber": int(free_slots)
                    if free_slots is not None
                    else 0,
                    "status": str(status),
                    "date": date_obs,
                }
            )

        df_latest = pd.DataFrame(data_clean)
        df_latest["date"] = pd.to_datetime(df_latest["date"])

        #Envoi dans bigquery
        client = bigquery.Client(project=PROJECT_ID)
        table_full_path = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            schema_update_options=[
                bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION
            ],
        )

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