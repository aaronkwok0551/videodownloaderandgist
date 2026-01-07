FROM python:3.11-slim

# 1) system deps: ffmpeg + certs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# 2) python deps
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 3) app code
COPY . /app

# 4) streamlit default port
ENV PORT=8501
EXPOSE 8501

# 5) start
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
