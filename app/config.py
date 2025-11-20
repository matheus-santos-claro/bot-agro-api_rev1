import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class Settings:
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # API Configuration
    API_TITLE: str = "Bot Agricola API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = """
    ?? Bot Agrícola - API para consultas técnicas sobre máquinas agrícolas
    
    Suporte para manuais de:
    - Case IH
    - John Deere  
    - New Holland
    - Valtra
    """
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Paths
    MANUAIS_PATH: str = os.getenv("MANUAIS_PATH", "./manuais/agro/md")
    
    # Response Configuration
    MAX_RESPONSE_TIME: int = 15  # seconds
    MAX_MANUAL_RESULTS: int = 5
    
    def validate_openai_key(self) -> bool:
        """Valida se a chave da OpenAI está configurada"""
        return bool(self.OPENAI_API_KEY and self.OPENAI_API_KEY.startswith('sk-'))

settings = Settings()
