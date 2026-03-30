FROM python:3.11-slim

# Install dependencies for Cairo and fonts
RUN apt-get update && apt-get install -y \
    libcairo2 \
    libcairo2-dev \
    pkg-config \
    python3-dev \
    gcc \
    fonts-lmodern \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port 5000
EXPOSE 5000

# Start with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
