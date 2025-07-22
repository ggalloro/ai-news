# Use an official lightweight Python image.
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy local code to the container image.
COPY . .

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt && \
    echo "--- VERIFYING LIBRARY VERSION ---" && \
    pip show google-cloud-storage && \
    echo "---------------------------------"

# Run the web server on container startup.
# Use Gunicorn for production.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
