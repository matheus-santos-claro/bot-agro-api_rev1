from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging
from datetime import datetime

from app.config import settings
from app.models.schemas import QuestionRequest, BotResponse, HealthResponse
from app.services.manual_processor import manual_processor
from app.services.openai_service import OpenAIService

# Configuração de logging simples
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicialização da aplicação
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependência para OpenAI Service
def get_openai_service():
    try:
        return OpenAIService()
    except ValueError as e:
        logger.error(f"Erro ao inicializar OpenAI Service: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Inicialização da aplicação"""
    logger.info("🌾 Iniciando Bot Agricola API...")
    
    try:
        # Carrega manuais
        start_time = time.time()
        await manual_processor.initialize()
        load_time = time.time() - start_time
        
        logger.info(f"📚 Manuais carregados: {manual_processor.manuais_carregados} arquivos em {load_time:.2f}s")
        
        # Valida configuração OpenAI
        if not settings.validate_openai_key():
            logger.warning("⚠️ OPENAI_API_KEY nao configurada!")
        else:
            logger.info("🔑 OpenAI API configurada com sucesso")
        
        logger.info("✅ API inicializada com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro na inicializacao: {str(e)}", exc_info=True)
        raise

@app.get("/", response_model=dict)
async def root():
    """Endpoint raiz"""
    return {
        "message": "🌾 Bot Agricola API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "health": "/health",
        "manuais_carregados": manual_processor.manuais_carregados,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check da aplicação"""
    logger.info("🔍 Health check solicitado")
    
    return HealthResponse(
        status="healthy",
        version=settings.API_VERSION,
        openai_configured=settings.validate_openai_key(),
        manuais_carregados=manual_processor.manuais_carregados,
        timestamp=datetime.now().isoformat()
    )

def sanitize_input(text: str) -> str:
    """Sanitiza entrada do usuário"""
    if not text:
        return ""
    
    # Remove caracteres de controle e limpa
    import re
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[<>{}[\]\]', '', text)
    
    return text.strip()

def validate_question(question: str) -> tuple[bool, str]:
    """Valida pergunta do usuário"""
    if not question or not question.strip():
        return False, "Pergunta nao pode estar vazia"
    
    if len(question.strip()) < 5:
        return False, "Pergunta muito curta (minimo 5 caracteres)"
    
    if len(question) > 500:
        return False, "Pergunta muito longa (maximo 500 caracteres)"
    
    return True, ""

@app.post("/pergunta", response_model=BotResponse)
async def fazer_pergunta(
    request: QuestionRequest,
    openai_service: OpenAIService = Depends(get_openai_service)
):
    """
    Endpoint principal para perguntas sobre máquinas agrícolas
    
    - **pergunta**: Sua pergunta técnica sobre máquinas agrícolas
    - **modelo_maquina**: Modelo específico (opcional)
    - **marca**: Marca da máquina (opcional)
    """
    start_time = time.time()
    request_id = f"req_{int(time.time() * 1000)}"
    
    try:
        # Sanitiza entradas
        pergunta_limpa = sanitize_input(request.pergunta)
        modelo_limpo = sanitize_input(request.modelo_maquina) if request.modelo_maquina else None
        
        # Validação básica
        is_valid, error_msg = validate_question(pergunta_limpa)
        if not is_valid:
            logger.warning(f"Pergunta invalida [{request_id}]: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Pergunta invalida: {error_msg}")
        
        # Log da requisição
        logger.info(f"Nova pergunta [{request_id}]: '{pergunta_limpa[:100]}...'")
        
        # Busca contexto nos manuais
        search_start = time.time()
        contexto, referencias = manual_processor.buscar_contexto_relevante(
            pergunta_limpa, 
            modelo_limpo
        )
        search_time = time.time() - search_start
        
        logger.info(f"Busca nos manuais [{request_id}]: {len(referencias)} manuais em {search_time:.2f}s")
        
        # Gera resposta com IA
        ai_start = time.time()
        resultado = await openai_service.generate_response(
            pergunta_limpa,
            contexto,
            modelo_limpo
        )
        ai_time = time.time() - ai_start
        
        logger.info(f"Resposta IA [{request_id}]: {resultado['modelo_usado']} em {ai_time:.2f}s")
        
        # Calcula score de confiança
        context_relevance = min(1.0, len(referencias) * 0.2)
        ai_quality = 0.9 if not resultado["fallback_usado"] else 0.3
        total_time = time.time() - start_time
        
        # Score simples
        confidence_score = (context_relevance * 0.4) + (ai_quality * 0.4) + min(0.2, len(referencias) * 0.05)
        confidence_score = max(0.0, min(1.0, confidence_score))
        
        # Monta resposta final
        response = BotResponse(
            resposta=resultado["resposta"],
            categoria=resultado["categoria"],
            confianca=confidence_score,
            referencias=referencias,
            tempo_processamento=total_time,
            modelo_usado=resultado["modelo_usado"],
            fallback_usado=resultado["fallback_usado"]
        )
        
        # Log de sucesso
        logger.info(f"✅ Pergunta processada [{request_id}]: confianca {confidence_score:.2f}, tempo {total_time:.2f}s")
        
        return response
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar pergunta [{request_id}]: {str(e)}", exc_info=True)
        
        # Resposta de erro amigável
        error_response = BotResponse(
            resposta="Desculpe, ocorreu um erro interno ao processar sua pergunta. Tente novamente em alguns momentos.",
            categoria="GERAL",
            confianca=0.0,
            referencias=[],
            tempo_processamento=time.time() - start_time,
            modelo_usado="erro",
            fallback_usado=True
        )
        
        return error_response

@app.get("/manuais/status")
async def status_manuais():
    """Status detalhado dos manuais carregados"""
    logger.info("📊 Status dos manuais solicitado")
    
    total_manuais = manual_processor.manuais_carregados
    status = "carregados" if total_manuais > 0 else "nao carregados"
    
    # Distribuição por marca
    marcas_info = {}
    if total_manuais > 0:
        for nome_arquivo in manual_processor.manuais_cache.keys():
            nome_lower = nome_arquivo.lower()
            if 'case' in nome_lower:
                marcas_info['Case IH'] = marcas_info.get('Case IH', 0) + 1
            elif 'john' in nome_lower or 'deere' in nome_lower:
                marcas_info['John Deere'] = marcas_info.get('John Deere', 0) + 1
            elif 'holland' in nome_lower:
                marcas_info['New Holland'] = marcas_info.get('New Holland', 0) + 1
            elif 'valtra' in nome_lower:
                marcas_info['Valtra'] = marcas_info.get('Valtra', 0) + 1
            else:
                marcas_info['Outros'] = marcas_info.get('Outros', 0) + 1
    
    return {
        "total_manuais": total_manuais,
        "path": settings.MANUAIS_PATH,
        "status": status,
        "marcas_distribuicao": marcas_info,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/test")
async def test_endpoint():
    """Endpoint de teste simples"""
    return {
        "status": "API funcionando!",
        "timestamp": datetime.now().isoformat(),
        "environment": settings.ENVIRONMENT,
        "openai_configured": settings.validate_openai_key(),
        "manuais_carregados": manual_processor.manuais_carregados
    }

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
