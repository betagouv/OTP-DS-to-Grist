import time

class TaskManager:
    """
    Gestionnaire de tâches asynchrones avec WebSocket
    pour les mises à jour en temps réel
    """

    def __init__(self):
        self.tasks = {}
        self.task_counter = 0
    
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
        """Émet une mise à jour via WebSocket"""
        socketio.emit('task_update', {
            'task_id': task_id,
            'task': self.tasks[task_id]
        })

    def get_task(self, task_id):
        """Récupère les informations d'une tâche"""
        return self.tasks.get(task_id)

