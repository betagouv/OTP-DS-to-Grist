
# 🚀 Déploiement

## Sur scalingo

1. Via git push
    1. Avoir une [clé publique ssh](https://doc.scalingo.com/platform/getting-started/setup-ssh-linux) dans le [compte utilisateur scalingo](https://dashboard.scalingo.com/account/keys)
    2. Ajouter la remote (ici nommé `scalingo`) : `git remote add scalingo <url-du-dépot-distant-de-scalingo>`
    3. Pousser / déployer la référence locale : `git push scalingo <branch-local>:main`
2. Via github : ❌ Pas les droits pour pointer la bonne organisation pour l'instant

### Debug

Scalingo n'affiche que certaines informations par défaut. Pour avoir plus d'informations :
1. Installer le paquet [scalingo-cli](https://doc.scalingo.com/tools/cli/start)
2. Être authentifié via un token scalingo (configuration dans l'espace utilisateur) : `export SCALINGO_API_TOKEN=<le-token>`
3. Puis afficher les derniers logs : `scalingo logs -a nom-de-lapp`

Si nécessaire, *redémarrer* l'application par exemple après un changement d'environnement : `scalingo restart -a nom-de-lapp`

## Avec Docker (optionnel)

Créez un `Dockerfile` :

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "app:app"]
```

Build et run :

```bash
docker build -t ds-to-grist .
docker run -p 5000:5000 --env-file .env ds-to-grist
```

## Avec systemd (Linux)

Créez un service systemd :

```ini
# /etc/systemd/system/ds-to-grist.service
[Unit]
Description=DS to Grist Sync Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/one-trick-pony-ds-grist
Environment=PATH=/path/to/one-trick-pony-ds-grist/venv/bin
EnvironmentFile=/path/to/one-trick-pony-ds-grist/.env
ExecStart=/path/to/one-trick-pony-ds-grist/venv/bin/gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Activation :

```bash
sudo systemctl daemon-reload
sudo systemctl enable ds-to-grist
sudo systemctl start ds-to-grist
```