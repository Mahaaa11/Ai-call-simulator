# Hébergement du simulateur web

Le simulateur principal est `web/simulation.html` avec 3 services backend :
- **Page web** (nginx)
- **TTS** voix prospect (edge-tts, port 8765)
- **API** sauvegarde conversations (MySQL, port 8766)

Chaque agent saisit sa **clé OpenRouter** dans l'interface (non stockée côté serveur).

---

## Option 1 — VPS avec Docker (recommandé)

### Prérequis
- Un serveur Linux (OVH, Hetzner, DigitalOcean, etc.)
- Docker + Docker Compose
- Nom de domaine (optionnel mais **obligatoire pour le micro** en HTTPS)

### Déploiement

```bash
# Sur le serveur
git clone <votre-repo> call-simulator
cd call-simulator/AI_Call_Simulator/web

cp .env.example .env
# Éditez .env : changez MYSQL_PASSWORD

chmod +x deploy.sh
./deploy.sh
```

Accès : `http://VOTRE_IP/simulation.html`

### HTTPS (micro obligatoire en production)

Le navigateur bloque le micro sans HTTPS. Sur le VPS :

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d simulateur.votredomaine.fr
```

Puis ajoutez un reverse proxy HTTPS (Caddy ou nginx + certificats) devant le port 80.

**Exemple Caddy** (`/etc/caddy/Caddyfile`) :

```text
simulateur.votredomaine.fr {
    reverse_proxy localhost:80
}
```

### Variables utiles

| Variable | Défaut | Description |
|----------|--------|-------------|
| `HTTP_PORT` | 80 | Port public nginx |
| `MYSQL_PASSWORD` | call_simulator | Mot de passe MySQL |
| `MYSQL_DATABASE` | call_simulator | Base de données |

```bash
HTTP_PORT=8080 ./deploy.sh   # si le port 80 est pris
```

### Commandes

```bash
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --build   # après mise à jour
```

---

## Option 2 — Local / test rapide (déjà en place)

```bash
cd AI_Call_Simulator/web
./start.sh
```

→ `http://localhost:8080/simulation.html`

---

## Option 3 — Tunnel temporaire (démo sans VPS)

Pour tester à distance sans acheter un serveur :

```bash
# Terminal 1
cd AI_Call_Simulator/web && ./start.sh

# Terminal 2
npx localtunnel --port 8080
# ou : cloudflared tunnel --url http://localhost:8080
```

⚠️ Le micro peut ne pas fonctionner via tunnel HTTP. Préférez HTTPS (Cloudflare Tunnel le fournit).

---

## Architecture production

```text
Internet
   │
   ▼
nginx:80  ──► simulation.html
   │
   ├── /tts/*      ──► tts_server:8765
   └── /conv-api/* ──► conversation_api:8766 ──► mysql:3306
```

L'app détecte automatiquement l'hébergement :
- **localhost** → ports 8765 / 8766 directs
- **serveur** → `/tts` et `/conv-api` via nginx

---

## Checklist avant mise en ligne

- [ ] Changer `MYSQL_PASSWORD` dans `.env`
- [ ] HTTPS activé (micro + reconnaissance vocale)
- [ ] Ports 80 (et 443) ouverts sur le firewall
- [ ] Crédits OpenRouter : chaque agent utilise sa propre clé
- [ ] Tester : voix prospect, enregistrement micro, évaluation /100, sauvegarde MySQL

---

## Streamlit (version alternative)

Si vous préférez la version Ollama/Whisper :

```bash
streamlit run ui/streamlit_app.py
```

Hébergement possible sur [Streamlit Community Cloud](https://streamlit.io/cloud) mais nécessite Ollama externe — la version **web** ci-dessus est recommandée pour la production.
