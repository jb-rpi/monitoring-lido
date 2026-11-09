# monitoring-lido

Ce projet contient un script Python pour surveiller l'état de plusieurs validateurs Lighthouse.

## Fonctionnalités

- Surveille l'état de plusieurs validateurs Lighthouse (`VALIDATOR_IDS`).
- Envoie une notification Discord groupée quand des validateurs passent hors ligne ou reviennent en ligne.
- Gère les redémarrages inattendus du nœud en conservant l'état entre les exécutions.

## Configuration

Le script utilise les variables d'environnement pour sa configuration. Copiez `.env.example` en `.env` à la racine du projet et adaptez-le :

```bash
cp .env.example .env
```

- `BEACON_NODE_URL`: L'URL de votre nœud Lighthouse Beacon.
- `VALIDATOR_IDS`: Liste d'index ou de clés publiques de validateurs, séparés par des virgules (`VALIDATOR_ID` reste accepté pour un seul validateur).
- `DISCORD_WEBHOOK_URL`: Webhook Discord du rapport de santé (`health-check.py`).
- `ALERT_WEBHOOK_URL`: Webhook Discord des alertes (`alert.py` et validateurs hors ligne). Optionnel : par défaut `DISCORD_WEBHOOK_URL`.

## Installation et Exécution

1.  **Créez un environnement virtuel et installez les dépendances :**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install requests python-dotenv psutil
    ```

2.  **Exécutez le script :**

    ```bash
    python src/main.py
    ```

## Intégration Cron

Les scripts sont conçus pour être exécuté régulièrement via un scheduler comme `cron`. Voici un exemple : validateurs et alertes toutes les 5 minutes, rapport de santé à 8h, 12h, 18h et 22h :

```cron
*/5 * * * * cd /home/jb/Projects/monitoring-lido && .venv/bin/python src/main.py >> monitoring.log 2>&1
*/5 * * * * cd /home/jb/Projects/monitoring-lido && .venv/bin/python src/alert.py >> monitoring.log 2>&1
0 8,12,18,22 * * * cd /home/jb/Projects/monitoring-lido && .venv/bin/python src/health-check.py >> monitoring.log 2>&1
```

Assurez-vous d'ajuster le chemin vers votre projet (`/home/jb/Projects/monitoring-lido`).
