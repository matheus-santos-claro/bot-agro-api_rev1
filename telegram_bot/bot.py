# telegram_bot/bot.py
import asyncio
import logging
import json
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import httpx

from .config import TELEGRAM_BOT_TOKEN, API_BASE_URL, ADMIN_IDS
from .database import telegram_db
from .backup_service import BackupService

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AgroTelegramBot:
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN não configurado")
        
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.api_client = httpx.AsyncClient(timeout=30.0)
        self.database = telegram_db
        self.backup_service = BackupService(self.database)
        
        self.setup_handlers()
        
        logger.info("🤖 Bot Telegram inicializado")
    
    def setup_handlers(self):
        """Configura handlers do bot"""
        # Comandos básicos
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        
        # Comandos de admin
        self.app.add_handler(CommandHandler("admin", self.admin_command))
        self.app.add_handler(CommandHandler("backup", self.backup_command))
        self.app.add_handler(CommandHandler("users", self.users_command))
        
        # Handler de mensagens
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_question))
        
        logger.info("✅ Handlers configurados")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        user_data = self._extract_user_data(update)
        await self.database.registrar_usuario(user_data)
        
        welcome_text = f"""
🌾 **Bot Agrícola Expert**

Olá {user_data.get('first_name', 'Usuário')}! 

Sou seu assistente especializado em máquinas agrícolas.

**🚜 Marcas suportadas:**
• Case IH • John Deere • New Holland
• Valtra • FENDT • Massey Ferguson

**📝 Como usar:**
Envie sua pergunta sobre:
• Especificações técnicas
• Configurações

**💡 Exemplo:**
"Qual a potência do motor da Case IH 4150?"

**🔧 Comandos disponíveis:**
/help - Ajuda detalhada
/stats - Suas estatísticas
/status - Status da API

Vamos começar! Envie sua primeira pergunta! 🚀
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        help_text = """
🔧 **Como usar o Bot Agrícola:**

**📋 Tipos de pergunta:**
• Especificações de motores e potência
• Configurações
• Características Gerais de Colheitadeiras, Tratores, Pulverizadores e Plantadeiras

**💡 Dicas importantes:**
• Seja específico com marca e modelo
• Uma marca por pergunta para melhor precisão
• Aguarde alguns segundos para a resposta
• Use termos técnicos quando possível

**🤖 Comandos disponíveis:**
/start - Iniciar/reiniciar bot
/help - Esta ajuda
/stats - Suas estatísticas pessoais
/status - Verificar status da API

**📝 Exemplos de perguntas:**
• "Motor da colheitadeira Case IH 4150"
• "Capacidade do Tanque de Grãos da Série S John Deere"
• "Quais Modelos disponíveis na Série TX das Colheitadeiras John Deere"
• "Qual modelo de transmissão do Trator MF 4707 da Massey Ferguson"

**🆘 Suporte:**
Se encontrar problemas, entre em contato com nossa equipe.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /status"""
        try:
            # Testa API
            response = await self.api_client.get(f"{API_BASE_URL}/health", timeout=10.0)
            
            if response.status_code == 200:
                api_status = "✅ Online"
                api_data = response.json()
            else:
                api_status = f"⚠️ Problema (Status: {response.status_code})"
                api_data = {}
            
            # Estatísticas do banco
            stats = await self.database.get_estatisticas_gerais()
            
            status_text = f"""
🔍 **Status do Sistema:**

**🌐 API Principal:** {api_status}
**📊 Base de Dados:** ✅ Funcionando

**📈 Estatísticas Gerais:**
• Total de usuários: {stats.get('total_usuarios', 0)}
• Interações registradas: {stats.get('total_interacoes', 0)}
• Usuários ativos (7d): {stats.get('usuarios_ativos_7d', 0)}
• Perguntas hoje: {stats.get('perguntas_hoje', 0)}

**🏆 Categoria mais perguntada:** {stats.get('categoria_mais_perguntada', 'N/A')}

