from flask import Flask
from config import Config
import os
import traceback
import time

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    print("\n" + "="*80)
    print("STARTUP DIAGNOSTICS")
    print("="*80)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("\nCritical Environment Variables:")
    critical_vars = ['GOOGLE_API_KEY', 'QDRANT_URL', 'QDRANT_API_KEY', 'SECRET_KEY']
    for var in critical_vars:
        value = os.getenv(var)
        status = "SET" if value else "MISSING"
        print(f"  {var}: {status}")
    print("\nOptional Environment Variables:")
    optional_vars = ['SUPABASE_URL', 'SUPABASE_KEY']
    for var in optional_vars:
        value = os.getenv(var)
        status = "SET" if value else "not set"
        print(f"  {var}: {status}")
    print("="*80 + "\n")
    
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
        print("⚠️  RAG service will not be initialized")
        app.config['RAG_SERVICE'] = None
        app.config['ANALYTICS_SERVICE'] = None
        app.config['SERVICES_INITIALIZED'] = True
    else:
        print(f"✅ Google API Key loaded")
        os.environ["GOOGLE_API_KEY"] = google_api_key
        
        # Initialize Ordinance RAG Service
        try:
            start_time = time.time()
            print("\n[RAG] Starting RAG Service initialization...")
            from .rag_service import initialize_rag_service
            
            required_configs = ['QDRANT_URL', 'QDRANT_API_KEY', 'COLLECTION_NAME', 'DATA_DIR']
            missing_configs = [cfg for cfg in required_configs if not app.config.get(cfg)]
            
            if missing_configs:
                print(f"[RAG] Missing config: {', '.join(missing_configs)}")
                raise ValueError(f"Missing required configuration: {', '.join(missing_configs)}")
            
            print(f"[RAG] Testing Qdrant connectivity...")
            qdrant_url = app.config.get('QDRANT_URL')
            qdrant_key = app.config.get('QDRANT_API_KEY')
            
            for attempt in range(1, 4):
                try:
                    import requests
                    headers = {"api-key": qdrant_key} if qdrant_key else {}
                    response = requests.head(qdrant_url, headers=headers, timeout=5)
                    print(f"[RAG] ✓ Qdrant connectivity OK")
                    break
                except requests.exceptions.Timeout:
                    print(f"[RAG] ⚠️  Timeout (attempt {attempt}/3)")
                except Exception as e:
                    print(f"[RAG] ⚠️  Connection failed: {str(e)[:60]} (attempt {attempt}/3)")
                if attempt < 3:
                    time.sleep(2)
            
            print("[RAG] Initializing RAG service...")
            rag_service = initialize_rag_service(app)
            app.config['RAG_SERVICE'] = rag_service
            
            elapsed = time.time() - start_time
            print(f"[RAG] ✅ RAG Service initialized ({elapsed:.2f}s)")
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[RAG] ❌ Failed after {elapsed:.2f}s: {type(e).__name__}: {str(e)[:100]}")
            print(f"[RAG] Full traceback: {traceback.format_exc()[:500]}")
            app.config['RAG_SERVICE'] = None
        
        # Initialize Analytics Service
        try:
            start_time = time.time()
            print("\n[ANALYTICS] Starting Analytics Service initialization...")
            from .analytics_service import initialize_analytics_service
            
            analytics_service = initialize_analytics_service(app)
            app.config['ANALYTICS_SERVICE'] = analytics_service
            
            elapsed = time.time() - start_time
            print(f"[ANALYTICS] ✅ Analytics Service initialized ({elapsed:.2f}s)")
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[ANALYTICS] ❌ Failed after {elapsed:.2f}s: {type(e).__name__}")
            print(f"[ANALYTICS] ⚠️  Analytics is optional - continuing without it")
            app.config['ANALYTICS_SERVICE'] = None
    
    app.config['SERVICES_INITIALIZED'] = True
    print("\n✅ Application initialization complete")
    print("="*80 + "\n")
    
    # Register blueprints
    with app.app_context():
        from . import routes
        app.register_blueprint(routes.bp)
    
    return app