"""
Guardião — Obsidian AI Agent
Reads the vault, generates insights with Claude, and sends them via WhatsApp.

Usage:
    python agent.py                  # Run once
    python agent.py --dry-run        # Print analysis, don't send WhatsApp
    python agent.py --vault C:/path  # Override vault path
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


def _load_env():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()


def _check_env(dry_run: bool):
    required = ["ANTHROPIC_API_KEY"]
    if not dry_run:
        required += ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
                     "TWILIO_WHATSAPP_NUMBER", "MY_WHATSAPP_NUMBER"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[ERRO] Variáveis de ambiente faltando: {', '.join(missing)}")
        print("       Copie .env.example para .env e preencha os valores.")
        sys.exit(1)


def run(vault_path: str, dry_run: bool = False):
    from vault_reader import read_vault
    from analyzer import analyze_vault
    from notifier import send_whatsapp

    stamp = datetime.now()
    print(f"\n{'='*50}")
    print(f" GUARDIÃO  {stamp.strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*50}")

    print(f"\n[1/3] Lendo vault: {vault_path}")
    vault_data = read_vault(vault_path)
    print(
        f"  → {vault_data['total_notes']} notas | "
        f"{len(vault_data['recent_notes'])} recentes | "
        f"{len(vault_data['all_tasks'])} tarefas pendentes"
    )

    print("\n[2/3] Analisando com IA...")
    analysis = analyze_vault(vault_data)

    header = (
        f"🧠 *Guardião — Análise Diária*\n"
        f"_{stamp.strftime('%d/%m/%Y às %H:%M')}_\n\n"
    )
    full_message = header + analysis

    print("\n--- ANÁLISE ---")
    print(full_message)
    print("---------------")

    if dry_run:
        print("\n[DRY RUN] WhatsApp não enviado.")
    else:
        print("\n[3/3] Enviando WhatsApp...")
        sids = send_whatsapp(full_message)
        print(f"  → {len(sids)} mensagem(ns) enviada(s)")

    print("\n✅ Concluído.\n")


def main():
    parser = argparse.ArgumentParser(description="Guardião — Obsidian AI Agent")
    parser.add_argument(
        "--vault",
        default=None,
        help="Caminho para o vault Obsidian (padrão: OBSIDIAN_VAULT_PATH do .env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Imprime a análise sem enviar WhatsApp",
    )
    args = parser.parse_args()

    _load_env()
    _check_env(dry_run=args.dry_run)

    vault_path = args.vault or os.environ.get("OBSIDIAN_VAULT_PATH", r"C:\Guardião")
    run(vault_path=vault_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
