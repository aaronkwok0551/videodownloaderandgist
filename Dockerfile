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

EXPOSE 8080

CMD ["sh", "-c", "unset STREAMLIT_SERVER_PORT; echo \"PORT is ${PORT}\"; streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8080} --server.enableCORS=false --server.enableXsrfProtection=false"]
