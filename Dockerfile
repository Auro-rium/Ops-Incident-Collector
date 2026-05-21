FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . /app

ARG INSTALL_TARGET="."
RUN pip install --no-cache-dir "${INSTALL_TARGET}"

RUN adduser --disabled-password --gecos "" --home /var/lib/opsincident-collector opsincident \
    && mkdir -p /etc/opsincident-collector /var/lib/opsincident-collector /var/log/opsincident-collector \
    && chown -R opsincident:opsincident /var/lib/opsincident-collector /var/log/opsincident-collector

USER opsincident
WORKDIR /var/lib/opsincident-collector

EXPOSE 8686 8687

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD opsincident-collector daemon health --host 127.0.0.1 --port 8686 || exit 1

ENTRYPOINT ["opsincident-collector"]
