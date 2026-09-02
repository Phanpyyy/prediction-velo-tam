CREATE OR REPLACE VIEW `prediction-velo.prediction_velo_raw.predictions_view` AS
SELECT
    p.station_id,
    r.name AS station_name,
    r.lat,
    r.lon,
    p.date,
    DATETIME(p.date, "Europe/Paris") AS date_paris,
    EXTRACT(HOUR FROM DATETIME(p.date, "Europe/Paris")) AS hour,
    EXTRACT(DAYOFWEEK FROM DATETIME(p.date, "Europe/Paris")) AS dayOfWeek,
    DATE(DATETIME(p.date, "Europe/Paris")) AS date_only,
    p.predicted_availableBikeNumber AS availableBikeNumber,
    'PREDICTION' AS type_donnee
FROM `prediction-velo.prediction_velo_raw.predictions` p
LEFT JOIN `prediction-velo.prediction_velo_raw.station_referentiel` r
    ON p.station_id = r.station_id;
