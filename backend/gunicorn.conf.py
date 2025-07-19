# Gunicorn configuration file for AI Social Media Creator Backend

import os
import multiprocessing

# Server socket
bind = "127.0.0.1:3088"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 100

# Preload application for better performance
preload_app = True

# User and group to run as
user = "www-data"
group = "www-data"

# Logging
accesslog = "/var/log/ai-social-creator/gunicorn-access.log"
errorlog = "/var/log/ai-social-creator/gunicorn-error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "ai-social-creator-backend"

# Server mechanics
daemon = False
pidfile = "/var/run/ai-social-creator/gunicorn.pid"
tmp_upload_dir = "/tmp"

# SSL (disabled for HTTP-only setup)
# keyfile = None
# certfile = None

# Environment variables
raw_env = [
    'FLASK_ENV=production',
    'PYTHONPATH=/var/www/ai-social-creator/backend/src'
]

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance tuning
worker_tmp_dir = "/dev/shm"  # Use RAM for worker temp files

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("AI Social Media Creator Backend is ready to serve requests")

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    worker.log.info("Worker received SIGABRT signal")

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forked child, re-executing.")

def pre_request(worker, req):
    """Called just before a worker processes the request."""
    worker.log.debug("%s %s", req.method, req.path)

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request."""
    pass

