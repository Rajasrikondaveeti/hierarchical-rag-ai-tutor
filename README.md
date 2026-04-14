# Network Security AI Tutor & Quiz Generator

**[Give the app a try](https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME)** — replace this URL with your deployed app, and set the same value as `PUBLIC_APP_URL` in `.env`.

I have developed an **AI Tutor and custom Quiz Generator**. It uses a **Retrieval-Augmented Generation (RAG)** system that answers questions primarily from my own **lecture slides and textbook** (PDFs in a local knowledge base). When the vector store does not surface relevant material, the app **falls back to the web** using **SerpAPI** (Google search results). Answers and quizzes are generated with **OpenAI** using a **small, fast model** (`gpt-4o-mini` by default).

The project ships with a **Gradio** web UI: an **AI Tutor** for Q&A and a **Quiz Center** that generates MCQs, true/false, and open questions from the same RAG context (or from web snippets if local retrieval is weak).

## Technologies Used
- **Language**: Python
- **LLM Integration**: OpenAI (`gpt-4o-mini`)
- **Embeddings**: Sentence-Transformers (`all-MiniLM-L12-v2`)
- **Vector Database**: Qdrant
- **Web Interface**: Gradio
- **Web Search Fallback**: SerpAPI (Google Search)
- **Document Processing**: PyMuPDF (`fitz`)
- **String Matching**: RapidFuzz & python-Levenshtein
- **Environment**: Docker & Hugging Face Spaces

## What this system does

1. **Ingest**: PDFs under `knowledge_base/` are split per page, embedded with [Sentence Transformers](https://www.sbert.net/) (`all-MiniLM-L12-v2`, 384-dim vectors), and stored in **Qdrant**.
2. **Retrieve**: Your question is embedded and matched against Qdrant; results are filtered with fuzzy text overlap so only plausible chunks are used.
3. **Generate**: **OpenAI** (`OPENAI_MODEL`, default `gpt-4o-mini`) produces answers and quiz content from retrieved context.
4. **Fallback**: If no good local chunks are found, **SerpAPI** fetches top Google organic results; the model answers from those snippets and linked titles.

## Prerequisites

- **Python 3.10+**
- **No Docker required.** Qdrant runs in **embedded mode** and stores data under `qdrant_storage/` in the project root (or set `QDRANT_PATH` / `QDRANT_URL` in `.env` if you prefer another folder or [Qdrant Cloud](https://cloud.qdrant.io/)).
- **OpenAI API key** and **SerpAPI API key** in a project-root **`.env`** file (see `.env.example`). Keys load automatically when you run the app.
- Optional: **`PUBLIC_APP_URL`** after you deploy (e.g. [Hugging Face Spaces](https://huggingface.co/spaces)) for the **“Give it a try”** link.

## Setup

### 1. Environment file

Copy `.env.example` to `.env` and fill in your keys:

```text
OPENAI_API_KEY=sk-...
SERPAPI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
PUBLIC_APP_URL=https://huggingface.co/spaces/you/your-space
```

Use standard `KEY=value` lines (no spaces around `=`). Never commit `.env` (it is listed in `.gitignore`).

### 2. Virtual environment (optional)

```powershell
cd path\to\Network_Security_Project
python -m venv venv
.\venv\Scripts\activate
```

If PowerShell blocks scripts:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Initialize the collection and load PDFs

Creates on-disk Qdrant storage and indexes every page of each PDF in `knowledge_base\`:

```powershell
python Scripts\initialise_qdrant.py
python Scripts\Data_insertion_qdrant.py
```

Place **lecture slides** and your **textbook** in `knowledge_base\` before ingestion. Re-run `Data_insertion_qdrant.py` after adding or changing PDFs.

### 5. Run the app

```powershell
python Scripts\chatbot_application.py
```

Open the local URL printed in the terminal (Gradio default is often `http://127.0.0.1:7860`).

Optional: set `GRADIO_SHARE=true` in the environment for a temporary Gradio public link (useful for quick demos; for GitHub, prefer a stable Space URL in `PUBLIC_APP_URL`).

### 6. Run Using Docker (Alternative)

To completely bypass local Python dependency issues, you can run the entire Tutor and Quiz Generator inside an isolated Docker container:

```powershell
docker build -t ai_tutor .
docker run -p 7860:7860 --env-file .env ai_tutor
```
Navigate your browser to `http://localhost:7860`.

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | Chat completions for tutor answers and quiz generation |
| `OPENAI_MODEL` | No | Default `gpt-4o-mini` (fast / cost-effective) |
| `SERPAPI_API_KEY` | Yes for web fallback | Google search via SerpAPI when RAG misses |
| `PUBLIC_APP_URL` | No | Public demo URL for **Give it a try** links in the UI and README |
| `GRADIO_SHARE` | No | Set to `true` for a temporary `share.gradio` link |
| `QDRANT_PATH` | No | Custom folder for embedded Qdrant data (default: `qdrant_storage/`) |
| `QDRANT_URL` | No | Remote Qdrant (e.g. cloud); use with `QDRANT_API_KEY` if required |

## Project layout

| Path | Role |
|------|------|
| `knowledge_base/` | PDFs (lectures, textbook) |
| `.env` | Local secrets (not committed) |
| `.env.example` | Template for required variables |
| `Scripts/qdrant_connection.py` | Builds Qdrant client (embedded disk by default; optional cloud URL) |
| `Scripts/initialise_qdrant.py` | Creates/recreates Qdrant collection `network_security_knowledge` |
| `Scripts/Data_insertion_qdrant.py` | Embeds and upserts all PDF pages |
| `Scripts/chatbot_application.py` | Gradio UI + RAG + OpenAI + SerpAPI + quiz |
| `qdrant_storage/` | Local vector DB files (created automatically; gitignored) |
| `requirements.txt` | Python dependencies |

## Security note

Keep **OpenAI** and **SerpAPI** keys only in `.env`. If a key was ever committed or shared, **rotate it** in the provider dashboards.

## Troubleshooting

- **Missing OpenAI errors**: Check `.env` uses `OPENAI_API_KEY=...` and that the file lives at the **project root** (next to `README.md`).
- **Empty or weak RAG answers**: Run `initialise_qdrant.py` then `Data_insertion_qdrant.py` with PDFs present in `knowledge_base\`.
- **Web fallback errors**: Confirm `SERPAPI_API_KEY` and quota on SerpAPI.

---

*Stack: Qdrant, Sentence Transformers, OpenAI, Gradio, SerpAPI, PyMuPDF.*
