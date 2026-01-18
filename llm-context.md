# Project context (LLM)

Goal:
- Script Python pour surveiller que le noeud nethermind/lighthouse fonctionne correctement - (doit prendre la possibilité de reboot lié à de la mainteance)

Constraints:
- Python > 3.12
- Pas de framework lourd
- Exécution cron-friendly

Current state:
- Script unique dans src/
- Output console + DISCORD indiqué dans .env

Do NOT assume:
- Pas de base de données
- Pas d’API propriétaire