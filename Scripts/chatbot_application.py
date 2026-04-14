# for building the web application interface
import logging
import os
import random
import re
import requests
from functools import lru_cache
from pathlib import Path

import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer, util

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from qdrant_connection import build_qdrant_client

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

logging.basicConfig(filename="query_logs.txt", level=logging.INFO)

embedder = SentenceTransformer("all-MiniLM-L12-v2")
qdrant_client = build_qdrant_client()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = (os.environ.get("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini").strip()
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "").strip()
PUBLIC_APP_URL = os.environ.get("PUBLIC_APP_URL", "").strip().rstrip("/")

_openai_client = None


def get_openai_client():
    global _openai_client
    if not OPENAI_API_KEY:
        return None
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def openai_chat(system: str, user: str, max_tokens: int = 512) -> str:
    client = get_openai_client()
    if not client:
        return (
            "⚠️ OPENAI_API_KEY is missing. Add it to the `.env` file in the project root "
            "(see `.env.example`)."
        )
    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.35,
        )
        return (r.choices[0].message.content or "").strip()
    except Exception as e:
        return f"⚠️ OpenAI request failed: {e}"

# Qdrant collection name
collection_name = "network_security_knowledge"

@lru_cache(maxsize=100)
def cached_generate_response(prompt, mode):
    # Implements Least Recently Used (LRU) caching for the last 100 queries to improve speed and reduce LLM load.
    return generate_response(prompt, mode)


# This function takes the user's Prompt and converts into an embedding and queries the Qdrant database for similar documents
# This uses fuzz.partial_ratio to filter results based on text similarity to ensure relevance

def find_relevant_document(prompt):
    emb = embedder.encode([prompt])[0]
    results = qdrant_client.query_points(
        collection_name=collection_name,
        query=emb.tolist(),
        limit=10
    ).points
    matches = []
    for hit in results:
        payload = hit.payload
        score = fuzz.partial_ratio(prompt.lower(), payload["text"].lower())
        if score > 60:
            matches.append(payload)
    return matches


# web_search function uses SerpAPI to perform online searches when no relevant documents are found in the local database.
def web_search(query):
    # --------------------------
    # Validate API Key
    # --------------------------
    if not SERPAPI_API_KEY or SERPAPI_API_KEY == "YOUR_KEY":
        return (
            "⚠️ ERROR: SERPAPI_API_KEY is missing or invalid.\n"
            "Please set a valid API key.\n"
            
            ""
        )

    try:
        # --------------------------
        # Perform SerpAPI Search
        # --------------------------
        r = requests.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": SERPAPI_API_KEY, "engine": "google", "num": 3}
        )

        # --------------------------
        # HTTP-Level Errors
        # --------------------------
        if r.status_code == 401:
            return ("⚠️ ERROR: Unauthorized (401). API key is wrong or expired.", "")
        if r.status_code == 403:
            return ("⚠️ ERROR: Forbidden (403). API key may be invalid or blocked.", "")
        if r.status_code == 429:
            return ("⚠️ ERROR: Rate limit exceeded (429). Free quota is used up.", "")
        if r.status_code != 200:
            return (f"⚠️ ERROR: HTTP {r.status_code}. Unable to fetch online results.", "")

        # --------------------------
        # Parse JSON Results
        # --------------------------
        data = r.json().get("organic_results", [])

        if not data:
            return ("⚠️ No results found for this query online.", "")

        # --------------------------
        # Extract snippets
        # --------------------------
        snippet = data[0].get("snippet", "⚠️ No snippet available.")
        urls = "\n".join([
            f"{d.get('title', 'No title')} – {d.get('link', '')}"
            for d in data
        ])

        return snippet, urls

    except Exception as e:
        # --------------------------
        # Catch Network / Parsing Errors
        # --------------------------
        return (f"⚠️ ERROR: Online search failed.\nDetails: {str(e)}", "")
    

