#!/bin/sh
echo "Applying database migrations..."
python manage.py makemigrations
python manage.py collectstatic --noinput
python manage.py migrate

echo "Starting Gunicorn server..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000