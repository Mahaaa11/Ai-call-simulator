# Déploiement sur jenna-controle.com (domaine propre)

## Problème actuel

La page `simulation.html` est servie, mais l'API MySQL (`conversation_api.py`) **n'est pas accessible** à l'URL :

`https://jenna-controle.com/conv-api/health`

Le navigateur appelle cette URL — si elle renvoie 404/502, MySQL apparaît « inactif ».

---

## Checklist serveur (3 étapes)

### 1. Configurer MySQL distant dans `web/.env`

Sur le serveur, copiez `.env.production.example` → `.env` :

```env
MYSQL_HOST=adresse-de-votre-mysql.com
MYSQL_PORT=3306
MYSQL_USER=votre_user
MYSQL_PASSWORD=votre_password
MYSQL_DATABASE=call_simulator
MYSQL_SSL=true
BIND_HOST=0.0.0.0
API_PORT=8766
```

Test :

```bash
cd AI_Call_Simulator/web
python3 conversation_api.py
# Doit afficher : Connexion MySQL : OK
```

Ctrl+C puis lancez en arrière-plan :

```bash
chmod +x start_production.sh
nohup ./start_production.sh > api.log 2>&1 &
```

### 2. Configurer Nginx

Copiez `nginx.jenna-controle.conf` dans votre config nginx (ex. `/etc/nginx/sites-available/jenna-controle`).

Points clés :

```nginx
location /conv-api/ {
    proxy_pass http://127.0.0.1:8766/;
}
location /tts/ {
    proxy_pass http://127.0.0.1:8765/;
}
```

Puis :

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 3. Vérifier depuis le navigateur

Ouvrez : `https://jenna-controle.com/conv-api/health`

Réponse attendue :

```json
{"ok": true, "database": "call_simulator"}
```

---

## Fichiers à déployer sur le serveur

```text
/var/www/ai-call-simulator/
  simulation.html
  config.json          ← copie de config.production.json
  conversation_api.py
  tts_server.py
  .env                 ← MYSQL distant (ne pas committer)
```

`config.json` :

```json
{
  "conversationApiUrl": "https://jenna-controle.com/conv-api",
  "ttsApiUrl": "https://jenna-controle.com/tts"
}
```

---

## Erreurs fréquentes

| Symptôme | Cause | Fix |
|----------|-------|-----|
| `/conv-api/health` → 404 | Nginx pas configuré | Ajouter proxy `/conv-api/` |
| `/conv-api/health` → 502 | API pas lancée | `start_production.sh` |
| API OK mais `ok: false` | Mauvais MYSQL_HOST | Corriger `web/.env` |
| SSL error MySQL | Hébergeur exige SSL | `MYSQL_SSL=true` |
| TTS warning | Normal | Voix navigateur utilisée en fallback |

---

## Service systemd (recommandé)

Créez `/etc/systemd/system/call-simulator-api.service` :

```ini
[Unit]
Description=Call Simulator API
After=network.target

[Service]
WorkingDirectory=/var/www/ai-call-simulator
ExecStart=/usr/bin/python3 conversation_api.py
Restart=always
Environment=BIND_HOST=0.0.0.0

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now call-simulator-api
```
