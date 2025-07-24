FROM python:3.9-slim
WORKDIR /app

# Copy semua file
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Jalankan bot
CMD ["python", "trojanbot.py"]
