import openai
import time
import logging
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        if not settings.validate_openai_key():
            raise ValueError("OPENAI_API_KEY não configurada ou inválida")
        
        openai.api_key = settings.OPENAI_API_KEY
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
    async def generate_response(self, pergunta: str, contexto_manuais: str, modelo_maquina: Optional[str] = None) -> Dict[str, Any]:
        """Gera resposta usando GPT-4o-mini"""
        start_time = time.time()
        
        try:
            # Prompt otimizado para máquinas agrícolas
            system_prompt = """Você é um especialista técnico em máquinas agrícolas com conhecimento profundo sobre:
- Case IH, John Deere, New Holland, Valtra, FENDT
- Manutenção preventiva e corretiva
- Especificações técnicas
- Operação e troubleshooting

INSTRUÇÕES:
1. Responda APENAS com base nos manuais fornecidos
2. Seja técnico, preciso e objetivo
3. Cite especificações quando relevante
4. Categorize sua resposta em: ESPECIFICAÇÕES, MANUTENÇÃO, OPERAÇÃO, TROUBLESHOOTING ou GERAL
5. Se não souber, diga claramente que a informação não está nos manuais disponíveis

FORMATO DA RESPOSTA:
[CATEGORIA]: Sua resposta técnica aqui..."""

            user_prompt = f"""
PERGUNTA: {pergunta}
{f"MODELO DA MÁQUINA: {modelo_maquina}" if modelo_maquina else ""}

CONTEXTO DOS MANUAIS:
{contexto_manuais}

Responda de forma técnica e precisa baseado apenas nas informações dos manuais fornecidos.
"""

            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=800,
                temperature=0.3,
                top_p=0.9
            )
            
            processing_time = time.time() - start_time
            
            resposta_completa = response.choices[0].message.content.strip()
            
            # Extrair categoria
            categoria = self._extract_category(resposta_completa)
            
            # Limpar resposta (remover marcador de categoria)
            resposta_limpa = self._clean_response(resposta_completa)
            
            return {
                "resposta": resposta_limpa,
                "categoria": categoria,
                "confianca": 0.9,  # Alta confiança com GPT-4o-mini
                "tempo_processamento": processing_time,
                "modelo_usado": settings.OPENAI_MODEL,
                "fallback_usado": False,
                "tokens_usados": response.usage.total_tokens
            }
            
        except Exception as e:
            logger.error(f"Erro na OpenAI API: {str(e)}")
            processing_time = time.time() - start_time
            
            return {
                "resposta": "Erro ao processar sua pergunta. Tente novamente.",
                "categoria": "GERAL",
                "confianca": 0.0,
                "tempo_processamento": processing_time,
                "modelo_usado": settings.OPENAI_MODEL,
                "fallback_usado": True,
                "erro": str(e)
            }
    
    def _extract_category(self, resposta: str) -> str:
        """Extrai categoria da resposta"""
        categorias = ["ESPECIFICAÇÕES", "MANUTENÇÃO", "OPERAÇÃO", "TROUBLESHOOTING", "GERAL"]
        
        for categoria in categorias:
            if f"[{categoria}]" in resposta.upper():
                return categoria
                
        return "GERAL"
    
    def _clean_response(self, resposta: str) -> str:
        """Remove marcadores de categoria da resposta"""
        import re
        # Remove padrões como [CATEGORIA]:
        cleaned = re.sub(r'\[.*?\]:\s*', '', resposta)
        return cleaned.strip()