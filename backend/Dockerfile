FROM python:3.12-slim

WORKDIR /app

# Eerst alleen requirements: deze laag wordt gecached zolang de lijst niet verandert
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Daarna de code
COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
