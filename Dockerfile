# Use an official Python runtime as a base image
FROM python:3.13-slim@sha256:1127090f9fff0b8e7c3a1367855ef8a3299472d2c9ed122948a576c39addeaf1

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
