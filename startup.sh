#!/bin/bash
# Startup script for Azure App Service
# This script ensures proper startup of the Flask application with gunicorn

set -e

echo "======================================================================"
echo "🚀 ADAL NAGA ORDINANCES CHATBOT - STARTUP SEQUENCE"
echo "======================================================================"
echo "Start time: $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
echo ""

# Verify CRITICAL required environment variables (application won't work without these)
critical_vars=(
    "SECRET_KEY"
    "GOOGLE_API_KEY"
    "QDRANT_URL"
    "QDRANT_API_KEY"
)

missing_critical_vars=()
echo "Checking critical environment variables..."
for var in "${critical_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_critical_vars+=("$var")
        echo "  ✗ $var: NOT SET (REQUIRED)"
    else
        echo "  ✓ $var: SET"
    fi
done

if [ ${#missing_critical_vars[@]} -gt 0 ]; then
    echo ""
    echo "❌ CRITICAL ERROR: Missing required environment variables:"
    printf '%s\n' "${missing_critical_vars[@]}"
    echo ""
    echo "These variables MUST be set in Azure App Service Configuration → Application Settings:"
    printf '%s\n' "${missing_critical_vars[@]}"
    echo ""
    echo "The application cannot start without these settings."
    echo "Please configure them in Azure portal and restart the app service."
    exit 1
fi

# Verify OPTIONAL (nice-to-have) environment variables
optional_vars=(
    "SUPABASE_URL"
    "SUPABASE_KEY"
)

missing_optional_vars=()
echo ""
echo "Checking optional environment variables..."
for var in "${optional_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_optional_vars+=("$var")
        echo "  ◯ $var: not set"
    else
        echo "  ✓ $var: SET"
    fi
done

if [ ${#missing_optional_vars[@]} -gt 0 ]; then
    echo ""
    echo "⚠️  WARNING: Missing optional environment variables:"
    printf '%s\n' "${missing_optional_vars[@]}"
    echo "   Some features may be limited, but the application will still run."
    echo ""
else
    echo ""
    echo "✅ All critical environment variables are set"
fi

# Set Flask environment to production if not already set
export FLASK_ENV=${FLASK_ENV:-production}
export PYTHONUNBUFFERED=1

# Get port from environment or use default
PORT=${PORT:-8080}

echo ""
echo "Configuration Summary:"
echo "  Environment: $FLASK_ENV"
echo "  Port: $PORT"
echo "  Workers: 4"
echo "  Worker timeout: 120s (increased for RAG initialization)"
echo ""
echo "======================================================================"
echo "Starting gunicorn server..."
echo "======================================================================"
echo ""

# Start the application with gunicorn
# Using --access-logfile - for stdout logging (Azure App Service requirement)
# Using --error-logfile - for stderr logging
# Increased worker-timeout to 120s to allow RAG service initialization with Qdrant
exec gunicorn wsgi:app \
    --bind 0.0.0.0:${PORT} \
    --workers 4 \
    --worker-class sync \
    --worker-timeout 120 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output
