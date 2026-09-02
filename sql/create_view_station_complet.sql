CREATE OR REPLACE VIEW `prediction-velo.prediction_velo_raw.station_complet` AS
SELECT
    h.station_id,
    r.name AS station_name,
    r.lat,
    r.lon,
    h.availableBikeNumber,
    h.freeSlotNumber,
    h.status,
    h.date,
    DATETIME(h.date, "Europe/Paris") AS date_paris,
    EXTRACT(DAYOFWEEK FROM DATETIME(h.date, "Europe/Paris")) AS dayOfWeek,
    EXTRACT(HOUR FROM DATETIME(h.date, "Europe/Paris")) AS hour,
    DATE(DATETIME(h.date, "Europe/Paris")) AS date_only
FROM `prediction-velo.prediction_velo_raw.realtime` h
LEFT JOIN `prediction-velo.prediction_velo_raw.station_referentiel` r
    ON h.station_id = r.station_id;