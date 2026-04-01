# Use an official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependencies file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY ./Admin-Backend ./Admin-Backend

# Set working dir to where main.py is
WORKDIR /app/Admin-Backend

# Expose FastAPI port
EXPOSE 8020

# Start FastAPI
CMD ["uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8020"]
