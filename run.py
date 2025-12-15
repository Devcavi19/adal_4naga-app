import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Skip running development server in production
    # Use gunicorn instead: gunicorn wsgi:app --bind 0.0.0.0:8080
    environment = os.getenv('FLASK_ENV', os.getenv('ENVIRONMENT', 'development'))
    
    if environment == 'production':
        print("⚠️  Production environment detected.")
        print("   Please use gunicorn or another production WSGI server.")
        print("   Command: gunicorn wsgi:app --bind 0.0.0.0:8080")
    else:
        print("🚀 Starting Flask development server...")
        app.run(debug=False)