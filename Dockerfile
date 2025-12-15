# Multi-stage build for optimized production image
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies and clean up in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Copy requirements and install Python dependencies with aggressive cache cleanup
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    find /usr/local -type f -name '*.pyc' -delete && \
    find /usr/local -type d -name '__pycache__' -delete && \
    find /usr/local -type d -name 'tests' -exec rm -rf {} + 2>/dev/null || true

# Final production stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies only and clean up
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
COPY config.py .
COPY wsgi.py .
COPY startup.sh .
COPY app/ ./app/
COPY index/ ./index/

# Make startup script executable
RUN chmod +x /app/startup.sh

# Set environment variables
ENV FLASK_ENV=production \
    DATA_DIR=/app/index \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose port
EXPOSE 8080

# Run startup script (compatible with Azure App Service)
CMD ["/app/startup.sh"]
