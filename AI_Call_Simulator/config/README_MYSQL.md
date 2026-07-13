# MySQL — Simulateur d'appels IA

## Fichier de connexion

**Chemin :** `AI_Call_Simulator/config/connexion_mysql.env`

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=call_simulator
MYSQL_DATABASE=call_simulator
CONVERSATION_API_URL=http://127.0.0.1:8766
```

| Paramètre | Valeur |
|-----------|--------|
| **Base de données** | `call_simulator` |
| **Tables** | `conversations`, `conversation_messages` |
| **Schéma SQL** | `web/mysql_schema.sql` |

---

## Activer en local (5 min)

```bash
cd AI_Call_Simulator/web

# 1. Démarrer MySQL (Docker)
docker compose up -d

# 2. Copier la connexion
cp ../config/connexion_mysql.env .env

# 3. Lancer l'API + simulateur
./start.sh
```

Ouvrez `http://localhost:8080/simulation.html` → statut **✅ MySQL connecté**.

---

## Activer sur Streamlit Cloud

Streamlit ne peut pas lancer MySQL directement. Il faut :

1. **Base MySQL cloud** (ex. [Railway](https://railway.app) → Add MySQL)
2. **API conversations** déployée (même Railway) :
   - Root : `AI_Call_Simulator/web`
   - Start : `python conversation_api.py`
   - Variables : `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `BIND_HOST=0.0.0.0`
3. **Streamlit Secrets** — ajoutez l'URL de l'API :

```toml
OPENROUTER_API_KEY = "sk-or-v1-..."
CONVERSATION_API_URL = "https://votre-api.railway.app"
```

---

## Tester la connexion

```bash
cd AI_Call_Simulator/web
python3 conversation_api.py
# → Connexion MySQL : OK
curl http://127.0.0.1:8766/health
```

Réponse attendue : `{"ok":true,"database":"call_simulator"}`
