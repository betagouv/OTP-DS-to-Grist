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

## Suivi des synchronisations manuelles

Chaque tâche porte son propriétaire (utilisateur et document Grist) et sa
démarche, émis avec les événements `task_update`. `SyncManager.sync_state`
renvoie l'état complet (logs retenus compris) des synchros d'un utilisateur
sur un document, pour qu'une page rouverte reprenne l'affichage : le client
l'obtient en accusé de réception du message socket `sync_state`
(`{grist_user_id, grist_doc_id}`), non authentifié comme `task_update`. Le
websocket (instance, branchement sur l'application, événements) vit dans
`live_tracking.py` ; `SyncManager` n'en dépend pas : il émet par le
`notify_callback` qu'on lui injecte. Chaque log
porte sa position absolue (`index`), ce qui permet de fusionner sans doublon
cet état et les envois en delta.

Une tâche terminée est oubliée aussitôt, sauf dans une série : ses démarches
terminées restent consultables jusqu'à la fin de la dernière. Tout est en
mémoire : rien n'est repris après un redémarrage.

## Historique des synchronisations

Chaque synchronisation, automatique ou manuelle, est enregistrée dans la table
`sync_logs` à sa fin. Les routes de `app.py` relisent cet historique pour
l'affichage : `GET /api/sync-log/latest-by-demarche` renvoie la dernière
synchronisation de chaque démarche sauvegardée (front Vue, tableau affiché au
chargement). La
route `GET /api/sync-log/latest`, qui donne la dernière synchro automatique et
la dernière manuelle du document, ne sert plus qu'au front legacy.

## tasks/

Opérations de niveau démarche exécutées pendant une synchronisation.
