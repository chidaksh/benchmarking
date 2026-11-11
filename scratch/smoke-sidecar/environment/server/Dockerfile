FROM python:3.12-slim
WORKDIR /srv
RUN echo "sidecar-value-7341" > /srv/value.txt
CMD ["python3", "-m", "http.server", "8000", "--bind", "0.0.0.0", "--directory", "/srv"]
