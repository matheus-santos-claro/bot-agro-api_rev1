import openai
import logging
import asyncio
from typing import Dict, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY não configurada")
        
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        logger.info(f"OpenAI Service inicializado com modelo: {self.model}")
    
    async def generate_response(
        self, 
        pergunta: str, 
        contexto: str, 
        modelo_maquina: Optional[str] = None
    ) -> Dict:
        """Gera resposta EXATAMENTE como seu notebook"""
        
        try:
            # Chama OpenAI EXATAMENTE como seu notebook
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um assistente técnico especializado em máquinas agrícolas."},
                    {"role": "user", "content": contexto},
                ],
                temperature=0.2,
            )
            
            # Extrai resposta
            texto_resposta = response.choices[0].message.content.strip()
            
            # Categoriza resposta
            categoria = self._extrair_categoria(texto_resposta)
            
            # Informações de uso
            usage = response.usage
            tokens_usados = usage.total_tokens if usage else 0
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            
            return {
                "resposta": texto_resposta,
                "categoria": categoria,
                "confianca": 0.90,
                "modelo_usado": self.model,
                "fallback_usado": False,
                "tokens_usados": tokens_usados,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens
            }
            
        except Exception as e:
            logger.error(f"❌ Erro no OpenAI Service: {str(e)}")
            return self._fallback_response(pergunta, str(e))
    
    def _extrair_categoria(self, resposta: str) -> str:
        """Extrai categoria da resposta"""
        resposta_lower = resposta.lower()
        
        if any(word in resposta_lower for word in ["potencia", "motor", "hp", "cv", "especificacao"]):
            return "ESPECIFICACOES"
        elif any(word in resposta_lower for word in ["manutencao", "trocar", "verificar", "oleo"]):
            return "MANUTENCAO"
        elif any(word in resposta_lower for word in ["operar", "usar", "configurar", "ajustar"]):
            return "OPERACAO"
        elif any(word in resposta_lower for word in ["problema", "erro", "falha", "nao funciona"]):
            return "TROUBLESHOOTING"
        else:
            return "GERAL"
    
    def _fallback_response(self, pergunta: str, erro: str) -> Dict:
        """Resposta de fallback"""
        return {
            "resposta": f"Erro ao processar pergunta: {erro}",
            "categoria": "GERAL",
            "confianca": 0.0,
            "modelo_usado": "erro",
            "fallback_usado": True,
            "tokens_usados": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0
        }
