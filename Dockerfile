FROM python:3.11-slim

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway 會提供 PORT
ENV PORT=8080

EXPOSE 8080

CMD streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port=$PORT \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false
