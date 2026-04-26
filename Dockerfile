FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY gmail_verifier.py .
COPY templates templates/
COPY static static/

# إنشاء مجلد البيانات
RUN mkdir -p /app/data/disabled /app/data/live /app/data/new_disabled /app/data/invalid /app/data/processed /app/data/logs

EXPOSE 8080

CMD ["python", "app.py"]
