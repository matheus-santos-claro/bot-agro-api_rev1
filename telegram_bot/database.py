# telegram_bot/database.py
import sqlite3
import asyncio
import aiosqlite
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from .config import DATABASE_PATH, BACKUP_INTERVAL_HOURS

logger = logging.getLogger(__name__)

class TelegramDatabase:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.backup_running = False
        
    async def initialize(self):
        """Inicializa banco e configura backup automático"""
        logger.info(f"🗄️ Inicializando banco SQLite: {self.db_path}")
        
        await self._create_tables()
        await self._migrate_if_needed()
        
        # Agenda backup automático
        asyncio.create_task(self._schedule_backups())
        
        logger.info("✅ Banco SQLite inicializado com sucesso")
    
    async def _create_tables(self):
        """Cria tabelas se não existirem"""
        async with aiosqlite.connect(self.db_path) as db:
            # Tabela de usuários
            await db.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    language_code TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_perguntas INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # Tabela de interações
            await db.execute("""
                CREATE TABLE IF NOT EXISTS interacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    pergunta TEXT NOT NULL,
                    pergunta_length INTEGER,
                    resposta_categoria TEXT,
                    resposta_confianca REAL,
                    tokens_usados INTEGER,
                    tempo_processamento REAL,
                    referencias_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_only DATE DEFAULT (date('now')),
                    FOREIGN KEY (user_id) REFERENCES usuarios (id)
                )
            """)
            
            # Tabela de estatísticas diárias
            await db.execute("""
                CREATE TABLE IF NOT EXISTS estatisticas_diarias (
                    data DATE PRIMARY KEY,
                    total_perguntas INTEGER DEFAULT 0,
                    usuarios_unicos INTEGER DEFAULT 0,
                    categoria_top TEXT,
                    confianca_media REAL,
                    tempo_medio REAL,
                    tokens_total INTEGER DEFAULT 0
                )
            """)
            
            # Índices para performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_interacoes_user ON interacoes(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_interacoes_date ON interacoes(date_only)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_active ON usuarios(is_active, last_interaction)")
            
            await db.commit()
    
    async def _migrate_if_needed(self):
        """Migra banco se necessário"""
        # Adiciona colunas que podem não existir em versões antigas
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("ALTER TABLE usuarios ADD COLUMN is_active BOOLEAN DEFAULT 1")
                await db.commit()
            except sqlite3.OperationalError:
                pass  # Coluna já existe
            
            try:
                await db.execute("ALTER TABLE interacoes ADD COLUMN pergunta_length INTEGER")
                await db.execute("ALTER TABLE interacoes ADD COLUMN date_only DATE DEFAULT (date('now'))")
                await db.commit()
            except sqlite3.OperationalError:
                pass  # Colunas já existem
    
    async def registrar_usuario(self, user_data: Dict):
        """Registra ou atualiza usuário"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO usuarios 
                (id, username, first_name, last_name, language_code, last_interaction, total_perguntas, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 
                    COALESCE((SELECT total_perguntas FROM usuarios WHERE id = ?), 0) + 1, 1)
            """, (
                user_data["id"],
                user_data.get("username"),
                user_data.get("first_name"),
                user_data.get("last_name"),
                user_data.get("language_code"),
                datetime.now(),
                user_data["id"]
            ))
            await db.commit()
            
            logger.info(f"👤 Usuário registrado: {user_data.get('first_name')} (@{user_data.get('username')})")
    
    async def registrar_interacao(self, user_id: int, pergunta: str, resposta: Dict):
        """Registra interação completa"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO interacoes 
                (user_id, pergunta, pergunta_length, resposta_categoria, resposta_confianca, 
                 tokens_usados, tempo_processamento, referencias_count, date_only)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now'))
            """, (
                user_id,
                pergunta,
                len(pergunta),
                resposta.get("categoria"),
                resposta.get("confianca"),
                resposta.get("tokens_usados"),
                resposta.get("tempo_processamento"),
                len(resposta.get("referencias", []))
            ))
            await db.commit()
            
            logger.info(f"💬 Interação registrada: user_id={user_id}, categoria={resposta.get('categoria')}")
    
    async def get_estatisticas_usuario(self, user_id: int) -> Dict:
        """Estatísticas de um usuário específico"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT 
                    u.total_perguntas,
                    u.created_at,
                    COUNT(i.id) as interacoes_registradas,
                    AVG(i.resposta_confianca) as confianca_media,
                    SUM(i.tokens_usados) as tokens_total,
                    u.last_interaction
                FROM usuarios u
                LEFT JOIN interacoes i ON u.id = i.user_id
                WHERE u.id = ?
                GROUP BY u.id
            """, (user_id,))
            
            row = await cursor.fetchone()
            if row:
                return {
                    "total_perguntas": row[0] or 0,
                    "membro_desde": row[1],
                    "interacoes_registradas": row[2] or 0,
                    "confianca_media": row[3] or 0,
                    "tokens_total": row[4] or 0,
                    "ultima_interacao": row[5]
                }
            return {}
    
    async def get_estatisticas_gerais(self) -> Dict:
        """Estatísticas gerais do bot"""
        async with aiosqlite.connect(self.db_path) as db:
            # Total de usuários
            cursor = await db.execute("SELECT COUNT(*) FROM usuarios WHERE is_active = 1")
            total_usuarios = (await cursor.fetchone())[0]
            
            # Total de interações
            cursor = await db.execute("SELECT COUNT(*) FROM interacoes")
            total_interacoes = (await cursor.fetchone())[0]
            
            # Categoria mais perguntada
            cursor = await db.execute("""
                SELECT resposta_categoria, COUNT(*) as count 
                FROM interacoes 
                WHERE resposta_categoria IS NOT NULL
                GROUP BY resposta_categoria 
                ORDER BY count DESC 
                LIMIT 1
            """)
            categoria_top = await cursor.fetchone()
            
            # Usuários ativos (últimos 7 dias)
            cursor = await db.execute("""
                SELECT COUNT(*) FROM usuarios 
                WHERE last_interaction > datetime('now', '-7 days') AND is_active = 1
            """)
            usuarios_ativos = (await cursor.fetchone())[0]
            
            # Estatísticas de hoje
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as perguntas_hoje,
                    COUNT(DISTINCT user_id) as usuarios_hoje,
                    AVG(resposta_confianca) as confianca_hoje
                FROM interacoes 
                WHERE date_only = date('now')
            """)
            stats_hoje = await cursor.fetchone()
            
            return {
                "total_usuarios": total_usuarios,
                "total_interacoes": total_interacoes,
                "categoria_mais_perguntada": categoria_top[0] if categoria_top else "N/A",
                "usuarios_ativos_7d": usuarios_ativos,
                "perguntas_hoje": stats_hoje[0] if stats_hoje else 0,
                "usuarios_hoje": stats_hoje[1] if stats_hoje else 0,
                "confianca_media_hoje": stats_hoje[2] if stats_hoje else 0
            }
    
    async def get_top_usuarios(self, limit: int = 10) -> List[Dict]:
        """Top usuários por número de perguntas"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT 
                    id, username, first_name, total_perguntas, last_interaction
                FROM usuarios 
                WHERE is_active = 1
                ORDER BY total_perguntas DESC 
                LIMIT ?
            """, (limit,))
            
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "username": row[1],
                    "first_name": row[2],
                    "total_perguntas": row[3],
                    "last_interaction": row[4]
                }
                for row in rows
            ]
    
    async def export_to_json(self) -> Dict:
        """Exporta banco completo para JSON"""
        logger.info("📤 Iniciando export do banco para JSON...")
        
        data = {
            "backup_date": datetime.now().isoformat(),
            "version": "1.0",
            "usuarios": [],
            "interacoes": [],
            "estatisticas": {}
        }
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Exporta usuários
                async with db.execute("SELECT * FROM usuarios") as cursor:
                    columns = [description[0] for description in cursor.description]
                    async for row in cursor:
                        data["usuarios"].append(dict(zip(columns, row)))
                
                # Exporta interações
                async with db.execute("SELECT * FROM interacoes ORDER BY created_at DESC LIMIT 1000") as cursor:
                    columns = [description[0] for description in cursor.description]
                    async for row in cursor:
                        data["interacoes"].append(dict(zip(columns, row)))
                
                # Adiciona estatísticas gerais
                data["estatisticas"] = await self.get_estatisticas_gerais()
        
        except Exception as e:
            logger.error(f"❌ Erro no export: {str(e)}")
            raise
        
        logger.info(f"✅ Export concluído: {len(data['usuarios'])} usuários, {len(data['interacoes'])} interações")
        return data
    
    async def _schedule_backups(self):
        """Backup automático programado"""
        if self.backup_running:
            return
        
        self.backup_running = True
        logger.info(f"🔄 Backup automático iniciado (intervalo: {BACKUP_INTERVAL_HOURS}h)")
        
        while True:
            try:
                await asyncio.sleep(BACKUP_INTERVAL_HOURS * 3600)  # Converte horas para segundos
                
                data = await self.export_to_json()
                logger.info(f"🔄 Backup automático realizado: {len(data['usuarios'])} usuários")
                
            except Exception as e:
                logger.error(f"❌ Erro no backup automático: {str(e)}")
                await asyncio.sleep(300)  # Aguarda 5 min antes de tentar novamente

# Instância global
telegram_db = TelegramDatabase()
