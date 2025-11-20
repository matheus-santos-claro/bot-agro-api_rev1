import openai
import logging
from typing import Dict, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY não configurada")
        
        # Versão atualizada do cliente OpenAI
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
            # Monta prompt otimizado
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(pergunta, contexto, modelo_maquina)
            
            # Chama OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=800,
                temperature=0.3,
                top_p=0.9
            )
            
            # Extrai resposta
            resposta_completa = response.choices[0].message.content
            categoria = self._extrair_categoria(resposta_completa)
            resposta_limpa = self._limpar_resposta(resposta_completa)
            
            # Calcula tokens usados
            tokens_usados = response.usage.total_tokens if response.usage else 0
            
            return {
                "resposta": resposta_limpa,
                "categoria": categoria,
                "confianca": 0.85,  # Score base para GPT
                "modelo_usado": self.model,
                "fallback_usado": False,
                "tokens_usados": tokens_usados
            }
            
        except openai.RateLimitError:
            logger.error("Rate limit atingido na OpenAI")
            return self._fallback_response(pergunta, "RATE_LIMIT")
            
        except openai.APIError as e:
            logger.error(f"Erro na API OpenAI: {str(e)}")
            return self._fallback_response(pergunta, "API_ERROR")
            
        except Exception as e:
            logger.error(f"Erro geral no OpenAI Service: {str(e)}")
            return self._fallback_response(pergunta, "GENERAL_ERROR")
    
    def _build_system_prompt(self) -> str:
        """Constrói prompt do sistema"""
        return """Você é um especialista técnico em máquinas agrícolas com conhecimento profundo sobre:
- Case IH, John Deere, New Holland, Valtra
- Manutenção preventiva e corretiva
- Especificações técnicas
- Operação e troubleshooting

INSTRUÇÕES IMPORTANTES:
1. Responda APENAS com base nos manuais fornecidos
2. Seja técnico, preciso e objetivo
3. Cite especificações quando relevante
4. Categorize sua resposta como: ESPECIFICACOES, MANUTENCAO, OPERACAO, TROUBLESHOOTING ou GERAL
5. Se não souber, diga claramente que a informação não está nos manuais disponíveis

FORMATO DA RESPOSTA:
[CATEGORIA]: Sua resposta técnica aqui..."""

    def _build_user_prompt(self, pergunta: str, contexto: str, modelo_maquina: Optional[str]) -> str:
        """Constrói prompt do usuário"""
        modelo_info = f"\nModelo específico: {modelo_maquina}" if modelo_maquina else ""
        
        return f"""CONTEXTO DOS MANUAIS:
{contexto}

PERGUNTA DO USUÁRIO:
{pergunta}{modelo_info}

Por favor, responda com base apenas nas informações dos manuais fornecidos acima."""

    def _extrair_categoria(self, resposta: str) -> str:
        """Extrai categoria da resposta"""
        categorias_validas = ["ESPECIFICACOES", "MANUTENCAO", "OPERACAO", "TROUBLESHOOTING", "GERAL"]
        
        for categoria in categorias_validas:
            if f"[{categoria}]" in resposta.upper():
                return categoria
        
        # Fallback baseado em palavras-chave
        resposta_lower = resposta.lower()
        if any(word in resposta_lower for word in ["potencia", "motor", "especificacao", "tecnic"]):
            return "ESPECIFICACOES"
        elif any(word in resposta_lower for word in ["manutencao", "trocar", "verificar", "limpar"]):
            return "MANUTENCAO"
        elif any(word in resposta_lower for word in ["operar", "usar", "configurar", "ajustar"]):
            return "OPERACAO"
        elif any(word in resposta_lower for word in ["problema", "erro", "falha", "nao funciona"]):
            return "TROUBLESHOOTING"
        else:
            return "GERAL"

    def _limpar_resposta(self, resposta: str) -> str:
        """Remove marcadores de categoria da resposta"""
        import re
        
        # Remove [CATEGORIA]: do início
        resposta_limpa = re.sub(r'^\[.*?\]:\s*', '', resposta)
        
        # Remove quebras de linha excessivas
        resposta_limpa = re.sub(r'\n{3,}', '\n\n', resposta_limpa)
        
        return resposta_limpa.strip()

    def _fallback_response(self, pergunta: str, erro_tipo: str) -> Dict:
        """Resposta de fallback quando OpenAI falha"""
        
        fallback_messages = {
            "RATE_LIMIT": "Desculpe, muitas requisições simultâneas. Tente novamente em alguns segundos.",
            "API_ERROR": "Erro temporário no serviço de IA. Tente novamente em alguns momentos.",
            "GENERAL_ERROR": "Erro interno no processamento. Verifique sua pergunta e tente novamente."
        }
        
        # Resposta básica baseada em palavras-chave
        pergunta_lower = pergunta.lower()
        
        if any(word in pergunta_lower for word in ["motor", "potencia", "especificacao"]):
            categoria = "ESPECIFICACOES"
            resposta_base = "Para especificações técnicas detalhadas, consulte o manual específico do seu equipamento."
        elif any(word in pergunta_lower for word in ["manutencao", "oleo", "filtro"]):
            categoria = "MANUTENCAO"
            resposta_base = "Para procedimentos de manutenção, consulte o manual de serviço da sua máquina."
        else:
            categoria = "GERAL"
            resposta_base = "Para informações específicas, consulte o manual do equipamento."
        
        resposta_final = f"{fallback_messages.get(erro_tipo, 'Erro no processamento.')} {resposta_base}"
        
        return {
            "resposta": resposta_final,
            "categoria": categoria,
            "confianca": 0.3,
            "modelo_usado": "fallback",
            "fallback_usado": True,
            "tokens_usados": 0
        }
