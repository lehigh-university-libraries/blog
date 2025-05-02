FROM python:3.13-slim@sha256:60248ff36cf701fcb6729c085a879d81e4603f7f507345742dc82d4b38d16784

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "http.server", "8000", "--directory", "public"]
