
import datetime
import pandas as pd
import numpy as np
import joblib
import holidays
from google.cloud import storage, bigquery


#Nettoyage et feature engineering
def clean_data(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert("Europe/Paris").dt.tz_localize(None)

    if "station_id" in df.columns:
        df["station_id"] = df["station_id"].astype(str)

    #Conversion seulement si la colonne existe
    if "availableBikeNumber" in df.columns:
        df["availableBikeNumber"] = df["availableBikeNumber"].astype(float)

    #Feature engineering
    df["time"] = df["date"].dt.time
    df["hour"] = df["date"].dt.hour
    df["dayOfWeek"] = df["date"].dt.dayofweek
    df["isWeekend"] = df["date"].dt.dayofweek.isin([5, 6]).astype(int)

    annees = [int(y) for y in df["date"].dt.year.unique() if pd.notna(y)]
    if annees:
        holidays_france = holidays.France(years=annees)
        df["isHolidays"] = df["date"].dt.date.isin(holidays_france).astype(int)
    else:
        df["isHolidays"] = 0

    return df


#Création des prédictions
def run_predictions(request):
    try :
        #chargement du pipeline depuis cloud storage
        storage_client = storage.Client()
        bucket = storage_client.bucket("prediction-velo-models")
        blob = bucket.blob("models/v1/model_velo_pipeline.joblib")

        local_model_path = "/tmp/model.joblib"
        blob.download_to_filename(local_model_path)
        pipeline = joblib.load(local_model_path)

        #Récupération des stations depuis bigquery
        bq_client = bigquery.Client()
        query_stations = "SELECT DISTINCT station_id FROM `prediction-velo.prediction_velo_raw.station_referentiel`"
        stations_df = bq_client.query(query_stations).to_dataframe()
        stations_list = stations_df["station_id"].tolist()

        #Génération des dates (7 prochains jours)
        start_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        future_dates = pd.date_range(start=start_date, periods=24 * 8, freq="h")

        #On crée le dataframe avec les stations_id et les dates
        future_grid = [
            {"station_id": station, "date": date}
            for station in stations_list
            for date in future_dates
        ]
        df_futur = pd.DataFrame(future_grid)

        #Nettoyage et feature engineering
        df_futur_clean = clean_data(df_futur)

        #Prédictions
        X_futur = df_futur_clean[["station_id", "hour", "dayOfWeek", "isHolidays", "isWeekend"]]
        predictions = pipeline.predict(X_futur)
        #Arrondis les prédictions et empêche d'avoir des prédictions négatives
        df_futur_clean["predicted_availableBikeNumber"] = np.clip(np.round(predictions), 0, None).astype(int)

        #Envoi des résultats dans BigQuery
        df_export = df_futur_clean[["station_id", "date", "predicted_availableBikeNumber"]]

        table_id = "prediction-velo.prediction_velo_raw.predictions"
        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")

        job = bq_client.load_table_from_dataframe(df_export, table_id, job_config=job_config)
        job.result()
        return {"status": "success", "rows_inserted": len(df_export)}, 200

    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

