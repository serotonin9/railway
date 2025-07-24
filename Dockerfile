FROM python:3.9-slim
WORKDIR /app

# Update pip dulu
RUN pip install --upgrade pip

# Install dependencies secara terpisah
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade-strategy=only-if-needed -r requirements.txt

# Copy kode
COPY . .

CMD ["python", "trojanbot.py"]
