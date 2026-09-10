import json
import logging
import datetime
from typing import Dict, Any, Optional

class JSONFormatter(logging.Formatter):
    """Custom formatter to output logs as structured JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Attach additional metadata fields if present on the log record
        for attr in ["trace_id", "span_id", "experiment_mode", "user_role", "event_type"]:
            if hasattr(record, attr):
                log_data[attr] = getattr(record, attr)
                
        if hasattr(record, "payload") and isinstance(record.payload, dict):
            log_data["payload"] = record.payload

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

def setup_logger(name: str = "llmops_prototype", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(JSONFormatter())
        logger.addHandler(console_handler)
        
    logger.propagate = False
    return logger

# Module-level default logger
logger = setup_logger()
