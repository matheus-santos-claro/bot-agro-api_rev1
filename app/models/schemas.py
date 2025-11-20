from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class QueryType(str, Enum):
    ESPECIFICACOES = "ESPECIFICAÇÕES"
    MANUTENCAO = "MANUTENÇÃO"
    OPERACAO = "OPERAÇÃO"
    TROUBLESHOOTING = "TROUBLESHOOTING"
    GERAL = "GERAL"

class QuestionRequest(BaseModel):
    pergunta: str = Field(..., min_length=5, max_length=500, description="Pergunta sobre máquinas agrícolas")
    modelo_maquina: Optional[str] = Field(None, description="Modelo específico da máquina (opcional)")
    marca: Optional[str] = Field(None, description="Marca da máquina (Case IH, John Deere, New Holland, Valtra)")

class ManualReference(BaseModel):
    arquivo: str
    relevancia: float
    trecho: str

class BotResponse(BaseModel):
    resposta: str
    categoria: QueryType
    confianca: float = Field(..., ge=0.0, le=1.0)
    referencias: List[ManualReference]
    tempo_processamento: float
    modelo_usado: str
    fallback_usado: bool = False

class HealthResponse(BaseModel):
    status: str
    version: str
    openai_configured: bool
    manuais_carregados: int
    timestamp: str