# Synchronisation

Rassemble les fonctionnalités de synchronisation, incluant la planification.

Avant de lancer le sous-processus, `SyncManager` vérifie que la clé API Grist
configurée dispose d'un accès propriétaire sur le document (contrôle partagé
avec `security.widget_auth`) : une clé en lecture seule ou sans accès fait
échouer la tâche immédiatement, avec un message explicite et un code d'erreur
API externe qui désactive le planning en cas de synchro planifiée.

## tasks/

Opérations de niveau démarche exécutées pendant une synchronisation, également
lançables en autonome depuis la racine : `python -m sync.tasks.<module>`.
