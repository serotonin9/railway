FROM python:3.10-slim  # Ganti ke Python 3.10 yang lebih stabil

WORKDIR /app

# Install dependencies satu per satu untuk isolasi error
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir python-telegram-bot==20.3 && \
    pip install --no-cache-dir solders==0.14.4 && \
    pip install --no-cache-dir requests==2.31.0 && \
    pip install --no-cache-dir solana==0.29.0 && \
    pip install --no-cache-dir base58==2.1.1

COPY . .

CMD ["python", "trojanbot.py"]
