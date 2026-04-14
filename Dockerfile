FROM python:3.12-slim

# Optimization: Ensure Python output is immediately flushed (vital for HF Spaces logs)
ENV PYTHONUNBUFFERED=1

# Working Directory
WORKDIR /app

# Optimization: Copy only required application files (avoiding bulky .venv if present, though .dockerignore is best practice)
COPY . /app

# Install Dependencies in a single optimized layer
RUN pip install --no-cache-dir \
    openenv-core \
    openai \
    pydantic \
    python-dotenv

# Debugging Support & Default Command:
# Echoes a startup message before executing the inference script
CMD ["sh", "-c", "echo 'Starting Autonomous Incident Response Environment...' && python inference.py"]
