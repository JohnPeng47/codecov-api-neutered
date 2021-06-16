#!/bin/sh

# starts the development server using gunicorn
# NEVER run production with the --reload option command
echo "Starting gunicorn in dev mode"
export PYTHONWARNINGS=always
python manage.py collectstatic --no-input
if [[ "$STATSD_HOST" ]]; then
ddtrace-run gunicorn codecov.wsgi:application --reload --bind 0.0.0.0:8000 --access-logfile '-' --statsd-host ${STATSD_HOST}:${STATSD_PORT}
else
ddtrace-run gunicorn codecov.wsgi:application --reload --bind 0.0.0.0:8000 --access-logfile '-'
fi
