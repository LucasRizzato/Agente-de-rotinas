"""
Guardião Bot — Telegram interactive interface.

Commands:
    /start      Welcome + saves your chat ID
    /resumo     Full AI analysis of the vault (same as daily report)
    /tarefas    List all pending tasks
    /add <text> Add a task to the Obsidian inbox
    /ajuda      Show this help

Run with:
    python bot.py
"""
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _vault_path() -> str:
    return os.environ.get("OBSIDIAN_VAULT_PATH", r"C:\Guardião")


def _inbox_file() -> Path:
    return Path(_vault_path()) / "📥 Inbox.md"


def _ensure_inbox() -> Path:
    inbox = _inbox_file()
    if not inbox.exists():
        inbox.write_text(
            "# 📥 Inbox\n\nTarefas adicionadas pelo Guardião Bot:\n\n",
            encoding="utf-8",
        )
    return inbox


# ── Command handlers ────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"👋 *Bem-vindo ao Guardião!*\n\n"
        f"Seu Chat ID é: `{chat_id}`\n"
        f"Adicione este valor como `TELEGRAM_CHAT_ID` no seu `.env`.\n\n"
        f"Use /ajuda para ver os comandos disponíveis.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *Guardião — Comandos*\n\n"
        "/resumo — Análise completa do vault agora\n"
        "/tarefas — Listar tarefas pendentes\n"
        "/add _texto_ — Adicionar tarefa ao Inbox\n"
        "/ajuda — Esta mensagem",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Analisando vault, aguarde...")
    try:
        from vault_reader import read_vault
        from analyzer import analyze_vault

        vault_data = read_vault(_vault_path())
        analysis = analyze_vault(vault_data)

        header = (
            f"🧠 *Guardião — Análise*\n"
            f"_{datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n"
        )
        full = header + analysis

        # Send in chunks if needed
        chunk_size = 4000
        chunks = [full[i : i + chunk_size] for i in range(0, len(full), chunk_size)]
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        log.exception("Erro no /resumo")
        await update.message.reply_text(f"❌ Erro: {e}")


async def cmd_tarefas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from vault_reader import read_vault

        vault_data = read_vault(_vault_path())
        tasks = vault_data["all_tasks"]

        if not tasks:
            await update.message.reply_text("✅ Nenhuma tarefa pendente encontrada!")
            return

        lines = [f"📋 *Tarefas pendentes ({len(tasks)})*\n"]
        for t in tasks[:20]:
            due = f" — 📅 {t['due_date'][:10]}" if t.get("due_date") else ""
            file_short = Path(t["file"]).stem
            lines.append(f"• {t['task']}{due}\n  _({file_short})_")

        if len(tasks) > 20:
            lines.append(f"\n_...e mais {len(tasks) - 20} tarefas_")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        log.exception("Erro no /tarefas")
        await update.message.reply_text(f"❌ Erro: {e}")


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        await update.message.reply_text(
            "⚠️ Use: /add _descrição da tarefa_\nExemplo: /add Revisar proposta até sexta",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        # Look for date hints like "até 05/06" or "dia 10" and convert to Obsidian format
        due_tag = ""
        date_match = re.search(r"(?:até|dia|em)\s+(\d{1,2})[/\-](\d{1,2})", text, re.I)
        if date_match:
            day, month = date_match.group(1), date_match.group(2)
            year = datetime.now().year
            due_tag = f" 📅 {year}-{int(month):02d}-{int(day):02d}"

        inbox = _ensure_inbox()
        task_line = f"- [ ] {text}{due_tag}\n"

        with inbox.open("a", encoding="utf-8") as f:
            f.write(task_line)

        confirmation = f"✅ Tarefa adicionada em *{inbox.name}*:\n`{task_line.strip()}`"
        await update.message.reply_text(confirmation, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        log.exception("Erro no /add")
        await update.message.reply_text(f"❌ Erro ao salvar: {e}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    load_dotenv(Path(__file__).parent / ".env")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("[ERRO] TELEGRAM_BOT_TOKEN não definido no .env")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    app.add_handler(CommandHandler("help", cmd_ajuda))
    app.add_handler(CommandHandler("resumo", cmd_resumo))
    app.add_handler(CommandHandler("tarefas", cmd_tarefas))
    app.add_handler(CommandHandler("add", cmd_add))

    log.info("Guardião Bot iniciado. Aguardando comandos...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
