import os
import sys
from pathlib import Path

# Add the project root to sys.path so we can import from Scripts
_ROOT = Path(__file__).resolve().parent
sys.path.append(str(_ROOT))

from Scripts.chatbot_application import app, custom_css

if __name__ == "__main__":
    # Hugging Face Spaces provides the port via the PORT environment variable
    # Gradio also looks for GRADIO_SERVER_PORT
    port = int(os.environ.get("PORT", 7860))
    
    print(f"🚀 Starting Network Security AI Tutor on port {port}...")
    
    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        css=custom_css,
        share=os.environ.get("GRADIO_SHARE", "").lower() in ("1", "true", "yes")
    )
