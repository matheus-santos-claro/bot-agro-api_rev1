# telegram_bot/backup_service.py
import json
import logging
from datetime import datetime
from io import BytesIO
from typing import Dict, Optional
import httpx
from .config import BACKUP_WEBHOOK_URL

logger = logging.getLogger(__name__)

class BackupService:
    def __init__(self, database):
        self.database = database
        self.webhook_url = BACKUP_WEBHOOK_URL
        
    async def create_backup_file(self) -> BytesIO:
        """Cria arquivo de backup em memória"""
        try:
            # Exporta dados do banco
            data = await self.database.export_to_json()
            
            # Converte para JSON formatado
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            
            # Cria arquivo em memória
            file_buffer = BytesIO(json_data.encode('utf-8'))
            file_buffer.name = f"backup_telegram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            logger.info(f"📁 Arquivo de backup criado: {file_buffer.name}")
            return file_buffer
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar backup: {str(e)}")
            raise
    
    async def send_to_webhook(self, data: Dict) -> bool:
        """Envia backup via webhook (opcional)"""
        if not self.webhook_url:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Backup enviado via webhook")
                    return True
                else:
                    logger.warning(f"⚠️ Webhook retornou status {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Erro ao enviar webhook: {str(e)}")
            return False
    
    def format_backup_stats(self, data: Dict) -> str:
        """Formata estatísticas do backup"""
        stats = data.get("estatisticas", {})
        
        return f"""📊 **Estatísticas do Backup:**

📅 **Data:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

👥 **Usuários:** {len(data.get('usuarios', []))}
💬 **Interações:** {len(data.get('interacoes', []))}

📈 **Estatísticas Gerais:**
• Total de usuários: {stats.get('total_usuarios', 0)}
• Usuários ativos (7d): {stats.get('usuarios_ativos_7d', 0)}
• Perguntas hoje: {stats.get('perguntas_hoje', 0)}
• Categoria top: {stats.get('categoria_mais_perguntada', 'N/A')}

🔄 **Backup realizado com sucesso!**"""

# Instância global
backup_service = None  # Será inicializado no bot principal
