FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pypdf==7.0.1

WORKDIR /app
COPY documents/ /app/documents/
RUN mkdir -p /app/output
