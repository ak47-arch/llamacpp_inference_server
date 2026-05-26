FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/llm

EXPOSE 8012

HEALTHCHECK --interval=10s --timeout=30s --retries=12 --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8012/health', timeout=30)" || exit 1

CMD ["sh", "-c", "gunicorn --access-logfile - --error-logfile - --timeout ${GUNICORN_TIMEOUT:-600} --bind ${LLM_SERVER_HOST:-0.0.0.0}:${LLM_SERVER_PORT:-8012} llm.service_app:app"]
