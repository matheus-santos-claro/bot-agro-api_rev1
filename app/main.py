# app/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import uuid
import re
import html
import unicodedata
from typing import Optional

from app.config import settings
from app.models.schemas import QuestionRequest, BotResponse, HealthResponse, ManualReference
from app.services.openai_service import OpenAIService
from app.services.manual_processor import manual_processor

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Inicialização da aplicação
app = FastAPI(
    title="🌾 Bot Agrícola API",
    description="API especializada em consultas sobre máquinas agrícolas",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicialização dos serviços
@app.on_event("startup")
async def startup_event():
    """Inicializa serviços na startup"""
    logger.info("🌾 Iniciando Bot Agricola API...")
    
    try:
        # Carrega manuais
        await manual_processor.initialize()
        logger.info(f"📚 Manuais carregados: {manual_processor.manuais_carregados} arquivos")
        
        # Testa OpenAI
        if settings.OPENAI_API_KEY:
            logger.info("🤖 OpenAI API configurada com sucesso")
        else:
            logger.warning("⚠️ OpenAI API não configurada")
        
        logger.info("✅ API inicializada com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro na inicialização: {str(e)}")

# Dependency injection para OpenAI Service
def get_openai_service() -> OpenAIService:
    return OpenAIService()

def sanitize_input(text: str) -> str:
    """Sanitiza entrada do usuário de forma segura"""
    if not text:
        return ""
    
    try:
        # Remove apenas caracteres realmente perigosos
        text = text.replace('<', '').replace('>', '')
        text = text.replace('{', '').replace('}', '')
        
        # Remove múltiplos espaços
        text = ' '.join(text.split())
        
        # Limita tamanho
        if len(text) > 500:
            text = text[:500]
        
        return text.strip()
        
    except Exception as e:
        logger.error(f"Erro na sanitização: {str(e)}")
        return text.strip() if text else ""

def validate_request(request: QuestionRequest) -> tuple[str, Optional[str], Optional[str]]:
    """Valida e sanitiza dados da requisição"""
    
    # Sanitiza pergunta
    pergunta_limpa = sanitize_input(request.pergunta)
    if not pergunta_limpa or len(pergunta_limpa) < 5:
        raise HTTPException(status_code=400, detail="Pergunta deve ter pelo menos 5 caracteres")
    
    # Sanitiza modelo e marca (opcionais)
    modelo_limpo = sanitize_input(request.modelo_maquina) if request.modelo_maquina and request.modelo_maquina != "string" else None
    marca_limpa = sanitize_input(request.marca) if request.marca and request.marca != "string" else None
    
    return pergunta_limpa, modelo_limpo, marca_limpa

# Endpoints
@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "message": "🌾 Bot Agrícola API - Especialista em Máquinas Agrícolas",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check da API"""
    logger.info("🔍 Health check solicitado")
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        openai_configured=bool(settings.OPENAI_API_KEY),
        manuais_carregados=manual_processor.manuais_carregados,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
    )

@app.get("/manuais/status")
async def manuais_status():
    """Status dos manuais carregados"""
    logger.info("📊 Status dos manuais solicitado")
    
    try:
        # Verifica se manual_processor foi inicializado e tem cache
        if not hasattr(manual_processor, 'manuais_cache') or manual_processor.manuais_cache is None:
            # Fallback: usa base_manuais se manuais_cache não existir
            if hasattr(manual_processor, 'base_manuais') and manual_processor.base_manuais:
                total_manuais = len(manual_processor.base_manuais)
                manuais_fonte = manual_processor.base_manuais
                usar_base_manuais = True
            else:
                return {
                    "total_manuais": 0,
                    "path": settings.MANUAIS_PATH,
                    "status": "não_inicializado",
                    "marcas_distribuicao": {},
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
        else:
            # Usa manuais_cache normalmente
            total_manuais = len(manual_processor.manuais_cache)
            manuais_fonte = manual_processor.manuais_cache.keys()
            usar_base_manuais = False
        
        # Conta manuais por marca
        marcas_count = {}
        
        if usar_base_manuais:
            # Conta usando base_manuais
            for manual in manuais_fonte:
                titulo = manual.get("titulo", "").lower()
                arquivo = manual.get("arquivo", "").lower()
                nome_completo = f"{titulo} {arquivo}".lower()
                
                if 'case' in nome_completo:
                    marcas_count['Case IH'] = marcas_count.get('Case IH', 0) + 1
                elif 'john' in nome_completo or 'deere' in nome_completo:
                    marcas_count['John Deere'] = marcas_count.get('John Deere', 0) + 1
                elif 'holland' in nome_completo:
                    marcas_count['New Holland'] = marcas_count.get('New Holland', 0) + 1
                elif 'valtra' in nome_completo:
                    marcas_count['Valtra'] = marcas_count.get('Valtra', 0) + 1
                elif 'fendt' in nome_completo:
                    marcas_count['FENDT'] = marcas_count.get('FENDT', 0) + 1
                elif 'massey' in nome_completo or 'ferguson' in nome_completo:
                    marcas_count['Massey Ferguson'] = marcas_count.get('Massey Ferguson', 0) + 1
                else:
                    marcas_count['Outros'] = marcas_count.get('Outros', 0) + 1
        else:
            # Conta usando manuais_cache (método original)
            for nome_arquivo in manuais_fonte:
                nome_lower = nome_arquivo.lower()
                if 'case' in nome_lower:
                    marcas_count['Case IH'] = marcas_count.get('Case IH', 0) + 1
                elif 'john' in nome_lower or 'deere' in nome_lower:
                    marcas_count['John Deere'] = marcas_count.get('John Deere', 0) + 1
                elif 'holland' in nome_lower:
                    marcas_count['New Holland'] = marcas_count.get('New Holland', 0) + 1
                elif 'valtra' in nome_lower:
                    marcas_count['Valtra'] = marcas_count.get('Valtra', 0) + 1
                elif 'fendt' in nome_lower:
                    marcas_count['FENDT'] = marcas_count.get('FENDT', 0) + 1
                elif 'massey' in nome_lower or 'ferguson' in nome_lower:
                    marcas_count['Massey Ferguson'] = marcas_count.get('Massey Ferguson', 0) + 1
                else:
                    marcas_count['Outros'] = marcas_count.get('Outros', 0) + 1
        
        return {
            "total_manuais": total_manuais,
            "path": settings.MANUAIS_PATH,
            "status": "carregados" if total_manuais > 0 else "vazio",
            "marcas_distribuicao": marcas_count,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "fonte_dados": "base_manuais" if usar_base_manuais else "manuais_cache"
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar status dos manuais: {str(e)}")
        
        # Retorna resposta de erro mas não quebra a API
        return {
            "total_manuais": 0,
            "path": settings.MANUAIS_PATH,
            "status": "erro",
            "marcas_distribuicao": {},
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "erro": str(e)
        }

@app.get("/test")
async def test_endpoint():
    """Endpoint de teste simples"""
    return {
        "status": "OK",
        "message": "API funcionando corretamente",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "manuais_carregados": manual_processor.manuais_carregados,
        "openai_configured": bool(settings.OPENAI_API_KEY)
    }

@app.post("/pergunta", response_model=BotResponse)
async def fazer_pergunta(
    request: QuestionRequest,
    openai_service: OpenAIService = Depends(get_openai_service)
):
    """Processa pergunta sobre máquinas agrícolas"""
    
    # ID único para tracking
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    try:
        # Valida e sanitiza entrada
        pergunta_limpa, modelo_limpo, marca_limpa = validate_request(request)
        
        logger.info(f"Nova pergunta [req_{request_id}]: '{pergunta_limpa[:50]}...'")
        
        # Busca contexto nos manuais
        busca_start = time.time()
        contexto, referencias_raw = manual_processor.buscar_contexto_relevante(
            pergunta_limpa, 
            modelo_limpo
        )
        busca_time = time.time() - busca_start
        
        logger.info(f"Busca nos manuais [req_{request_id}]: {len(referencias_raw)} manuais em {busca_time:.2f}s")
        
        # Gera resposta com IA
        ia_start = time.time()
        resposta_ia = await openai_service.generate_response(
            pergunta_limpa,
            contexto,
            modelo_limpo
        )
        ia_time = time.time() - ia_start
        
        logger.info(f"Resposta IA [req_{request_id}]: {resposta_ia.get('modelo_usado', 'unknown')} em {ia_time:.2f}s")
        
        # Monta referências
        referencias = [
            ManualReference(
                arquivo=ref.get("arquivo", ""),
                relevancia=ref.get("relevancia", 0.0),
                trecho=ref.get("trecho", "")[:200] + "..." if len(ref.get("trecho", "")) > 200 else ref.get("trecho", "")
            )
            for ref in referencias_raw
        ]
        
        # Tempo total
        tempo_total = time.time() - start_time
        
        logger.info(f"✅ Pergunta processada [req_{request_id}]: confianca {resposta_ia.get('confianca', 0)}, tempo {tempo_total:.2f}s")
        
        return BotResponse(
            resposta=resposta_ia.get("resposta", "Erro ao gerar resposta"),
            categoria=resposta_ia.get("categoria", "GERAL"),
            confianca=resposta_ia.get("confianca", 0.0),
            referencias=referencias,
            tempo_processamento=tempo_total,
            modelo_usado=resposta_ia.get("modelo_usado", "unknown"),
            fallback_usado=resposta_ia.get("fallback_usado", True),
            tokens_usados=resposta_ia.get("tokens_usados", 0),
            prompt_tokens=resposta_ia.get("prompt_tokens", 0),
            completion_tokens=resposta_ia.get("completion_tokens", 0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao processar pergunta [req_{request_id}]: {str(e)}")
        
        return BotResponse(
            resposta="Desculpe, ocorreu um erro interno ao processar sua pergunta. Tente novamente em alguns momentos.",
            categoria="GERAL",
            confianca=0.0,
            referencias=[],
            tempo_processamento=time.time() - start_time,
            modelo_usado="erro",
            fallback_usado=True,
            tokens_usados=0,
            prompt_tokens=0,
            completion_tokens=0
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
