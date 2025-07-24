FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install python-telegram-bot==20.3 && \
    pip install solders==0.14.4 && \
    pip install requests==2.31.0 && \
    pip install solana==0.29.0 && \
    pip install base58==2.1.1
COPY . .
CMD ["python", "trojanbot.py"]
