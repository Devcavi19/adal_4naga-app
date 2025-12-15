# Quick Start Guide - Naga City Ordinances RAG Chatbot

## 🚀 Quick Setup (5 minutes)

### Prerequisites
- Python 3.12.1
- Virtual environment: `venv/` (with pinned dependencies in `requirements.txt`)
- Environment variables configured in `.env`

### Step 1: Verify you have the virtual environment
```bash
# Check that venv exists and is activated
source venv/bin/activate

# Verify Python version
python --version  # Should be 3.12.1
```

**If `venv/` doesn't exist**, create it:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Verify environment variables
```bash
# Check if .env file exists with required variables
cat .env | grep GOOGLE_API_KEY
cat .env | grep QDRANT_API_KEY
cat .env | grep SUPABASE_URL
```

### Step 3: Verify data files exist
```bash
# Check if indexed data exists
ls -la index/
# You should see: pdf_analysis_metadata.json, pdf_urls.json, rag_test_results.json
```

**If data files are missing**, ensure the RAG service initialization runs:
```bash
python -c "from app.rag_service import RAGService; rag = RAGService(); print('RAG Service initialized successfully')"
```

### Step 4: Run the application locally
```bash
# Make sure venv is activated
source venv/bin/activate

# Run Flask development server
python run.py
```

The application will start at:
```
http://localhost:5000
```

### Step 5: Run with Gunicorn (Production)
```bash
gunicorn wsgi:app --bind 0.0.0.0:8080 --workers 4
```

---

## 🔧 If Something Goes Wrong

### Error: "Collection not found"
```bash
# You need to run document processor first
cd /home/dfaurellano/avila/Adal_Smart_Naga_Hackathon
python document_processor.py
```

### Error: "BM25 index not found"
```bash
# Check data directory in .env
echo $DATA_DIR
# Should point to: /home/dfaurellano/avila/Adal_Smart_Naga_Hackathon/data

# Verify files exist
ls -la /home/dfaurellano/avila/Adal_Smart_Naga_Hackathon/data/
```

### Error: "GOOGLE_API_KEY not found"
```bash
# Check .env file
cd hacknaga_ui
cat .env | grep GOOGLE_API_KEY
# Make sure it's set and not commented out
```

### Error: "Qdrant connection failed"
```bash
# Verify credentials in .env
cat .env | grep QDRANT
# Check that QDRANT_URL and QDRANT_API_KEY are correct
```

---

## 📝 Testing the Chatbot

### Test Query 1: General Search
```
"Find ordinances about waste management"
```

### Test Query 2: Specific Ordinance
```
"What is Ordinance 2023-045 about?"
```

### Test Query 3: Penalties
```
"What are the penalties for noise violations?"
```

### Test Query 4: Follow-up (tests conversation memory)
```
User: "What ordinances regulate street vendors?"
Bot: [provides answer]
User: "What are the registration requirements?"
Bot: [uses context from previous question]
```

---

## 🎯 Key Features to Test

1. **Hybrid Search**: Try exact ordinance numbers vs. general topics
2. **Conversation Memory**: Ask follow-up questions
3. **Streaming**: Watch responses appear in real-time
4. **Authentication**: Login with CSPC email
5. **Chat History**: Create multiple conversations

---

## 📊 System Architecture

```
User Query
    ↓
Hybrid Search (70% Semantic + 30% BM25)
    ↓
Qdrant Vector DB + BM25 Index
    ↓
Top 5 Relevant Ordinances
    ↓
Google Gemini LLM
    ↓
Streaming Response
```

---

## 🔐 Authentication

- **Allowed Domains**: @cspc.edu.ph, @my.cspc.edu.ph
- **Provider**: Supabase
- **Features**: Email/password + Google OAuth

To test:
1. Go to http://localhost:5000
2. Click "Sign Up"
3. Use CSPC email (e.g., test@cspc.edu.ph)
4. Create password (min 8 characters)

---

## 📁 Project Structure

```
hacknaga_ui/
├── app/
│   ├── rag_service.py      ← New ordinances RAG service
│   ├── routes.py           ← Updated API endpoints
│   ├── __init__.py         ← Updated initialization
│   └── auth_service.py     ← Authentication (unchanged)
├── config.py               ← Updated configuration
├── requirements.txt        ← New dependencies
├── verify_setup.py         ← Setup verification script
├── run.py                  ← Application entry
└── .env                    ← Environment variables (updated)
```

---

## 🛠️ Maintenance

### Adding New Ordinances
1. Add PDFs to the ordinances directory
2. Run `python document_processor.py`
3. Restart the Flask app

### Updating Configuration
Edit `hacknaga_ui/config.py`:
- `TOP_K`: Number of results (default: 5)
- `SEMANTIC_WEIGHT`: Semantic search weight (default: 0.7)
- `BM25_WEIGHT`: Keyword search weight (default: 0.3)

### Monitoring
- Check terminal logs for errors
- Watch for "✅" success messages
- Monitor Qdrant dashboard for vector count

---

## 📚 Documentation

- **Full Documentation**: `README_ORDINANCES.md`
- **Revision Summary**: `REVISION_SUMMARY.md`
- **Setup Verification**: `verify_setup.py`

---

## 🆘 Support Checklist

Before asking for help, verify:
- [ ] Environment variables are set (check with `verify_setup.py`)
- [ ] Data files exist in `data/` directory
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Qdrant connection works
- [ ] No errors in terminal logs

---

## ✅ Success Indicators

When everything works, you'll see:
```
✅ Supabase authentication initialized
✅ Google API Key loaded: AIza...
🔧 Initializing Ordinance RAG Service...
✅ Connected to collection: naga_ordinances
✅ Loaded BM25 index with XXX documents
✅ Ordinance RAG Service initialized successfully
 * Running on http://127.0.0.1:5000
```

**You're ready to go!** 🎉
