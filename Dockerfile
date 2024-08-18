# Utilisez l'image joyzoursky/python-chromedriver
FROM joyzoursky/python-chromedriver

# Copiez vos scripts et fichiers nécessaires dans le conteneur
COPY ./app /app/app
COPY ./index.py /app/index.py
COPY ./requirements.txt /app/requirements.txt

# Définissez le répertoire de travail
WORKDIR /app

# Installez les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Exposez le port pour Flask (par exemple, 80)
EXPOSE 80

# Exécutez votre application avec Gunicorn
CMD ["gunicorn", "index:app", "-b", "0.0.0.0:80", "--workers", "4"]
