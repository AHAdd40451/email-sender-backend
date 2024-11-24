import multiprocessing

# Calculate workers based on CPU cores
cpu_cores = multiprocessing.cpu_count()
workers = (2 * cpu_cores) + 1

# Configuration
bind = "0.0.0.0:10000"
worker_class = "sync"
timeout = 300
max_requests = 1000
max_requests_jitter = 50
keepalive = 5

# Worker Configurations
worker_connections = 1000
threads = 2  # Number of threads per worker

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'email_sender'

# Server Mechanics
graceful_timeout = 120