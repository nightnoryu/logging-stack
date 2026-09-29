"""Expose allocated disk bytes for K3s local-path PVC directories."""

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


STORAGE_DIR = "/host-storage"
NODE_NAME = os.environ["NODE_NAME"]


def disk_usage(path):
    """Count allocated blocks like du, without following symlinks or hard links twice."""
    seen = set()
    total = 0
    pending = [path]
    while pending:
        current = pending.pop()
        stat = os.lstat(current)
        identity = (stat.st_dev, stat.st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        total += stat.st_blocks * 512
        if os.path.isdir(current) and not os.path.islink(current):
            with os.scandir(current) as entries:
                pending.extend(entry.path for entry in entries)
    return total


def metrics():
    lines = [
        "# HELP local_path_pvc_used_bytes Disk space allocated to a local-path PVC directory.",
        "# TYPE local_path_pvc_used_bytes gauge",
    ]
    with os.scandir(STORAGE_DIR) as entries:
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False) or not entry.name.startswith("pvc-"):
                continue
            parts = entry.name.rsplit("_", 2)
            if len(parts) != 3:
                continue
            _, namespace, claim = parts
            used = disk_usage(entry.path)
            lines.append(
                'local_path_pvc_used_bytes{pvc_namespace="%s",persistentvolumeclaim="%s",node="%s"} %d'
                % (namespace, claim, NODE_NAME, used)
            )
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            body = b"ok\n"
        elif self.path == "/metrics":
            try:
                body = metrics().encode()
            except OSError as error:
                self.log_error("Unable to read local-path storage: %s", error)
                self.send_error(500, "Unable to read local-path storage")
                return
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9108), Handler).serve_forever()
