"""
RAG Service for Flask integration with hybrid search
Adapted from rag_tester.py with Qdrant, BM25, and smart retrieval
"""
from typing import Tuple, Generator
import os
import json
import pickle
from pathlib import Path
import traceback
from dotenv import load_dotenv

# LangChain components
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Embeddings and Vector DB
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# BM25 for keyword search
from rank_bm25 import BM25Okapi

# LLM
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Content moderation
DISALLOWED = ("how to make a bomb", "explosive materials", "hatred", "self-harm")

# Global variable to store the initialized RAG chain
rag_chain = None
retriever_components = None

class RAGService:
    """RAG Service class with hybrid search and streaming generation methods"""
    
    def __init__(self, chain, qdrant_client, embedding_model, collection_name, bm25_index, bm25_metadata):
        self.chain = chain
        self.qdrant_client = qdrant_client
        self.embedding_model = embedding_model
        self.collection_name = collection_name
        self.bm25_index = bm25_index
        self.bm25_metadata = bm25_metadata
    
    def hybrid_search(self, query, top_k=6):
        """Perform hybrid search and return formatted results"""
        docs = hybrid_search(query, self.qdrant_client, self.embedding_model, self.collection_name, self.bm25_index, self.bm25_metadata, top_k=top_k)
        
        results = []
        for doc in docs:
            results.append({
                'text': doc.page_content,
                'metadata': doc.metadata,
                'hybrid_score': doc.metadata.get('hybrid_score', 0),
                'sources': [doc.metadata.get('source', '')]
            })
        return results
    
    def generate_response_streaming(self, question, context, chat_history):
        """Generate streaming response using the chain"""
        # Format context
        formatted_context = format_docs(context) if isinstance(context, list) else context
        
        # Format chat history
        formatted_history = format_chat_history(chat_history)
        
        inputs = {
            "question": question,
            "chat_history": formatted_history,
            "context": formatted_context
        }
        
        # Stream the response
        for chunk in self.chain.stream(inputs):
            yield chunk

def is_allowed(question: str) -> bool:
    """Check if the question contains disallowed content"""
    ql = question.lower()
    return not any(term in ql for term in DISALLOWED)

def detect_embedding_type(persist_dir="index"):
    """
    Detect which embedding model was used to create the index
    """
    metadata_file = os.path.join(persist_dir, "embedding_model.txt")
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r') as f:
            return f.read().strip()
    
    return "huggingface"  # Default to HuggingFace

def load_retriever(persist_dir="index"):
    """
    Load retriever components: Qdrant client, embedding model, BM25 index
    Returns tuple: (qdrant_client, embedding_model, bm25_index, bm25_metadata)
    """
    print(f"🔍 Loading retriever components from {persist_dir}...")
    
    # Load environment variables
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    collection_name = os.getenv("COLLECTION_NAME", "naga_full")
    
    # Initialize embedding model
    print("🤖 Loading embedding model: all-MiniLM-L6-v2")
    embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    
    # Initialize Qdrant client
    print("🔗 Connecting to Qdrant Cloud...")
    qdrant_client = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
    )
    
    # Verify collection exists
    try:
        collection_info = qdrant_client.get_collection(collection_name)
        print(f"✅ Connected to collection '{collection_name}' with {collection_info.points_count} points")
    except Exception as e:
        print(f"❌ Collection '{collection_name}' not found: {e}")
        raise
    
    # Load BM25 index
    bm25_index, bm25_metadata = load_bm25_index(persist_dir)
    
    print("✅ Retriever components loaded successfully")
    return qdrant_client, embedding_model, bm25_index, bm25_metadata

def load_bm25_index(persist_dir="index"):
    """
    Load BM25 index and metadata from disk
    """
    bm25_path = os.path.join(persist_dir, "bm25_index.pkl")
    metadata_path = os.path.join(persist_dir, "bm25_metadata.pkl")
    
    try:
        with open(bm25_path, 'rb') as f:
            bm25_index = pickle.load(f)
        
        with open(metadata_path, 'rb') as f:
            bm25_metadata = pickle.load(f)
        
        print(f"✅ Loaded BM25 index with {len(bm25_metadata)} documents")
        return bm25_index, bm25_metadata
        
    except FileNotFoundError:
        print("⚠️  BM25 index not found. Run document_processor.py first!")
        return None, []