def generate_response(prompt, mode):
    docs = find_relevant_document(prompt)

    if docs:
        ctx = (
            f"Answer using only the context below. If it is insufficient, say so briefly.\n\n"
            f"Question: {prompt}\n\nContext:\n"
        )
        for d in docs:
            ctx += d["text"] + "\n\n"
        system = (
            "You are a network security tutor. Ground answers in the provided context; "
            "do not invent facts not supported by it."
        )
        if mode == "Concise":
            system += " Respond in at most 2 short sentences."
        else:
            system += " Give a clear, structured explanation."
        out = openai_chat(system, ctx, max_tokens=600)
        if mode == "Concise" and out and not out.startswith("⚠️"):
            out = out.split("\n")[0]
        unique_docs = list(set([d["document"] for d in docs]))
        src = "\n".join(unique_docs)
        return out, src

    snippet, src = web_search(prompt)
    if snippet.startswith("⚠️"):
        return snippet, src
    system = (
        "You are a network security tutor. Answer from the web excerpt and source titles; "
        "note uncertainty if the excerpt is thin."
    )
    user = f"Question: {prompt}\n\nWeb excerpt:\n{snippet}\n\nSources:\n{src}"
    out = openai_chat(system, user, max_tokens=500)
    return out, src or "Internet Search"


# Parses the raw model output to extract different question types
def parse_mcq(block, source):
    q = re.search(r"QUESTION:\s*(.+)", block)
    A = re.search(r"A\)\s*(.+)", block)
    B = re.search(r"B\)\s*(.+)", block)
    C = re.search(r"C\)\s*(.+)", block)
    D = re.search(r"D\)\s*(.+)", block)
    correct = re.search(r"CORRECT:\s*([A-D])", block)

    if not (q and A and B and C and D and correct):
        return None

    opts = [A.group(1).strip(), B.group(1).strip(),
            C.group(1).strip(), D.group(1).strip()]
    correct_opt = opts["ABCD".index(correct.group(1).strip())]

    return {
        "type": "MCQ",
        "question": q.group(1).strip(),
        "options": opts,
        "answer": correct_opt,
        "source": source
    }

# Parses True/False questions from the GPT4All output
def parse_tf(block, source):
    q = re.search(r"QUESTION:\s*(.+)", block)
    correct = re.search(r"CORRECT:\s*(True|False)", block, re.I)

    if not (q and correct):
        return None

    return {
        "type": "TF",
        "question": q.group(1).strip(),
        "options": ["True", "False"],
        "answer": correct.group(1).capitalize(),
        "source": source
    }

# Parses Open-ended questions from the GPT4All output
def parse_open(block, source):
    q = re.search(r"QUESTION:\s*(.+)", block)
    ans = re.search(r"EXPECTED_ANSWER:\s*(.+)", block)

    if not (q and ans):
        return None

    return {
        "type": "OPEN",
        "question": q.group(1).strip(),
        "answer": ans.group(1).strip(),
        "source": source
    }

# List of topics for quiz generation
SLIDE_TOPICS = [
    "CIA Triad", "Security Attacks", "Symmetric Encryption",
    "Public Key Cryptography", "Hashing", "MAC", "AES", "DES",
    "Kerberos", "Diffie-Hellman", "Digital Signatures", "PKI"
]



# if mode is "Random Quiz", a random topic from SLIDE_TOPICS is selected.
# if mode is "Topic-Specific Quiz", the provided topic is used.
def generate_quiz(topic, mode):
    if mode == "Random Quiz":
        topic = random.choice(SLIDE_TOPICS)
    
    if mode == "Topic-Specific Quiz" and not topic.strip():
        topic = random.choice(SLIDE_TOPICS)
    

    docs = find_relevant_document(topic)

    if docs:
        context = "\n\n".join([d["text"] for d in docs[:3]])
        # Remove page number from quiz source - show only document name
        source = docs[0]['document']
    else:
        snippet, _ = web_search(topic)
        context = snippet
        source = "Internet Search"

    # STRICT MCQ generation prompt
    prompt = f"""
Generate EXACTLY 5 quiz questions about {topic}.
DO NOT SKIP ANY QUESTION
FORMAT:
MCQ1:
QUESTION: <text>
A) <text>
B) <text>
C) <text>
D) <text>
CORRECT: <A/B/C/D>

MCQ2:
QUESTION: <text>
A) <text>
B) <text>
C) <text>
D) <text>
CORRECT: <A/B/C/D>

TF1:
QUESTION: <text>
CORRECT: True/False

TF2:
QUESTION: <text>
CORRECT: True/False

OPEN:
QUESTION: <text>
EXPECTED_ANSWER: <short>

RULES:
- No repeated options
- No extra explanations
- Each option must be on a new line
- Follow format exactly
CONTENT:
{context}
"""

    raw = openai_chat(
        "You follow formatting instructions exactly. Output only the quiz in the specified format, no preamble.",
        prompt,
        max_tokens=1200,
    )

    mcq_blocks = re.findall(r"MCQ\d+:(.+?)(?=MCQ|TF|OPEN|$)", raw, re.DOTALL)
    tf_blocks = re.findall(r"TF\d+:(.+?)(?=MCQ|TF|OPEN|$)", raw, re.DOTALL)
    open_block = re.search(r"OPEN:(.+)$", raw, re.DOTALL)

    quiz = []

    for blk in mcq_blocks[:2]:
        q = parse_mcq(blk, source)
        if q: quiz.append(q)

    for blk in tf_blocks[:2]:
        q = parse_tf(blk, source)
        if q: quiz.append(q)

    if open_block:
        q = parse_open(open_block.group(1), source)
        if q: quiz.append(q)

    # FORCE OPEN QUESTION LAST
    quiz = sorted(quiz, key=lambda x: x["type"] == "OPEN")

    return quiz[:5]