**⏰ Última verificação:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            """
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Erro ao verificar status: {str(e)}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stats - Estatísticas do usuário"""
        user_id = update.effective_user.id
        
        try:
            stats = await self.database.get_estatisticas_usuario(user_id)
            
            if not stats:
                await update.message.reply_text("❌ Nenhuma estatística encontrada. Use /start para se registrar.")
                return
            
            # Formata datas
            membro_desde = stats.get('membro_desde', '')
            if membro_desde:
                try:
                    dt = datetime.fromisoformat(membro_desde.replace('Z', '+00:00'))
                    membro_desde_fmt = dt.strftime('%d/%m/%Y')
                except:
                    membro_desde_fmt = membro_desde[:10]
            else:
                membro_desde_fmt = 'N/A'
            
            ultima_interacao = stats.get('ultima_interacao', '')
            if ultima_interacao:
                try:
                    dt = datetime.fromisoformat(ultima_interacao.replace('Z', '+00:00'))
                    ultima_interacao_fmt = dt.strftime('%d/%m/%Y %H:%M')
                except:
                    ultima_interacao_fmt = ultima_interacao[:16]
            else:
                ultima_interacao_fmt = 'N/A'
            
            confianca_media = stats.get('confianca_media', 0)
            confianca_pct = f"{confianca_media:.1%}" if confianca_media else "N/A"
            
            stats_text = f"""
📊 **Suas Estatísticas:**

**👤 Perfil:**
• Membro desde: {membro_desde_fmt}
• Última interação: {ultima_interacao_fmt}

**📈 Atividade:**
• Total de perguntas: {stats.get('total_perguntas', 0)}
• Interações registradas: {stats.get('interacoes_registradas', 0)}

**🎯 Qualidade:**
• Confiança média das respostas: {confianca_pct}
• Tokens utilizados: {stats.get('tokens_total', 0):,}

**💡 Dica:** Continue fazendo perguntas para melhorar suas estatísticas!
            """
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas: {str(e)}")
            await update.message.reply_text("❌ Erro ao buscar suas estatísticas. Tente novamente.")
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /admin - Estatísticas gerais (apenas admins)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Comando disponível apenas para administradores")
            return
        
        try:
            stats = await self.database.get_estatisticas_gerais()
            top_users = await self.database.get_top_usuarios(5)
            
            # Formata top usuários
            top_users_text = ""
            for i, user in enumerate(top_users, 1):
                nome = user.get('first_name', 'N/A')
                username = user.get('username', '')
                username_fmt = f"@{username}" if username else ""
                perguntas = user.get('total_perguntas', 0)
                top_users_text += f"{i}. {nome} {username_fmt} - {perguntas} perguntas\n"
            
            admin_text = f"""
🔧 **Painel Administrativo:**

**📊 Estatísticas Gerais:**
• Total de usuários: {stats.get('total_usuarios', 0)}
• Total de interações: {stats.get('total_interacoes', 0)}
• Usuários ativos (7d): {stats.get('usuarios_ativos_7d', 0)}

**📅 Hoje:**
• Perguntas: {stats.get('perguntas_hoje', 0)}
• Usuários únicos: {stats.get('usuarios_hoje', 0)}
• Confiança média: {stats.get('confianca_media_hoje', 0):.1%}

**🏆 Top 5 Usuários:**
{top_users_text}

**🎯 Categoria mais perguntada:** {stats.get('categoria_mais_perguntada', 'N/A')}

**🔧 Comandos de admin:**
/backup - Gerar backup do banco
/users - Listar usuários ativos
            """
            
            await update.message.reply_text(admin_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Erro ao buscar estatísticas administrativas: {str(e)}")
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /backup - Gerar backup (apenas admin)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Comando disponível apenas para administradores")
            return
        
        try:
            await update.message.reply_text("🔄 Gerando backup do banco de dados...")
            
            # Cria arquivo de backup
            backup_file = await self.backup_service.create_backup_file()
            
            # Exporta dados para estatísticas
            data = await self.database.export_to_json()
            stats_text = self.backup_service.format_backup_stats(data)
            
            # Envia arquivo
            backup_file.seek(0)  # Volta para o início do arquivo
            await update.message.reply_document(
                document=backup_file,
                caption=stats_text,
                parse_mode='Markdown'
            )
            
            logger.info(f"📤 Backup enviado para admin {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Erro ao gerar backup: {str(e)}")
            await update.message.reply_text(f"❌ Erro ao gerar backup: {str(e)}")
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /users - Listar usuários (apenas admin)"""
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Comando disponível apenas para administradores")
            return
        
        try:
            top_users = await self.database.get_top_usuarios(10)
            
            if not top_users:
                await update.message.reply_text("📭 Nenhum usuário encontrado")
                return
            
            users_text = "👥 **Top 10 Usuários Ativos:**\n\n"
            
            for i, user in enumerate(top_users, 1):
                nome = user.get('first_name', 'N/A')
                username = user.get('username', '')
                username_fmt = f"@{username}" if username else ""
                perguntas = user.get('total_perguntas', 0)
                
                # Formata última interação
                ultima = user.get('last_interaction', '')
                if ultima:
                    try:
                        dt = datetime.fromisoformat(ultima.replace('Z', '+00:00'))
                        ultima_fmt = dt.strftime('%d/%m %H:%M')
                    except:
                        ultima_fmt = ultima[:10]
                else:
                    ultima_fmt = 'N/A'
                
                users_text += f"{i}. **{nome}** {username_fmt}\n"
                users_text += f"   📊 {perguntas} perguntas | 🕒 {ultima_fmt}\n\n"
            
            await update.message.reply_text(users_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Erro ao listar usuários: {str(e)}")
    
    async def handle_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processa perguntas dos usuários"""
        user_data = self._extract_user_data(update)
        pergunta = update.message.text
        
        logger.info(f"❓ Pergunta de {user_data.get('first_name')} (@{user_data.get('username')}): {pergunta[:50]}...")
        
        # Registra usuário
        await self.database.registrar_usuario(user_data)
        
        # Envia "digitando..."
        await update.message.reply_chat_action("typing")
        
        try:
            # Chama API
            resposta_api = await self.call_api(pergunta)
            
            if resposta_api:
                # Registra interação no banco
                await self.database.registrar_interacao(user_data["id"], pergunta, resposta_api)
                
                # Formata e envia resposta
                formatted_response = self.format_response(resposta_api)
                await update.message.reply_text(formatted_response, parse_mode='Markdown')
                
                logger.info(f"✅ Resposta enviada para {user_data.get('first_name')}")
            else:
                await update.message.reply_text(
                    "❌ Não consegui processar sua pergunta no momento. "
                    "Verifique se a API está funcionando com /status e tente novamente."
                )
                
        except Exception as e:
            logger.error(f"Erro ao processar pergunta: {str(e)}")
            await update.message.reply_text(
                "⚠️ Ocorreu um erro interno. Nossa equipe foi notificada. "
                "Tente novamente em alguns segundos."
            )
    
    async def call_api(self, pergunta: str) -> dict:
        """Chama API de manuais"""
        try:
            response = await self.api_client.post(
                f"{API_BASE_URL}/pergunta",
                json={"pergunta": pergunta},
                timeout=25.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API retornou status {response.status_code}: {response.text}")
                return None
                
        except asyncio.TimeoutError:
            logger.error("Timeout na chamada da API")
            return None
        except Exception as e:
            logger.error(f"Erro na chamada da API: {str(e)}")
            return None
    
    def format_response(self, api_response: dict) -> str:
        """Formata resposta da API para Telegram"""
        resposta = api_response.get("resposta", "")
        categoria = api_response.get("categoria", "")
        confianca = api_response.get("confianca", 0)
        referencias = api_response.get("referencias", [])
        tempo = api_response.get("tempo_processamento", 0)
        
        # Limita tamanho da resposta (Telegram tem limite de 4096 caracteres)
        if len(resposta) > 3500:
            resposta = resposta[:3500] + "\n\n[...resposta truncada...]"
        
        # Monta resposta formatada
        formatted = f"🤖 **Resposta:**\n\n{resposta}\n\n"
        
        # Adiciona informações técnicas
        formatted += f"📊 **Categoria:** {categoria}\n"
        formatted += f"🎯 **Confiança:** {confianca:.0%}\n"
        formatted += f"⏱️ **Tempo:** {tempo:.1f}s\n"
        
        # Adiciona referências se houver
        if referencias:
            formatted += f"\n📚 **Fontes consultadas:**\n"
            for i, ref in enumerate(referencias[:3], 1):  # Máximo 3 referências
                arquivo = ref.get("arquivo", "").replace(".md", "")
                relevancia = ref.get("relevancia", 0)
                formatted += f"{i}. {arquivo} (relevância: {relevancia:.1%})\n"
        
        return formatted
    
    def _extract_user_data(self, update: Update) -> dict:
        """Extrai dados do usuário do update"""
        user = update.effective_user
        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code
        }
    
    async def initialize(self):
        """Inicializa bot e dependências"""
        logger.info("🚀 Inicializando Bot Agrícola...")
        
        # Inicializa banco de dados
        await self.database.initialize()
        
        logger.info("✅ Bot inicializado com sucesso!")
    
    async def run(self):
        """Executa o bot - VERSÃO CORRIGIDA"""
        try:
            # Inicializa o bot
            await self.initialize()
            
            logger.info("🤖 Bot rodando! Aguardando mensagens...")
            
            # Método correto para python-telegram-bot 20.x
            await self.app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao executar bot: {str(e)}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Limpeza ao finalizar"""
        logger.info("🧹 Finalizando bot...")
        
        try:
            await self.api_client.aclose()
        except Exception as e:
            logger.error(f"Erro na limpeza: {str(e)}")
        
        logger.info("👋 Bot finalizado")

# Instância global
agro_bot = AgroTelegramBot()
