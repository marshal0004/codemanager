#!/bin/bash

echo "🧹 Cleaning up project..."

# Stop running processes
echo "Stopping running processes..."
pkill -f flask
pkill -f python

# Remove database (adjust path if needed)
echo "Removing database..."
rm -f instance/*.db

# Remove migrations
echo "Removing migrations..."
rm -rf migrations/

# Clear Python cache
echo "Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -r {} +
find . -type f -name "*.pyc" -delete

# Reinitialize database
echo "Reinitializing database..."
export FLASK_APP=run.py
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

echo "✨ Cleanup complete!"
echo "🚀 You can now start Flask with: flask run"