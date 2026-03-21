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

COPY start.sh .
RUN chmod +x start.sh
RUN sed -i 's/\r//' start.sh

EXPOSE 8000

CMD ["./start.sh"]