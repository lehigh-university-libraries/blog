# Use an official Python runtime as a base image
FROM python:3.13-slim@sha256:8f3aba466a471c0ab903dbd7cb979abd4bda370b04789d25440cc90372b50e04

# Set the working directory
WORKDIR /app

# Copy the requirements (if you have one) and install them
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8000 for the local server
EXPOSE 8000

# Default command to run when the container starts
CMD ["python", "-m", "http.server", "8000", "--directory", "public"]
