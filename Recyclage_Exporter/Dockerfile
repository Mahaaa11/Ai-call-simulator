FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Définir DATABASE_URL au runtime pour PostgreSQL (Supabase, Neon, Railway…)
# Sans variable : SQLite persistant dans /app/data/store/recyclage.db
VOLUME ["/app/data/store"]

EXPOSE 8501

CMD ["streamlit", "run", "ui/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
