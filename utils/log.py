import os

PROGRESS_START = 2

# Nombre maximal d'erreurs d'une synchro reproduites (logs serveur, sync_logs)
MAX_SYNC_ERRORS = 20

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


def format_numbers(numbers: set[str], limit: int = 20) -> str:
    """Numéros triés, tronqués au-delà de `limit` pour garder un log lisible."""
    ordered = sorted(numbers, key=lambda number: (len(number), number))
    shown = ", ".join(ordered[:limit])
    if len(ordered) > limit:
        shown += f", … (+{len(ordered) - limit})"
    return shown


def log_sync_errors(
    header: str, errors: list[dict[str, str]], limit: int = MAX_SYNC_ERRORS
) -> None:
    """En-tête puis erreurs horodatées d'une synchro, tronquées au-delà de `limit`."""
    log_error(header)
    for error in errors[:limit]:
        log_error(f"  {error['timestamp']} {error['message']}")
    if len(errors) > limit:
        log_error(f"  … (+{len(errors) - limit})")


log_progress = LogProgress(ceiling=98)