def semantic_search(query: str, qdrant_client, embedding_model, collection_name, top_k: int = 6):
    """
    Perform semantic search using Qdrant
    """
    # Generate query embedding
    query_embedding = embedding_model.encode(query).tolist()
    
    # Search in Qdrant
    search_results = qdrant_client.query_points(
        collection_name=collection_name,
        query=query_embedding,
        limit=top_k
    )
    
    # Format results as LangChain-like docs
    results = []
    for hit in search_results.points:
        from langchain_core.documents import Document
        doc = Document(
            page_content=hit.payload["text"],
            metadata={**hit.payload["metadata"], "score": hit.score}
        )
        results.append(doc)
    
    return results

def bm25_search(query: str, bm25_index, bm25_metadata, top_k: int = 6):
    """
    Perform BM25 keyword search
    """
    if not bm25_index or not bm25_metadata:
        return []
    
    # Tokenize query
    tokenized_query = query.lower().split()
    
    # Get BM25 scores
    scores = bm25_index.get_scores(tokenized_query)
    
    # Get top-k results
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    
    results = []
    for idx in top_indices:
        if scores[idx] > 0:  # Only include results with non-zero scores
            from langchain_core.documents import Document
            doc = Document(
                page_content=bm25_metadata[idx]["text"],
                metadata={**bm25_metadata[idx]["metadata"], "score": float(scores[idx])}
            )
            results.append(doc)
    
    return results

def hybrid_search(query: str, qdrant_client, embedding_model, collection_name, bm25_index, bm25_metadata, top_k: int = 6, semantic_weight: float = 0.7, bm25_weight: float = 0.3):
    """
    Perform hybrid search combining semantic and BM25 results
    """
    # Get results from both methods
    semantic_results = semantic_search(query, qdrant_client, embedding_model, collection_name, top_k * 2)
    bm25_results = bm25_search(query, bm25_index, bm25_metadata, top_k * 2)
    
    # Normalize scores to [0, 1] range
    def normalize_scores(results):
        if not results:
            return results
        scores = [r.metadata.get('score', 0) for r in results]
        max_score = max(scores)
        min_score = min(scores)
        score_range = max_score - min_score
        
        if score_range > 0:
            for r in results:
                r.metadata['normalized_score'] = (r.metadata.get('score', 0) - min_score) / score_range
        else:
            for r in results:
                r.metadata['normalized_score'] = 1.0
        return results
    
    semantic_results = normalize_scores(semantic_results)
    bm25_results = normalize_scores(bm25_results)
    
    # Combine results with weighted scores
    combined = {}
    
    # Add semantic results
    for result in semantic_results:
        text = result.page_content
        combined[text] = {
            "doc": result,
            "hybrid_score": result.metadata.get('normalized_score', 0) * semantic_weight,
            "semantic_score": result.metadata.get('normalized_score', 0),
            "bm25_score": 0.0
        }
    
    # Add/update with BM25 results
    for result in bm25_results:
        text = result.page_content
        if text in combined:
            combined[text]["bm25_score"] = result.metadata.get('normalized_score', 0)
            combined[text]["hybrid_score"] += result.metadata.get('normalized_score', 0) * bm25_weight
        else:
            combined[text] = {
                "doc": result,
                "hybrid_score": result.metadata.get('normalized_score', 0) * bm25_weight,
                "semantic_score": 0.0,
                "bm25_score": result.metadata.get('normalized_score', 0)
            }
    
    # Sort by hybrid score and return top-k docs
    sorted_results = sorted(
        combined.values(),
        key=lambda x: x["hybrid_score"],
        reverse=True
    )[:top_k]
    
    docs = []
    for item in sorted_results:
        doc = item["doc"]
        doc.metadata['hybrid_score'] = item["hybrid_score"]
        doc.metadata['semantic_score'] = item["semantic_score"]
        doc.metadata['bm25_score'] = item["bm25_score"]
        docs.append(doc)
    
    return docs


def is_exhaustive_query(query: str) -> bool:
    """
    Detect if the query is asking for exhaustive/comprehensive results
    """
    exhaustive_keywords = [
        "all", "list", "every", "give me all", "show me all",
        "how many", "what are all", "enumerate", "complete list"
    ]
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in exhaustive_keywords)


