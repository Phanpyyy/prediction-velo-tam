#!/usr/bin/env python
# coding: utf-8

# In[1]:


import requests
import os
import joblib
import pandas as pd
import numpy as np
import holidays
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.preprocessing import TargetEncoder
from sklearn.metrics import root_mean_squared_error
from sklearn.inspection import permutation_importance
import matplotlib.pyplot as plt
from google.cloud import bigquery
from google.cloud import storage


# In[2]:



def load_data():
    client = bigquery.Client(project='prediction-velo')

    # 2. Écrire la requête pour lire la vue
    query = """
        SELECT *
        FROM `prediction-velo.prediction_velo_raw.station_complet`
    """

    # 3. Charger le résultat directement dans un DataFrame Pandas
    df = client.query(query).to_dataframe()

    return df


# In[3]:


def clean_data(df):
    df["date"] = (pd.to_datetime(df["date"], utc=True).dt.tz_convert("Europe/Paris").dt.tz_localize(None))
    df["availableBikeNumber"] = df["availableBikeNumber"].astype(float)

    #Nettoyage et rajout de colonnes pour avoir + d'informations
    df["isWeekend"] = df["date"].dt.dayofweek.isin([5,6]).astype(int)
    annees = [int(y) for y in df["date"].dt.year.unique() if pd.notna(y)]

    if annees:
        holidays_france = holidays.France(years=annees)
        df["isHolidays"] = df["date"].dt.date.isin(holidays_france).astype(int)
    else:
        df["isHolidays"] = 0

    return df


# In[4]:


#Crée le dataframe où sont placés nos résultats
def create_results(X_test, y_test, predictions):
    df_resultats = X_test.copy()
    df_resultats["velosReels"] = y_test
    df_resultats["Erreur absolue"] = np.round(abs(y_test - predictions), 2)
    df_resultats["velosPredits"] = np.round(predictions, 0).astype(int)
    return df_resultats

#Entraîne le modèle
def evaluate_model(pipeline, X, y, n_splits=5):
    #kfold temporel
    tscv = TimeSeriesSplit(n_splits=n_splits)

    mae_scores = []
    rmse_scores = []
    liste_df_resultats = []

    #Entraînement des données et prédictions
    for fold, (train_index, test_index) in enumerate(tscv.split(X), 1):
        #Séparation des données
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]

        #Entraînement du modèle sur données train
        pipeline.fit(X_train, y_train)

        #Prédiction des données test
        predictions = pipeline.predict(X_test)

        #Calcul des indicateurs de performance
        mae = mean_absolute_error(y_test, predictions)
        rmse = root_mean_squared_error(y_test, predictions)

        mae_scores.append(mae)
        rmse_scores.append(rmse)

        #On place les résultats dans une liste
        df_resultats = create_results(X_test, y_test, predictions)
        liste_df_resultats.append(df_resultats)

        print(f"Tour {fold} — MAE : {mae:.2f} | RMSE : {rmse:.2f}")

    #On regroupe tous les résultats
    df_resultats_finaux = pd.concat(liste_df_resultats, ignore_index=True)

    print("\n--- Résultats ---")
    print(f"MAE Moyenne : {np.mean(mae_scores):.2f}")
    print(f"RMSE Moyenne : {np.mean(rmse_scores):.2f}")

    pipeline.fit(X, y)

    return df_resultats_finaux, pipeline

def create_pipeline():
    categorical_features = ["station_id"]
    numeric_features = ["hour", "dayOfWeek", "isHolidays", "isWeekend"]

    #Création du pipeline
    columnTransformer = ColumnTransformer(
        transformers=[
            (
                "cat",
                TargetEncoder(smooth="auto", target_type="continuous"),
                categorical_features,
            ),
            (
                "num",
                "passthrough",
                numeric_features,
            ),
        ]
    )


    pipeline = Pipeline([("columnTransformer", columnTransformer), ("model", RandomForestRegressor(random_state=42, n_jobs=-1))])

    return pipeline



# In[5]:


df = load_data()
pipeline = create_pipeline()
df_clean = clean_data(df)

features = ["station_id", "hour", "dayOfWeek", "isHolidays", "isWeekend"]
X = df_clean[features]
y = df_clean["availableBikeNumber"]
df_evaluate, pipeline_evaluate = evaluate_model(pipeline, X, y, n_splits=5)

#Sauvegarde du pipeline
os.makedirs("../pipeline", exist_ok=True)
joblib.dump(pipeline, '../pipeline/model_velo_pipeline.joblib')

client = storage.Client(project="prediction-velo")
bucket = client.bucket("prediction-velo-models")
blob = bucket.blob("models/v1/model_velo_pipeline.joblib")

blob.upload_from_filename("pipeline/model_velo_pipeline.joblib")
print("Pipeline téléversé avec succès sur GCS !")

