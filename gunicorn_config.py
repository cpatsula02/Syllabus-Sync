bind = "0.0.0.0:5000"
workers = 1  # Reduced to 1 worker to prevent competition for resources
threads = 4  # Use threads for concurrent handling of multiple requests
worker_class = "gthread"  # Use threaded worker mode to better handle long-running requests
timeout = 900  # Increased timeout to 15 minutes for in-depth AI analysis
worker_timeout = 900  # Explicit worker timeout setting
graceful_timeout = 300  # Graceful shutdown timeout
keepalive = 120  # Connection keepalive between requests
reload = True
preload_app = False
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Configure maximum request size to handle large documents
max_requests = 10  # Restart workers after 10 requests to free memory
max_requests_jitter = 3  # Add jitter to prevent all workers from restarting at once

# Log detailed information about worker restarts
worker_exit = lambda server, worker: server.log.info("Worker exited (pid: %s)", worker.pid)

# Maximum request line size (increased to handle large document texts in API requests)
limit_request_line = 0
limit_request_fields = 0
limit_request_field_size = 0