"""
Módulo de logging centralizado para SmartGrid-Agent.
Configura el formato y nivel de logging para todo el proyecto.
"""
import os
import logging
import sys
from typing import Optional


_loggers_configured = set()


def setup_logger(name: str = "ArgoTool", level: int = logging.INFO) -> logging.Logger:
    """
    Configura el logger con el formato y nivel de logging especificado.

    Args:
        name: Nombre del logger (por defecto "ArgoTool")
        level: Nivel de logging (por defecto INFO)

    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)

    if name in _loggers_configured:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Handler para archivo
    log_file = os.getenv('LOG_FILE')
    if log_file and log_file.strip(): 
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.addHandler(console_handler)

    _loggers_configured.add(name)

    # Evitar propagación para prevenir duplicación
    logger.propagate = False

    return logger


default_logger = setup_logger()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Obtiene un logger con nombre específico.

    Args:
        name: Nombre del módulo/componente (opcional)

    Returns:
        Logger configurado
    """
    if name:
        return setup_logger(f"ArgoTool.{name}")
    return default_logger
