# MBA — Multimodal Behavioral Analytics

A real-time multimodal behavioral analytics backend built with FastAPI, featuring audio analysis (Whisper), computer vision (MediaPipe), and NLP capabilities.

## 🚀 Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + WebSockets |
| Audio | OpenAI Whisper, Faster-Whisper, LibROSA |
| Vision | MediaPipe, OpenCV |
| NLP | Transformers, SentenceTransformers, NLTK |
| ML | PyTorch 2.3, PEFT, Accelerate |
| DB | Supabase, SQLAlchemy, PostgreSQL |

## 📁 Project Structure

```
MBD/
├── backend/
│   ├── main.py              # FastAPI app entrypoint
│   ├── requirements.txt     # Python dependencies
│   ├── .env.example         # Environment variables template
│   ├── core/                # Config, settings
│   ├── routers/             # REST + WebSocket routes
│   ├── services/            # Business logic services
│   ├── models/              # Data models
│   └── ml_bridge/           # ML model wrappers
└── data/
    ├── embeddings/
    ├── exports/
    ├── labeled/
    └── processed/
```

## ⚙️ Setup

### 1. Clone the repository
```bash
git clone https://github.com/yashitamoulin01-star/mba-multimodal-analytics.git
cd mba-multimodal-analytics
```

### 2. Create and activate virtual environment
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Configure environment
```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your credentials
```

### 5. Run the server
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root info |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |
| WS | `/ws/session/{session_id}` | Real-time session |

## 📋 Requirements

- Python 3.11+
- CUDA (optional, for GPU acceleration)