"""
 Grades the quiz based on user answers and the generated quiz
 Provides feedback and a grade
 for MCQ and TF questions, it checks for exact matches
 for OPEN questions, it uses semantic similarity to grade
 Similarity > 0.65 = Full point (Correct)
 Similarity > 0.40 = Half point (Partial) 
 Similarity <=0.40 = Zero points (Wrong)
"""
def grade_quiz(user_answers, quiz):
    score = 0
    details = ""

    for i, (ua, q) in enumerate(zip(user_answers, quiz)):
        if ua in [None, "", []]:
            details += f"Q{i+1}: ✗ Not answered - Correct: {q['answer']}\n"
            continue
        if q["type"] in ["MCQ", "TF"]:
            if ua == q["answer"]:
                score += 1
                details += f"Q{i+1}: ✓ Correct\n"
            else:
                details += f"Q{i+1}: ✗ Wrong — Correct: {q['answer']}\n"
        else:
            emb1 = embedder.encode([ua], convert_to_tensor=True)
            emb2 = embedder.encode([q["answer"]], convert_to_tensor=True)
            sim = float(util.pytorch_cos_sim(emb1, emb2))

            if sim > 0.65:
                score += 1
                details += f"Q{i+1}: ✓ Correct (Sim={sim:.2f})\n"
            elif sim > 0.40:
                score += 0.5
                details += f"Q{i+1}: ◐ Partial (Sim={sim:.2f})\n"
            else:
                details += f"Q{i+1}: ✗ Wrong (Sim={sim:.2f})\n"

    return score, details


# Renders the quiz UI dynamically based on the generated quiz
def render_quiz(mode, topic):
    quiz = generate_quiz(topic, mode)

    # FIXED LAYOUT - Always handle all 5 slots
    q_updates, a_updates, s_updates = [], [], []

    for i in range(5):  # Always loop 5 times
        if i < len(quiz):  # If we have a question for this slot
            q = quiz[i]
            q_updates.append(gr.update(value=f"**Question {i+1}** ({q['type']})\n\n{q['question']}", visible=True))

            if q["type"] == "OPEN":
                a_updates.append(gr.update(value="", visible=True))
            else:
                a_updates.append(gr.update(value=None, choices=q["options"], visible=True))

            s_updates.append(gr.update(value=f"📚 Source: {q['source']}", visible=True))
        else:  # No question for this slot - hide it
            q_updates.append(gr.update(value="", visible=False))
            a_updates.append(gr.update(visible=False))
            s_updates.append(gr.update(value="", visible=False))

    return (
        quiz,
        gr.update(value="✅ Quiz generated successfully! Answer the questions below.", visible=True),
        *q_updates, *a_updates, *s_updates
    )




#############################################
###############  UI SETUP  ##################
#############################################

