import os
from datetime import datetime
from config import BASE_DIR

LOGS_PATH = os.path.join(BASE_DIR, "storage", "logs")
os.makedirs(LOGS_PATH, exist_ok=True)

def get_logger(report_id: str):
    log_path = os.path.join(LOGS_PATH, f"{report_id}.log")

    def log(message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        print(line, end="")  # also shows in terminal
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)

    return log