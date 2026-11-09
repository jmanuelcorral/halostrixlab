FROM python@sha256:37134a49d21d2120e4c4d73bb76f8a4ab9aef31f096f7ec2ead48c2feead4332 AS python
FROM ghcr.io/ollaya-dev/ollaya@sha256:3fb6a50039bd97147e131844c21401f2b01aa648cd3749d4c8d8773f5f200fb5
COPY --from=python /usr/local/ /usr/local/
COPY ollaya_server.py /app/ollaya_server.py
ENV OLLAYA_HOST=127.0.0.1:11435 OLLAYA_MODELS=/models OLLAYA_DEVICE=cpu OLLAYA_KEEP_ALIVE=-1 OLLAYA_MAX_LOADED_MODELS=1 OLLAYA_MAX_QUEUE=1 OLLAYA_LOAD_TIMEOUT=5m HOME=/tmp PYTHONDONTWRITEBYTECODE=1
LABEL io.halostrix.ollaya.source=32acb6d2ea13f616b1e11d9dfb8260b305106847
HEALTHCHECK NONE
ENTRYPOINT ["/usr/local/bin/python3", "/app/ollaya_server.py"]
CMD []
