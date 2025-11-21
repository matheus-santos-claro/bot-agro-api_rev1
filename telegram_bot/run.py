# telegram_bot/run.py
"""
Executor principal do Bot Telegram
"""
import asyncio
import logging
import sys
import os

# Adiciona o diretório pai ao path para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_bot.bot import agro_bot

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('telegram_bot.log')
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Função principal"""
    logger.info("🚀 Iniciando Bot Agrícola Telegram...")
    
    try:
        await agro_bot.run()
    except KeyboardInterrupt:
        logger.info("🛑 Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {str(e)}")
        raise

if __name__ == "__main__":
    # Executa o bot
    asyncio.run(main())
