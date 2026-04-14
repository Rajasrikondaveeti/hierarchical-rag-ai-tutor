# AI Tutor & Quiz Generator

I have developed an Artificial Intelligence Tutor and interactive Quiz Generator. This application uses Retrieval-Augmented Generation (RAG) to dynamically answer questions directly from custom course documents, lecture slides, and textbooks. It seamlessly falls back to securely browsing the internet when it cannot find local knowledge, and auto-generates comprehensive quizzes to test user understanding!

## Technologies Used
This complete production system incorporates the following technologies:
- LLM Generation: OpenAI API (gpt-4o-mini)
- Embeddings Model: Sentence-Transformers (all-MiniLM-L12-v2)
- Vector Database: Qdrant
- Web Application UI: Gradio
- Web Search Fallback: SerpAPI
- Document Processing: PyMuPDF (fitz)
- String Comparison & Fuzzy Matching: RapidFuzz & python-Levenshtein
- Environment & Deployment: Docker & Hugging Face Spaces

## Functional Pipeline
1. Initialization: Run `Scripts/initialise_qdrant.py` to create a fresh collection in Qdrant.
2. Data Ingestion: Place PDFs in `knowledge_base/` and run `Scripts/Data_insertion_qdrant.py` to chunk/embed them into Qdrant.
3. Web Host: Run `Scripts/chatbot_application.py` (or `app.py`) to start the localized interface. 
4. The system processes prompts, embeds them, searches the Vector DB, and pipes the highly relevant chunks to the OpenAI responder.

## To Run the Project (Locally Python):
Simply activate the environment and run the application:
  python Scripts\chatbot_application.py

## To Run the Project (Using Docker):
Since a container image is provided, you can completely sidestep local Python setups:
  1. Build the network security app image: 
     docker build -t ai_tutor .
  2. Run the platform mapping the web UI port: 
     docker run -p 7860:7860 --env-file .env ai_tutor
  3. UI will be available at http://localhost:7860