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

# Importações dos utilitários
from app.utils import (
    app_logger, 
    generate_request_id, 
    format_response_time,
    calculate_confidence_score,
    extract_machine_info
)
from app.utils.validators import (
    validate_question, 
    validate_machine_model, 
    validate_brand,
    sanitize_input
)

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
        app_logger.logger.error(f"Erro ao inicializar OpenAI Service: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Inicialização da aplicação"""
    app_logger.logger.info("🌾 Iniciando Bot Agrícola API...")
    
    try:
        # Carrega manuais
        start_time = time.time()
        await manual_processor.initialize()
        load_time = time.time() - start_time
        
        app_logger.logger.info(
            f"📚 Manuais carregados: {manual_processor.manuais_carregados} arquivos em {format_response_time(load_time)}"
        )
        
        # Valida configuração OpenAI
        if not settings.validate_openai_key():
            app_logger.logger.warning("⚠️ OPENAI_API_KEY não configurada!")
        else:
            app_logger.logger.info("🔑 OpenAI API configurada com sucesso")
        
        app_logger.logger.info("✅ API inicializada com sucesso!")
        
    except Exception as e:
        app_logger.logger.error(f"❌ Erro na inicialização: {str(e)}", exc_info=True)
        raise

@app.get("/", response_model=dict)
async def root():
    """Endpoint raiz"""
    return {
        "message": "   Bot Agrícola API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "health": "/health",
        "manuais_carregados": manual_processor.manuais_carregados,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check da aplicação"""
    app_logger.logger.info("🔍 Health check solicitado")
    
    return HealthResponse(
        status="healthy",
        version=settings.API_VERSION,
        openai_configured=settings.validate_openai_key(),
        manuais_carregados=manual_processor.manuais_carregados,
        timestamp=datetime.now().isoformat()
    )

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
    # Gera ID único para a requisição
    request_id = generate_request_id()
    start_time = time.time()
    
    try:
        # Sanitiza entradas
        pergunta_limpa = sanitize_input(request.pergunta)
        modelo_limpo = sanitize_input(request.modelo_maquina) if request.modelo_maquina else None
        marca_limpa = sanitize_input(request.marca) if request.marca else None
        
        # Validações de entrada
        is_valid_question, error_msg = validate_question(pergunta_limpa)
        if not is_valid_question:
            app_logger.logger.warning(f"Pergunta inválida [{request_id}]: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Pergunta inválida: {error_msg}")
        
        if modelo_limpo:
            is_valid_model, error_msg = validate_machine_model(modelo_limpo)
            if not is_valid_model:
                app_logger.logger.warning(f"Modelo inválido [{request_id}]: {error_msg}")
                raise HTTPException(status_code=400, detail=f"Modelo inválido: {error_msg}")
        
        if marca_limpa:
            is_valid_brand, error_msg = validate_brand(marca_limpa)
            if not is_valid_brand:
                app_logger.logger.warning(f"Marca inválida [{request_id}]: {error_msg}")
                raise HTTPException(status_code=400, detail=f"Marca inválida: {error_msg}")
        
        # Log da requisição
        app_logger.log_request(request_id, pergunta_limpa, modelo_limpo)
        
        # Extrai informações adicionais da pergunta
        machine_info = extract_machine_info(pergunta_limpa)
        if machine_info['marca'] and not marca_limpa:
            marca_limpa = machine_info['marca']
        if machine_info['modelo'] and not modelo_limpo:
            modelo_limpo = machine_info['modelo']
        
        # Busca contexto nos manuais
        search_start = time.time()
        contexto, referencias = manual_processor.buscar_contexto_relevante(
            pergunta_limpa, 
            modelo_limpo
        )
        search_time = time.time() - search_start
        
        # Log da busca nos manuais
        app_logger.log_manual_search(request_id, len(referencias), search_time)
        
        # Gera resposta com IA
        ai_start = time.time()
        resultado = await openai_service.generate_response(
            pergunta_limpa,
            contexto,
            modelo_limpo
        )
        ai_time = time.time() - ai_start
        
        # Log da resposta da IA
        tokens_used = resultado.get("tokens_usados", 0)
        app_logger.log_ai_response(request_id, resultado["modelo_usado"], tokens_used, ai_time)
        
        # Calcula score de confiança aprimorado
        context_relevance = min(1.0, len(referencias) * 0.2)  # Mais manuais = mais relevância
        ai_quality = 0.9 if not resultado["fallback_usado"] else 0.3
        total_time = time.time() - start_time
        
        confidence_score = calculate_confidence_score(
            context_relevance=context_relevance,
            ai_response_quality=ai_quality,
            manual_matches=len(referencias),
            processing_time=total_time
        )
        
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
        
        # Log de performance
        app_logger.log_performance(request_id, total_time, confidence_score)
        
        # Log de sucesso
        app_logger.logger.info(
            f"✅ Pergunta processada [{request_id}]: "
            f"{len(referencias)} manuais, confiança {confidence_score:.2f}, "
            f"tempo {format_response_time(total_time)}"
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTPExceptions (erros de validação)
        raise
        
    except Exception as e:
        # Log de erro detalhado
        app_logger.log_error(request_id, e, "processamento_pergunta")
        
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
    app_logger.logger.info("📊 Status dos manuais solicitado")
    
    # Estatísticas básicas
    total_manuais = manual_processor.manuais_carregados
    status = "carregados" if total_manuais > 0 else "não carregados"
    
    # Informações adicionais se manuais estão carregados
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
        "timestamp": datetime.now().isoformat(),
        "memoria_cache": f"{len(str(manual_processor.manuais_cache)) / 1024:.1f} KB" if manual_processor.manuais_cache else "0 KB"
    }

@app.get("/manuais/search-test")
async def test_manual_search(q: str = "motor"):
    """
    Endpoint de teste para busca nos manuais
    
    - **q**: Termo de busca para testar
    """
    if not q or len(q.strip()) < 3:
        raise HTTPException(status_code=400, detail="Termo de busca deve ter pelo menos 3 caracteres")
    
    app_logger.logger.info(f"🔍 Teste de busca: '{q}'")
    
    start_time = time.time()
    contexto, referencias = manual_processor.buscar_contexto_relevante(q)
    search_time = time.time() - start_time
    
    return {
        "termo_busca": q,
        "manuais_encontrados": len(referencias),
        "tempo_busca": format_response_time(search_time),
        "referencias": referencias[:3],  # Apenas os 3 primeiros
        "contexto_preview": contexto[:500] + "..." if len(contexto) > 500 else contexto
    }

@app.get("/debug/info")
async def debug_info():
    """Informações de debug (apenas para desenvolvimento)"""
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail="Endpoint não disponível em produção")
    
    return {
        "environment": settings.ENVIRONMENT,
        "debug_mode": settings.DEBUG,
        "openai_model": settings.OPENAI_MODEL,
        "openai_configured": settings.validate_openai_key(),
        "max_response_time": settings.MAX_RESPONSE_TIME,
        "max_manual_results": settings.MAX_MANUAL_RESULTS,
        "manuais_path": settings.MANUAIS_PATH,
        "python_version": f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}",
        "fastapi_version": __import__('fastapi').__version__
    }

if __name__ == "__main__":
    import uvicorn
    
    # Configuração para desenvolvimento
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )