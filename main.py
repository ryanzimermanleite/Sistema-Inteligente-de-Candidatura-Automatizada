"""
Match Vagas — Sistema de Match Automático de Vagas com IA.

Entry point principal da aplicação.
"""

import sys
import os

# Garante que o diretório do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger
from core.database import init_database
from gui.app import MatchVagasApp


def main() -> None:
    """Inicializa e executa a aplicação."""
    # Configura o logger global
    setup_logger()

    from loguru import logger

    logger.info("=" * 60)
    logger.info("Match Vagas — Iniciando aplicação")
    logger.info("=" * 60)

    # Inicializa o banco de dados
    try:
        init_database()
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {e}")
        sys.exit(1)

    # Cria e executa a aplicação GUI
    try:
        app = MatchVagasApp()
        app.mainloop()
    except Exception as e:
        logger.critical(f"Erro fatal na aplicação: {e}")
        raise
    finally:
        logger.info("Aplicação encerrada")


if __name__ == "__main__":
    main()
