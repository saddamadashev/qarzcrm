# Python-ning eng yengil versiyasini tanlaymiz
FROM python:3.11-slim

# Ishchi katalogni yaratamiz
WORKDIR /app

# Kutubxonalar ro'yxatini nusxalaymiz
COPY requirements.txt .

# Kutubxonalarni o'rnatamiz
RUN pip install --no-cache-dir -r requirements.txt

# Barcha kodlarni konteyner ichiga nusxalaymiz
COPY . .

# Botni ishga tushirish buyrug'i
CMD ["python", "main.py"]