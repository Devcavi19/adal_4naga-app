from flask import Flask
from config import Config
import os
import traceback
import time
import threading
from datetime import datetime

# Global initialization state tracker
_init_state = {
    'status': 'not_started',  # not_started, initializing, complete, error
    'message': '',
    'services': {
        'supabase': {'status': 'pending', 'time_ms': 0},
        'rag': {'status': 'pending', 'time_ms': 0},
        'analytics': {'status': 'pending', 'time_ms': 0}
    },
    'error_details': None,
    'started_at': None,
    'completed_at': None
}

def get_init_state():
    """Return current initialization state"""
    return _init_state.copy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Store init state in app config for access from routes
    app.config['INIT_STATE'] = _init_state
    
    print("\n" + "="*80)
    print("STARTUP DIAGNOSTICS")
    print("="*80)
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
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
    
    # Initialize startup state
    _init_state['status'] = 'initializing'
    _init_state['started_at'] = datetime.utcnow().isoformat() + 'Z'
    
    # Initialize Supabase Auth (synchronously - required before app can serve)
    try:
        start_time = time.time()
        from .auth_service import auth_service
        auth_service.init_app(app)
        elapsed_ms = int((time.time() - start_time) * 1000)
        _init_state['services']['supabase']['status'] = 'complete'
        _init_state['services']['supabase']['time_ms'] = elapsed_ms
        print(f"✅ Supabase authentication initialized ({elapsed_ms}ms)")
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        _init_state['services']['supabase']['status'] = 'failed'
        _init_state['services']['supabase']['time_ms'] = elapsed_ms
        print(f"❌ Failed to initialize Supabase auth: {str(e)}")
    
    # Verify GOOGLE_API_KEY is loaded
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("⚠️  GOOGLE_API_KEY not found in environment variables")
        print("⚠️  RAG and Analytics services will not be initialized")
        app.config['RAG_SERVICE'] = None
        app.config['ANALYTICS_SERVICE'] = None
        _init_state['services']['rag']['status'] = 'disabled'
        _init_state['services']['analytics']['status'] = 'disabled'
        _init_state['status'] = 'complete'
        _init_state['completed_at'] = datetime.utcnow().isoformat() + 'Z'
    else:
        print(f"✅ Google API Key loaded")
        os.environ["GOOGLE_API_KEY"] = google_api_key
        
        # Start RAG and Analytics initialization in background threads (non-blocking)
        def initialize_rag_async():
            """Initialize RAG service in background"""
            try:
                start_time = time.time()
                _init_state['services']['rag']['status'] = 'initializing'
                print("\n[RAG] Starting RAG Service initialization in background thread...")
                from .rag_service import initialize_rag_service
                
                required_configs = ['QDRANT_URL', 'QDRANT_API_KEY', 'COLLECTION_NAME', 'DATA_DIR']
                missing_configs = [cfg for cfg in required_configs if not app.config.get(cfg)]
                
                if missing_configs:
                    error_msg = f"Missing required configuration: {', '.join(missing_configs)}"
                    print(f"[RAG] ❌ {error_msg}")
                    _init_state['services']['rag']['status'] = 'failed'
                    _init_state['error_details'] = error_msg
                    return
                
                print(f"[RAG] Testing Qdrant connectivity...")
                qdrant_url = app.config.get('QDRANT_URL')
                qdrant_key = app.config.get('QDRANT_API_KEY')
                
                qdrant_ok = False
                for attempt in range(1, 6):
                    try:
                        import requests
                        headers = {"api-key": qdrant_key} if qdrant_key else {}
                        response = requests.head(qdrant_url, headers=headers, timeout=5)
                        print(f"[RAG] ✓ Qdrant connectivity OK (HTTP {response.status_code})")
                        qdrant_ok = True
                        break
                    except requests.exceptions.Timeout:
                        print(f"[RAG] ⚠️  Timeout (attempt {attempt}/5)")
                    except Exception as e:
                        print(f"[RAG] ⚠️  Connection failed: {str(e)[:60]} (attempt {attempt}/5)")
                    if attempt < 5:
                        time.sleep(3)
                
                if not qdrant_ok:
                    print("[RAG] ❌ Could not connect to Qdrant after 5 attempts")
                    _init_state['services']['rag']['status'] = 'failed'
                    _init_state['error_details'] = 'Qdrant connection failed'
                    return
                
                print("[RAG] Initializing RAG service...")
                rag_service = initialize_rag_service(app)
                app.config['RAG_SERVICE'] = rag_service
                
                elapsed = time.time() - start_time
                elapsed_ms = int(elapsed * 1000)
                _init_state['services']['rag']['status'] = 'complete'
                _init_state['services']['rag']['time_ms'] = elapsed_ms
                print(f"[RAG] ✅ RAG Service initialized ({elapsed_ms}ms)")
                
            except Exception as e:
                elapsed = time.time() - start_time
                elapsed_ms = int(elapsed * 1000)
                _init_state['services']['rag']['status'] = 'failed'
                _init_state['services']['rag']['time_ms'] = elapsed_ms
                print(f"[RAG] ❌ Failed after {elapsed_ms}ms: {type(e).__name__}: {str(e)[:100]}")
                print(f"[RAG] Traceback: {traceback.format_exc()[:500]}")
                app.config['RAG_SERVICE'] = None
                _init_state['error_details'] = f"{type(e).__name__}: {str(e)[:100]}"
        
        def initialize_analytics_async():
            """Initialize Analytics service in background"""
            try:
                start_time = time.time()
                _init_state['services']['analytics']['status'] = 'initializing'
                print("\n[ANALYTICS] Starting Analytics Service initialization in background thread...")
                from .analytics_service import initialize_analytics_service
                
                analytics_service = initialize_analytics_service(app)
                app.config['ANALYTICS_SERVICE'] = analytics_service
                
                elapsed = time.time() - start_time
                elapsed_ms = int(elapsed * 1000)
                _init_state['services']['analytics']['status'] = 'complete'
                _init_state['services']['analytics']['time_ms'] = elapsed_ms
                print(f"[ANALYTICS] ✅ Analytics Service initialized ({elapsed_ms}ms)")
                
            except Exception as e:
                elapsed = time.time() - start_time
                elapsed_ms = int(elapsed * 1000)
                _init_state['services']['analytics']['status'] = 'failed'
                _init_state['services']['analytics']['time_ms'] = elapsed_ms
                print(f"[ANALYTICS] ❌ Failed after {elapsed_ms}ms: {type(e).__name__}")
                print(f"[ANALYTICS] ⚠️  Analytics is optional - continuing without it")
                app.config['ANALYTICS_SERVICE'] = None
        
        # Start background initialization threads
        rag_thread = threading.Thread(target=initialize_rag_async, daemon=True, name='RAG-Init')
        analytics_thread = threading.Thread(target=initialize_analytics_async, daemon=True, name='Analytics-Init')
        
        rag_thread.start()
        analytics_thread.start()
        
        print("\n[MAIN] Background initialization threads started (non-blocking)")
    
    # Mark services as initialized at main thread level (even if background threads still running)
    app.config['SERVICES_INITIALIZED'] = True
    print("\n✅ Application ready to accept requests (services initializing in background)")
    print("="*80 + "\n")
    
    # Register blueprints
    with app.app_context():
        from . import routes
        app.register_blueprint(routes.bp)
    
    return app