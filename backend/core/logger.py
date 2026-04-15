import logging
import os
from config import settings

# LOG PAPKANI YARATAMIZ
os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)

# LOGGER
logger = logging.getLogger("cafe_logger")
logger.setLevel(logging.INFO)

# FORMAT
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)

# FILE HANDLER
file_handler = logging.FileHandler(settings.LOG_FILE)
file_handler.setFormatter(formatter)

# CONSOLE HANDLER
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# ADD HANDLERS
logger.addHandler(file_handler)
logger.addHandler(console_handler)