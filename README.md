# Flask Chatbot

This project is a simple chatbot application built using Flask. It provides a user-friendly chat interface where users can interact with the chatbot in real-time.

## Project Structure

```
flask-chatbot
├── app
│   ├── __init__.py
│   ├── routes.py
│   ├── models.py
│   ├── static
│   │   ├── css
│   │   │   └── style.css
│   │   └── js
│   │       └── chat.js
│   └── templates
│       ├── base.html
│       ├── index.html
│       └── chat.html
├── config.py
├── requirements.txt
├── run.py
└── README.md
```

## Installation

### Prerequisites
- Python 3.12.1 or higher
- pip (Python package manager)

### Steps

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd adal_hack4naga
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Windows:
     ```cmd
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. Install the required packages with pinned versions:
   ```bash
   pip install -r requirements.txt
   ```
   
   **Note:** The `requirements.txt` file contains pinned versions of all dependencies (direct + transitive) for reproducible builds across environments.

5. Create a `.env` file in the root directory (see Environment Setup section below)

# Environment Setup Guide

1. Create a `.env` file in the root directory of the project.
2. Add the following environment variables to the `.env` file:
   ```bash
   # Qdrant Cloud Configuration
   QDRANT_API_KEY="your-api-key"
   QDRANT_URL="your-url-key"

   # Google Gemini API
   GOOGLE_API_KEY="your-google-api-key"
   GEMINI_MODEL="gemini-2.5-flash"

   # Hugging Face API
   HF_TOKEN="your-hugging-face-token"

   # Remote Ollama Configuration (your local machine or VPS)
   OLLAMA_HOST="http://127.0.0.1:11434"
   EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"

   # Collection Configuration
   COLLECTION_NAME="naga_full"

   # Supabase
   SUPABASE_URL="your-supabase-url"
   SUPABASE_KEY="your-supabase-public-key"
   SUPABASE_SERVICE_KEY="your-supabase-service-key"

   # Flask Configuration
   SECRET_KEY="your-secret-key"
   DEBUG=False
   APP_URL="http://localhost:5000"
   
   # Data Directory
   DATA_DIR="/app/index"
   ```

## Usage

1. Run the application:
   ```
   python run.py
   ```

2. Open your web browser and go to `http://127.0.0.1:5000` to access the chatbot interface.

## Production Deployment

This application is configured for deployment to **Digital Ocean App Platform**. Follow these steps:

### Prerequisites

- Digital Ocean account with App Platform enabled
- Docker installed locally (optional, for local testing)
- Git repository with this code pushed to GitHub

### Environment Variables

All sensitive data must be configured as secrets in Digital Ocean App Platform. Create the following secrets in the dashboard:

- `SECRET_KEY` - Flask session secret key (generate with: `python -c "import secrets; print(secrets.token_hex(32))"`)
- `GOOGLE_API_KEY` - Google Gemini API key
- `QDRANT_URL` - Qdrant vector database endpoint URL
- `QDRANT_API_KEY` - Qdrant API key
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_KEY` - Supabase anonymous key
- `SUPABASE_SERVICE_KEY` - Supabase service role key
- `APP_URL` - Your application's public URL (e.g., `https://your-app.ondigitalocean.app`)
- `GEMINI_MODEL` - Gemini model name (optional, defaults to `gemini-2.5-flash`)
- `COLLECTION_NAME` - Qdrant collection name (optional, defaults to `naga_ordinances`)

See `.env.example` for all configurable environment variables.

### Deploy to Digital Ocean

1. **Connect your GitHub repository:**
   - Go to Digital Ocean App Platform
   - Click "Create App"
   - Select your GitHub repository
   - Choose the main branch

2. **Configure the app:**
   - The `.do/app.yaml` file will be auto-detected
   - Add all required secrets in the "Environment" section of the dashboard
   - Configure resource allocation (basic-s recommended for testing)

3. **Deploy:**
   - Click "Deploy" and Digital Ocean will build and deploy your application
   - The app will be available at `https://<app-name>.ondigitalocean.app`

### Health Checks

The application includes a `/health` endpoint for monitoring:
```bash
curl https://your-app-url.ondigitalocean.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-15T10:30:00.000000",
  "service": "Adal Smart Naga Ordinances RAG Chatbot"
}
```

### Local Testing with Docker

To test the Docker build locally:

```bash
# Build the image
docker build -t adal-naga:latest .

# Run with environment variables
docker run -p 8080:8080 \
  -e SECRET_KEY="test-secret-key" \
  -e GOOGLE_API_KEY="your-api-key" \
  -e QDRANT_URL="your-qdrant-url" \
  -e QDRANT_API_KEY="your-api-key" \
  -e SUPABASE_URL="your-supabase-url" \
  -e SUPABASE_KEY="your-key" \
  -e SUPABASE_SERVICE_KEY="your-service-key" \
  -e APP_URL="http://localhost:8080" \
  adal-naga:latest

# Access at http://localhost:8080
```

### Troubleshooting

**Application won't start:**
- Check that all required environment variables are set
- View logs in Digital Ocean App Platform dashboard
- Ensure `SECRET_KEY` is set (it's required for security)

**Database connection issues:**
- Verify Supabase credentials are correct
- Check that Supabase project is active and accessible
- Ensure service key has appropriate permissions

**RAG/Vector database issues:**
- Verify Qdrant endpoint and API key are correct
- Check that the `index/` directory is properly bundled in the Docker image
- Ensure collection name matches your Qdrant setup

**Health check failing:**
- The `/health` endpoint should respond even if other services are unavailable
- If it fails, check application startup logs
- Verify port 8080 is properly exposed

## Features

- Real-time chat interface
- User-friendly design
- Easy to extend and modify
- Production-ready deployment configuration
- Health monitoring and checks

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.