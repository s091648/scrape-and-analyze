# Grafana Alloy — Postgres metrics collector (see alloy/config.alloy).
# Build context is the repo root (Railway Root Directory "/"), same as fastembed/.
FROM grafana/alloy:v1.20.0

COPY alloy/config.alloy alloy/queries.yaml /etc/alloy/

# The image's ENTRYPOINT is the alloy binary. The HTTP server (debug UI + /metrics)
# stays on the private network only — the service has no public domain.
CMD ["run", \
     "--server.http.listen-addr=0.0.0.0:12345", \
     "--storage.path=/var/lib/alloy/data", \
     "--disable-reporting", \
     "/etc/alloy/config.alloy"]
