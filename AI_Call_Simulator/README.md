# Simulateur d'appels sortants IA

Deux interfaces pour entraîner les agents sur des appels sortants énergie en français :

| Interface | Stack | Usage |
|-----------|-------|--------|
| **`web/simulation.html`** | OpenRouter + Nemotron, TTS edge, MySQL | Simulateur principal (voix, profils calibrés, /100) |
| **`ui/streamlit_app.py`** | Ollama + Whisper + knowledge base | Version Python modulaire + import d'appels réels |

---

## Simulateur web (recommandé)

### Structure

```text
AI_Call_Simulator/web/
  simulation.html       # App principale (HTML/JS)
  tts_server.py         # Voix prospect — port 8765
  conversation_api.py   # Sauvegarde MySQL — port 8766
  mysql_schema.sql
  docker-compose.yml    # MySQL 8
  start.sh              # Démarre tout
  .env.example
```

### Démarrage rapide

```bash
cd AI_Call_Simulator/web
chmod +x start.sh
./start.sh
```

Puis ouvrir **http://localhost:8080/simulation.html** (Cmd+Shift+R).

### Hébergement production (VPS + Docker)

```bash
cd AI_Call_Simulator/web
chmod +x deploy.sh
./deploy.sh
```

Voir **`web/DEPLOY.md`** pour HTTPS, domaine, firewall et checklist complète.

### Démarrage manuel (3 terminaux)

```bash
cd AI_Call_Simulator/web
docker compose up -d
pip install pymysql edge-tts

python3 tts_server.py          # 8765
python3 conversation_api.py    # 8766
python3 -m http.server 8080
```

Configurer `web/.env` (copie de `.env.example`) pour MySQL.

---

## Streamlit (Ollama)

Application modulaire avec moteur Python, objections PDF, transcription d'appels réels.

### Requirements

- Python 3.12
- Ollama + `qwen2.5:3b`
- Microphone

### Setup

```bash
cd AI_Call_Simulator
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5:3b
streamlit run ui/streamlit_app.py
```

---

## Structure du projet

```text
AI_Call_Simulator/
  web/                  # Simulateur HTML + services
  ui/streamlit_app.py   # Interface Streamlit
  engine/               # Logique métier Python
  data/                 # Knowledge base, transcripts, training
  scripts/              # Import/transcription appels
  requirements.txt
```

---

## Notes Streamlit

1. `Démarrer l'appel` → le prospect parle en premier.
2. Enregistrer → `Transcrire l'audio` → `Envoyer au prospect`.
3. Les enregistrements réels peuvent être importés comme références de style.

Piper TTS n'est pas requis : synthèse navigateur (Streamlit) ou edge-tts (web).
