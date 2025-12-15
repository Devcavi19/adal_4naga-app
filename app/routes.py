from flask import Blueprint, render_template, request, jsonify, Response, current_app, redirect, url_for, session
import json
import time
import traceback
import threading
from functools import wraps
from datetime import datetime, timedelta

bp = Blueprint('main', __name__)

# Health check endpoint for monitoring (no authentication required)
@bp.route('/health')
def health():
    """Health check endpoint for deployment monitoring"""
    rag_service = current_app.config.get('RAG_SERVICE')
    analytics_service = current_app.config.get('ANALYTICS_SERVICE')
    
    # Check if critical services are initialized
    services_status = {
        'rag_service': rag_service is not None,
        'analytics_service': analytics_service is not None
    }
    
    # All critical services must be initialized for app to be healthy
    is_healthy = all(services_status.values())
    status_code = 200 if is_healthy else 503
    
    return jsonify({
        'status': 'healthy' if is_healthy else 'degraded',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'Adal Smart Naga Ordinances RAG Chatbot',
        'services': services_status
    }), status_code

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_role = session.get('user', {}).get('role', 'user')
        if user_role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    return render_template('chat.html')

@bp.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('main.chat'))
    return render_template('login.html')

@bp.route('/signup')
def signup():
    if 'user' in session:
        return redirect(url_for('main.chat'))
    return render_template('signup.html')

@bp.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@bp.route('/charter')
def charter():
    """Charter page"""
    return render_template('charter.html')

@bp.route('/pricing')
def pricing():
    """Pricing page"""
    return render_template('pricing.html')

# Authentication API Routes
@bp.route('/api/auth/signup', methods=['POST'])
def api_signup():
    """Handle email signup"""
    from .auth_service import auth_service
    
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    result, status_code = auth_service.sign_up_with_email(email, password, full_name)
    return jsonify(result), status_code

@bp.route('/api/auth/signin', methods=['POST'])
def api_signin():
    """Handle email signin"""
    from .auth_service import auth_service
    
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    result, status_code = auth_service.sign_in_with_email(email, password)
    
    if status_code == 200:
        session['user'] = result['user']
        session['access_token'] = result['session']['access_token']
    
    return jsonify(result), status_code

@bp.route('/api/auth/google')
def api_google_auth():
    """Get Google OAuth URL"""
    from .auth_service import auth_service
    
    result, status_code = auth_service.sign_in_with_google()
    return jsonify(result), status_code

