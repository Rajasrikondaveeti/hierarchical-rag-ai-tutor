FROM python:3.10-slim

# Create a non-root user (Required for Hugging Face Spaces and best security practice)
RUN useradd -m -u 1000 user
USER user

# Set essential environment variables
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    GRADIO_SERVER_NAME="0.0.0.0" \
    GRADIO_SERVER_PORT="7860"

# Setup working directory as the non-root user
WORKDIR $HOME/app

# Copy requirements and install them securely
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Explicitly ensure the heavy packages that failed the bulk install earlier are present
RUN pip install --no-cache-dir --user gradio sentence-transformers

# Copy the remaining project files
COPY --chown=user . .

# Expose the Gradio container port
EXPOSE 7860

# Define the entry point for the container
CMD ["python", "app.py"]
