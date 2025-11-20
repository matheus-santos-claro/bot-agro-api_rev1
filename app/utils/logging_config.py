"""
Configuração de logging personalizada
"""

import logging
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path

class ColoredFormatter(logging.Formatter):
    """Formatter com cores para diferentes níveis de log"""
    
    # Códigos de cor ANSI
    COLORS = {
        'DEBUG': '\033[36m',    # Ciano
        'INFO': '\033[32m',     # Verde
        'WARNING': '\033[33m',  # Amarelo
        'ERROR': '\033[31m',    # Vermelho
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        # Adiciona cor baseada no nível
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Formata timestamp
        record.timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Adiciona informações extras se disponíveis
        if hasattr(record, 'request_id'):
            record.request_info = f" [REQ:{record.request_id}]"
        else:
            record.request_info = ""
        
        if hasattr(record, 'processing_time'):
            record.time_info = f" ({record.processing_time:.3f}s)"
        else:
            record.time_info = ""
        
        # Formato base
        log_format = (
            f"{color}[{record.timestamp}] {record.levelname:8}{reset} "
            f"| {record.name:20} | {record.message}"
            f"{record.request_info}{record.time_info}"
        )
        
        # Adiciona informações de exceção se existirem
        if record.exc_info:
            log_format += f"\n{self.formatException(record.exc_info)}"
        
        return log_format

class AgricultureBotLogger:
    """Logger customizado para o Bot Agrícola"""
    
    def __init__(self, name: str = "bot_agro"):
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Configura o logger"""
        # Remove handlers existentes
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Define nível
        self.logger.setLevel(logging.INFO)
        
        # Handler para console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredFormatter())
        
        # Handler para arquivo (se em produção)
        file_handler = self._create_file_handler()
        
        # Adiciona handlers
        self.logger.addHandler(console_handler)
        if file_handler:
            self.logger.addHandler(file_handler)
        
        # Evita propagação para o logger raiz
        self.logger.propagate = False
    
    def _create_file_handler(self) -> Optional[logging.FileHandler]:
        """Cria handler para arquivo de log"""
        try:
            # Cria diretório de logs se não existir
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            # Nome do arquivo com data
            log_file = log_dir / f"bot_agro_{datetime.now().strftime('%Y%m%d')}.log"
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # Formato para arquivo (sem cores)
            file_format = (
                "[%(asctime)s] %(levelname)-8s | %(name)-20s | %(message)s"
            )
            file_handler.setFormatter(logging.Formatter(file_format))
            
            return file_handler
            
        except Exception as e:
            print(f"Erro ao criar handler de arquivo: {e}")
            return None
    
    def log_request(self, request_id: str, question: str, model: Optional[str] = None):
        """Log de nova requisição"""
        extra = {'request_id': request_id}
        model_info = f" (Modelo: {model})" if model else ""
        self.logger.info(
            f"Nova pergunta recebida: '{question[:100]}...'{model_info}",
            extra=extra
        )
    
    def log_manual_search(self, request_id: str, found_manuals: int, processing_time: float):
        """Log de busca nos manuais"""
        extra = {
            'request_id': request_id,
            'processing_time': processing_time
        }
        self.logger.info(
            f"Busca nos manuais: {found_manuals} manuais encontrados",
            extra=extra
        )
    
    def log_ai_response(self, request_id: str, model: str, tokens: int, processing_time: float):
        """Log de resposta da IA"""
        extra = {
            'request_id': request_id,
            'processing_time': processing_time
        }
        self.logger.info(
            f"Resposta IA gerada: {model} ({tokens} tokens)",
            extra=extra
        )
    
    def log_error(self, request_id: str, error: Exception, context: str = ""):
        """Log de erro"""
        extra = {'request_id': request_id}
        context_info = f" ({context})" if context else ""
        self.logger.error(
            f"Erro{context_info}: {str(error)}",
            extra=extra,
            exc_info=True
        )
    
    def log_performance(self, request_id: str, total_time: float, confidence: float):
        """Log de performance"""
        extra = {
            'request_id': request_id,
            'processing_time': total_time
        }
        
        if total_time > 10:
            level = "WARNING"
            message = f"Resposta lenta (confiança: {confidence:.2f})"
        else:
            level = "INFO"
            message = f"Resposta processada (confiança: {confidence:.2f})"
        
        getattr(self.logger, level.lower())(message, extra=extra)

def setup_logging(name: str = "bot_agro", level: str = "INFO") -> AgricultureBotLogger:
    """
    Configura logging para a aplicação
    
    Args:
        name: Nome do logger
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Instância do logger configurado
    """
    # Configura nível global
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    
    # Silencia logs verbosos de bibliotecas externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    return AgricultureBotLogger(name)

# Logger global para a aplicação
app_logger = setup_logging()