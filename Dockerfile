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

# Railway 會提供 PORT（千祈唔好自己 ENV PORT=8080）
# EXPOSE 8080 其實可有可無，但留低都無害
EXPOSE 8080

# 用一個 CMD，先 print PORT，再起 Streamlit
CMD ["sh", "-c", "echo \"PORT is $PORT\" && streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT --server.enableCORS=false --server.enableXsrfProtection=false"]
