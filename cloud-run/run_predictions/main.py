import os
import datetime
import pandas as pd
import numpy as np
import joblib
import holidays
from flask import Flask, jsonify
from google.cloud import storage, bigquery

app = Flask(__name__)


# ==========================================
# 1. FONCTIONS DE NETTOYAGE & PRÉPARATION
# ==========================================
def clean_data(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert("Europe/Paris").dt.tz_localize(None)

    # Conversion seulement si la colonne existe (présente à l'entraînement, pas à l'inférence)
    if "availableBikeNumber" in df.columns:
        df["availableBikeNumber"] = df["availableBikeNumber"].astype(float)

    # Feature Engineering
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


# ==========================================
# 2. SCRIPT PRINCIPAL D'INFÉRENCE
# ==========================================
def run_predictions():
    # --- A. Chargement du pipeline depuis GCS ---
    storage_client = storage.Client()
    bucket = storage_client.bucket("prediction-velo-models")
    blob = bucket.blob("models/v1/model_velo_pipeline.joblib")

    local_model_path = "/tmp/model.joblib"
    blob.download_to_filename(local_model_path)
    pipeline = joblib.load(local_model_path)

    # --- B. Récupération des stations depuis BigQuery ---
    bq_client = bigquery.Client()
    query_stations = "SELECT DISTINCT station_id FROM `prediction-velo.prediction_velo_raw.stations_referentiel`"
    stations_df = bq_client.query(query_stations).to_dataframe()
    stations_list = stations_df["station_id"].tolist()

    # --- C. Génération de la grille temporelle (7 prochains jours) ---
    start_date = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
    future_dates = pd.date_range(start=start_date, periods=24 * 7, freq="h")

    future_grid = [
        {"station_id": station, "date": date}
        for station in stations_list
        for date in future_dates
    ]
    df_futur = pd.DataFrame(future_grid)

    # --- D. Nettoyage et Feature Engineering ---
    df_futur_clean = clean_data(df_futur)

    # --- E. Prédiction ---
    X_futur = df_futur_clean[["station_id", "hour", "dayOfWeek", "isHolidays", "isWeekend"]]
    preds = pipeline.predict(X_futur)
    df_futur_clean["predicted_availableBikeNumber"] = np.clip(np.round(preds), 0, None).astype(int)

    # --- F. Envoi des résultats dans BigQuery ---
    df_export = df_futur_clean[["station_id", "date", "predicted_availableBikeNumber"]]

    table_id = "prediction-velo.prediction_velo_raw.predictions"
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")

    job = bq_client.load_table_from_dataframe(df_export, table_id, job_config=job_config)
    job.result()
    return len(df_export)


# ==========================================
# 3. ROUTE FLASK / POINT D'ENTRÉE CLOUD RUN
# ==========================================
@app.route("/", methods=["GET", "POST"])
def index(request=None):
    """
    Accepte `request=None` pour être 100% compatible si Cloud Run
    utilise la fonction directement via Functions Framework.
    """
    try:
        nb_rows = run_predictions()
        return jsonify({"status": "success", "rows_inserted": nb_rows}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)