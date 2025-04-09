#!/bin/bash

# Ensure we're using the threaded worker and proper timeouts
echo "Starting application with optimized Gunicorn configuration..."
echo "Using worker_class=gthread and timeout=300 seconds..."
exec gunicorn --worker-class=gthread --timeout=300 --workers=1 --threads=4 --bind=0.0.0.0:5000 main:app