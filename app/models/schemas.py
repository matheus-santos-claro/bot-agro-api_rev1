from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class QuestionRequest(BaseModel):
    pergunta: str = Field(..., min_length=5, max_length=500, description="Pergunta sobre máquinas agrícolas")
    modelo_maquina: Optional[str] = Field(None, max_length=100, description="Modelo específico da máquina (opcional)")
    marca: Optional[str] = Field(None, max_length=50, description="Marca da máquina (opcional)")

class ManualReference(BaseModel):
    arquivo: str
    relevancia: float
    trecho: str

class BotResponse(BaseModel):
    resposta: str
    categoria: str
    confianca: float
    referencias: List[ManualReference]
    tempo_processamento: float
    modelo_usado: str
    fallback_usado: bool
    tokens_usados: Optional[int] = 0
    prompt_tokens: Optional[int] = 0
    completion_tokens: Optional[int] = 0

class HealthResponse(BaseModel):
    status: str
    version: str
    openai_configured: bool
    manuais_carregados: int
    timestamp: str
