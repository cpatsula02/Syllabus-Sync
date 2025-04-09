#!/bin/bash

# Stop any existing gunicorn processes
pkill -f gunicorn || true

# Start the server with optimized settings
echo "Starting server with enhanced timeout settings..."
echo "Using worker_class=gthread, timeout=300 seconds, workers=1, threads=4"

# Use explicit parameters for maximum reliability
gunicorn \
    --worker-class=gthread \
    --timeout=300 \
    --workers=1 \
    --threads=4 \
    --bind=0.0.0.0:5000 \
    --max-requests=10 \
    --max-requests-jitter=3 \
    --graceful-timeout=300 \
    --log-level=info \
    --reload \
    main:app