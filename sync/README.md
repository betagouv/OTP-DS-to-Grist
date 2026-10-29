# Synchronisation

Rassemble les fonctionnalités de synchronisation, incluant la planification.

Avant de lancer le sous-processus, `SyncManager` vérifie que la clé API Grist
configurée dispose d'un accès propriétaire sur le document (contrôle partagé
avec `security.widget_auth`) : une clé en lecture seule ou sans accès fait
échouer la tâche immédiatement, avec un message explicite et un code d'erreur
API externe qui désactive le planning en cas de synchro planifiée.

En cas d'échec du sous-processus, le message présenté à l'utilisateur est
volontairement court : les tracebacks Python et le stderr complet sont filtrés
du résumé (et bornés en longueur), le détail restant dans les logs de la tâche.

## Synchronisation automatique

Un job quotidien unique (APScheduler), à `SYNC_HOUR:SYNC_MINUTE` dans le fuseau
`SYNC_TZ` (par défaut 00:00, Europe/Paris), met en file toutes les
configurations dont le planning est activé. Le séquenceur les exécute ensuite
une par une, dans l'ordre d'arrivée, quel que soit leur document Grist : il n'y
a pas de file par document, une seule file globale.

```text
 APScheduler : job quotidien, SYNC_HOUR:SYNC_MINUTE (défaut 00:00 Europe/Paris)
        |
        v
 user_schedules : plannings enabled = true, triés par otp_config_id
        |
        |  pour chaque configuration
        v
 configuration trouvée dans otp_configurations ? --- non ---> ignorée (log)
        |
       oui
        v
 config déjà en attente ou en cours ------------------- oui ---> pas de 2e mise
 dans le séquenceur ?                                            en file
        |
       non
        v
 +--------------------------------------------------------------+
 | SÉQUENCEUR (SyncSequencer, sync/sequencer.py)                |
 | file globale, traitée dans l'ordre d'arrivée                 |
 | une seule synchro à la fois, tous documents Grist confondus  |
 +--------------------------------------------------------------+
        |
        |  à son tour (parfois longtemps après la mise en file)
        v
 planning toujours activé et configuration ---------- non ---> ignorée (log)
 toujours présente ? (relues en base)
        |
       oui
        v
 synchronisation avec la configuration relue
 (contrôle d'accès Grist, puis sous-process grist_processor_working_all.py)
        |
        +---> sync_logs : une ligne par synchro (auto = true)
        |
        v
 erreur d'API externe ? ------------------------------- oui ---> planning
 code EXIT_CODE_EXTERNAL_API_ERROR (2), seul code                 désactivé
 qui désactive, renvoyé dans deux cas :
  - clé Grist sans droits propriétaire (contrôle d'accès)
  - échec de la vérification des connexions dans le
    sous-process (token DN, document ou démarche invalide)
        |
       non (succès, ou erreur transitoire comme
        |   EXIT_CODE_GRIST_READ_ERROR (3))
        v
 planning conservé : nouvel essai au prochain job quotidien
```

Points à retenir :

- **Relecture au démarrage** : une synchro peut attendre longtemps dans la
  file. Le planning et la configuration sont donc relus au moment où elle
  démarre, pas au moment de la mise en file.
- **Arrêt de l'application** (redéploiement) : le scheduler s'arrête d'abord,
  puis seule la synchro en cours est attendue ; celles en attente sont annulées
  et reprendront au prochain job quotidien.
- **Un seul worker gunicorn** : la file est en mémoire, elle n'est pas partagée
  entre plusieurs processus.

## Synchronisation de toutes les démarches (« Tout synchroniser »)

`POST /api/start-sync-all` synchronise toutes les démarches complètes de
l'utilisateur et du document du jeton widget. La série a sa propre séquence
(une instance de `SyncSequencer`), distincte de celle des synchros
automatiques :

- les démarches passent une par une, dans l'ordre, même si la page est fermée ;
  une démarche en erreur n'arrête pas les suivantes ;
- chaque démarche est une tâche suivie par les événements `task_update`, d'abord
  à l'état `queued` (en attente), puis `running` à son tour ;
- une seule série à la fois par utilisateur et document ; les séries de
  plusieurs utilisateurs tournent en parallèle ;
- une série peut tourner en même temps qu'une synchro automatique du même
  document (risque accepté) ;
- à l'arrêt de l'application, comme pour la séquence automatique, seule la
  synchro en cours est attendue.

Le bouton de synchronisation d'une seule démarche (`POST /api/start-sync`) ne
passe par aucune séquence : la synchro démarre immédiatement.

## tasks/

Opérations de niveau démarche exécutées pendant une synchronisation, également
lançables en autonome depuis la racine : `python -m sync.tasks.<module>`.
