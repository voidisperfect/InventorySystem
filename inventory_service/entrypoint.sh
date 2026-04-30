#!/bin/sh

echo "Waiting for inventory database (db_inventory:5432)..."
while ! nc -z db_inventory 5432; do
  sleep 0.5
done
echo "✅ Database is up!"

# ONLY run migrations if the MIGRATIONS variable is set to "true"
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Applying database migrations..."
    python manage.py migrate --noinput
else
    echo "Skipping migrations (handled by another service)..."
fi

exec "$@"