def smart_retrieve(query: str, qdrant_client, embedding_model, collection_name, bm25_index, bm25_metadata):
    """
    Adaptive retrieval that adjusts k and uses hybrid search based on query intent
    
    - For exhaustive queries ("give me all X"): Uses high k + threshold filtering
    - For specific queries: Uses standard hybrid retrieval
    """
    is_exhaustive = is_exhaustive_query(query)
    
    if is_exhaustive:
        # Exhaustive query: retrieve more docs and filter by similarity threshold
        print(f"🔍 Detected exhaustive query - using adaptive hybrid retrieval (k=50)")
        docs = hybrid_search(query, qdrant_client, embedding_model, collection_name, bm25_index, bm25_metadata, top_k=50)
        
        # Debug: Show score distribution
        if docs:
            scores = [doc.metadata.get('score', 0) for doc in docs[:10]]
            print(f"📊 Sample scores (top 10): min={min(scores):.3f}, max={max(scores):.3f}")
        
        # Dynamic threshold based on score distribution
        if docs:
            best_score = docs[0].metadata.get('score', 0)
            threshold = min(best_score * 1.5, 2.0)
            print(f"🎯 Using adaptive threshold: {threshold:.3f} (based on best score: {best_score:.3f})")
            
            filtered_docs = [doc for doc in docs if doc.metadata.get('score', 0) <= threshold]
        else:
            filtered_docs = []
        
        print(f"✅ Retrieved {len(filtered_docs)} relevant documents")
        return filtered_docs
    else:
        # Standard hybrid search: top-k most relevant
        print(f"🔍 Standard hybrid search (k=6)")
        return hybrid_search(query, qdrant_client, embedding_model, collection_name, bm25_index, bm25_metadata, top_k=6)


def format_docs(docs):
    """Format documents with enhanced metadata for thesis-specific retrieval."""
    out = []
    abstract_docs = []
    other_docs = []
    
    # Separate abstracts and other content for prioritization
    for doc in docs:
        # Handle both Document objects and dicts
        if hasattr(doc, 'metadata'):
            meta = doc.metadata or {}
            text = doc.page_content
        elif isinstance(doc, dict):
            meta = doc.get('metadata', {})
            text = doc.get('text', doc.get('page_content', ''))
        else:
            continue  # Skip invalid items
        
        if meta.get("content_type") == "abstract":
            abstract_docs.append((text, meta))
        else:
            other_docs.append((text, meta))
    
    # Process abstracts first (higher priority)
    for i, (text, meta) in enumerate(abstract_docs, 1):
        src = meta.get("source", "document").replace("\\", "/").split("/")[-1]
        page = meta.get("page", "")
        content_type = meta.get("content_type", "")
        chapter = meta.get("chapter", "")
        url = meta.get("url", "")  # Retrieve URL from metadata
        
        # Extract title from filename (remove extension and format)
        if src != "document":
            title = src.rsplit('.', 1)[0]  # Remove extension
            title = title.replace('Ordno-', 'Ordinance No. ').replace('-', ' ').replace('_', ' ')
        else:
            title = "Document"
        
        label_parts = [title]
        if page:
            label_parts.append(f"p.{page}")
        if content_type:
            label_parts.append(f"({content_type})")
        if chapter:
            label_parts.append(f"Ch.{chapter}")
        
        label = f"{' '.join(label_parts)}"
        if url:
            label = f'<a href="{url}" target="_blank">{label}</a>'  # HTML link that opens in a new tab
        else:
            label = f"[{label}]"  # Fallback to plain text if no URL
        out.append(text + f"\n{label}")
    
    # Then process other documents
    start_idx = len(abstract_docs) + 1
    for i, (text, meta) in enumerate(other_docs, start_idx):
        src = meta.get("source", "document").replace("\\", "/").split("/")[-1]
        page = meta.get("page", "")
        content_type = meta.get("content_type", "")
        chapter = meta.get("chapter", "")
        url = meta.get("url", "")  # Retrieve URL from metadata
        
        # Extract title from filename (remove extension and format)
        if src != "document":
            title = src.rsplit('.', 1)[0]  # Remove extension
            title = title.replace('Ordno-', 'Ordinance No. ').replace('-', ' ').replace('_', ' ')
        else:
            title = "Document"
        
        label_parts = [title]
        if page:
            label_parts.append(f"p.{page}")
        if content_type:
            label_parts.append(f"({content_type})")
        if chapter:
            label_parts.append(f"Ch.{chapter}")
        
        label = f"{' '.join(label_parts)}"
        if url:
            label = f'<a href="{url}" target="_blank">{label}</a>'  # HTML link that opens in a new tab
        else:
            label = f"[{label}]"  # Fallback to plain text if no URL
        out.append(text + f"\n{label}")
    
    return "\n\n".join(out)


