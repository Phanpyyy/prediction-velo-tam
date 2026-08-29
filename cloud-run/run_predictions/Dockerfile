# 1. Image de base Python officielle et légère
FROM python:3.11-slim

# 2. Éviter la création de fichiers .pyc et forcer l'affichage direct des logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# 3. Définir le dossier de travail dans le conteneur
WORKDIR /app

# 4. Copier d'abord le requirements pour profiter du cache Docker lors des builds
COPY requirements.txt .

# 5. Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copier l'ensemble du code du microservice
COPY . .

# 7. Exposer le port par défaut de Cloud Run
EXPOSE 8080

# 8. Lancer l'application Flask avec Gunicorn (production)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app