# Tâches de niveau démarche

Ce dossier rassemble les opérations de synchronisation liées à la démarche dans
son ensemble, indépendamment des dossiers effectivement traités :

- `instructeurs` : synchronisation des instructeurs ;
- `labels` : rafraîchissement des étiquettes (sync incrémentale uniquement) ;
- `deleted_dossiers` : marquage des dossiers supprimés côté DN.

Chaque tâche est isolée : un échec n'empêche pas le déroulement des autres, et
elle est lançable en autonome depuis la racine du projet
(`python -m sync.tasks.<module>`).
