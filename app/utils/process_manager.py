import os
import json
import psutil
from typing import Dict, Optional
from pathlib import Path

class ProcessManager:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.process_file = self.data_dir / "processes.json"
        self.processes = self._load_processes()

    def _load_processes(self) -> Dict:
        if self.process_file.exists():
            try:
                with open(self.process_file, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_processes(self):
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.process_file, "w") as f:
            json.dump(self.processes, f)

    def register_process(self, name: str, pid: int):
        self.processes[name] = pid
        self._save_processes()

    def unregister_process(self, name: str):
        if name in self.processes:
            del self.processes[name]
            self._save_processes()

    def get_process_status(self, name: str) -> Dict:
        pid = self.processes.get(name)
        if not pid:
            return {"running": False, "pid": None}

        try:
            process = psutil.Process(pid)
            return {
                "running": True,
                "pid": pid,
                "cpu_percent": process.cpu_percent(),
                "memory_percent": process.memory_percent(),
                "created": process.create_time()
            }
        except:
            self.unregister_process(name)
            return {"running": False, "pid": None}

    def stop_process(self, name: str) -> bool:
        pid = self.processes.get(name)
        if not pid:
            return False

        try:
            process = psutil.Process(pid)
            process.terminate()
            process.wait(timeout=5)
            self.unregister_process(name)
            return True
        except:
            try:
                process.kill()
                self.unregister_process(name)
                return True
            except:
                return False