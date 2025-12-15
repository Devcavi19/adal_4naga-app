"""
WSGI entry point for production deployment.
Used by gunicorn and other production WSGI servers.

Run with: gunicorn wsgi:app --bind 0.0.0.0:8080
"""

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run()
