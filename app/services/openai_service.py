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
        
        # Cliente OpenAI moderno
        self.client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=30.0,
            max_retries=2
        )
        
        self.model = settings.OPENAI_MODEL
        logger.info(f"OpenAI Service inicializado com modelo: {self.model}")
    
    async def generate_response(
        self, 
        pergunta: str, 
        contexto: str, 
        modelo_maquina: Optional[str] = None
    ) -> Dict:
        """Gera resposta usando OpenAI GPT"""
        
        try:
            # Executa em thread separada
            response = await asyncio.to_thread(
                self._call_openai_sync,
                pergunta,
                contexto,
                modelo_maquina
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Erro no OpenAI Service: {str(e)}")
            return self._fallback_response(pergunta)
    
    def _call_openai_sync(self, pergunta: str, contexto: str, modelo_maquina: Optional[str] = None) -> Dict:
        """Chamada síncrona para OpenAI"""
        
        system_prompt = """Você é um especialista técnico em máquinas agrícolas com conhecimento sobre:
- Case IH, John Deere, New Holland, Valtra
- Manutenção, especificações técnicas, operação

INSTRUÇÕES:
1. Responda APENAS com base nos manuais fornecidos
2. Seja técnico e preciso
3. Categorize como: ESPECIFICACOES, MANUTENCAO, OPERACAO, TROUBLESHOOTING ou GERAL
4. Formato: [CATEGORIA]: Resposta..."""

        modelo_info = f"\nModelo: {modelo_maquina}" if modelo_maquina else ""
        
        user_prompt = f"""MANUAIS:
{contexto}

PERGUNTA: {pergunta}{modelo_info}

Responda com base apenas nos manuais acima."""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=800,
            temperature=0.3
        )
        
        resposta_completa = response.choices[0].message.content
        categoria = self._extrair_categoria(resposta_completa)
        resposta_limpa = self._limpar_resposta(resposta_completa)
        
        return {
            "resposta": resposta_limpa,
            "categoria": categoria,
            "confianca": 0.85,
            "modelo_usado": self.model,
            "fallback_usado": False,
            "tokens_usados": response.usage.total_tokens if response.usage else 0
        }
    
    def _extrair_categoria(self, resposta: str) -> str:
        """Extrai categoria da resposta"""
        categorias = ["ESPECIFICACOES", "MANUTENCAO", "OPERACAO", "TROUBLESHOOTING", "GERAL"]
        
        for categoria in categorias:
            if f"[{categoria}]" in resposta.upper():
                return categoria
        
        # Fallback
        resposta_lower = resposta.lower()
        if any(word in resposta_lower for word in ["potencia", "motor", "especificacao"]):
            return "ESPECIFICACOES"
        elif any(word in resposta_lower for word in ["manutencao", "trocar", "oleo"]):
            return "MANUTENCAO"
        elif any(word in resposta_lower for word in ["operar", "usar", "configurar"]):
            return "OPERACAO"
        elif any(word in resposta_lower for word in ["problema", "erro", "falha"]):
            return "TROUBLESHOOTING"
        else:
            return "GERAL"

    def _limpar_resposta(self, resposta: str) -> str:
        """Remove marcadores de categoria"""
        import re
        resposta_limpa = re.sub(r'^\[.*?\]:\s*', '', resposta)
        return resposta_limpa.strip()

    def _fallback_response(self, pergunta: str) -> Dict:
        """Resposta de fallback"""
        pergunta_lower = pergunta.lower()
        
        if any(word in pergunta_lower for word in ["4150", "colheitadeira", "case"]):
            categoria = "ESPECIFICACOES"
            resposta = "Para especificações da colheitadeira Case IH 4150, incluindo motor e potência, consulte o manual técnico específico do modelo."
        elif any(word in pergunta_lower for word in ["motor", "potencia"]):
            categoria = "ESPECIFICACOES"
            resposta = "Para especificações de motor e potência, consulte o manual técnico do equipamento."
        else:
            categoria = "GERAL"
            resposta = "Para informações específicas, consulte o manual do equipamento."
        
        return {
            "resposta": resposta,
            "categoria": categoria,
            "confianca": 0.3,
            "modelo_usado": "fallback",
            "fallback_usado": True,
            "tokens_usados": 0
        }
