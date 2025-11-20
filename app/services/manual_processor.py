import os
import glob
import logging
import numpy as np
from typing import List, Dict, Tuple, Optional
import aiofiles
import asyncio
import re
from app.config import settings

logger = logging.getLogger(__name__)

class ManualProcessor:
    def __init__(self):
        self.manuais_cache = {}
        self.manuais_embeddings = {}  # Cache de embeddings dos títulos
        self.manuais_carregados = 0
        self.openai_client = None
        
    async def initialize(self):
        """Carrega todos os manuais e gera embeddings na inicialização"""
        await self.carregar_manuais()
        await self.gerar_embeddings_titulos()
        
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
                    if conteudo:  # Só adiciona se tem conteúdo
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
    
    async def gerar_embeddings_titulos(self):
        """Gera embeddings dos títulos dos manuais para busca semântica"""
        try:
            # Importa OpenAI apenas quando necessário
            import openai
            
            if not settings.OPENAI_API_KEY:
                logger.warning("OpenAI API key não configurada, usando busca por palavras-chave apenas")
                return
            
            self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            
            logger.info("Gerando embeddings dos títulos dos manuais...")
            
            for nome_arquivo in self.manuais_cache.keys():
                try:
                    # Usa o nome do arquivo como título (sem .md)
                    titulo = nome_arquivo.replace('.md', '')
                    
                    # Gera embedding do título
                    response = await asyncio.to_thread(
                        self.openai_client.embeddings.create,
                        model="text-embedding-3-small",
                        input=titulo
                    )
                    
                    embedding = np.array(response.data[0].embedding)
                    self.manuais_embeddings[nome_arquivo] = embedding
                    
                except Exception as e:
                    logger.error(f"Erro ao gerar embedding para {nome_arquivo}: {str(e)}")
                    continue
            
            logger.info(f"Embeddings gerados para {len(self.manuais_embeddings)} manuais")
            
        except Exception as e:
            logger.error(f"Erro ao configurar embeddings: {str(e)}")
            self.openai_client = None
    
    def buscar_contexto_relevante(self, pergunta: str, modelo_maquina: str = None) -> Tuple[str, List[Dict]]:
        """
        Busca híbrida: Embeddings semânticos + palavras-chave
        Retorna os 3 manuais mais relevantes com contexto completo
        """
        if not self.manuais_cache:
            return "Nenhum manual carregado.", []
        
        try:
            # 1. DETECTA MÚLTIPLAS MARCAS (como no seu código original)
            marcas_detectadas = self._detectar_marcas_na_pergunta(pergunta)
            
            if len(marcas_detectadas) > 1:
                marcas_fmt = ", ".join([m.title() for m in marcas_detectadas])
                return (f"⚠️ Percebi que sua pergunta envolve múltiplas marcas ({marcas_fmt}). "
                       "Para garantir uma resposta precisa e detalhada, "
                       "por favor pergunte sobre uma marca por vez. 😊"), []
            
            # 2. BUSCA SEMÂNTICA (se embeddings disponíveis)
            if self.openai_client and self.manuais_embeddings:
                top_manuais = self._busca_semantica_por_titulo(pergunta)
            else:
                # 3. FALLBACK: Busca por palavras-chave (seu método original)
                top_manuais = self._busca_por_palavras_chave(pergunta, modelo_maquina)
            
            if not top_manuais:
                return self._fallback_offline(pergunta), []
            
            # 4. MONTA CONTEXTO COMPLETO DOS 3 MANUAIS (como você queria)
            contexto_completo = self._montar_contexto_completo(top_manuais)
            
            # 5. PREPARA REFERÊNCIAS
            referencias = []
            for manual in top_manuais:
                nome_arquivo = manual.get('arquivo', manual.get('nome', ''))
                conteudo = manual.get('conteudo', manual.get('texto', ''))
                
                referencias.append({
                    "arquivo": nome_arquivo,
                    "relevancia": manual.get('relevancia', 0.9),
                    "trecho": self._extrair_trecho_relevante(conteudo, pergunta)[:300] + "..."
                })
            
            logger.info(f"Busca realizada: {len(referencias)} manuais selecionados")
            
            return contexto_completo, referencias
            
        except Exception as e:
            logger.error(f"Erro na busca: {str(e)}")
            return self._fallback_offline(pergunta), []
    
    def _detectar_marcas_na_pergunta(self, pergunta: str) -> List[str]:
        """Detecta marcas mencionadas na pergunta (do seu código original)"""
        marcas = ["john deere", "new holland", "case ih", "case", "fendt", "valtra", "massey"]
        pergunta_lower = pergunta.lower()
        return [m for m in marcas if m in pergunta_lower]
    
    def _busca_semantica_por_titulo(self, pergunta: str, top_n: int = 3) -> List[Dict]:
        """
        Busca semântica usando embeddings (baseado no seu notebook)
        """
        try:
            # Gera embedding da pergunta
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=pergunta
            )
            emb_pergunta = np.array(response.data[0].embedding)
            
            # Calcula similaridades
            similaridades = []
            
            for nome_arquivo, embedding_titulo in self.manuais_embeddings.items():
                # Similaridade coseno
                sim = np.dot(emb_pergunta, embedding_titulo) / (
                    np.linalg.norm(emb_pergunta) * np.linalg.norm(embedding_titulo)
                )
                
                similaridades.append({
                    'arquivo': nome_arquivo,
                    'nome': nome_arquivo.replace('.md', ''),
                    'conteudo': self.manuais_cache[nome_arquivo],
                    'texto': self.manuais_cache[nome_arquivo],
                    'relevancia': float(sim),
                    'embedding_titulo': embedding_titulo
                })
            
            # Ordena por similaridade e pega os top N
            similares_ordenados = sorted(similaridades, key=lambda x: x['relevancia'], reverse=True)
            
            logger.info(f"Busca semântica: top 3 relevâncias = {[f'{x['relevancia']:.3f}' for x in similares_ordenados[:3]]}")
            
            return similares_ordenados[:top_n]
            
        except Exception as e:
            logger.error(f"Erro na busca semântica: {str(e)}")
            return []
    
    def _busca_por_palavras_chave(self, pergunta: str, modelo_maquina: str = None, top_n: int = 3) -> List[Dict]:
        """
        Busca por palavras-chave (seu método original como fallback)
        """
        # Extrai palavras-chave
        palavras_chave = self._extrair_palavras_chave(pergunta, modelo_maquina)
        
        # Busca nos manuais
        resultados = []
        
        for nome_arquivo, conteudo in self.manuais_cache.items():
            relevancia = self._calcular_relevancia_palavras(conteudo, palavras_chave, modelo_maquina)
            
            if relevancia > 0.05:  # Threshold baixo para pegar mais resultados
                resultados.append({
                    'arquivo': nome_arquivo,
                    'nome': nome_arquivo.replace('.md', ''),
                    'conteudo': conteudo,
                    'texto': conteudo,
                    'relevancia': relevancia
                })
        
        # Ordena por relevância
        resultados.sort(key=lambda x: x['relevancia'], reverse=True)
        
        logger.info(f"Busca por palavras-chave: {len(resultados)} manuais encontrados")
        
        return resultados[:top_n]
    
    def _extrair_palavras_chave(self, pergunta: str, modelo_maquina: str = None) -> List[str]:
        """Extrai palavras-chave relevantes (seu método original)"""
        palavras = pergunta.lower().split()
        
        # Adiciona modelo da máquina se fornecido
        if modelo_maquina and modelo_maquina != "string":
            palavras.extend(modelo_maquina.lower().split())
        
        # Remove palavras comuns (stop words)
        stop_words = {
            'o', 'a', 'e', 'de', 'do', 'da', 'em', 'um', 'uma', 'para', 'com', 
            'não', 'que', 'se', 'na', 'por', 'mais', 'as', 'os', 'como', 'mas',
            'foi', 'ao', 'ele', 'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser',
            'qual', 'quais', 'string'
        }
        
        palavras_filtradas = [p for p in palavras if p not in stop_words and len(p) > 2]
        
        return palavras_filtradas[:15]  # Limita a 15 palavras-chave
    
    def _calcular_relevancia_palavras(self, conteudo: str, palavras_chave: List[str], modelo_maquina: str = None) -> float:
        """Calcula relevância baseado em palavras-chave (seu método original)"""
        conteudo_lower = conteudo.lower()
        score = 0.0
        
        # Pontuação por palavras-chave
        for palavra in palavras_chave:
            count = conteudo_lower.count(palavra.lower())
            score += count * 0.1
        
        # Bonus para modelo específico
        if modelo_maquina and modelo_maquina != "string" and modelo_maquina.lower() in conteudo_lower:
            score += 0.5
        
        # Bonus para termos técnicos importantes
        termos_importantes = [
            'motor', 'potencia', 'hp', 'cv', '4150', 'colheitadeira', 
            'especificacao', 'cilindrada', 'torque'
        ]
        
        for termo in termos_importantes:
            if termo in conteudo_lower:
                score += 0.2
        
        # Normaliza
        return min(score, 1.0)
    
    def _extrair_trecho_relevante(self, conteudo: str, pergunta: str) -> str:
        """Extrai trecho mais relevante (seu método original melhorado)"""
        if not conteudo:
            return ""
        
        palavras_pergunta = pergunta.lower().split()
        linhas = conteudo.split('\n')
        melhor_trecho = ""
        melhor_score = 0
        
        for i, linha in enumerate(linhas):
            # Analisa janela de 5 linhas
            janela = '\n'.join(linhas[max(0, i-2):min(len(linhas), i+3)])
            
            # Score baseado em palavras da pergunta
            score = sum(1 for palavra in palavras_pergunta 
                       if len(palavra) > 2 and palavra in janela.lower())
            
            if score > melhor_score:
                melhor_score = score
                melhor_trecho = janela
        
        return melhor_trecho if melhor_trecho else conteudo[:300]
    
    def _montar_contexto_completo(self, top_manuais: List[Dict]) -> str:
        """
        Monta contexto completo dos 3 manuais (como você queria)
        """
        contextos = []
        
        for i, manual in enumerate(top_manuais, 1):
            nome = manual.get('nome', manual.get('arquivo', f'Manual {i}'))
            conteudo = manual.get('conteudo', manual.get('texto', ''))
            relevancia = manual.get('relevancia', 0.0)
            
            # Limita conteúdo para não explodir o contexto
            if len(conteudo) > 3000:
                conteudo = conteudo[:3000] + "\n[...conteúdo truncado...]"
            
            contexto_manual = f"""
### {nome} ###
(Relevância: {relevancia:.3f})

{conteudo}

---
"""
            contextos.append(contexto_manual)
        
        contexto_final = '\n'.join(contextos)
        
        # Adiciona instrução para a IA (como no seu prompt original)
        instrucao = f"""
Você é um especialista técnico em máquinas agrícolas.
Use apenas o conteúdo dos manuais abaixo para responder à pergunta do usuário.

Instruções:
- Mantenha um tom profissional e cordial
- Cite sempre o nome do manual usado como base
- Se a informação não estiver nos manuais, diga claramente
- Para Case IH 4150: forneça especificações detalhadas se disponível

📘 CONTEXTO DOS MANUAIS:
{contexto_final}

🧭 PERGUNTA DO USUÁRIO:
"""
        
        return instrucao
    
    def _fallback_offline(self, pergunta: str) -> str:
        """Fallback estruturado (seu método original)"""
        return """
INFORMAÇÃO GERAL SOBRE MÁQUINAS AGRÍCOLAS:

Para consultas específicas sobre manutenção, operação ou especificações técnicas, 
recomendamos consultar o manual específico do seu equipamento ou contatar o 
suporte técnico autorizado da marca.

MARCAS SUPORTADAS:
- Case IH: Linha completa de equipamentos agrícolas (incluindo colheitadeiras)
- John Deere: Linha completa de equipamentos agrícolas  
- New Holland: Linha completa de equipamentos agrícolas 
- Valtra: Linha completa de equipamentos agrícolas 
- FENDT: Linha completa de equipamentos agrícolas 

Para melhor assistência, informe:
1. Marca e modelo da máquina
2. Tipo de problema ou dúvida específica
3. Contexto da operação

Total de manuais disponíveis: """ + str(self.manuais_carregados)

# Instância global
manual_processor = ManualProcessor()
