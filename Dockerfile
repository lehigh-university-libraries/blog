# Use an official Python runtime as a base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements (if you have one) and install them
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pygmentize -S default -f html > public/pygments.css

# Copy the rest of the application code
COPY . .

# Expose port 8000 for the local server
EXPOSE 8000

# Default command to run when the container starts
CMD ["python", "-m", "http.server", "8000", "--directory", "public"]
