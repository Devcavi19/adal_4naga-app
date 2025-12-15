"""
Analytics Service for Admin Dashboard
Handles TF-IDF keyword extraction, anonymization, notification detection, and background jobs
"""

import threading
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import json

# Data processing
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

# Supabase
from flask import current_app


class AnalyticsService:
    """Service for analytics tracking, keyword extraction, and notifications"""
    
    def __init__(self):
        self.tfidf_vectorizer = None
        self.last_keyword_computation = None
        self.keyword_cache = {}
        
    def initialize(self, admin_supabase):
        """Initialize the analytics service with Supabase client"""
        self.admin_supabase = admin_supabase
        print("✅ Analytics Service initialized")
    
    # ============================================
    # Keyword Extraction (TF-IDF)
    # ============================================
    
    def extract_keywords_tfidf(self, text: str, top_n: int = 5) -> List[str]:
        """
        Extract top keywords from text using TF-IDF
        
        Args:
            text: Input text to extract keywords from
            top_n: Number of top keywords to return
            
        Returns:
            List of top keywords
        """
        try:
            if not text or len(text.strip()) < 3:
                return []
            
            # Simple preprocessing
            text = text.lower().strip()
            
            # Use sklearn's TfidfVectorizer for single document
            # For better results with single doc, we create a simple corpus
            vectorizer = TfidfVectorizer(
                max_features=top_n,
                stop_words='english',
                ngram_range=(1, 2),  # Unigrams and bigrams
                min_df=1,
                max_df=1.0
            )
            
            # Fit and transform
            try:
                tfidf_matrix = vectorizer.fit_transform([text])
                feature_names = vectorizer.get_feature_names_out()
                
                # Get scores
                scores = tfidf_matrix.toarray()[0]
                
                # Sort by score
                top_indices = scores.argsort()[-top_n:][::-1]
                keywords = [feature_names[i] for i in top_indices if scores[i] > 0]
                
                return keywords
            except:
                # Fallback: simple word frequency
                words = text.split()
                # Remove common words
                stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'can', 'about', 'what', 'when', 'where', 'who', 'why', 'how'}
                words = [w for w in words if w.lower() not in stop_words and len(w) > 3]
                counter = Counter(words)
                return [word for word, _ in counter.most_common(top_n)]
                
        except Exception as e:
            print(f"⚠️  Keyword extraction error: {str(e)}")
            return []
    
    def compute_keyword_trends(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Compute keyword trends from recent queries
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of {keyword, count, trend} dictionaries
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Fetch recent queries with cached keywords
            response = self.admin_supabase.table('query_analytics')\
                .select('keywords, created_at')\
                .gte('created_at', cutoff_time.isoformat())\
                .not_.is_('keywords', 'null')\
                .execute()
            
            if not response.data:
                return []
            
            # Aggregate keywords
            keyword_counts = Counter()
            for record in response.data:
                keywords = record.get('keywords', [])
                if isinstance(keywords, list):
                    keyword_counts.update(keywords)
            
            # Return top keywords
            trends = [
                {'keyword': keyword, 'count': count}
                for keyword, count in keyword_counts.most_common(50)
            ]
            
            return trends
            
        except Exception as e:
            print(f"⚠️  Keyword trends error: {str(e)}")
            return []
    
    def get_top_keywords(self, limit: int = 10, days: int = 7) -> List[Dict]:
        """
        Get top keywords from recent queries
        
        Args:
            limit: Maximum number of keywords to return
            days: Number of days to look back
            
        Returns:
            List of {keyword, count} dictionaries
        """
        try:
            from_date = datetime.utcnow() - timedelta(days=days)
            
            result = self.admin_supabase.table('query_analytics')\
                .select('keywords')\
                .gte('created_at', from_date.isoformat())\
                .not_.is_('keywords', 'null')\
                .execute()
            
            if not result.data:
                return []
            
            # Count keyword frequencies
            keyword_counts = Counter()
            for row in result.data:
                if row.get('keywords'):
                    keywords = row['keywords']
                    if isinstance(keywords, list):
                        keyword_counts.update(keywords)
            
            # Sort and return top keywords
            sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
            return [{'keyword': k, 'count': c} for k, c in sorted_keywords[:limit]]
        
        except Exception as e:
            print(f"❌ Error getting top keywords: {e}")
            return []
    
    def get_topic_clusters(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Group queries by shared keywords (simple clustering)
        
        Args:
            date_from: Start date (ISO format)
            date_to: End date (ISO format)
            
        Returns:
            Dictionary of {keyword: [query_ids]}
        """
        try:
            query = self.admin_supabase.table('query_analytics').select('id, keywords')
            
            if date_from:
                query = query.gte('created_at', date_from)
            if date_to:
                query = query.lte('created_at', date_to)
            
            response = query.not_.is_('keywords', 'null').execute()
            
            if not response.data:
                return {}
            
            # Group by keywords
            clusters = {}
            for record in response.data:
                keywords = record.get('keywords', [])
                if isinstance(keywords, list):
                    for keyword in keywords:
                        if keyword not in clusters:
                            clusters[keyword] = []
                        clusters[keyword].append(record['id'])
            
            return clusters
            
        except Exception as e:
            print(f"⚠️  Topic clustering error: {str(e)}")
            return {}
    
    def update_query_keywords_batch(self, hours_back: int = 24):
        """
        Background job: Compute and cache keywords for recent queries
        
        Args:
            hours_back: How many hours back to process
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            # Fetch queries without cached keywords
            response = self.admin_supabase.table('query_analytics')\
                .select('id, query_text, keywords')\
                .gte('created_at', cutoff_time.isoformat())\
                .execute()
            
            if not response.data:
                print("ℹ️  No queries to process for keywords")
                return
            
            updated_count = 0
            for record in response.data:
                # Skip if keywords already computed
                if record.get('keywords') and len(record.get('keywords', [])) > 0:
                    continue
                
                # Extract keywords
                keywords = self.extract_keywords_tfidf(record['query_text'], top_n=10)
                
                if keywords:
                    # Update record
                    self.admin_supabase.table('query_analytics')\
                        .update({'keywords': keywords})\
                        .eq('id', record['id'])\
                        .execute()
                    
                    updated_count += 1
            
            print(f"✅ Updated keywords for {updated_count} queries")
            self.last_keyword_computation = datetime.utcnow()
            
        except Exception as e:
            print(f"❌ Batch keyword update error: {str(e)}")
    
    # ============================================
    # User Anonymization
    # ============================================
    
    def anonymize_user(self, user_id: str, email: Optional[str] = None) -> str:
        """
        Anonymize user by creating a hash-based identifier
        
        Args:
            user_id: User UUID
            email: Optional email for context
            
        Returns:
            Anonymized identifier like "User#a1b2c3"
        """
        try:
            # Create a short hash from user_id
            hash_obj = hashlib.md5(user_id.encode())
            short_hash = hash_obj.hexdigest()[:6]
            
            return f"User#{short_hash}"
            
        except Exception as e:
            print(f"⚠️  Anonymization error: {str(e)}")
            return "User#unknown"
    
    def get_anonymized_user_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get user activity data with anonymization
        
        Args:
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            
        Returns:
            DataFrame with anonymized user data
        """
        try:
            # COMPETITION: response_time_ms temporarily hidden from analytics exports.
            # Database field continues collecting data. To reactivate: add response_time_ms back to select().
            query = self.admin_supabase.table('query_analytics')\
                .select('user_id, created_at, search_method, keywords')
            
            if start_date:
                query = query.gte('created_at', start_date)
            if end_date:
                query = query.lte('created_at', end_date)
            
            response = query.execute()
            
            if not response.data:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(response.data)
            
            # Anonymize user IDs
            df['anonymized_user'] = df['user_id'].apply(self.anonymize_user)
            df = df.drop(columns=['user_id'])
            
            return df
            
        except Exception as e:
            print(f"❌ Get anonymized user data error: {str(e)}")
            return pd.DataFrame()
    
    # ============================================
    # Notification System (Anomaly Detection)
    # ============================================
    
    def check_query_spike(self, threshold_multiplier: float = 2.0) -> Optional[Dict[str, Any]]:
        """
        Detect if current hour has unusually high query volume
        
        Args:
            threshold_multiplier: Spike threshold (e.g., 2.0 = 2x normal)
            
        Returns:
            Notification dict if spike detected, None otherwise
        """
        try:
            # Get queries in last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            response_recent = self.admin_supabase.table('query_analytics')\
                .select('id', count='exact')\
                .gte('created_at', one_hour_ago.isoformat())\
                .execute()
            
            current_count = response_recent.count if hasattr(response_recent, 'count') else 0
            
            # Get average hourly queries over last 7 days
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            response_historical = self.admin_supabase.table('query_analytics')\
                .select('id', count='exact')\
                .gte('created_at', seven_days_ago.isoformat())\
                .execute()
            
            historical_count = response_historical.count if hasattr(response_historical, 'count') else 0
            avg_hourly = historical_count / (7 * 24) if historical_count > 0 else 1
            
            # Check if spike
            if current_count > avg_hourly * threshold_multiplier:
                return {
                    'notification_type': 'alert',
                    'title': 'Query Volume Spike Detected',
                    'message': f'Current hour has {current_count} queries (avg: {avg_hourly:.1f})',
                    'severity': 'warning',
                    'metadata': json.dumps({
                        'current_count': current_count,
                        'average_count': avg_hourly,
                        'multiplier': current_count / avg_hourly if avg_hourly > 0 else 0
                    })
                }
            
            return None
            
        except Exception as e:
            print(f"⚠️  Query spike check error: {str(e)}")
            return None
    
    def check_error_rate(self, threshold_percent: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Detect if error rate is too high
        
        Args:
            threshold_percent: Error rate threshold (e.g., 10.0 = 10%)
            
        Returns:
            Notification dict if high error rate, None otherwise
        """
        try:
            # Get counts from last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            # Total queries
            response_queries = self.admin_supabase.table('query_analytics')\
                .select('id', count='exact')\
                .gte('created_at', one_hour_ago.isoformat())\
                .execute()
            
            total_queries = response_queries.count if hasattr(response_queries, 'count') else 0
            
            # Total errors
            response_errors = self.admin_supabase.table('error_logs')\
                .select('id', count='exact')\
                .gte('created_at', one_hour_ago.isoformat())\
                .execute()
            
            total_errors = response_errors.count if hasattr(response_errors, 'count') else 0
            
            if total_queries == 0:
                return None
            
            error_rate = (total_errors / total_queries) * 100
            
            if error_rate > threshold_percent:
                return {
                    'notification_type': 'alert',
                    'title': 'High Error Rate Detected',
                    'message': f'Error rate is {error_rate:.1f}% ({total_errors}/{total_queries})',
                    'severity': 'critical',
                    'metadata': json.dumps({
                        'error_count': total_errors,
                        'query_count': total_queries,
                        'error_rate': error_rate
                    })
                }
            
            return None
            
        except Exception as e:
            print(f"⚠️  Error rate check error: {str(e)}")
            return None
    
    def check_satisfaction_drop(self, threshold_percent: float = 60.0) -> Optional[Dict[str, Any]]:
        """
        Detect if user satisfaction is below threshold
        
        Args:
            threshold_percent: Satisfaction threshold (e.g., 60.0 = 60%)
            
        Returns:
            Notification dict if low satisfaction, None otherwise
        """
        try:
            # Get feedback from last 24 hours
            one_day_ago = datetime.utcnow() - timedelta(days=1)
            
            response = self.admin_supabase.table('user_feedback')\
                .select('rating')\
                .gte('created_at', one_day_ago.isoformat())\
                .execute()
            
            if not response.data or len(response.data) < 10:  # Need at least 10 ratings
                return None
            
            # Calculate satisfaction (rating >= 4 is positive)
            ratings = [r['rating'] for r in response.data]
            positive_count = sum(1 for r in ratings if r >= 4)
            satisfaction_rate = (positive_count / len(ratings)) * 100
            
            if satisfaction_rate < threshold_percent:
                return {
                    'notification_type': 'warning',
                    'title': 'Low User Satisfaction',
                    'message': f'Satisfaction rate is {satisfaction_rate:.1f}% (threshold: {threshold_percent}%)',
                    'severity': 'warning',
                    'metadata': json.dumps({
                        'satisfaction_rate': satisfaction_rate,
                        'total_feedback': len(ratings),
                        'positive_count': positive_count
                    })
                }
            
            return None
            
        except Exception as e:
            print(f"⚠️  Satisfaction check error: {str(e)}")
            return None
    
    # COMPETITION: check_slow_responses() method temporarily disabled for competition presentation.
    # Database continues collecting response_time_ms. To reactivate: uncomment method below and line 508 call in run_anomaly_checks().
    # def check_slow_responses(self, threshold_ms: int = 5000) -> Optional[Dict[str, Any]]:
    #     """
    #     Detect if average response time is too slow
    #     
    #     Args:
    #         threshold_ms: Response time threshold in milliseconds
    #         
    #     Returns:
    #         Notification dict if responses are slow, None otherwise
    #     """
    #     try:
    #         # Get queries from last hour
    #         one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    #         
    #         response = self.admin_supabase.table('query_analytics')\
    #             .select('response_time_ms')\
    #             .gte('created_at', one_hour_ago.isoformat())\
    #             .not_.is_('response_time_ms', 'null')\
    #             .execute()
    #         
    #         if not response.data or len(response.data) < 5:
    #             return None
    #         
    #         # Calculate average
    #         times = [r['response_time_ms'] for r in response.data]
    #         avg_time = sum(times) / len(times)
    #         
    #         if avg_time > threshold_ms:
    #             return {
    #                 'notification_type': 'warning',
    #                 'title': 'Slow Response Times',
    #                 'message': f'Average response time is {avg_time:.0f}ms (threshold: {threshold_ms}ms)',
    #                 'severity': 'warning',
    #                 'metadata': json.dumps({
    #                     'avg_response_time_ms': avg_time,
    #                     'sample_size': len(times),
    #                     'threshold_ms': threshold_ms
    #                 })
    #             }
    #         
    #         return None
    #         
    #     except Exception as e:
    #         print(f"⚠️  Response time check error: {str(e)}")
    #         return None
    
    def run_anomaly_checks(self):
        """
        Run all anomaly detection checks and create notifications
        """
        try:
            print("🔍 Running anomaly checks...")
            
            checks = [
                self.check_query_spike(),
                self.check_error_rate(),
                self.check_satisfaction_drop(),
                # COMPETITION: Temporarily disabled - uncomment to enable slow response monitoring
                # self.check_slow_responses()
            ]
            
            # Filter out None results
            notifications = [n for n in checks if n is not None]
            
            # Insert notifications
            for notif in notifications:
                self.admin_supabase.table('admin_notifications').insert(notif).execute()
                print(f"📢 Created notification: {notif['title']}")
            
            if not notifications:
                print("✅ No anomalies detected")
            
        except Exception as e:
            print(f"❌ Anomaly check error: {str(e)}")
    
    # ============================================
    # Background Jobs
    # ============================================
    
    def start_background_jobs(self):
        """
        Start background threads for periodic tasks
        """
        # Keyword computation job (runs hourly)
        keyword_thread = threading.Thread(target=self._keyword_job_loop, daemon=True)
        keyword_thread.start()
        print("✅ Started keyword computation background job")
        
        # Anomaly detection job (runs hourly)
        anomaly_thread = threading.Thread(target=self._anomaly_job_loop, daemon=True)
        anomaly_thread.start()
        print("✅ Started anomaly detection background job")
    
    def _keyword_job_loop(self):
        """Background loop for keyword computation"""
        while True:
            try:
                time.sleep(3600)  # Run every hour
                print("⏰ Running scheduled keyword computation...")
                self.update_query_keywords_batch(hours_back=2)
            except Exception as e:
                print(f"❌ Keyword job error: {str(e)}")
    
    def _anomaly_job_loop(self):
        """Background loop for anomaly detection"""
        while True:
            try:
                time.sleep(3600)  # Run every hour
                print("⏰ Running scheduled anomaly checks...")
                self.run_anomaly_checks()
            except Exception as e:
                print(f"❌ Anomaly job error: {str(e)}")


# Global analytics service instance
analytics_service = AnalyticsService()


def get_analytics_service():
    """Get the global analytics service instance"""
    return analytics_service


def initialize_analytics_service(app):
    """Initialize analytics service with Flask app"""
    from .auth_service import auth_service
    
    analytics_service.initialize(auth_service.admin_supabase)
    
    # Start background jobs
    analytics_service.start_background_jobs()
    
    return analytics_service
