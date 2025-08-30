FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgthread-2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements_web.txt .
RUN pip install --no-cache-dir -r requirements_web.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p uploads static/outputs templates static logs

# Set environment variables
ENV FLASK_APP=web_app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -sf http://localhost:5000/status || exit 1

# Run the application
CMD ["python", "run_web.py"]
