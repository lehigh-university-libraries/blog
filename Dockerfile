# Use an official Python runtime as a base image
FROM python:3.13-slim@sha256:f3614d98f38b0525d670f287b0474385952e28eb43016655dd003d0e28cf8652

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
