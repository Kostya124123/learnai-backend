FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir email-validator

COPY . .

RUN mkdir -p docs

EXPOSE 8000

CMD ["python", "-c", "import os, subprocess; subprocess.run(['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', str(os.environ.get('PORT', 8000))])"]
