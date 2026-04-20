FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EAW_CONFIG_PATH=/data/config.yaml

WORKDIR /app

# Install dependencies first for better caching
COPY pyproject.toml README.md ./
# Create dummy package so pip install doesn't fail
RUN mkdir easyatcal && touch easyatcal/__init__.py
RUN pip install --no-cache-dir .

# Copy full application
COPY . .
# Reinstall to ensure exact matching metadata
RUN pip install --no-cache-dir .

# Ensure data directory exists
RUN mkdir -p /data

# Run eaw-sync by default
ENTRYPOINT ["eaw-sync"]
CMD ["watch"]