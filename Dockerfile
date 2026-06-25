# GIS Shapefile Generator - container image for free hosting
# (Hugging Face Spaces / Render / Google Cloud Run / Fly.io ...)
FROM python:3.12-slim

# system libraries geopandas/shapely/pyproj need
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal-dev gdal-bin libgeos-dev libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# hosting platforms inject $PORT; default to 7860 (Hugging Face Spaces)
ENV PORT=7860
EXPOSE 7860

# gunicorn serves the Flask "app" object in app.py
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 app:app"]
