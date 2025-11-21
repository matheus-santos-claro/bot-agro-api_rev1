# app/main.py
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.services.manual_processor import manual_processor

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modelos Pydantic
class PerguntaRequest(BaseModel):
    pergunta: str
    modelo_maquina: str = None

class PerguntaResponse(BaseModel):
    resposta: str
    categoria: str
    confianca: float
    referencias: List[Dict]
    tempo_processamento: float
    modelo_usado: str
    fallback_usado: bool
    tokens_usados: int

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str

class ManuaisStatusResponse(BaseModel):
    total_manuais: int
    manuais_carregados: int
    embeddings_gerados: bool
    status: str
    manuais_lista: List[str]

# Contexto de inicialização
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação"""
    logger.info("🚀 Iniciando aplicação...")
    
    # Inicializa o processador de manuais
    try:
        await manual_processor.initialize()
        logger.info("✅ Manual processor inicializado com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar manual processor: {str(e)}")
        raise
    
    yield
    
    logger.info("🛑 Finalizando aplicação...")

# Criação da aplicação FastAPI
app = FastAPI(
    title="Bot Agrícola API",
    description="API especializada em consultas sobre máquinas agrícolas com busca semântica",
    version="1.0.0",
    lifespan=lifespan
)

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints

@app.get("/", response_model=Dict[str, str])
async def root():
    """Endpoint raiz"""
    return {
        "message": "Bot Agrícola API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Verificação de saúde da API"""
    logger.info("❤️ Health check solicitado")
    
    from datetime import datetime
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )

@app.get("/manuais/status", response_model=ManuaisStatusResponse)
async def manuais_status():
    """Status dos manuais carregados"""
    logger.info("📊 Status dos manuais solicitado")
    
    try:
        # Verifica se o processador foi inicializado
        if not manual_processor.inicializado:
            raise HTTPException(
                status_code=503, 
                detail="Sistema ainda não inicializado. Aguarde alguns segundos."
            )
        
        # Coleta informações dos manuais
        total_manuais = len(manual_processor.base_manuais)
        manuais_carregados = manual_processor.manuais_carregados
        
        # Lista dos manuais carregados
        manuais_lista = []
        for manual in manual_processor.base_manuais:
            manuais_lista.append(manual.get("titulo", "Título não disponível"))
        
        # Verifica se embeddings foram gerados
        embeddings_gerados = False
        if manual_processor.base_manuais:
            primeiro_manual = manual_processor.base_manuais[0]
            embeddings_gerados = (
                "embedding_titulo" in primeiro_manual and 
                len(primeiro_manual.get("embedding_titulo", [])) > 0
            )
        
        # Determina status geral
        if total_manuais == 0:
            status = "no_manuals"
        elif not embeddings_gerados:
            status = "loading_embeddings"
        elif total_manuais == manuais_carregados:
            status = "ready"
        else:
            status = "partial_load"
        
        logger.info(f"📊 Status: {total_manuais} manuais, embeddings: {embeddings_gerados}")
        
        return ManuaisStatusResponse(
            total_manuais=total_manuais,
            manuais_carregados=manuais_carregados,
            embeddings_gerados=embeddings_gerados,
            status=status,
            manuais_lista=manuais_lista
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar status dos manuais: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno ao verificar status dos manuais: {str(e)}"
        )

@app.post("/pergunta", response_model=PerguntaResponse)
async def processar_pergunta(request: PerguntaRequest):
    """Processa pergunta sobre máquinas agrícolas"""
    inicio = time.time()
    
    logger.info(f"❓ Nova pergunta recebida: '{request.pergunta[:50]}...'")
    
    try:
        # Verifica se o sistema está inicializado
        if not manual_processor.inicializado:
            raise HTTPException(
                status_code=503,
                detail="Sistema ainda não inicializado. Aguarde alguns segundos e tente novamente."
            )
        
        # Verifica se há manuais carregados
        if not manual_processor.base_manuais:
            raise HTTPException(
                status_code=503,
                detail="Nenhum manual carregado. Sistema em manutenção."
            )
        
        # Busca contexto relevante
        contexto, referencias = manual_processor.buscar_contexto_relevante(
            request.pergunta, 
            request.modelo_maquina
        )
        
        # Se não encontrou contexto relevante, retorna mensagem educativa
        if not referencias:
            tempo_processamento = time.time() - inicio
            
            return PerguntaResponse(
                resposta=contexto,  # Já contém a mensagem apropriada
                categoria="ORIENTACAO",
                confianca=0.8,
                referencias=[],
                tempo_processamento=tempo_processamento,
                modelo_usado="sistema",
                fallback_usado=True,
                tokens_usados=0
            )
        
        # Importa e usa o serviço OpenAI
        from app.services.openai_service import openai_service
        
        # Gera resposta usando OpenAI
        resposta_openai = await openai_service.gerar_resposta(contexto)
        
        tempo_processamento = time.time() - inicio
        
        # Determina categoria baseada no conteúdo da resposta
        categoria = "GERAL"
        resposta_lower = resposta_openai.get("resposta", "").lower()
        
        if any(word in resposta_lower for word in ["motor", "potência", "cv", "hp", "especificação"]):
            categoria = "ESPECIFICACOES"
        elif any(word in resposta_lower for word in ["manutenção", "manter", "trocar", "verificar"]):
            categoria = "MANUTENCAO"
        elif any(word in resposta_lower for word in ["operar", "configurar", "ajustar", "usar"]):
            categoria = "OPERACAO"
        elif any(word in resposta_lower for word in ["problema", "erro", "falha", "troubleshoot"]):
            categoria = "TROUBLESHOOTING"
        
        # Calcula confiança baseada na qualidade das referências
        confianca = 0.7  # Base
        if referencias:
            relevancia_media = sum(ref.get("relevancia", 0) for ref in referencias) / len(referencias)
            confianca = min(0.95, 0.5 + relevancia_media * 0.5)
        
        logger.info(f"✅ Resposta gerada em {tempo_processamento:.2f}s - Categoria: {categoria}")
        
        return PerguntaResponse(
            resposta=resposta_openai.get("resposta", "Erro ao gerar resposta"),
            categoria=categoria,
            confianca=confianca,
            referencias=referencias,
            tempo_processamento=tempo_processamento,
            modelo_usado=resposta_openai.get("modelo_usado", settings.OPENAI_MODEL),
            fallback_usado=False,
            tokens_usados=resposta_openai.get("tokens_usados", 0)
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        tempo_processamento = time.time() - inicio
        logger.error(f"❌ Erro ao processar pergunta: {str(e)}")
        
        # Retorna resposta de erro amigável
        return PerguntaResponse(
            resposta=f"Desculpe, ocorreu um erro interno ao processar sua pergunta. "
                    f"Nossa equipe foi notificada. Tente novamente em alguns minutos.",
            categoria="ERRO",
            confianca=0.0,
            referencias=[],
            tempo_processamento=tempo_processamento,
            modelo_usado="sistema",
            fallback_usado=True,
            tokens_usados=0
        )

@app.get("/test")
async def test_endpoint():
    """Endpoint de teste simples"""
    return {
        "message": "API funcionando!",
        "timestamp": time.time(),
        "manuais_carregados": len(manual_processor.base_manuais) if manual_processor.inicializado else 0
    }

# Tratamento de erros globais
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"❌ Erro não tratado: {str(exc)}")
    return {
        "error": "Erro interno do servidor",
        "message": "Nossa equipe foi notificada sobre este problema"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
