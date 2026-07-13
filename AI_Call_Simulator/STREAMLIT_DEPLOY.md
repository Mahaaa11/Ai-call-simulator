# Déploiement Streamlit Cloud (le plus rapide)

## 1. Stocker la clé API

### En local (test)

Éditez `AI_Call_Simulator/.env` :

```env
OPENROUTER_API_KEY=sk-or-v1-votre-cle
```

Puis :

```bash
cd AI_Call_Simulator
source .venv/bin/activate   # ou créez le venv
pip install -r requirements.txt
streamlit run app.py
```

### Sur Streamlit Cloud

1. Allez sur [share.streamlit.io](https://share.streamlit.io)
2. **Settings → Secrets** — ajoutez OpenRouter **et MySQL** :

```toml
OPENROUTER_API_KEY = "sk-or-v1-..."
MYSQL_HOST = "votre-hote-mysql.com"
MYSQL_PORT = 3306
MYSQL_USER = "votre_user"
MYSQL_PASSWORD = "votre_password"
MYSQL_DATABASE = "call_simulator"
MYSQL_SSL = "true"
```

Les conversations sont **sauvegardées automatiquement** dans MySQL à la fin de chaque appel.

Alternative : si vous avez une API externe, utilisez `CONVERSATION_API_URL` au lieu de MYSQL_*.

---

## 2. Structure requise sur GitHub

```text
votre-repo/
  AI_Call_Simulator/
    app.py
    requirements.txt          # streamlit uniquement
    .streamlit/config.toml
    web/simulation.html
    ui/streamlit_web_simulator.py
```

---

## 3. Ce qui fonctionne sur Streamlit Cloud

| Fonction | Statut |
|----------|--------|
| Simulation prospect (OpenRouter/Nemotron) | ✅ |
| Micro agent (reconnaissance vocale) | ✅ (HTTPS fourni par Streamlit) |
| Voix prospect | ✅ voix navigateur (fallback auto) |
| Évaluation /100 | ✅ |
| Sauvegarde MySQL | ❌ (optionnel, pas bloquant) |
| TTS edge-tts serveur | ❌ (fallback navigateur) |

---

## 4. Déploiement en 5 minutes

```bash
# 1. Commit & push
git add AI_Call_Simulator/
git commit -m "Deploy simulateur Streamlit"
git push

# 2. share.streamlit.io → New app
#    Repo + branch + AI_Call_Simulator/app.py

# 3. Ajouter le secret OPENROUTER_API_KEY

# 4. Deploy → URL du type :
#    https://votre-app.streamlit.app
```

---

## 5. Version locale complète (Ollama + MySQL + TTS)

Pour la version Python complète avec Ollama :

```bash
pip install -r requirements-full.txt
streamlit run ui/streamlit_app.py
```

La version web OpenRouter (recommandée) : `streamlit run app.py`
