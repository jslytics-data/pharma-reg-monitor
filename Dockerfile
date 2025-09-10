# Use an official lightweight Python image
FROM python:3.11-slim

# Set environment variables for best practices
ENV PYTHONUNBUFFERED True
ENV PORT 8080

# Set the working directory in the container
WORKDIR /app

# Copy and install dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's source code
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# Define the command to run the application using a production server
# Using --timeout 0 is recommended for Cloud Run to let the service manage timeouts.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "main:app"]