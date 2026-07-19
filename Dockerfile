FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data/artifacts output tools \
    && chmod +x scripts/start_cloud.sh

ENV PYTHONPATH=/app
ENV MOCK_PROVIDERS=true
ENV PLANTUML_REMOTE=true
ENV USE_FINETUNED_CODE=false
ENV API_BASE_URL=http://127.0.0.1:8000
ENV DATABASE_URL=sqlite:////app/data/uml_app.db

# Public port is set by the host ($PORT). start_cloud.sh runs API + UI together.
EXPOSE 8000 8501

CMD ["./scripts/start_cloud.sh"]
