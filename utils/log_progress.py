PROGRESS_START = 2

class LogProgress:
    def __init__(
        self,
        ceiling=5,
        increment=0.1,
        start=PROGRESS_START
    ):
        self.ceiling = ceiling
        self.increment = increment
        self._value = start
        self.start = start
    
    def log(
        self,
        phase_name,
        *,
        reset=False
    ):
        if reset:
            self._value = self.start
        self._value = min(self._value + self.increment, self.ceiling)
        print(f"Progression: {self._value} - {phase_name}...", flush=True)
    
    def reset(self):
        self._value = self.start
