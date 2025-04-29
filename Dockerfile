FROM python:3.13-slim@sha256:549df749715caa7da8649af1fbf5c0096838a0d69c544dc53c3b3864bfeda4e3

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "http.server", "8000", "--directory", "public"]
