from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    # SECRET_KEY MUST be set in environment for production
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set. This is required for session security.")
    
    # Debug mode - explicitly controlled via environment, default to False for safety
    DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
    
    # Google API Configuration
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    
    # Qdrant Vector Database Configuration
    QDRANT_URL = os.getenv('QDRANT_URL')
    QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
    COLLECTION_NAME = os.getenv('COLLECTION_NAME', 'naga_ordinances')
    
    # Embedding Model Configuration
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    
    # Data Directory (for BM25 index) - baked into Docker image at /app/index
    DATA_DIR = os.getenv('DATA_DIR', '/app/index')
    
    # RAG Configuration
    TOP_K = 5  # Number of results to retrieve
    SEMANTIC_WEIGHT = 0.7  # Weight for semantic search
    BM25_WEIGHT = 0.3  # Weight for BM25 search
    
    # Supabase Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
    
    # Application URL - must be set for production
    APP_URL = os.getenv('APP_URL', 'http://localhost:5000')
    
    # Allowed email domains for CSPC
    ALLOWED_EMAIL_DOMAINS = ['@cspc.edu.ph', '@my.cspc.edu.ph']
    
    # Admin Configuration
    ADMIN_EMAILS = [
        'admin@cspc.edu.ph',
        'heavila@my.cspc.edu.ph'
        # Add more admin emails here
    ]