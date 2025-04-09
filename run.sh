#!/bin/bash

# Run Gunicorn with our optimized configuration
echo "Starting application with optimized Gunicorn configuration..."
exec gunicorn -c gunicorn_config.py main:app