@bp.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback - both hash fragment and query params"""
    from .auth_service import auth_service
    
    # Check for authorization code in query params (OAuth flow)
    code = request.args.get('code')
    
    if code:
        # Exchange code for session
        result, status_code = auth_service.exchange_code_for_session(code)
        
        if status_code == 200:
            session['user'] = result['user']
            session['access_token'] = result['session']['access_token']
            return redirect(url_for('main.chat'))
        else:
            return redirect(url_for('main.login', error='auth_failed'))
    
    # Otherwise render callback page to handle hash fragment
    return render_template('auth_callback.html')

@bp.route('/api/auth/callback/session', methods=['POST'])
def api_callback_session():
    """Handle session creation from OAuth callback"""
    from .auth_service import auth_service
    
    data = request.get_json()
    access_token = data.get('access_token')
    
    if not access_token:
        return jsonify({'error': 'Access token required'}), 400
    
    # Get user info from token
    result, status_code = auth_service.get_user(access_token)
    
    if status_code == 200:
        session['user'] = result['user']
        session['access_token'] = access_token
        return jsonify({'success': True, 'redirect': '/chat'}), 200
    
    return jsonify({'error': 'Failed to get user info'}), status_code

@bp.route('/api/auth/signout', methods=['POST'])
def api_signout():
    """Handle signout"""
    from .auth_service import auth_service
    
    session.clear()
    result, status_code = auth_service.sign_out()
    return jsonify(result), status_code

@bp.route('/api/auth/user', methods=['GET'])
def api_get_user():
    """Get current user"""
    if 'user' in session:
        return jsonify({'user': session['user']}), 200
    return jsonify({'error': 'Not authenticated'}), 401

# Chat API Routes - WITH CONVERSATION MEMORY
@bp.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    """Handle chat messages with conversation memory and streaming"""
    from .rag_service import is_allowed, format_chat_history, get_rag_service
    from .auth_service import auth_service
    from .analytics_service import get_analytics_service
    from datetime import datetime, timedelta
    
    # Analytics tracking variables
    request_start_time = time.time()
    analytics_data = {
        'user_id': None,
        'chat_session_id': None,
        'query_text': None,
        'response_time_ms': None,
        'documents_retrieved': 0,
        'search_method': 'hybrid',
        'hybrid_score': None,
        'tokens_used': 0,
        'keywords': []
    }
    
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        chat_id = data.get('chat_id', None)
        
        # Store for analytics
        analytics_data['query_text'] = user_message
        
        print(f"📨 Received message: {user_message[:100]}...")
        
        if not is_allowed(user_message):
            return jsonify({'error': 'Sorry, I can\'t assist with that.'}), 400
        
        user_id = session.get('user', {}).get('id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Store for analytics
        analytics_data['user_id'] = user_id
        
        # Create new chat session if needed
        if not chat_id:
            title = user_message[:50] + ('...' if len(user_message) > 50 else '')
            chat_session, status = auth_service.create_chat_session(user_id, title)
            
            if status != 200:
                print(f"❌ Failed to create chat session: {chat_session}")
                return jsonify({'error': 'Failed to create chat session'}), 500
            
            chat_id = chat_session['id']
            print(f"✅ Created new chat session: {chat_id}")
        
        # Store for analytics
        analytics_data['chat_session_id'] = chat_id
        
        # Fetch conversation history from database
        messages, status = auth_service.get_chat_messages(chat_id)
        
        chat_history = ""
        if status == 200 and messages:
            # Format last 5 exchanges for context (limit to prevent token overflow)
            chat_history = format_chat_history(messages, max_exchanges=5)
            print(f"📚 Loaded {len(messages)} total messages, using last {min(10, len(messages))} for context")
        else:
            print(f"📚 No previous conversation history")
        
        # Get RAG service
        try:
            rag_service = get_rag_service()
        except RuntimeError:
            print("⚠️  RAG service not available, using fallback")
            def generate_fallback():
                yield json.dumps({'chat_id': chat_id}) + '\n'
                response = "I apologize, but the AI system is currently unavailable. Please try again later."
                for char in response:
                    yield json.dumps({'token': char}) + '\n'
                    time.sleep(0.03)
                yield json.dumps({'done': True, 'error': 'system_unavailable'}) + '\n'
            
            return Response(generate_fallback(), mimetype='application/json')
        
        bot_response = ""
        stream_error = None
        
        def save_messages_and_analytics_async():
            """Save messages and analytics to database in background thread AFTER streaming completes"""
            try:
                print(f"💾 Saving messages to database in background...")
                
                # Save user message
                msg_result, msg_status = auth_service.save_chat_message(chat_id, 'user', user_message)
                if msg_status == 200:
                    print(f"✅ User message saved")
                else:
                    print(f"⚠️  Failed to save user message: {msg_result}")
                
                # Save bot response (even if partial due to error)
                if bot_response:
                    msg_result, msg_status = auth_service.save_chat_message(chat_id, 'bot', bot_response)
                    if msg_status == 200:
                        print(f"✅ Bot response saved ({len(bot_response)} chars)")
                    else:
                        print(f"⚠️  Failed to save bot response: {msg_result}")
                
                # Save analytics data
                try:
                    analytics_service = get_analytics_service()
                    
                    # Calculate response time
                    response_time_ms = int((time.time() - request_start_time) * 1000)
                    analytics_data['response_time_ms'] = response_time_ms
                    analytics_data['tokens_used'] = len(bot_response)  # Approximate
                    
                    # Extract keywords
                    keywords = analytics_service.extract_keywords_tfidf(user_message, top_n=10)
                    analytics_data['keywords'] = keywords
                    
                    # Prepare analytics record
                    analytics_record = {
                        'user_id': analytics_data['user_id'],
                        'chat_session_id': analytics_data['chat_session_id'],
                        'query_text': analytics_data['query_text'],
                        'keywords': analytics_data['keywords'],
                        'response_time_ms': analytics_data['response_time_ms'],
                        'documents_retrieved': analytics_data['documents_retrieved'],
                        'search_method': analytics_data['search_method'],
                        'hybrid_score': analytics_data['hybrid_score'],
                        'tokens_used': analytics_data['tokens_used'],
                        'expires_at': (datetime.utcnow() + timedelta(days=90)).isoformat()
                    }
                    
                    # Insert to database
                    auth_service.admin_supabase.table('query_analytics').insert(analytics_record).execute()
                    print(f"✅ Analytics saved: {response_time_ms}ms, {analytics_data['documents_retrieved']} docs")
                    
                except Exception as analytics_error:
                    print(f"⚠️  Failed to save analytics: {str(analytics_error)}")
                        
            except Exception as e:
                print(f"❌ Error saving messages in background: {str(e)}")
                print(f"📋 Traceback: {traceback.format_exc()}")
        
        def generate():
            nonlocal bot_response, stream_error
            try:
                print(f"🔄 Starting streaming with hybrid search...")
                chunk_count = 0
                start_time = time.time()
                max_chunks = 10000  # Safety limit to prevent infinite loops
                last_chunk_time = start_time
                
                # Send chat_id FIRST - immediate flush
                yield json.dumps({'chat_id': chat_id}) + '\n'
                
                # Perform hybrid search to get context
                print(f"🔍 Performing hybrid search...")
                context = rag_service.hybrid_search(user_message)
                print(f"📄 Retrieved {len(context)} documents from hybrid search")
                
                # Track analytics data
                analytics_data['documents_retrieved'] = len(context)
                if context and len(context) > 0:
                    # Get average hybrid score
                    scores = [doc.get('hybrid_score', 0) for doc in context if 'hybrid_score' in doc]
                    if scores:
                        analytics_data['hybrid_score'] = sum(scores) / len(scores)
                
                # Stream the response with monitoring
                for chunk in rag_service.generate_response_streaming(user_message, context, chat_history):
                    if chunk:
                        bot_response += chunk
                        chunk_count += 1
                        current_time = time.time()
                        
                        # Safety check for max chunks
                        if chunk_count > max_chunks:
                            print(f"⚠️  Hit max chunk limit ({max_chunks}) - stopping stream")
                            stream_error = "response_too_long"
                            break
                        
                        # Timeout check (if no chunks for 30 seconds)
                        if current_time - last_chunk_time > 30:
                            print(f"⚠️  Stream timeout - no chunks for 30s")
                            stream_error = "stream_timeout"
                            break
                        
                        last_chunk_time = current_time
                        
                        # Yield each token immediately - no buffering
                        yield json.dumps({'token': chunk}) + '\n'
                        
                        # Log progress every 100 chunks
                        if chunk_count % 100 == 0:
                            elapsed = current_time - start_time
                            print(f"📊 Progress: {chunk_count} chunks, {len(bot_response)} chars, {elapsed:.1f}s")
                
                elapsed_time = time.time() - start_time
                print(f"✅ Stream completed: {chunk_count} chunks, {len(bot_response)} chars in {elapsed_time:.2f}s")
                
                # Send completion signal with metadata
                completion_data = {
                    'done': True,
                    'chunks': chunk_count,
                    'chars': len(bot_response),
                    'time': round(elapsed_time, 2)
                }
                
                if stream_error:
                    completion_data['warning'] = stream_error
                    print(f"⚠️  Stream completed with warning: {stream_error}")
                
                yield json.dumps(completion_data) + '\n'
                
                # Save to database AFTER streaming completes (in background thread)
                threading.Thread(target=save_messages_and_analytics_async, daemon=True).start()
                
            except Exception as e:
                # Better error handling with actual error message
                error_type = type(e).__name__
                error_msg = str(e)
                print(f"❌ Error in RAG service ({error_type}): {error_msg}")
                print(f"📋 Traceback: {traceback.format_exc()}")
                
                # If we have partial response, send it
                if bot_response:
                    print(f"⚠️  Sending partial response ({len(bot_response)} chars)")
                
                # Send error with details
                error_data = {
                    'error': 'An error occurred while generating the response.',
                    'error_type': error_type,
                    'done': True,
                    'partial': len(bot_response) > 0
                }
                
                # Don't expose internal errors to user, but log them
                if 'timeout' in error_msg.lower():
                    error_data['user_message'] = 'The request took too long. Please try a simpler question.'
                elif 'rate' in error_msg.lower() or 'quota' in error_msg.lower():
                    error_data['user_message'] = 'The service is currently busy. Please try again in a moment.'
                else:
                    error_data['user_message'] = 'An unexpected error occurred. Please try again.'
                
                yield json.dumps(error_data) + '\n'
                
                # Still save partial response if available
                if bot_response:
                    threading.Thread(target=save_messages_and_analytics_async, daemon=True).start()
                
                # Log error to error_logs table
                try:
                    error_record = {
                        'user_id': analytics_data['user_id'],
                        'error_type': error_type,
                        'error_message': error_msg[:500],  # Limit length
                        'stack_trace': traceback.format_exc()[:2000],  # Limit length
                        'endpoint': '/api/chat',
                        'request_data': json.dumps({'message': user_message[:200]}),
                        'expires_at': (datetime.utcnow() + timedelta(days=90)).isoformat()
                    }
                    auth_service.admin_supabase.table('error_logs').insert(error_record).execute()
                except Exception as log_error:
                    print(f"⚠️  Failed to log error: {str(log_error)}")
        
        return Response(generate(), mimetype='application/json')
        
    except Exception as e:
        print(f"❌ Error in chat_api: {str(e)}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@bp.route('/api/chat/history', methods=['GET'])
@login_required
def get_chat_history():
    """Return chat history for student"""
    from .auth_service import auth_service
    
    user_id = session.get('user', {}).get('id')
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    sessions, status = auth_service.get_user_chat_sessions(user_id)
    
    if status == 200:
        return jsonify({'history': sessions})
    
    return jsonify({'error': 'Failed to load chat history'}), 500

@bp.route('/api/chat/<chat_id>', methods=['GET'])
@login_required
def get_chat(chat_id):
    """Get specific chat conversation"""
    from .auth_service import auth_service
    
    messages, status = auth_service.get_chat_messages(chat_id)
    
    if status == 200:
        return jsonify({'chat_id': chat_id, 'messages': messages})
    
    return jsonify({'error': 'Failed to load chat'}), 500

@bp.route('/api/chat/<chat_id>', methods=['DELETE'])
@login_required
def delete_chat(chat_id):
    """Delete a chat session"""
    from .auth_service import auth_service
    
    result, status = auth_service.delete_chat_session(chat_id)
    return jsonify(result), status

@bp.route('/api/chat/<chat_id>/title', methods=['PUT'])
@login_required
def update_chat_title(chat_id):
    """Update chat session title"""
    from .auth_service import auth_service
    
    data = request.get_json()
    title = data.get('title', '')
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    result, status = auth_service.update_chat_session_title(chat_id, title)
    return jsonify(result), status

@bp.route('/api/search', methods=['POST'])
@login_required
def search_documents():
    """Search for relevant ordinances using hybrid search"""
    from .rag_service import is_allowed, get_rag_service
    
    data = request.get_json()
    query = data.get('query', '')
    
    if not is_allowed(query):
        return jsonify({'error': 'Sorry, I can\'t assist with that.'}), 400
    
    try:
        rag_service = get_rag_service()
    except RuntimeError:
        return jsonify({'error': 'Search system unavailable'}), 503
    
    try:
        # Use hybrid search for better results
        results = rag_service.hybrid_search(query)
        
        formatted_results = []
        for result in results:
            formatted_results.append({
                'content': result['text'],
                'metadata': result['metadata'],
                'score': result.get('hybrid_score', 0),
                'sources': result.get('sources', [])
            })
        
        return jsonify({'results': formatted_results})
    
    except Exception as e:
        print(f"❌ Search error: {e}")
        return jsonify({'error': 'Search failed'}), 500

# ============================================
# Admin Dashboard API Routes
# ============================================

@bp.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard page"""
    user_role = session.get('user', {}).get('role', 'user')
    if user_role != 'admin':
        return redirect(url_for('main.chat'))
    return render_template('admin.html')

