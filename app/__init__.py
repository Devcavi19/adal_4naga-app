from flask import Flask
from config import Config
import os
import traceback

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize Supabase Auth
    try:
        from .auth_service import auth_service
        auth_service.init_app(app)
        print("✅ Supabase authentication initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Supabase auth: {str(e)}")
    
    # Verify GOOGLE_API_KEY is loaded
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("❌ GOOGLE_API_KEY not found in environment variables")
        raise ValueError("GOOGLE_API_KEY not found in environment variables")
    
    print(f"✅ Google API Key loaded: {google_api_key[:20]}...")
    
    # Set the API key in environment for Google services
    os.environ["GOOGLE_API_KEY"] = google_api_key
    
    # Initialize Ordinance RAG Service
    try:
        import time
        start_time = time.time()
        print("[RAG] Starting Ordinance RAG Service initialization...")
        from .rag_service import initialize_rag_service
        
        # Verify configuration
        required_configs = ['QDRANT_URL', 'QDRANT_API_KEY', 'COLLECTION_NAME', 'DATA_DIR']
        missing_configs = [cfg for cfg in required_configs if not app.config.get(cfg)]
        
        if missing_configs:
            print(f"[RAG] Missing configuration: {', '.join(missing_configs)}")
            print(f"[RAG] Current config values:")
            for cfg in required_configs:
                value = app.config.get(cfg)
                if value:
                    print(f"   {cfg}: {str(value)[:50]}...")
                else:
                    print(f"   {cfg}: NOT SET")
            raise ValueError(f"Missing required configuration: {', '.join(missing_configs)}")
        
        # Initialize RAG service
        print("[RAG] Connecting to Qdrant vector database...")
        rag_service = initialize_rag_service(app)
        app.config['RAG_SERVICE'] = rag_service
        
        elapsed = time.time() - start_time
        print(f"[RAG] Ordinance RAG Service initialized successfully ({elapsed:.2f}s)")
        print(f"   Collection: {app.config['COLLECTION_NAME']}")
        print(f"   Data directory: {app.config['DATA_DIR']}")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[RAG] Failed to initialize RAG service after {elapsed:.2f}s: {str(e)}")
        print(f"[RAG] Traceback: {traceback.format_exc()}")
        print("[RAG] App will continue but RAG features may not work")
        app.config['RAG_SERVICE'] = None
    
    # Initialize Analytics Service
    try:
        import time
        start_time = time.time()
        print("[ANALYTICS] Starting Analytics Service initialization...")
        from .analytics_service import initialize_analytics_service
        
        analytics_service = initialize_analytics_service(app)
        app.config['ANALYTICS_SERVICE'] = analytics_service
        
        elapsed = time.time() - start_time
        print(f"[ANALYTICS] Analytics Service initialized successfully ({elapsed:.2f}s)")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[ANALYTICS] Failed to initialize Analytics service after {elapsed:.2f}s: {str(e)}")
        print(f"[ANALYTICS] Traceback: {traceback.format_exc()}")
        print("[ANALYTICS] App will continue but analytics features may not work")
        app.config['ANALYTICS_SERVICE'] = None
    
    # Mark initialization as complete for health checks
    app.config['SERVICES_INITIALIZED'] = True
    
    # Register blueprints
    with app.app_context():
        from . import routes
        app.register_blueprint(routes.bp)
    
    return app