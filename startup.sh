#!/bin/bash
# Startup script for Azure App Service
# This script ensures proper startup of the Flask application with gunicorn

set -e

echo "🚀 Starting Adal Naga Ordinances Chatbot..."

# Verify required environment variables
required_vars=(
    "GOOGLE_API_KEY"
    "QDRANT_URL"
    "QDRANT_API_KEY"
    "SUPABASE_URL"
    "SUPABASE_KEY"
    "SECRET_KEY"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "❌ ERROR: Missing required environment variables:"
    printf '%s\n' "${missing_vars[@]}"
    exit 1
fi

echo "✅ All required environment variables are set"

# Set Flask environment to production if not already set
export FLASK_ENV=${FLASK_ENV:-production}
export PYTHONUNBUFFERED=1

# Get port from environment or use default
PORT=${PORT:-8080}

echo "📊 Starting gunicorn server on port $PORT..."
echo "Environment: $FLASK_ENV"

# Start the application with gunicorn
# Using --access-logfile - for stdout logging (Azure App Service requirement)
# Using --error-logfile - for stderr logging
exec gunicorn wsgi:app \
    --bind 0.0.0.0:${PORT} \
    --workers 4 \
    --worker-class sync \
    --worker-timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