def format_chat_history(messages: list, max_exchanges: int = 5) -> str:
    """
    Format chat history for inclusion in the prompt
    
    Args:
        messages: List of message dicts with 'role' and 'content', or a pre-formatted string
        max_exchanges: Maximum number of exchanges to include (default 5 = 10 messages)
    
    Returns:
        Formatted string of conversation history
    """
    if isinstance(messages, str):
        return messages  # Already formatted
    
    if not messages:
        return ""
    
    # Take last N messages (max_exchanges * 2 for user+bot pairs)
    recent_messages = messages[-(max_exchanges * 2):]
    
    history_lines = []
    for msg in recent_messages:
        role = "Human" if msg['role'] == 'user' else "Assistant"
        content = msg['content']
        
        # Truncate very long messages to prevent token overflow
        if len(content) > 500:
            content = content[:500] + "..."
        
        history_lines.append(f"{role}: {content}")
    
    return "\n".join(history_lines)


# Load abstract and title data files
try:
    abstract_file = os.path.join("index", "data_abstract.txt")
    title_file = os.path.join("index", "data_title_url.txt")
    
    file_content1 = ""
    file_content2 = ""
    
    if os.path.exists(abstract_file):
        with open(abstract_file, "r", encoding="utf-8") as f1:
            file_content1 = f1.read()
            print(f"✅ Loaded data_abstract.txt")
    
    if os.path.exists(title_file):
        with open(title_file, "r", encoding="utf-8") as f2:
            file_content2 = f2.read()
            print(f"✅ Loaded data_title_url.txt")
except Exception as e:
    print(f"⚠️ Could not load data files: {e}")
    file_content1 = ""
    file_content2 = ""

SYSTEM_PROMPT = f"""
You are Adal, an AI assistant specialized in Naga City Government information and transparency.

You were created and are maintained by TEAM VIRGO.

Your current knowledge base includes various documents from Naga City Government, such as ordinances, regulations, reports, announcements, and other public information available on the Naga City Government webpage.

CORE RESPONSIBILITIES:
- Help users discover and explore Naga City Government information, including ordinances, regulations, services, departments, and public announcements
- Provide complete excerpts from documents when requested or when relevant to the query
- Generate proper citations for document sources
- Suggest related information based on semantic similarity
- Handle both specific queries (returns top relevant results) and exhaustive queries (returns all matching results)
- Maintain conversation context and refer back to previous exchanges when relevant
- Act as a knowledgeable government employee, providing accurate and helpful information about Naga City's government operations

LANGUAGE HANDLING (MULTIMODAL):
- Detect the primary language of the user's query.
- If the query is primarily in Tagalog (Filipino), respond entirely in Tagalog.
- If the query is primarily in Bicol, respond entirely in Bicol.
- For all other languages (including English or mixed/undetected languages), respond entirely in English.
- Maintain the detected language throughout the conversation unless the user explicitly switches languages in a new query.
- If the user asks or switches to a different language (English, Tagalog, or Bicol) in mid-conversation, switch to that language for subsequent responses.

RESPONSE GUIDELINES:
- Always answer based STRICTLY on the provided context
- Always answer direct to the point
- Use conversation history to provide contextual responses (e.g., "As I mentioned earlier...", "Regarding the document we discussed...")
- If information is not in the context, clearly state "I didn't find that information in my knowledge base, but you can try rephrasing your question and I'll search again"
- When providing document excerpts, give the COMPLETE text if available in context
- For government-related queries, prioritize excerpt and metadata information
- Include proper citations at the end using format: [Source Document, Page X, Naga City Government](url) if a URL is available in the context
- If the question is too vague, ask clarifying questions to narrow down the topic
- For "give me all" or "list all" queries, provide a comprehensive list of ALL matching documents found in context
- Ensure that any links provided open in a new tab
- Always provide a follow-up question as the conclusion of response generation, before reaching token or chunk limits

QUERY TYPES TO HANDLE:
- "What is [document/ordinance title] about?" → Provide excerpt and key details
- "Show me the excerpt of..." → Provide complete document text
- "Find information about [topic]" → List relevant documents with brief descriptions
- "Give me all documents on [topic]" → List ALL matching documents comprehensively
- "How many documents about [topic]?" → Count and list all matching documents
- "Who regulates [subject]?" → Identify relevant documents and their provisions
- "What department handles [field]?" → Identify relevant departments and their documents
- "What services does the city offer?" → Provide information on government services
- "Tell me about [government announcement/report]" → Summarize or excerpt relevant content
- Follow-up questions → Use conversation history to maintain context

CITATION FORMAT:
Example: [Naga City Document Title, 2023, Naga City Government](https://example.com/document.pdf)

Remember: You are helping unlock Naga City Government's knowledge for the public, acting as a transparent and informative resource."""

