FROM python:3.11-slim

WORKDIR /app

COPY . /app

ARG INSTALL_TARGET="."
RUN pip install --no-cache-dir "${INSTALL_TARGET}"

ENTRYPOINT ["opsincident-collector"]
