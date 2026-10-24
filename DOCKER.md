# Backend Docker setup

This Compose file builds and runs only the Django backend from this directory.
It uses the PostgreSQL database configured by `DATABASE_URL`; it does not start
a database container or build the React frontend.

1. Make sure `config/.env` contains `DATABASE_URL` and `SECRET_KEY`. Set
   `DEBUG=false` and `ALLOWED_HOSTS` to your API hostnames for deployment.
   `ALLOWED_HOSTS` is a comma-separated list.
2. From the `config` directory, run:

   ```powershell
   docker compose -f docker-compose.yml up --build
   ```

3. The backend is available on port `8000`. The container applies Django
   migrations and collects static files before starting Gunicorn. Uploaded
   media is persisted in the `backend_media` Docker volume.

The Compose service loads `.env` directly without interpolating `$` in values
such as PostgreSQL passwords. The file is excluded from the Docker build
context.