# Custom CSS for modern UI
custom_css = """
#main-container {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
}

.gradio-container {
    max-width: 1200px !important;
    margin: auto;
}

#header-title {
    text-align: center;
    color: white;
    font-size: 2.5em;
    font-weight: bold;
    margin-bottom: 10px;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

#header-subtitle {
    text-align: center;
    color: #e0e0e0;
    font-size: 1.2em;
    margin-bottom: 30px;
}

.card {
    background: white;
    border-radius: 15px;
    padding: 25px;
    box-shadow: 0 8px 16px rgba(0,0,0,0.2);
    margin: 15px 0;
}

.question-box {
    background: #f8f9fa;
    border-left: 4px solid #667eea;
    padding: 15px;
    border-radius: 8px;
    margin: 10px 0;
}

.score-display {
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    color: white;
    padding: 20px;
    border-radius: 12px;
    text-align: center;
    font-size: 1.5em;
    font-weight: bold;
}
"""

_demo_try_sidebar = (
    f"### 🚀 Try the live app\n"
    f"**[Give the quiz generator a try]({PUBLIC_APP_URL})** — share this link on GitHub or your portfolio.\n"
    if PUBLIC_APP_URL
    else (
        "### 🚀 Try the live app\n"
        "After you deploy (for example [Hugging Face Spaces](https://huggingface.co/spaces)), set **`PUBLIC_APP_URL`** in `.env` "
        "to the public URL. The same link is documented at the top of `README.md` for visitors.\n"
    )
)

_quiz_demo_banner = (
    f'<p style="text-align:center;margin:0 0 12px 0;"><a href="{PUBLIC_APP_URL}" target="_blank" rel="noopener noreferrer" '
    f'style="font-size:1.15em;font-weight:600;">Give the quiz generator a try → open live demo</a></p>'
    if PUBLIC_APP_URL
    else (
        '<p style="text-align:center;color:#666;margin:0 0 12px 0;">'
        "Set <code>PUBLIC_APP_URL</code> in <code>.env</code> after deployment so this becomes a clickable link for reviewers."
        "</p>"
    )
)

