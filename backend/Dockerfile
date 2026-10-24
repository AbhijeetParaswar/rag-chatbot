FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for fitz/PyMuPDF and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY backend ./backend
COPY data/create_sample_pdfs.py ./data/create_sample_pdfs.py

# Create persistent directories
RUN mkdir -p /app/data/pdfs /app/data/chroma

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
