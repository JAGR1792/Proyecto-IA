"""Configuración de logging estructurado."""

import logging
import sys
from typing import Any, Dict

from src.utilidades.config import settings


def configurar_logging() -> None:
    """Configura logging estructurado (JSON para producción, texto para desarrollo)."""

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Handler consola
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if settings.log_format == "json":
        # Formato JSON simple
        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                import json
                log_data: Dict[str, Any] = {
                    "timestamp": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_data, ensure_ascii=False)

        handler.setFormatter(JsonFormatter())
    else:
        # Formato texto legible
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # Silenciar loggers ruidosos
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.info("Logging configurado", extra={"level": settings.log_level, "format": settings.log_format})


def obtener_logger(nombre: str) -> logging.Logger:
    """Obtiene logger configurado para un módulo."""
    return logging.getLogger(nombre)