with gr.Blocks(title="🔐 Network Security Learning Hub") as app:
    
    # Header
    gr.HTML("""
        <div id="main-container">
            <h1 id="header-title">🔐 Network Security Learning Hub</h1>
            <p id="header-subtitle">AI-Powered Tutor & Interactive Quiz System</p>
        </div>
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            # Sidebar Navigation
            gr.Markdown("""
            ### 📋 Navigation
            Choose your learning mode:
            - **💬 AI Tutor**: Ask questions and get instant answers
            - **📝 Quiz Center**: Test your knowledge with AI-generated quizzes
            """)
            
            gr.Markdown("""
            ### 📚 Available Topics
            - CIA Triad
            - Security Attacks
            - Encryption Methods
            - PKI & Digital Signatures
            - And more...
            """)
            gr.Markdown(_demo_try_sidebar)
        
        with gr.Column(scale=3):
            with gr.Tabs():
                
                # ============ TUTOR TAB ============
                with gr.Tab("💬 AI Tutor", id="tutor-tab"):
                    gr.Markdown("""
                    <div class="card">
                    <h2>🤖 Ask Your Security Questions</h2>
                    <p>Get instant, AI-powered answers from your slides and textbook (RAG), with web search when needed. Answers use OpenAI.</p>
                    </div>
                    """)
                    
                    with gr.Row():
                        with gr.Column():
                            t_in = gr.Textbox(
                                lines=5, 
                                label="💭 Your Question",
                                placeholder="Example: What is the CIA Triad in network security?",
                                elem_classes="question-box"
                            )
                            
                            with gr.Row():
                                t_mode = gr.Radio(
                                    ["Concise", "Detailed"], 
                                    value="Detailed",
                                    label="Response Style",
                                    info="Choose how detailed you want the answer"
                                )
                                ask_btn = gr.Button("🔍 Get Answer", variant="primary", size="lg")
                    
                    with gr.Row():
                        with gr.Column():
                            t_out = gr.Textbox(
                                lines=12, 
                                label="💡 Answer"
                            )
                            t_src = gr.Textbox(
                                lines=4, 
                                label="📎 Sources"
                            )
                    
                    def ui_generate(p, m):
                        try:
                            return cached_generate_response(p, m)
                        except Exception as e:
                            import traceback
                            return f"⚠️ CRASH: {str(e)}\n\n{traceback.format_exc()}", "ERROR TRACE"
                    ask_btn.click(
                        ui_generate,
                        [t_in, t_mode],
                        [t_out, t_src]
                    )

                # ============ QUIZ TAB ============
                with gr.Tab("📝 Quiz Center", id="quiz-tab"):
                    gr.HTML(f'<div class="card">{_quiz_demo_banner}</div>')
                    gr.Markdown("""
                    <div class="card">
                    <h2>🎯 Test Your Knowledge</h2>
                    <p>Generate personalized quizzes on network security topics. Answer MCQs, True/False, and open-ended questions!</p>
                    </div>
                    """)
                    
                    # Quiz Configuration
                    with gr.Row():
                        with gr.Column(scale=2):
                            quiz_mode = gr.Radio(
                                ["Random Quiz", "Topic-Specific Quiz"], 
                                value="Random Quiz",
                                label="🎲 Quiz Mode",
                                info="Choose random topics or specify your own"
                            )
                        with gr.Column(scale=2):
                            topic_input = gr.Textbox(
                                label="📌 Specific Topic (Optional)",
                                placeholder="e.g., AES, Kerberos, Digital Signatures"
                            )
                        with gr.Column(scale=1):
                            generate_btn = gr.Button("🎨 Generate Quiz", variant="primary", size="lg")
                    
                    loading_msg = gr.Markdown("👆 Click 'Generate Quiz' to start your assessment", elem_id="loading-msg")
                    
                    quiz_state = gr.State()
                    
                    # Quiz Questions Container
                    gr.Markdown("---")
                    
                    with gr.Group():
                        q1 = gr.Markdown(visible=False, elem_classes="question-box")
                        a1 = gr.Radio([], visible=False, label="Select your answer")
                        s1 = gr.Markdown(visible=False)
                    
                    with gr.Group():
                        q2 = gr.Markdown(visible=False, elem_classes="question-box")
                        a2 = gr.Radio([], visible=False, label="Select your answer")
                        s2 = gr.Markdown(visible=False)
                    
                    with gr.Group():
                        q3 = gr.Markdown(visible=False, elem_classes="question-box")
                        a3 = gr.Radio([], visible=False, label="Select your answer")
                        s3 = gr.Markdown(visible=False)
                    
                    with gr.Group():
                        q4 = gr.Markdown(visible=False, elem_classes="question-box")
                        a4 = gr.Radio([], visible=False, label="Select your answer")
                        s4 = gr.Markdown(visible=False)
                    
                    with gr.Group():
                        q5 = gr.Markdown(visible=False, elem_classes="question-box")
                        a5 = gr.Textbox(lines=4, visible=False, label="Write your answer", placeholder="Type your detailed answer here...")
                        s5 = gr.Markdown(visible=False)
                    
                    gr.Markdown("---")
                    
                    # Grading Section
                    with gr.Row():
                        grade_btn = gr.Button("📊 Submit & Grade Quiz", variant="stop", size="lg", scale=2)
                    
                    with gr.Row():
                        with gr.Column(scale=1):
                            score_out = gr.Textbox(label="🏆 Your Score", elem_classes="score-display")
                        with gr.Column(scale=2):
                            details_out = gr.Textbox(lines=12, label="📋 Detailed Feedback")
                    
                    # Event Handlers
                    generate_btn.click(
                        lambda: gr.update(value="⏳ Generating your personalized quiz... Please wait...", visible=True),
                        None,
                        loading_msg
                    ).then(
                        render_quiz,
                        [quiz_mode, topic_input],
                        [quiz_state, loading_msg,
                         q1, q2, q3, q4, q5,
                         a1, a2, a3, a4, a5,
                         s1, s2, s3, s4, s5]
                    )

                    def grade_ui(quiz, a1, a2, a3, a4, a5):
                        if not quiz or len(quiz) == 0:
                            return "⚠️ No Quiz Generated", "Please generate a quiz first before grading!"
       
                        answers = [a1, a2, a3, a4, a5]
                        score, detail = grade_quiz(answers, quiz)
                        return f"🎯 {score}/5", detail

                    grade_btn.click(
                        grade_ui,
                        [quiz_state, a1, a2, a3, a4, a5],
                        [score_out, details_out]
                    )

    # Footer
    gr.Markdown("""
    ---
    <div style="text-align: center; color: #666; padding: 20px;">
    <p>🔒 Powered by OpenAI ({OPENAI_MODEL}), Sentence Transformers & Qdrant</p>
    </div>
    """)

app.launch(
    share=os.environ.get("GRADIO_SHARE", "").lower() in ("1", "true", "yes"),
    css=custom_css,
)