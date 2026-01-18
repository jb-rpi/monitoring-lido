# monitoring-lido

Ce projet contient un script Python pour surveiller l'état d'un validateur Lighthouse.

## Fonctionnalités

- Surveille l'état du validateur Lighthouse.
- Envoie des notifications sur Discord si le validateur est hors ligne.
- Gère les redémarrages inattendus du nœud en conservant l'état entre les exécutions.

## Configuration

Le script utilise les variables d'environnement pour sa configuration. Créez un fichier `.env` à la racine du projet avec les informations suivantes :

```env
BEACON_NODE_URL=http://localhost:5052
VALIDATOR_ID=YOUR_VALIDATOR_ID_OR_PUBLIC_KEY
DISCORD_WEBHOOK_URL=YOUR_DISCORD_WEBHOOK_URL
```

- `BEACON_NODE_URL`: L'URL de votre nœud Lighthouse Beacon.
- `VALIDATOR_ID`: L'ID public de votre validateur ou son index.
- `DISCORD_WEBHOOK_URL`: L'URL du webhook Discord pour envoyer les notifications.

## Installation et Exécution

1.  **Créez un environnement virtuel et installez les dépendances :**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install requests
    ```

2.  **Exécutez le script :**

    ```bash
    python src/main.py
    ```

## Intégration Cron

Le script est conçu pour être exécuté régulièrement via un scheduler comme `cron`. Voici un exemple d'entrée cron pour exécuter le script toutes les 5 minutes :

```cron
*/5 * * * * cd /home/jb/Projects/monitoring-lido && source .venv/bin/activate && python src/main.py >> /var/log/monitoring-lido.log 2>&1
```

Assurez-vous d'ajuster le chemin vers votre projet (`/home/jb/Projects/monitoring-lido`).
