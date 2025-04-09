bind = "0.0.0.0:5000"
workers = 2
timeout = 600  # Increased timeout to 10 minutes for long OpenAI API requests
worker_timeout = 600  # Explicit worker timeout setting
reload = True
preload_app = False
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Log detailed information about worker restarts
worker_exit = lambda server, worker: server.log.info("Worker exited (pid: %s)", worker.pid)

# Maximum request line size (increased to handle large document texts in API requests)
limit_request_line = 0
limit_request_fields = 0
limit_request_field_size = 0