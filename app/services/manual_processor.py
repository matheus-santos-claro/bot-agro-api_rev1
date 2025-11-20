import os
import glob
import logging
import numpy as np
from typing import List, Dict, Tuple, Optional
import aiofiles
import asyncio
from app.config import settings

logger = logging.getLogger(__name__)

class ManualProcessor:
    def __init__(self):
        self.manuais_cache = {}
        self.manuais_embeddings = {}
        self.manuais_carregados = 0
        self.openai_client = None
        self.embeddings_gerados = False
        
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
            
            logger.info(f"🔍 Encontrados {len(arquivos_md)} arquivos .md em {settings.MANUAIS_PATH}")
            
            if not arquivos_md:
                logger.error(f"❌ Nenhum arquivo .md encontrado em {settings.MANUAIS_PATH}")
                return {}
            
            tasks = []
            for arquivo in arquivos_md:
                tasks.append(self._carregar_arquivo(arquivo))
            
            resultados = await asyncio.gather(*tasks, return_exceptions=True)
            
            for resultado in resultados:
                if isinstance(resultado, tuple):
                    nome_arquivo, conteudo = resultado
                    if conteudo and len(conteudo.strip()) > 100:  # Só adiciona se tem conteúdo substancial
                        self.manuais_cache[nome_arquivo] = conteudo
                        logger.info(f"✅ Carregado: {nome_arquivo} ({len(conteudo)} chars)")
                    else:
                        logger.warning(f"⚠️ Arquivo vazio ou muito pequeno: {nome_arquivo}")
                    
            self.manuais_carregados = len(self.manuais_cache)
            logger.info(f"📚 Total carregados: {self.manuais_carregados} manuais")
            
            # Lista alguns manuais para debug
            for nome in list(self.manuais_cache.keys())[:5]:
                logger.info(f"📄 Manual disponível: {nome}")
            
            return self.manuais_cache
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar manuais: {str(e)}")
            return {}
    
    async def _carregar_arquivo(self, caminho_arquivo: str) -> Tuple[str, str]:
        """Carrega um arquivo individual de forma assíncrona"""
        try:
            async with aiofiles.open(caminho_arquivo, 'r', encoding='utf-8') as file:
                conteudo = await file.read()
                nome_arquivo = os.path.basename(caminho_arquivo)
                return (nome_arquivo, conteudo)
        except Exception as e:
            logger.error(f"❌ Erro ao carregar {caminho_arquivo}: {str(e)}")
            return (os.path.basename(caminho_arquivo), "")
    
    async def gerar_embeddings_titulos(self):
        """Gera embeddings dos títulos dos manuais para busca semântica"""
        try:
            import openai
            
            if not settings.OPENAI_API_KEY:
                logger.warning("⚠️ OpenAI API key não configurada, usando busca por palavras-chave apenas")
                return
            
            if not self.manuais_cache:
                logger.warning("⚠️ Nenhum manual carregado para gerar embeddings")
                return
            
            self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            
            logger.info(f"🧠 Gerando embeddings para {len(self.manuais_cache)} manuais...")
            
            embeddings_gerados = 0
            
            for nome_arquivo in self.manuais_cache.keys():
                try:
                    # Usa o nome do arquivo como título (sem .md)
                    titulo = nome_arquivo.replace('.md', '')
                    
                    logger.info(f"🔄 Gerando embedding para: {titulo}")
                    
                    # Gera embedding do título
                    response = await asyncio.to_thread(
                        self.openai_client.embeddings.create,
                        model="text-embedding-3-small",
                        input=titulo
                    )
                    
                    embedding = np.array(response.data[0].embedding)
                    self.manuais_embeddings[nome_arquivo] = embedding
                    embeddings_gerados += 1
                    
                    logger.info(f"✅ Embedding gerado para: {titulo}")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao gerar embedding para {nome_arquivo}: {str(e)}")
                    continue
            
            self.embeddings_gerados = embeddings_gerados > 0
            logger.info(f"🎉 Embeddings gerados com sucesso: {embeddings_gerados}/{len(self.manuais_cache)}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao configurar embeddings: {str(e)}")
            self.openai_client = None
            self.embeddings_gerados = False
    
    def buscar_contexto_relevante(self, pergunta: str, modelo_maquina: str = None) -> Tuple[str, List[Dict]]:
        """
        Busca híbrida: Embeddings semânticos + palavras-chave
        """
        if not self.manuais_cache:
            logger.error("❌ Nenhum manual carregado")
            return "Nenhum manual carregado.", []
        
        logger.info(f"🔍 Iniciando busca para: '{pergunta}' (modelo: {modelo_maquina})")
        
        try:
            # 1. DETECTA MÚLTIPLAS MARCAS
            marcas_detectadas = self._detectar_marcas_na_pergunta(pergunta)
            logger.info(f"🏷️ Marcas detectadas: {marcas_detectadas}")
            
            if len(marcas_detectadas) > 1:
                marcas_fmt = ", ".join([m.title() for m in marcas_detectadas])
                return (f"⚠️ Percebi que sua pergunta envolve múltiplas marcas ({marcas_fmt}). "
                       "Para garantir uma resposta precisa e detalhada, "
                       "por favor pergunte sobre uma marca por vez. 😊"), []
            
            # 2. BUSCA SEMÂNTICA (se disponível)
            top_manuais = []
            
            if self.embeddings_gerados and self.openai_client:
                logger.info("🧠 Usando busca semântica com embeddings")
                top_manuais = self._busca_semantica_por_titulo(pergunta)
            
            # 3. FALLBACK: Busca por palavras-chave
            if not top_manuais:
                logger.info("🔤 Usando busca por palavras-chave (fallback)")
                top_manuais = self._busca_por_palavras_chave(pergunta, modelo_maquina)
            
            if not top_manuais:
                logger.warning("❌ Nenhum manual relevante encontrado")
                return self._fallback_offline(pergunta), []
            
            # Log dos manuais encontrados
            for i, manual in enumerate(top_manuais):
                nome = manual.get('arquivo', manual.get('nome', 'Desconhecido'))
                relevancia = manual.get('relevancia', 0.0)
                logger.info(f"📄 Manual {i+1}: {nome} (relevância: {relevancia:.3f})")
            
            # 4. MONTA CONTEXTO COMPLETO
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
            
            logger.info(f"✅ Busca concluída: {len(referencias)} manuais selecionados")
            
            return contexto_completo, referencias
            
        except Exception as e:
            logger.error(f"❌ Erro na busca: {str(e)}")
            return self._fallback_offline(pergunta), []
    
    def _detectar_marcas_na_pergunta(self, pergunta: str) -> List[str]:
        """Detecta marcas mencionadas na pergunta"""
        marcas = ["john deere", "new holland", "case ih", "case", "fendt", "valtra", "massey"]
        pergunta_lower = pergunta.lower()
        return [m for m in marcas if m in pergunta_lower]
    
    def _busca_semantica_por_titulo(self, pergunta: str, top_n: int = 3) -> List[Dict]:
        """Busca semântica usando embeddings"""
        try:
            logger.info(f"🧠 Gerando embedding da pergunta: '{pergunta}'")
            
            # Gera embedding da pergunta
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=pergunta
            )
            emb_pergunta = np.array(response.data[0].embedding)
            
            logger.info(f"✅ Embedding da pergunta gerado: {len(emb_pergunta)} dimensões")
            
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
                    'relevancia': float(sim)
                })
                
                logger.info(f"📊 {nome_arquivo}: similaridade = {sim:.3f}")
            
            # Ordena por similaridade
            similares_ordenados = sorted(similaridades, key=lambda x: x['relevancia'], reverse=True)
            
            # Log dos top 3
            for i, manual in enumerate(similares_ordenados[:3]):
                logger.info(f"🏆 Top {i+1}: {manual['arquivo']} (sim: {manual['relevancia']:.3f})")
            
            return similares_ordenados[:top_n]
            
        except Exception as e:
            logger.error(f"❌ Erro na busca semântica: {str(e)}")
            return []
    
    def _busca_por_palavras_chave(self, pergunta: str, modelo_maquina: str = None, top_n: int = 3) -> List[Dict]:
        """Busca por palavras-chave como fallback"""
        logger.info("🔤 Iniciando busca por palavras-chave")
        
        # Extrai palavras-chave
        palavras_chave = self._extrair_palavras_chave(pergunta, modelo_maquina)
        logger.info(f"🔑 Palavras-chave: {palavras_chave}")
        
        # Busca nos manuais
        resultados = []
        
        for nome_arquivo, conteudo in self.manuais_cache.items():
            relevancia = self._calcular_relevancia_palavras(conteudo, palavras_chave, modelo_maquina)
            
            if relevancia > 0.05:  # Threshold baixo
                resultados.append({
                    'arquivo': nome_arquivo,
                    'nome': nome_arquivo.replace('.md', ''),
                    'conteudo': conteudo,
                    'texto': conteudo,
                    'relevancia': relevancia
                })
                
                logger.info(f"📄 {nome_arquivo}: relevância = {relevancia:.3f}")
        
        # Ordena por relevância
        resultados.sort(key=lambda x: x['relevancia'], reverse=True)
        
        logger.info(f"🔤 Busca por palavras-chave: {len(resultados)} manuais encontrados")
        
        return resultados[:top_n]
    
    def _extrair_palavras_chave(self, pergunta: str, modelo_maquina: str = None) -> List[str]:
        """Extrai palavras-chave relevantes"""
        palavras = pergunta.lower().split()
        
        # Adiciona modelo da máquina se fornecido
        if modelo_maquina and modelo_maquina != "string":
            palavras.extend(modelo_maquina.lower().split())
        
        # Remove palavras comuns
        stop_words = {
            'o', 'a', 'e', 'de', 'do', 'da', 'em', 'um', 'uma', 'para', 'com', 
            'não', 'que', 'se', 'na', 'por', 'mais', 'as', 'os', 'como', 'mas',
            'foi', 'ao', 'ele', 'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser',
            'qual', 'quais', 'string'
        }
        
        palavras_filtradas = [p for p in palavras if p not in stop_words and len(p) > 2]
        
        return palavras_filtradas[:15]
    
    def _calcular_relevancia_palavras(self, conteudo: str, palavras_chave: List[str], modelo_maquina: str = None) -> float:
        """Calcula relevância baseado em palavras-chave"""
        conteudo_lower = conteudo.lower()
        score = 0.0
        
        # Pontuação por palavras-chave
        for palavra in palavras_chave:
            count = conteudo_lower.count(palavra.lower())
            score += count * 0.1
        
        # Bonus para modelo específico
        if modelo_maquina and modelo_maquina != "string" and modelo_maquina.lower() in conteudo_lower:
            score += 0.5
        
        # Bonus para termos importantes da pergunta
        termos_importantes = ['4150', 'colheitadeira', 'case', 'motor', 'potencia', 'hp', 'cv']
        for termo in termos_importantes:
            if termo in conteudo_lower:
                score += 0.3
        
        return min(score, 1.0)
    
    def _extrair_trecho_relevante(self, conteudo: str, pergunta: str) -> str:
        """Extrai trecho mais relevante"""
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
        """Monta contexto completo dos manuais"""
        if not top_manuais:
            return "Nenhum manual relevante encontrado."
        
        contextos = []
        
        for i, manual in enumerate(top_manuais, 1):
            nome = manual.get('nome', manual.get('arquivo', f'Manual {i}'))
            conteudo = manual.get('conteudo', manual.get('texto', ''))
            relevancia = manual.get('relevancia', 0.0)
            
            # Limita conteúdo
            if len(conteudo) > 4000:
                conteudo = conteudo[:4000] + "\n[...conteúdo truncado...]"
            
            contexto_manual = f"""
### MANUAL {i}: {nome} ###
Relevância: {relevancia:.3f}

{conteudo}

---
"""
            contextos.append(contexto_manual)
        
        contexto_final = '\n'.join(contextos)
        
        return f"""
Você é um especialista técnico em máquinas agrícolas.
Use EXCLUSIVAMENTE o conteúdo dos manuais abaixo para responder à pergunta.

INSTRUÇÕES CRÍTICAS:
- Responda APENAS com informações dos manuais fornecidos
- Cite sempre o manual usado como fonte
- Se a informação não estiver nos manuais, diga claramente
- Seja preciso com especificações técnicas

📘 CONTEXTO DOS MANUAIS:
{contexto_final}
"""
    
    def _fallback_offline(self, pergunta: str) -> str:
        """Fallback quando não há contexto"""
        return f"""
INFORMAÇÃO GERAL SOBRE MÁQUINAS AGRÍCOLAS:

Para consultas específicas sobre manutenção, operação ou especificações técnicas, 
recomendamos consultar o manual específico do seu equipamento.

MARCAS SUPORTADAS:
- Case IH: Linha completa de equipamentos agrícolas
- John Deere: Linha completa de equipamentos agrícolas  
- New Holland: Linha completa de equipamentos agrícolas 
- Valtra: Linha completa de equipamentos agrícolas 
- FENDT: Linha completa de equipamentos agrícolas 

Total de manuais disponíveis: {self.manuais_carregados}
"""

# Instância global
manual_processor = ManualProcessor()
