# Sauvegarde MySQL — hébergement cPanel (jenna-controle.com)

Vos identifiants MySQL utilisent `localhost` → la base n'est accessible **que depuis votre serveur**.
Streamlit Cloud ne peut pas s'y connecter directement.

**Solution :** une petite API PHP sur `jenna-controle.com` + Streamlit qui l'appelle.

---

## Étape 1 — Uploader l'API PHP sur jenna-controle.com

### Via cPanel File Manager

1. Connectez-vous à **cPanel** de jenna-controle.com
2. Ouvrez `public_html/`
3. Créez le dossier `conv-api/`
4. Uploadez `web/save_api.php` → renommez en `public_html/conv-api/index.php`
5. Éditez `index.php` lignes 21-24 avec vos identifiants :

```php
$DB_USER = 'zetvyznnvz_simulator';
$DB_PASS = 'VOTRE_MOT_DE_PASSE';
$DB_NAME = 'zetvyznnvz_simulator';
```

(`$DB_HOST` reste `localhost`)

---

## Étape 2 — Tester l'API

Ouvrez dans le navigateur :

**https://jenna-controle.com/conv-api/health**

Réponse attendue :
```json
{"ok":true,"database":"zetvyznnvz_simulator"}
```

Si erreur → vérifiez user/password dans `index.php`.

---

## Étape 3 — Secrets Streamlit Cloud

[share.streamlit.io](https://share.streamlit.io) → votre app → **Settings → Secrets** :

```toml
OPENROUTER_API_KEY = "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"

CONVERSATION_API_URL = "https://jenna-controle.com/conv-api"
```

**Ne mettez PAS** `MYSQL_HOST=localhost` dans Streamlit — ça ne marchera pas.

→ **Save**

---

## Étape 4 — Pousser le code (si pas fait)

```bash
cd "/Users/macbookpro/Documents/agent conversation"
git add AI_Call_Simulator/
git commit -m "API PHP MySQL pour hebergement mutualise"
git push
```

---

## Résultat

```
Agents (autres PC)
    → Streamlit Cloud
    → https://jenna-controle.com/conv-api  (PHP)
    → MySQL localhost sur le serveur
    → conversations sauvegardées ✅
```

---

## Sécurité

- Changez le mot de passe MySQL dans cPanel (il a été partagé dans le chat)
- Ne commitez jamais le mot de passe dans Git

---

## Dépannage

| Problème | Solution |
|----------|----------|
| `/conv-api/health` → 404 | Vérifiez que `index.php` est dans `public_html/conv-api/` |
| `Access denied` | Vérifiez user/password dans index.php |
| Streamlit : MySQL inactif | Vérifiez `CONVERSATION_API_URL` dans Secrets |
| CORS error | Le PHP gère déjà CORS (`Access-Control-Allow-Origin: *`) |
