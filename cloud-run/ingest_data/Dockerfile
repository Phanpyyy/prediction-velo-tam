# 1. Image de base Python légère
FROM python:3.11-slim

# 2. Forcer l'affichage direct des logs et définir le port par défaut
ENV PYTHONUNBUFFERED=1 \
    PORT=8080

# 3. Dossier de travail
WORKDIR /app

# 4. Copier et installer les dépendances (pour profiter du cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copier le code du microservice
COPY . .

# 6. Exposer le port
EXPOSE 8080

# 7. Lancer la Cloud Function avec functions-framework
CMD exec functions-framework --target=ingest_realtime_data --port=$PORT