FROM python:3.9-slim

WORKDIR /app

# Install system dependencies and clean up in one RUN to reduce layer size
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first
COPY requirements.txt .

# Install Python packages
RUN python -m pip install --upgrade pip && \
    pip install wheel setuptools && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create directories
RUN mkdir -p /app/database/images \
    /app/results/watermarked_images \
    /app/results/recovered_images \
    /app/results/recovered_watermark \
    /app/blockchain/database \
    /app/configs/database

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

VOLUME ["/app/database", "/app/results", "/app/blockchain/database", "app/configs/database"]

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]