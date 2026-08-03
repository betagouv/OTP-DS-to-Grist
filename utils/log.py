import os

PROGRESS_START = 2

# Configuration du niveau de log
LOG_LEVEL = int(os.getenv("LOG_LEVEL", "1"))


class LogProgress:
    def __init__(
        self,
        ceiling=5,
        increment=0.1,
        start=PROGRESS_START,
    ):
        self.ceiling = ceiling
        self.increment = increment
        self._value = start
        self.start = start

    def log(
        self,
        phase_name,
        *,
        reset=False,
    ):
        if reset:
            self._value = self.start
        self._value = min(self._value + self.increment, self.ceiling)
        print(f"Progression: {self._value} - {phase_name}...", flush=True)

    def reset(self):
        self._value = self.start


def log(message, level=1):
    """Fonction de log conditionnelle selon le niveau défini"""
    if level <= LOG_LEVEL:
        print(message)


def log_verbose(message):
    """Log uniquement en mode verbose"""
    log(message, 2)


def log_error(message):
    """Log d'erreur (toujours affiché)"""
    print(f"ERREUR: {message}")


log_progress = LogProgress(ceiling=98)
