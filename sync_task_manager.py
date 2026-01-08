import time
import threading
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone


class SyncTaskManager:
    """
    Gestionnaire de synchronisations asynchrones avec callbacks de notification
    pour les mises à jour en temps réel
    """

    def __init__(self, notify_callback=None):
        self.tasks = {}
        self.task_counter = 0
        self.notify_callback = notify_callback

    def notify(self, event_type, data):
        """Méthode publique pour les notifications"""
        if self.notify_callback:
            self.notify_callback(event_type, data)

    def start_sync(self, server_config):
        """Démarre une nouvelle synchronisation avec la configuration donnée"""
        return self.start_task(self.run_synchronization_task, server_config)

    def run_synchronization_task(
            self,
            config,
            progress_callback=None,
            log_callback=None
    ):
        """
        Exécute la synchronisation avec callbacks pour le suivi en temps réel
        """
        try:
            if progress_callback:
                progress_callback(5, "Préparation de l'environnement...")

            # Mettre à jour les variables d'environnement avec la configuration
            env_mapping = {
                'ds_api_token': 'DEMARCHES_API_TOKEN',
                'demarche_number': 'DEMARCHE_NUMBER',
                'grist_base_url': 'GRIST_BASE_URL',
                'grist_api_key': 'GRIST_API_KEY',
                'grist_doc_id': 'GRIST_DOC_ID',
                'grist_user_id': 'GRIST_USER_ID',
                # Filtres depuis la configuration DB
                'filter_date_start': 'DATE_DEPOT_DEBUT',
                'filter_date_end': 'DATE_DEPOT_FIN',
                'filter_statuses': 'STATUTS_DOSSIERS',
                'filter_groups': 'GROUPES_INSTRUCTEURS',
            }

            # Copie de l'environnement pour éviter la pollution globale
            env_copy = os.environ.copy()

            if progress_callback:
                progress_callback(
                    10,
                    "Configuration des variables d'environnement..."
                )

            # Mettre à jour les variables d'environnement avec les filtres
            if config.get('filter_date_start'):
                env_copy['DATE_DEPOT_DEBUT'] = config['filter_date_start']
            if config.get('filter_date_end'):
                env_copy['DATE_DEPOT_FIN'] = config['filter_date_end']
            if config.get('filter_statuses'):
                env_copy['STATUTS_DOSSIERS'] = config['filter_statuses']
            if config.get('filter_groups'):
                env_copy['GROUPES_INSTRUCTEURS'] = config['filter_groups']

            # Appliquer la configuration à l'environnement
            for key, env_key in env_mapping.items():
                if key in config:
                    env_copy[env_key] = config[key]

            # Appliquer les variables d'environnement pour ce thread
            os.environ.update(env_copy)

            if progress_callback:
                progress_callback(
                    20,
                    "Chargement des données depuis Démarches Simplifiées..."
                )

            # Définir les filtres dans la copie d'environnement (pas dans l'environnement global)
            for config_key, env_key in env_mapping.items():
                env_copy[env_key] = str(config.get(config_key, ''))

            # ✅ Afficher les filtres effectivement utilisés (après définition)
            if log_callback:
                log_callback("=== CONFIGURATION DES FILTRES ===")

                # Vérifier et afficher les variables d'environnement de la copie
                date_debut = env_copy.get("DATE_DEPOT_DEBUT", "").strip()
                date_fin = env_copy.get("DATE_DEPOT_FIN", "").strip()
                statuts = env_copy.get("STATUTS_DOSSIERS", "").strip()
                groupes = env_copy.get("GROUPES_INSTRUCTEURS", "").strip()

                if date_debut:
                    log_callback(f"✓ Filtre date début: {date_debut}")
                else:
                    log_callback("○ Date début: AUCUN FILTRE (tous les dossiers)")

                if date_fin:
                    log_callback(f"✓ Filtre date fin: {date_fin}")
                else:
                    log_callback("○ Date fin: AUCUN FILTRE (tous les dossiers)")

                if statuts:
                    log_callback(f"✓ Filtre statuts: {statuts}")
                else:
                    log_callback("○ Statuts: AUCUN FILTRE (tous les dossiers)")

                if groupes:
                    log_callback(f"✓ Filtres groupes: {groupes}")
                else:
                    log_callback("○ Groupes: AUCUN FILTRE (tous les dossiers)")

                log_callback("====================================")

            if progress_callback:
                progress_callback(10, "Configuration des variables d'environnement...")

            # Appliquer les variables d'environnement pour ce thread
            os.environ.update(env_copy)

            if progress_callback:
                progress_callback(20, "Lancement du script de synchronisation...")

            # Lancer le script de synchronisation principal
            script_path = os.path.join(os.path.dirname(__file__), "grist_processor_working_all.py")

            if log_callback:
                log_callback(f"Lancement du script: {script_path}")

            # Exécuter le script de synchronisation
            process = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                env=env_copy,  # Utiliser l'environnement mis à jour
                cwd=os.path.dirname(__file__)
            )

            # Mots-clés pour estimer la progression
            progress_keywords = {
                "Récupération de la démarche": (15, "Récupération des données de la démarche..."),
                "Démarche trouvée": (20, "Démarche trouvée - Analyse des données..."),
                "Nombre de dossiers trouvés": (25, "Dossiers trouvés - Préparation du traitement..."),
                "Types de colonnes détectés": (35, "Analyse de la structure des données..."),
                "Table dossiers": (45, "Création/mise à jour des tables Grist..."),
                "Table champs": (50, "Configuration des champs..."),
                "Traitement du lot": (60, "Traitement des dossiers..."),
                "Dossiers traités avec succès": (90, "Finalisation du traitement..."),
                "Traitement terminé": (100, "Traitement terminé!")
            }

            current_progress = 20

            # Lire la sortie en temps réel
            for line in process.stdout.split('\n'):
                if not line.strip():
                    continue

                # Ajouter le log
                if log_callback:
                    log_callback(line.strip())

                # Mettre à jour la progression
                for keyword, (value, status_text) in progress_keywords.items():
                    if keyword in line and value > current_progress:
                        current_progress = value
                        if progress_callback:
                            progress_callback(current_progress, status_text)
                        break

                # Détecter le pourcentage dans les lignes de progression
                if "Progression:" in line and "/" in line:
                    try:
                        # Extraire X/Y du texte "Progression: X/Y dossiers"
                        parts = line.split("Progression:")[1].strip().split("/")
                        current = int(parts[0].strip())
                        total = int(parts[1].split()[0].strip())

                        if total > 0:
                            batch_progress = 60 + (30 * (current / total))
                            if batch_progress > current_progress:
                                current_progress = batch_progress
                                if progress_callback:
                                    progress_callback(current_progress, f"Traitement des dossiers: {current}/{total}")
                    except (ValueError, IndexError):
                        pass

            # Traiter les erreurs
            if process.returncode != 0:
                error_output = process.stderr
                if error_output and log_callback:
                    for line in error_output.split('\n'):
                        if line.strip():
                            log_callback(f"ERREUR: {line.strip()}")

                raise subprocess.CalledProcessError(process.returncode, process.args)

            # Analyser le résultat
            success_count = 0
            error_count = 0
            total_processed = 0
            errors_list = []

            # Fonctions helper pour parsing
            def _parse_success_count(line):
                """Extrait le nombre de succès depuis une ligne de log"""
                if "Dossiers traités avec succès:" not in line:
                    return None, None

                try:
                    parts = line.split(":", 1)
                    if len(parts) <= 1:
                        return None, None

                    num_str = parts[1].strip()
                    if "/" in num_str:
                        # Format "X/Y"
                        success = int(num_str.split("/")[0].strip())
                        total = int(num_str.split("/")[1].strip())
                        return success, total
                    else:
                        # Format "X"
                        success = int(num_str)
                        return success, None
                except (ValueError, IndexError):
                    return None, None

            def _parse_error_count(line):
                """Extrait le nombre d'erreurs depuis une ligne de log"""
                if "Dossiers en échec:" not in line:
                    return None

                try:
                    parts = line.split(":", 1)
                    if len(parts) <= 1:
                        return None
                    return int(parts[1].strip())
                except (ValueError, IndexError):
                    return None

            # Parser la sortie pour extraire les statistiques
            for line in process.stdout.split('\n'):
                # Essayer de parser succès
                success_parsed, total_parsed = _parse_success_count(line)
                if success_parsed is not None:
                    success_count = success_parsed
                    if total_parsed is not None:
                        total_processed = total_parsed

                # Essayer de parser erreurs
                error_parsed = _parse_error_count(line)
                if error_parsed is not None:
                    error_count = error_parsed

                # Essayer de parser total (si présent dans logs)
                if "Total dossiers traités:" in line:
                    try:
                        total_processed = int(line.split(":")[1].strip())
                    except (ValueError, IndexError):
                        pass

            # Calculer total si pas déjà extrait
            if total_processed == 0:
                total_processed = success_count + error_count

            if progress_callback:
                progress_callback(95, "Finalisation...")

            if log_callback:
                log_callback(f"Synchronisation terminée: {success_count} dossiers synchronisés, {error_count} erreurs")

            # Préparer le résultat
            result = {
                'success': error_count == 0,
                'message': f"Synchronisation terminée: {success_count}/{total_processed} dossiers synchronisés" if error_count == 0 else f"Synchronisation terminée avec {error_count} erreurs sur {total_processed} dossiers",
                'dossier_count': total_processed,
                'success_count': success_count,
                'error_count': error_count,
                'total_processed': total_processed,
                'errors': errors_list,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            if progress_callback:
                progress_callback(100, result['message'])

            return result

        except Exception as e:
            error_msg = f"Erreur lors de la synchronisation: {str(e)}"
            if log_callback:
                log_callback(error_msg)

            if log_callback:
                log_callback(traceback.format_exc())

            return {
                'success': False,
                'message': error_msg,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'traceback': traceback.format_exc()
            }

    def start_task(self, task_function, *args, **kwargs):
        """Démarre une nouvelle tâche asynchrone"""
        self.task_counter += 1
        task_id = f"task_{self.task_counter}"

        self.tasks[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': 'Initialisation...',
            'start_time': time.time(),
            'logs': []
        }

        # Démarrer la tâche dans un thread séparé
        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, task_function, *args),
            kwargs=kwargs
        )
        thread.start()

        return task_id

    def _run_task(self, task_id, task_function, *args, **kwargs):
        """Exécute une tâche avec gestion des erreurs"""
        try:
            # Ajouter le callback de progression
            kwargs['progress_callback'] = lambda progress, message: self._update_progress(task_id, progress, message)
            kwargs['log_callback'] = lambda message: self._add_log(task_id, message)

            result = task_function(*args, **kwargs)

            self.tasks[task_id].update({
                'status': 'completed',
                'progress': 100,
                'message': 'Tâche terminée avec succès',
                'result': result,
                'end_time': time.time()
            })

            self._emit_update(task_id)

        except Exception as e:
            self.tasks[task_id].update({
                'status': 'error',
                'message': f'Erreur: {str(e)}',
                'error': str(e),
                'end_time': time.time()
            })

            self._emit_update(task_id)

    def _update_progress(self, task_id, progress, message):
        """Met à jour la progression d'une tâche"""
        if task_id in self.tasks:
            self.tasks[task_id]['progress'] = progress
            self.tasks[task_id]['message'] = message
            self._emit_update(task_id)

    def _add_log(self, task_id, message):
        """Ajoute un log à une tâche"""
        if task_id in self.tasks:
            self.tasks[task_id]['logs'].append({
                'timestamp': time.time(),
                'message': message
            })
            self._emit_update(task_id)

    def _emit_update(self, task_id):
        """Émet une mise à jour via notification callback"""
        self.notify('task_update', {
            'task_id': task_id,
            'task': self.tasks[task_id]
        })

    def get_task(self, task_id):
        """Récupère les informations d'une tâche"""
        return self.tasks.get(task_id)
