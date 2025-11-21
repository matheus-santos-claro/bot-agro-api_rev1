# telegram_bot/run.py
import asyncio
import logging
from telegram_bot.bot import agro_bot

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Função principal - VERSÃO SÍNCRONA"""
    try:
        logger.info("🚀 Iniciando Bot Agrícola Telegram...")
        
        # Executa bot de forma síncrona
        agro_bot.app.run_polling(
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {str(e)}")
        raise

if __name__ == '__main__':
    main()
