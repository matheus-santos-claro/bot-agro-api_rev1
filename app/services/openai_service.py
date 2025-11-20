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
        
        # Cliente OpenAI moderno (v1.51.2) com configurações otimizadas
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
        """Gera resposta usando OpenAI GPT com suporte a gpt-4o-mini"""
        
        try:
            # Executa chamada OpenAI em thread separada para não bloquear
            response = await asyncio.to_thread(
                self._call_openai_sync,
                pergunta,
                contexto,
                modelo_maquina
            )
            
            return response
            
        except openai.RateLimitError:
            logger.error("Rate limit atingido na OpenAI")
            return self._fallback_response(pergunta, "RATE_LIMIT")
            
        except openai.APIError as e:
            logger.error(f"Erro na API OpenAI: {str(e)}")
            return self._fallback_response(pergunta, "API_ERROR")
            
        except Exception as e:
            logger.error(f"Erro geral no OpenAI Service: {str(e)}")
            return self._fallback_response(pergunta, "GENERAL_ERROR")
    
    def _call_openai_sync(self, pergunta: str, contexto: str, modelo_maquina: Optional[str] = None) -> Dict:
        """Chamada síncrona para OpenAI (executada em thread separada)"""
        
        # Monta prompt otimizado
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(pergunta, contexto, modelo_maquina)
        
        # Chama OpenAI com configurações otimizadas para gpt-4o-mini
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1000,
            temperature=0.2,  # Mais determinístico para respostas técnicas
            top_p=0.9,
            frequency_penalty=0.1,
            presence_penalty=0.1
        )
        
        # Extrai resposta
        resposta_completa = response.choices[0].message.content
        categoria = self._extrair_categoria(resposta_completa)
        resposta_limpa = self._limpar_resposta(resposta_completa)
        
        # Informações de uso
        usage = response.usage
        tokens_usados = usage.total_tokens if usage else 0
        
        return {
            "resposta": resposta_limpa,
            "categoria": categoria,
            "confianca": 0.90,  # Alta confiança para GPT-4o-mini
            "modelo_usado": self.model,
            "fallback_usado": False,
            "tokens_usados": tokens_usados,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0
        }
    
    def _build_system_prompt(self) -> str:
        """Prompt otimizado para GPT-4o-mini"""
        return """Você é um especialista técnico em máquinas agrícolas com vasta experiência em:

🚜 MARCAS ESPECIALIZADAS:
- Case IH: Tratores, colheitadeiras, plantadeiras
- John Deere: Linha completa de equipamentos agrícolas
- New Holland: Tratores, colheitadeiras, implementos
- Valtra: Tratores e máquinas especializadas

�� ÁREAS DE EXPERTISE:
- Especificações técnicas (motores, potência, capacidades)
- Manutenção preventiva e corretiva
- Operação e configuração de equipamentos
- Diagnóstico e solução de problemas (troubleshooting)

📋 INSTRUÇÕES CRÍTICAS:
1. Responda EXCLUSIVAMENTE com base nos manuais técnicos fornecidos
2. Seja preciso, técnico e objetivo nas especificações
3. Cite números exatos quando disponíveis (potência, capacidades, etc.)
4. Categorize OBRIGATORIAMENTE sua resposta como:
   - [ESPECIFICACOES]: Para dados técnicos, potência, capacidades
   - [MANUTENCAO]: Para procedimentos de manutenção
   - [OPERACAO]: Para instruções de uso e configuração
   - [TROUBLESHOOTING]: Para diagnóstico de problemas
   - [GERAL]: Para informações gerais

5. Se a informação NÃO estiver nos manuais, declare claramente: "Esta informação específica não está disponível nos manuais consultados."

FORMATO OBRIGATÓRIO:
[CATEGORIA]: Resposta técnica detalhada..."""

    def _build_user_prompt(self, pergunta: str, contexto: str, modelo_maquina: Optional[str]) -> str:
        """Constrói prompt do usuário com contexto otimizado"""
        
        modelo_info = f"\n🎯 MODELO ESPECÍFICO: {modelo_maquina}" if modelo_maquina else ""
        
        return f"""📚 CONTEXTO DOS MANUAIS TÉCNICOS:
{contexto}

❓ PERGUNTA DO USUÁRIO:
{pergunta}{modelo_info}

🎯 INSTRUÇÃO: Analise os manuais acima e forneça uma resposta técnica precisa, citando especificações exatas quando disponíveis."""

    def _extrair_categoria(self, resposta: str) -> str:
        """Extrai categoria da resposta com fallback inteligente"""
        categorias_validas = ["ESPECIFICACOES", "MANUTENCAO", "OPERACAO", "TROUBLESHOOTING", "GERAL"]
        
        # Busca categoria explícita
        for categoria in categorias_validas:
            if f"[{categoria}]" in resposta.upper():
                return categoria
        
        # Fallback baseado em análise de conteúdo
        resposta_lower = resposta.lower()
        
        # Palavras-chave para ESPECIFICACOES
        spec_keywords = ["potencia", "motor", "hp", "cv", "especificacao", "tecnic", "capacidade", 
                        "cilindrada", "torque", "rpm", "litros", "peso", "dimensao"]
        if any(word in resposta_lower for word in spec_keywords):
            return "ESPECIFICACOES"
        
        # Palavras-chave para MANUTENCAO
        maint_keywords = ["manutencao", "trocar", "verificar", "limpar", "oleo", "filtro", 
                         "lubrificar", "substituir", "inspecionar", "ajustar"]
        if any(word in resposta_lower for word in maint_keywords):
            return "MANUTENCAO"
        
        # Palavras-chave para OPERACAO
        op_keywords = ["operar", "usar", "configurar", "ajustar", "ligar", "desligar", 
                      "velocidade", "marcha", "controle", "painel"]
        if any(word in resposta_lower for word in op_keywords):
            return "OPERACAO"
        
        # Palavras-chave para TROUBLESHOOTING
        trouble_keywords = ["problema", "erro", "falha", "nao funciona", "defeito", 
                           "diagnostico", "solucao", "corrigir", "consertar"]
        if any(word in resposta_lower for word in trouble_keywords):
            return "TROUBLESHOOTING"
        
        return "GERAL"

    def _limpar_resposta(self, resposta: str) -> str:
        """Limpa e formata a resposta"""
        import re
        
        if not resposta:
            return "Resposta não disponível."
        
        # Remove [CATEGORIA]: do início
        resposta_limpa = re.sub(r'^\[.*?\]:\s*', '', resposta)
        
        # Remove quebras de linha excessivas
        resposta_limpa = re.sub(r'\n{3,}', '\n\n', resposta_limpa)
        
        # Remove espaços extras
        resposta_limpa = re.sub(r' {2,}', ' ', resposta_limpa)
        
        return resposta_limpa.strip()

    def _fallback_response(self, pergunta: str, erro_tipo: str) -> Dict:
        """Resposta de fallback inteligente baseada na pergunta"""
        
        fallback_messages = {
            "RATE_LIMIT": "⏳ Muitas requisições simultâneas. Aguarde alguns segundos e tente novamente.",
            "API_ERROR": "🔧 Erro temporário no serviço de IA. Tente novamente em alguns momentos.",
            "GENERAL_ERROR": "❌ Erro interno no processamento. Verifique sua pergunta e tente novamente."
        }
        
        # Análise inteligente da pergunta para resposta contextual
        pergunta_lower = pergunta.lower()
        
        if any(word in pergunta_lower for word in ["4150", "colheitadeira", "case"]):
            categoria = "ESPECIFICACOES"
            resposta_base = """Para especificações da colheitadeira Case IH 4150, consulte:

🔍 INFORMAÇÕES TÍPICAS:
- Motor: Consulte manual técnico para especificações exatas
- Potência: Varia conforme configuração (consulte manual)
- Sistema: Colheitadeira axial com tecnologia Case IH

📚 RECOMENDAÇÃO: Acesse o manual técnico específico do modelo 4150 para dados precisos de motor e potência."""
            
        elif any(word in pergunta_lower for word in ["motor", "potencia", "especificacao"]):
            categoria = "ESPECIFICACOES"
            resposta_base = "Para especificações técnicas detalhadas como potência do motor, consulte o manual específico do seu equipamento."
            
        elif any(word in pergunta_lower for word in ["manutencao", "oleo", "filtro"]):
            categoria = "MANUTENCAO"
            resposta_base = "Para procedimentos de manutenção, consulte o manual de serviço da sua máquina agrícola."
            
        else:
            categoria = "GERAL"
            resposta_base = "Para informações específicas, consulte o manual do equipamento ou contate o suporte técnico."
        
        resposta_final = f"{fallback_messages.get(erro_tipo, 'Erro no processamento.')} {resposta_base}"
        
        return {
            "resposta": resposta_final,
            "categoria": categoria,
            "confianca": 0.3,
            "modelo_usado": "fallback",
            "fallback_usado": True,
            "tokens_usados": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0
        }
