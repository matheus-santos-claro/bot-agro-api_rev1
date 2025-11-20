import os
import glob
import logging
from typing import List, Dict, Tuple
import aiofiles
import asyncio
from app.config import settings

logger = logging.getLogger(__name__)

class ManualProcessor:
    def __init__(self):
        self.manuais_cache = {}
        self.manuais_carregados = 0
        
    async def initialize(self):
        """Carrega todos os manuais na inicialização"""
        await self.carregar_manuais()
        
    async def carregar_manuais(self) -> Dict[str, str]:
        """Carrega todos os manuais .md de forma assíncrona"""
        if self.manuais_cache:
            return self.manuais_cache
            
        try:
            pattern = os.path.join(settings.MANUAIS_PATH, "*.md")
            arquivos_md = glob.glob(pattern)
            
            logger.info(f"Encontrados {len(arquivos_md)} arquivos .md")
            
            tasks = []
            for arquivo in arquivos_md:
                tasks.append(self._carregar_arquivo(arquivo))
            
            resultados = await asyncio.gather(*tasks, return_exceptions=True)
            
            for resultado in resultados:
                if isinstance(resultado, tuple):
                    nome_arquivo, conteudo = resultado
                    self.manuais_cache[nome_arquivo] = conteudo
                    
            self.manuais_carregados = len(self.manuais_cache)
            logger.info(f"Carregados {self.manuais_carregados} manuais com sucesso")
            
            return self.manuais_cache
            
        except Exception as e:
            logger.error(f"Erro ao carregar manuais: {str(e)}")
            return {}
    
    async def _carregar_arquivo(self, caminho_arquivo: str) -> Tuple[str, str]:
        """Carrega um arquivo individual de forma assíncrona"""
        try:
            async with aiofiles.open(caminho_arquivo, 'r', encoding='utf-8') as file:
                conteudo = await file.read()
                nome_arquivo = os.path.basename(caminho_arquivo)
                return (nome_arquivo, conteudo)
        except Exception as e:
            logger.error(f"Erro ao carregar {caminho_arquivo}: {str(e)}")
            return (os.path.basename(caminho_arquivo), "")
    
    def buscar_contexto_relevante(self, pergunta: str, modelo_maquina: str = None) -> Tuple[str, List[Dict]]:
        """Busca contexto relevante nos manuais"""
        if not self.manuais_cache:
            return "Nenhum manual carregado.", []
        
        # Palavras-chave da pergunta
        palavras_chave = self._extrair_palavras_chave(pergunta, modelo_maquina)
        
        # Busca nos manuais
        resultados = []
        
        for nome_arquivo, conteudo in self.manuais_cache.items():
            relevancia = self._calcular_relevancia(conteudo, palavras_chave, modelo_maquina)
            
            if relevancia > 0.1:  # Threshold mínimo
                trecho_relevante = self._extrair_trecho_relevante(conteudo, palavras_chave)
                
                resultados.append({
                    "arquivo": nome_arquivo,
                    "relevancia": relevancia,
                    "trecho": trecho_relevante[:500] + "..." if len(trecho_relevante) > 500 else trecho_relevante
                })
        
        # Ordena por relevância
        resultados.sort(key=lambda x: x["relevancia"], reverse=True)
        resultados = resultados[:settings.MAX_MANUAL_RESULTS]
        
        # Monta contexto
        if not resultados:
            return self._fallback_offline(pergunta), []
        
        contexto = "\n\n".join([
            f"MANUAL: {r['arquivo']}\nCONTEÚDO: {r['trecho']}"
            for r in resultados
        ])
        
        return contexto, resultados
    
    def _extrair_palavras_chave(self, pergunta: str, modelo_maquina: str = None) -> List[str]:
        """Extrai palavras-chave relevantes"""
        palavras = pergunta.lower().split()
        
        # Adiciona modelo da máquina se fornecido
        if modelo_maquina:
            palavras.extend(modelo_maquina.lower().split())
        
        # Remove palavras comuns
        stop_words = {'o', 'a', 'de', 'da', 'do', 'que', 'como', 'para', 'com', 'em', 'na', 'no'}
        palavras_filtradas = [p for p in palavras if p not in stop_words and len(p) > 2]
        
        return palavras_filtradas
    
    def _calcular_relevancia(self, conteudo: str, palavras_chave: List[str], modelo_maquina: str = None) -> float:
        """Calcula relevância do conteúdo"""
        conteudo_lower = conteudo.lower()
        score = 0.0
        
        # Pontuação por palavras-chave
        for palavra in palavras_chave:
            count = conteudo_lower.count(palavra.lower())
            score += count * 0.1
        
        # Bonus para modelo específico
        if modelo_maquina and modelo_maquina.lower() in conteudo_lower:
            score += 0.5
        
        # Normaliza
        return min(score, 1.0)
    
    def _extrair_trecho_relevante(self, conteudo: str, palavras_chave: List[str]) -> str:
        """Extrai trecho mais relevante do conteúdo"""
        linhas = conteudo.split('\n')
        melhor_trecho = ""
        melhor_score = 0
        
        for i, linha in enumerate(linhas):
            # Analisa janela de 5 linhas
            janela = '\n'.join(linhas[max(0, i-2):min(len(linhas), i+3)])
            
            score = sum(1 for palavra in palavras_chave if palavra.lower() in janela.lower())
            
            if score > melhor_score:
                melhor_score = score
                melhor_trecho = janela
        
        return melhor_trecho if melhor_trecho else conteudo[:500]
    
    def _fallback_offline(self, pergunta: str) -> str:
        """Fallback estruturado quando não há contexto relevante"""
        return """
INFORMAÇÃO GERAL SOBRE MÁQUINAS AGRÍCOLAS:

Para consultas específicas sobre manutenção, operação ou especificações técnicas, 
recomendamos consultar o manual específico do seu equipamento ou contatar o 
suporte técnico autorizado da marca.

MARCAS SUPORTADAS:
- Case IH: Linha completa de equipamentos agrícolas 
- John Deere: Linha completa de equipamentos agrícolas  
- New Holland: Linha completa de equipamentos agrícolas 
- Valtra: Linha completa de equipamentos agrícolas 
- FENDT: Linha completa de equipamentos agrícolas 

Para melhor assistência, informe:
1. Marca e modelo da máquina
2. Tipo de problema ou dúvida específica
3. Contexto da operação
        """

# Instância global
manual_processor = ManualProcessor()