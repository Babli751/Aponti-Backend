# Python 3.11 kullanıyoruz
FROM python:3.11-slim

# Çalışma dizini
WORKDIR /app

# Gereksinimleri yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Uvicorn ile başlat (FastAPI örneği)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
