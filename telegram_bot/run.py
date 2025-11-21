# telegram_bot/run.py
import os
import sys
import logging
from pathlib import Path

# Configuração de paths
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
sys.path.insert(0, str(project_root))

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Função principal do bot"""
    try:
        logger.info("🚀 Iniciando Bot Agrícola Telegram...")
        
        # Import após configurar path
        from telegram_bot.bot import agro_bot
        
        # Executa o bot
        agro_bot.app.run_polling(
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot interrompido")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {str(e)}")
        raise

if __name__ == '__main__':
    main()
