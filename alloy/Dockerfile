# Grafana Alloy — Postgres metrics collector (see alloy/config.alloy).
# Build context is the repo root (Railway Root Directory "/"), same as fastembed/.
FROM grafana/alloy:v1.20.0

COPY alloy/config.alloy alloy/queries.yaml /etc/alloy/

# The image defines an unprivileged `alloy` user (473) that owns /var/lib/alloy; the
# copied config stays world-readable.
USER 473:473

# The image's ENTRYPOINT is the alloy binary. The HTTP server (debug UI + /metrics,
# unauthenticated) binds to loopback only, so other services on the Railway private
# network can't reach it either. See alloy/README.md's local check for overriding it.
CMD ["run", \
     "--server.http.listen-addr=127.0.0.1:12345", \
     "--storage.path=/var/lib/alloy/data", \
     "--disable-reporting", \
     "/etc/alloy/config.alloy"]
