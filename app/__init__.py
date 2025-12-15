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
        print("🔧 Initializing Ordinance RAG Service...")
        from .rag_service import initialize_rag_service
        
        # Verify configuration
        required_configs = ['QDRANT_URL', 'QDRANT_API_KEY', 'COLLECTION_NAME', 'DATA_DIR']
        missing_configs = [cfg for cfg in required_configs if not app.config.get(cfg)]
        
        if missing_configs:
            print(f"⚠️  Missing configuration: {', '.join(missing_configs)}")
            print(f"� Current config values:")
            for cfg in required_configs:
                value = app.config.get(cfg)
                if value:
                    print(f"   {cfg}: {str(value)[:50]}...")
                else:
                    print(f"   {cfg}: NOT SET")
            raise ValueError(f"Missing required configuration: {', '.join(missing_configs)}")
        
        # Initialize RAG service
        rag_service = initialize_rag_service(app)
        app.config['RAG_SERVICE'] = rag_service
        
        print("✅ Ordinance RAG Service initialized successfully")
        print(f"   Collection: {app.config['COLLECTION_NAME']}")
        print(f"   Data directory: {app.config['DATA_DIR']}")
        
    except Exception as e:
        print(f"❌ Failed to initialize RAG service: {str(e)}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        print("⚠️  App will continue but RAG features may not work")
        app.config['RAG_SERVICE'] = None
    
    # Initialize Analytics Service
    try:
        print("🔧 Initializing Analytics Service...")
        from .analytics_service import initialize_analytics_service
        
        analytics_service = initialize_analytics_service(app)
        app.config['ANALYTICS_SERVICE'] = analytics_service
        
        print("✅ Analytics Service initialized successfully")
        
    except Exception as e:
        print(f"❌ Failed to initialize Analytics service: {str(e)}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        print("⚠️  App will continue but analytics features may not work")
        app.config['ANALYTICS_SERVICE'] = None
    
    # Register blueprints
    with app.app_context():
        from . import routes
        app.register_blueprint(routes.bp)
    
    return app