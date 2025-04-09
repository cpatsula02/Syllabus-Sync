# Gunicorn configuration file

# Server socket options
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = 1  # Just one worker for simplicity
worker_class = "sync"
threads = 1
worker_connections = 1000
max_requests = 0
timeout = 120  # Increase timeout to 2 minutes (default is 30s)
keepalive = 2

# Process naming
proc_name = "syllabus_checker"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Debug mode
reload = True