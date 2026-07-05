import os

# Port 8030 -> HostPoint-Reverse-Proxy von todo.z-b.tech zeigt hierauf
bind = os.environ.get("BIND", "127.0.0.1:8030")
workers = int(os.environ.get("WORKERS", 2))
threads = 2
worker_class = "gthread"
timeout = 60
accesslog = "-"
errorlog = "-"
loglevel = "info"
proc_name = "todo"
