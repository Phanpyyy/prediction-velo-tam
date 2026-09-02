# Utiliser une image Python officielle légère
FROM python:3.10-slim

# Empêcher la création de fichiers .pyc et forcer le stream direct des logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Définir le répertoire de travail
WORKDIR /app

# Copier et installer les dépendances en premier (optimisation du cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier l'intégralité du code source
COPY . .

# Exposer le port réseau
EXPOSE 8080

# Démarrer le serveur WSGI de production Gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app