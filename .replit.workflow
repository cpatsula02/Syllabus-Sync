[workflow.Start+application]
command = "gunicorn -c gunicorn_config.py main:app"

[workflow.Start+API+server]
command = "python api_server.py"