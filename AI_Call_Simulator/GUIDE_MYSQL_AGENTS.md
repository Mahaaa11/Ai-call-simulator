# MySQL en ligne pour Streamlit (agents sur plusieurs PC)

## Pourquoi

- Les agents utilisent **Streamlit Cloud** (`*.streamlit.app`) depuis n'importe quel PC
- Streamlit doit écrire dans une base **accessible sur Internet**
- MySQL sur votre Mac (`127.0.0.1`) **ne fonctionne pas** pour eux

**Solution : MySQL gratuit sur Railway + Secrets Streamlit**

Durée : ~15 minutes.

---

## Étape 1 — Créer MySQL sur Railway

1. Allez sur [railway.app](https://railway.app) → connectez GitHub
2. **New Project** → **Provision MySQL**
3. Cliquez sur le service **MySQL** → onglet **Variables** ou **Connect**

Notez ces valeurs (noms Railway habituels) :

| Variable Railway | → Secret Streamlit |
|------------------|-------------------|
| `MYSQLHOST` | `MYSQL_HOST` |
| `MYSQLPORT` | `MYSQL_PORT` |
| `MYSQLUSER` | `MYSQL_USER` |
| `MYSQLPASSWORD` | `MYSQL_PASSWORD` |
| `MYSQLDATABASE` | `MYSQL_DATABASE` |

Si la base s'appelle autre chose, créez la base `call_simulator` ou utilisez celle fournie.

---

## Étape 2 — Pousser le code sur GitHub

```bash
cd "/Users/macbookpro/Documents/agent conversation"
git add AI_Call_Simulator/
git commit -m "Sauvegarde conversations MySQL depuis Streamlit"
git push
```

---

## Étape 3 — Secrets Streamlit Cloud

1. [share.streamlit.io](https://share.streamlit.io) → votre app **ai-call-simulator**
2. **Settings → Secrets**
3. Collez (avec **vos vraies valeurs Railway**) :

```toml
OPENROUTER_API_KEY = "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"

MYSQL_HOST = "containers-us-west-XXX.railway.app"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "le_mot_de_passe_railway"
MYSQL_DATABASE = "railway"
MYSQL_SSL = "true"
```

4. **Save** → attendez le redéploiement (1–2 min)

---

## Étape 4 — Vérifier

1. Ouvrez l'URL Streamlit de vos agents
2. Message attendu : **✅ MySQL connecté via Streamlit**
3. Faites un appel test → **Raccrocher et Lancer l'Évaluation**
4. Message : **✅ Conversation #X enregistrée dans MySQL**

---

## Voir les conversations sauvegardées

Connectez-vous à MySQL Railway (CLI ou client type DBeaver) :

```sql
USE railway;  -- ou call_simulator
SELECT id, profile_key, score_total, score_level, created_at
FROM conversations
ORDER BY id DESC
LIMIT 20;
```

Les tables sont créées automatiquement au premier enregistrement.

---

## Si MySQL ne connecte pas

| Erreur | Solution |
|--------|----------|
| `Can't connect` | Vérifiez `MYSQL_HOST` et `MYSQL_PORT` Railway |
| SSL error | Gardez `MYSQL_SSL = "true"` |
| Access denied | Vérifiez user/password Railway |
| MySQL configuré mais inaccessible (warning Streamlit) | Attendez 2 min après Save, rafraîchissez |

---

## Alternative : MySQL sur le serveur jenna-controle.com

Si vous préférez votre propre serveur au lieu de Railway :

1. Installez MySQL sur le VPS `jenna-controle.com`
2. Créez la base `call_simulator` + utilisateur
3. Ouvrez le port 3306 (ou utilisez l'hôte interne si Streamlit n'est pas sur le même serveur)
4. Mettez l'**IP publique ou hostname** du serveur dans `MYSQL_HOST` (pas `127.0.0.1`)

Streamlit Cloud doit pouvoir joindre ce host depuis Internet.

---

## Résumé

```
Agents (PC 1, 2, 3…)
        ↓
Streamlit Cloud (*.streamlit.app)
        ↓  pymysql
MySQL Railway (en ligne)
        ↓
tables conversations + conversation_messages
```

Votre Mac n'a plus besoin d'être allumé.