# Updated prompt template with conversation history
CONVERSATIONAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{chat_history}\n\nCurrent Question: {question}\n\nRelevant Context:\n{context}"),
])


def build_chain(embedding_type=None) -> Tuple:
    """
    Build basic RAG chain (non-streaming) - matches rag_chain.py exactly
    Returns: (chain, vectorstore)
    """
    qdrant_client, embedding_model, bm25_index, bm25_metadata = load_retriever()
    collection_name = os.getenv("COLLECTION_NAME", "naga_full")
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Create a custom retrieval function that uses smart_retrieve
    def custom_retrieve(inputs: dict) -> str:
        question = inputs.get("question", "")
        docs = smart_retrieve(question, qdrant_client, embedding_model, collection_name, bm25_index, bm25_metadata)
        return format_docs(docs)
    
    # Build chain with smart retrieval integration and conversation history
    chain = (
        {
            "context": custom_retrieve, 
            "question": lambda x: x.get("question", ""),
            "chat_history": lambda x: x.get("chat_history", "")
        }
        | CONVERSATIONAL_PROMPT
        | llm
        | StrOutputParser()
    )
    
    # Return both chain and vectorstore for flexibility
    return chain, (qdrant_client, embedding_model, bm25_index, bm25_metadata)


def build_streaming_chain(persist_dir="index"):
    """
    Build RAG chain with streaming support, smart retrieval, and conversation memory
    Uses same configuration as build_chain but with streaming enabled
    Returns: (chain, vectorstore)
    """
    try:
        print("🚀 Building streaming RAG chain with conversation memory...")
        
        # Load vectorstore using the same function as build_chain
        qdrant_client, embedding_model, bm25_index, bm25_metadata = load_retriever(persist_dir)
        collection_name = os.getenv("COLLECTION_NAME", "naga_full")
        
        print("🤖 Initializing Gemini LLM with streaming...")
        # Create LLM with streaming - using same model as rag_chain.py
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            streaming=True
        )
        
        # Create custom retrieval function that uses smart_retrieve
        def custom_retrieve(inputs: dict) -> str:
            question = inputs.get("question", "")
            docs = smart_retrieve(question, qdrant_client, embedding_model, collection_name, bm25_index, bm25_metadata)
            formatted = format_docs(docs)
            
            # Log context size to detect overload
            print(f"📏 Context size: {len(formatted)} chars, {len(docs)} docs")
            
            # Warn if context is too large
            if len(formatted) > 50000:
                print(f"⚠️  Large context detected ({len(formatted)} chars) - may cause truncation")
            
            return formatted
        
        # Build chain with smart retrieval and conversation history
        chain = (
            {
                "context": custom_retrieve,
                "question": lambda x: x.get("question", ""),
                "chat_history": lambda x: x.get("chat_history", "")
            }
            | CONVERSATIONAL_PROMPT
            | llm
            | StrOutputParser()
        )
        
        print("✅ Streaming RAG chain with conversation memory built successfully")
        print(f"   - Model: gemini-2.5-flash")
        print(f"   - Temperature: 0")
        print(f"   - Streaming: enabled")
        print(f"   - Conversation memory: enabled")
        return chain, (qdrant_client, embedding_model, bm25_index, bm25_metadata)
        
    except Exception as e:
        print(f"❌ Failed to build streaming chain: {str(e)}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        raise e


def get_rag_service():
    """
    Get the initialized RAG service instance.
    Returns the RAGService instance if initialized, otherwise None.
    """
    if rag_chain is None:
        print("⚠️  RAG service not initialized. Call initialize_rag_service first.")
    return rag_chain


def initialize_rag_service(app):
    """
    Initialize the RAG service by building the streaming chain.
    Returns the RAGService instance.
    """
    global rag_chain, retriever_components
    try:
        chain, components = build_streaming_chain()
        qdrant_client, embedding_model, bm25_index, bm25_metadata = components
        collection_name = os.getenv("COLLECTION_NAME", "naga_full")
        
        rag_service_instance = RAGService(chain, qdrant_client, embedding_model, collection_name, bm25_index, bm25_metadata)
        
        rag_chain = rag_service_instance  # Store the instance
        retriever_components = components
        
        print("✅ RAG service initialized successfully")
        return rag_service_instance
    except Exception as e:
        print(f"❌ Failed to initialize RAG service: {e}")
        raise