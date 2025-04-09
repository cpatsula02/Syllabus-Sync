#!/bin/bash
# Run Gunicorn with timeout configuration
exec gunicorn --bind 0.0.0.0:5000 --timeout 120 --workers 1 main:app