@bp.route('/api/feedback', methods=['POST'])
@login_required
def submit_feedback():
    """Submit user feedback on a bot response"""
    from .auth_service import auth_service
    
    try:
        data = request.get_json()
        chat_session_id = data.get('chat_session_id')
        chat_message_id = data.get('chat_message_id')  # Optional - for legacy support
        rating = data.get('rating')  # 1-5
        feedback_text = data.get('feedback_text', '')
        
        if not rating:
            return jsonify({'error': 'Rating is required'}), 400
        
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400
        
        user_id = session.get('user', {}).get('id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # If chat_message_id not provided, find the most recent bot message in the session
        if not chat_message_id and chat_session_id:
            messages_response = auth_service.admin_supabase.table('chat_messages')\
                .select('id')\
                .eq('chat_session_id', chat_session_id)\
                .eq('role', 'bot')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
            
            if messages_response.data and len(messages_response.data) > 0:
                chat_message_id = messages_response.data[0]['id']
            else:
                return jsonify({'error': 'No bot message found in this session'}), 404
        
        if not chat_message_id:
            return jsonify({'error': 'Could not identify message for feedback'}), 400
        
        # Insert feedback
        feedback_record = {
            'chat_message_id': chat_message_id,
            'user_id': user_id,
            'rating': rating,
            'feedback_text': feedback_text
        }
        
        auth_service.admin_supabase.table('user_feedback').insert(feedback_record).execute()
        
        return jsonify({'message': 'Feedback submitted successfully'}), 200
        
    except Exception as e:
        print(f"❌ Feedback submission error: {str(e)}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to submit feedback'}), 500

# ============================================
# Admin API Endpoints (with @admin_required)
# ============================================

def log_admin_action(action_type: str, resource: str, filters: dict = None):
    """Helper function to log admin actions"""
    try:
        from .auth_service import auth_service
        
        admin_id = session.get('user', {}).get('id')
        if not admin_id:
            return
        
        audit_record = {
            'admin_user_id': admin_id,
            'action_type': action_type,
            'resource_accessed': resource,
            'filters_applied': json.dumps(filters) if filters else None,
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')[:500]
        }
        
        auth_service.admin_supabase.table('admin_audit_log').insert(audit_record).execute()
        
    except Exception as e:
        print(f"⚠️  Failed to log admin action: {str(e)}")

@bp.route('/api/admin/analytics/overview', methods=['GET'])
@admin_required
def admin_analytics_overview():
    """Get dashboard overview statistics"""
    from .auth_service import auth_service
    from .analytics_service import get_analytics_service
    
    try:
        log_admin_action('view_dashboard', 'analytics_overview')
        
        analytics_service = get_analytics_service()
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)
        
        # Total queries (today, week, month)
        queries_today = auth_service.admin_supabase.table('query_analytics')\
            .select('id', count='exact')\
            .gte('created_at', today_start.isoformat())\
            .execute()
        
        queries_week = auth_service.admin_supabase.table('query_analytics')\
            .select('id', count='exact')\
            .gte('created_at', week_start.isoformat())\
            .execute()
        
        queries_month = auth_service.admin_supabase.table('query_analytics')\
            .select('id', count='exact')\
            .gte('created_at', month_start.isoformat())\
            .execute()
        
        # Active users (unique users who queried this week)
        active_users_response = auth_service.admin_supabase.table('query_analytics')\
            .select('user_id')\
            .gte('created_at', week_start.isoformat())\
            .execute()
        
        unique_users = len(set(r['user_id'] for r in active_users_response.data)) if active_users_response.data else 0
        
        # COMPETITION: Response time calculation temporarily hidden from UI for competition presentation.
        # NOTE: Database query_analytics.response_time_ms field continues collecting data.
        # Backend calculation preserved for post-competition analysis.
        # To reactivate: Uncomment lines below and line 723 avg_response_time_ms in overview_data dict.
        # Average response time (this week)
        # avg_response_response = auth_service.admin_supabase.table('query_analytics')\
        #     .select('response_time_ms')\
        #     .gte('created_at', week_start.isoformat())\
        #     .not_.is_('response_time_ms', 'null')\
        #     .execute()
        # 
        # avg_response_time = 0
        # if avg_response_response.data:
        #     times = [r['response_time_ms'] for r in avg_response_response.data]
        #     avg_response_time = sum(times) / len(times) if times else 0
        
        # Satisfaction rate (this week)
        feedback_response = auth_service.admin_supabase.table('user_feedback')\
            .select('rating')\
            .gte('created_at', week_start.isoformat())\
            .execute()
        
        satisfaction_rate = 0
        total_feedback = 0
        if feedback_response.data:
            ratings = [r['rating'] for r in feedback_response.data]
            total_feedback = len(ratings)
            positive_count = sum(1 for r in ratings if r >= 4)
            satisfaction_rate = (positive_count / total_feedback * 100) if total_feedback > 0 else 0
        
        # Top keywords (this week)
        top_keywords = analytics_service.compute_keyword_trends(hours=168)[:10]  # 7 days
        
        # Unread notifications
        notifications_response = auth_service.admin_supabase.table('admin_notifications')\
            .select('id', count='exact')\
            .eq('is_read', False)\
            .execute()
        
        overview_data = {
            'queries_today': queries_today.count if hasattr(queries_today, 'count') else 0,
            'queries_week': queries_week.count if hasattr(queries_week, 'count') else 0,
            'queries_month': queries_month.count if hasattr(queries_month, 'count') else 0,
            'active_users': unique_users,
            # COMPETITION: Temporarily hidden - uncomment to include in API response
            # 'avg_response_time_ms': round(avg_response_time, 0),
            'satisfaction_rate': round(satisfaction_rate, 1),
            'total_feedback': total_feedback,
            'top_keywords': top_keywords,
            'unread_notifications': notifications_response.count if hasattr(notifications_response, 'count') else 0
        }
        
        return jsonify(overview_data), 200
        
    except Exception as e:
        print(f"❌ Admin overview error: {str(e)}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to load overview'}), 500

@bp.route('/api/admin/analytics/queries', methods=['GET'])
@admin_required
def admin_analytics_queries():
    """Get query logs with filters"""
    from .auth_service import auth_service
    from .analytics_service import get_analytics_service
    
    try:
        # Get query parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        keyword = request.args.get('keyword')
        search_method = request.args.get('search_method')
        min_rating = request.args.get('min_rating')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        log_admin_action('view_queries', 'query_analytics', {
            'date_from': date_from,
            'date_to': date_to,
            'keyword': keyword,
            'search_method': search_method
        })
        
        analytics_service = get_analytics_service()
        
        # Build query
        query = auth_service.admin_supabase.table('query_analytics').select('*')
        
        if date_from:
            query = query.gte('created_at', date_from)
        if date_to:
            query = query.lte('created_at', date_to)
        if search_method:
            query = query.eq('search_method', search_method)
        
        # Execute query with pagination
        offset = (page - 1) * per_page
        response = query.order('created_at', desc=True).range(offset, offset + per_page - 1).execute()
        
        if not response.data:
            return jsonify({'queries': [], 'total': 0, 'page': page, 'per_page': per_page}), 200
        
        # Anonymize user data
        anonymized_queries = []
        for record in response.data:
            record['anonymized_user'] = analytics_service.anonymize_user(record['user_id'])
            record.pop('user_id', None)  # Remove actual user_id
            
            # Filter by keyword if specified
            if keyword:
                keywords = record.get('keywords', [])
                if not keywords or keyword.lower() not in [k.lower() for k in keywords]:
                    continue
            
            anonymized_queries.append(record)
        
        # Get total count (approximate)
        count_response = auth_service.admin_supabase.table('query_analytics').select('id', count='exact').execute()
        total_count = count_response.count if hasattr(count_response, 'count') else len(response.data)
        
        return jsonify({
            'queries': anonymized_queries,
            'total': total_count,
            'page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        print(f"❌ Admin queries error: {str(e)}")
        return jsonify({'error': 'Failed to load queries'}), 500

@bp.route('/api/admin/analytics/trends', methods=['GET'])
@admin_required
def admin_analytics_trends():
    """Get trend data for charts"""
    from .auth_service import auth_service
    
    try:
        log_admin_action('view_trends', 'analytics_trends')
        
        # Get queries per day for last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        response = auth_service.admin_supabase.table('query_analytics')\
            .select('created_at')\
            .gte('created_at', thirty_days_ago.isoformat())\
            .execute()
        
        if not response.data:
            return jsonify({'queries_per_day': [], 'queries_per_hour': []}), 200
        
        # Group by day
        from collections import defaultdict
        queries_by_day = defaultdict(int)
        queries_by_hour = defaultdict(int)
        
        for record in response.data:
            created_at_str = record['created_at']
            try:
                # Fix: Handle Supabase timestamp format with microseconds
                # Format: 2025-11-20T10:31:06.5996+00:00
                if '+' in created_at_str and '.' in created_at_str:
                    # Split on '.' to remove problematic microseconds
                    date_part, tz_part = created_at_str.split('.')
                    # Extract timezone from tz_part (e.g., "5996+00:00" -> "+00:00")
                    tz_offset = '+' + tz_part.split('+')[1] if '+' in tz_part else '+00:00'
                    created_at_str = date_part + tz_offset
                
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                day_key = created_at.strftime('%Y-%m-%d')
                hour_key = created_at.hour
                
                queries_by_day[day_key] += 1
                queries_by_hour[hour_key] += 1
            except Exception as parse_error:
                print(f"⚠️  Skipping invalid timestamp: {record['created_at']} - {str(parse_error)}")
                continue
        
        # Format for charts
        queries_per_day = [{'date': day, 'count': count} for day, count in sorted(queries_by_day.items())]
        queries_per_hour = [{'hour': hour, 'count': count} for hour, count in sorted(queries_by_hour.items())]
        
        return jsonify({
            'queries_per_day': queries_per_day,
            'queries_per_hour': queries_per_hour
        }), 200
        
    except Exception as e:
        print(f"❌ Admin trends error: {str(e)}")
        return jsonify({'error': 'Failed to load trends'}), 500

@bp.route('/api/admin/analytics/export/<export_type>', methods=['GET'])
@admin_required
def admin_analytics_export(export_type):
    """Export analytics data as CSV or JSON"""
    from .auth_service import auth_service
    from .analytics_service import get_analytics_service
    import pandas as pd
    from io import StringIO
    
    try:
        format_type = request.args.get('format', 'csv')  # csv or json
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        log_admin_action('export_data', f'{export_type}_{format_type}', {
            'date_from': date_from,
            'date_to': date_to
        })
        
        analytics_service = get_analytics_service()
        
        if export_type == 'queries':
            # Export query logs
            query = auth_service.admin_supabase.table('query_analytics').select('*')
            
            if date_from:
                query = query.gte('created_at', date_from)
            if date_to:
                query = query.lte('created_at', date_to)
            
            response = query.order('created_at', desc=True).limit(10000).execute()
            
            if not response.data:
                return jsonify({'error': 'No data to export'}), 404
            
            # Convert to DataFrame and anonymize
            df = pd.DataFrame(response.data)
            df['anonymized_user'] = df['user_id'].apply(analytics_service.anonymize_user)
            df = df.drop(columns=['user_id'])
            
        elif export_type == 'stats':
            # Export aggregated statistics
            # Get daily summaries
            response = auth_service.admin_supabase.table('analytics_summary_daily')\
                .select('*')\
                .order('summary_date', desc=True)\
                .limit(365)\
                .execute()
            
            if not response.data:
                return jsonify({'error': 'No stats to export'}), 404
            
            df = pd.DataFrame(response.data)
        else:
            return jsonify({'error': 'Invalid export type'}), 400
        
        # Generate export
        if format_type == 'csv':
            output = StringIO()
            df.to_csv(output, index=False)
            csv_data = output.getvalue()
            
            return Response(
                csv_data,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename={export_type}_{datetime.utcnow().strftime("%Y%m%d")}.csv'}
            )
        else:  # json
            json_data = df.to_json(orient='records', date_format='iso')
            
            return Response(
                json_data,
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment; filename={export_type}_{datetime.utcnow().strftime("%Y%m%d")}.json'}
            )
        
    except Exception as e:
        print(f"❌ Export error: {str(e)}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Export failed'}), 500

@bp.route('/api/admin/notifications', methods=['GET'])
@admin_required
def admin_get_notifications():
    """Get admin notifications"""
    from .auth_service import auth_service
    
    try:
        is_read = request.args.get('is_read')
        
        query = auth_service.admin_supabase.table('admin_notifications').select('*')
        
        if is_read is not None:
            query = query.eq('is_read', is_read.lower() == 'true')
        
        response = query.order('created_at', desc=True).limit(50).execute()
        
        return jsonify({'notifications': response.data}), 200
        
    except Exception as e:
        print(f"❌ Notifications error: {str(e)}")
        return jsonify({'error': 'Failed to load notifications'}), 500

@bp.route('/api/admin/notifications/<notification_id>/mark-read', methods=['PUT'])
@admin_required
def admin_mark_notification_read(notification_id):
    """Mark notification as read"""
    from .auth_service import auth_service
    
    try:
        auth_service.admin_supabase.table('admin_notifications')\
            .update({'is_read': True})\
            .eq('id', notification_id)\
            .execute()
        
        return jsonify({'message': 'Notification marked as read'}), 200
        
    except Exception as e:
        print(f"❌ Mark notification error: {str(e)}")
        return jsonify({'error': 'Failed to update notification'}), 500

@bp.route('/api/admin/users/activity', methods=['GET'])
@admin_required
def admin_user_activity():
    """Get anonymized user activity statistics"""
    from .auth_service import auth_service
    from .analytics_service import get_analytics_service
    
    try:
        log_admin_action('view_users', 'user_activity')
        
        analytics_service = get_analytics_service()
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Get user activity data
        df = analytics_service.get_anonymized_user_data(date_from, date_to)
        
        if df.empty:
            return jsonify({'users': []}), 200
        
        # Group by user and aggregate
        # COMPETITION: response_time_ms aggregation temporarily hidden from UI.
        # Database continues collecting data. To reactivate: uncomment response_time_ms lines below.
        user_stats = df.groupby('anonymized_user').agg({
            'created_at': 'count',
            # 'response_time_ms': 'mean'
        }).rename(columns={
            'created_at': 'query_count',
            # 'response_time_ms': 'avg_response_time'
        }).reset_index()
        
        user_stats = user_stats.to_dict('records')
        
        return jsonify({'users': user_stats}), 200
        
    except Exception as e:
        print(f"❌ User activity error: {str(e)}")
        return jsonify({'error': 'Failed to load user activity'}), 500

@bp.route('/api/admin/maintenance/cleanup', methods=['POST'])
@admin_required
def admin_maintenance_cleanup():
    """Manually trigger cleanup of expired data"""
    from .auth_service import auth_service
    
    try:
        log_admin_action('maintenance_cleanup', 'database')
        
        # Call the cleanup function
        auth_service.admin_supabase.rpc('cleanup_expired_analytics').execute()
        
        return jsonify({'message': 'Cleanup completed successfully'}), 200
        
    except Exception as e:
        print(f"❌ Cleanup error: {str(e)}")
        return jsonify({'error': 'Cleanup failed'}), 500

@bp.route('/api/admin/maintenance/aggregate', methods=['POST'])
@admin_required
def admin_maintenance_aggregate():
    """Manually trigger daily aggregation"""
    from .auth_service import auth_service
    
    try:
        log_admin_action('maintenance_aggregate', 'database')
        
        # Call the aggregation function
        auth_service.admin_supabase.rpc('aggregate_to_daily_summary').execute()
        
        return jsonify({'message': 'Aggregation completed successfully'}), 200
        
    except Exception as e:
        print(f"❌ Aggregation error: {str(e)}")
        return jsonify({'error': 'Aggregation failed'}), 500