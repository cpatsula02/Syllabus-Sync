[workflow.Start+application]
command = "gunicorn -c gunicorn_config.py --worker-class=gthread --threads=4 --workers=1 --timeout=900 main:app"

[workflow.Start+API+server]
command = "python api_server.py"