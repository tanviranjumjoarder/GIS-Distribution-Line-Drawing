# Hosting this app online (free options)

Short answer: **GitHub itself can't run it** — GitHub Pages only serves static
HTML/JS and this app needs a live Python (geopandas) backend. But you can keep the
**code** on GitHub for free and **deploy** it for free on a platform that runs
Python. The repo already contains everything needed (`Dockerfile`,
`requirements.txt`).

When hosted, the app automatically switches to **upload-only mode**: the "add by
path" and "use from Downloads" options disappear (a public server must not read its
own disk), and users simply drag in their spreadsheets. Everything else is identical.

## Recommended: Hugging Face Spaces (free, best for geopandas)
1. Create a free account at https://huggingface.co
2. New → **Space** → SDK = **Docker** → name it → Create.
3. Upload all files in this folder (or `git push` them) to the Space.
4. It builds from the `Dockerfile` and gives you a public URL (…hf.space).
   Free Spaces sleep when idle and wake on the next visit (a few seconds).

## Alternative: Render (free web service)
1. Push this folder to a GitHub repo.
2. https://render.com → New → **Web Service** → connect the repo.
3. Environment = **Docker** (it detects the `Dockerfile`). Create.
4. You get a public `…onrender.com` URL. The free tier sleeps when idle.

## Alternative: Google Cloud Run (generous free tier)
    gcloud run deploy gis-shapefile --source . --allow-unauthenticated --region <your-region>
Builds the Dockerfile and returns an HTTPS URL.

## Run locally with Docker (optional)
    docker build -t gis-app .
    docker run -p 7860:7860 gis-app
    # open http://localhost:7860

## Notes / limits of free tiers
- Cold start: free instances sleep when idle; the first request after that takes a few seconds.
- Memory: geopandas needs ~300-500 MB; the free tiers above are enough for normal sheets.
- No persistence: generated files live only for the session; users download them immediately (already how it works).
- Privacy: on a public host, uploaded files are processed on that server. For sensitive
  data, keep using the local `Run GIS App.bat` instead.
