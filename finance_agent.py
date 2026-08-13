"""
Agente Financeiro Perinity — lê o Gmail e:

  1. Notas fiscais de colaboradores PJ (para: nfefopag@perinity.com)
     -> organiza em pastas por mês e registra na planilha de controle.
  2. Notas/boletos de fornecedores (para: financeiro@perinity.com)
     -> organiza em pastas por mês e registra na mesma planilha.
  3. Demais e-mails que pareçam exigir uma ação do Lucas
     -> resumo enviado por Telegram.

Uso:
    python finance_agent.py                  # roda as 3 rotinas
    python finance_agent.py --dry-run         # simula, não grava nada
    python finance_agent.py --only pj         # roda só uma rotina (pj/fornecedores/diversos)
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import gmail_client
from finance_extractor import (
    build_fornecedor_filename,
    build_pj_filename,
    extract_email_received_date,
    extract_emission_date,
    extract_invoice_number,
    extract_sender_name,
    is_boleto_filename,
    month_folder_name,
)
from spreadsheet import (
    CATEGORIA_FORNECEDOR,
    CATEGORIA_PJ,
    already_logged,
    append_row,
    load_or_create,
    save,
)

LABEL_PJ_PROCESSADA = "Guardiao/NF-PJ-Processada"
LABEL_FORNECEDOR_PROCESSADA = "Guardiao/NF-Fornecedor-Processada"
LABEL_DIVERSOS_REVISADO = "Guardiao/Revisado"


def _load_env():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()


def _check_env(dry_run: bool):
    required = ["ANTHROPIC_API_KEY", "PJ_INBOX_ADDRESS", "FORNECEDOR_INBOX_ADDRESS",
                "PJ_NOTAS_BASE_PATH", "FORNECEDOR_NOTAS_BASE_PATH", "CONTROL_SHEET_PATH"]
    if not dry_run:
        required += ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[ERRO] Variáveis de ambiente faltando: {', '.join(missing)}")
        print("       Copie .env.example para .env e preencha os valores.")
        sys.exit(1)


def _max_results() -> int:
    return int(os.environ.get("GMAIL_MAX_RESULTS", "50"))


# ── Regra 1: colaboradores PJ ────────────────────────────────────────────────

def process_pj_inbox(service, dry_run: bool) -> int:
    address = os.environ["PJ_INBOX_ADDRESS"]
    base_path = os.environ["PJ_NOTAS_BASE_PATH"]
    sheet_path = os.environ["CONTROL_SHEET_PATH"]

    query = f'to:{address} -label:"{LABEL_PJ_PROCESSADA}"'
    messages = gmail_client.list_messages(service, query, _max_results())
    print(f"  → {len(messages)} e-mail(s) novo(s) em {address}")

    processed = 0
    for stub in messages:
        message = gmail_client.get_message(service, stub["id"])
        info = gmail_client.message_summary(message)
        attachments = gmail_client.list_attachments(message)

        received = extract_email_received_date(info["date"])
        month_folder = month_folder_name(received)
        colaborador = extract_sender_name(info["from"])
        folder = Path(base_path) / month_folder

        wb = load_or_create(sheet_path)
        if already_logged(wb, info["id"]):
            gmail_client.mark_processed(service, info["id"], LABEL_PJ_PROCESSADA)
            continue

        body = gmail_client.get_body_text(message)

        if not attachments:
            print(f"  [AVISO] Sem anexo: '{info['subject']}' de {colaborador} — marcado para verificação")
            append_row(
                wb, categoria=CATEGORIA_PJ, mes_pasta=month_folder, nome=colaborador,
                numero_nota="VERIFICAR",
                observacoes="E-mail sem anexo — verificar manualmente",
                assunto=info["subject"], gmail_message_id=info["id"],
            )
        else:
            for attachment in attachments:
                numero = extract_invoice_number(info["subject"], body, attachment["filename"])
                ext = Path(attachment["filename"]).suffix or ".pdf"
                filename = build_pj_filename(colaborador, numero, ext)
                obs = "" if numero != "VERIFICAR" else "Não foi possível identificar o número da nota"

                print(f"  → PJ: {colaborador} | {month_folder} | {filename}")
                if not dry_run:
                    folder.mkdir(parents=True, exist_ok=True)
                    data = gmail_client.download_attachment(service, info["id"], attachment["attachment_id"])
                    (folder / filename).write_bytes(data)

                append_row(
                    wb, categoria=CATEGORIA_PJ, mes_pasta=month_folder, nome=colaborador,
                    numero_nota=numero, mes_emissao=month_folder, arquivo_nf=filename,
                    observacoes=obs, assunto=info["subject"], gmail_message_id=info["id"],
                )

        if not dry_run:
            save(wb, sheet_path)
            gmail_client.mark_processed(service, info["id"], LABEL_PJ_PROCESSADA)
        processed += 1

    return processed


# ── Regra 2: fornecedores (não colaboradores) ────────────────────────────────

def process_fornecedor_inbox(service, dry_run: bool) -> int:
    address = os.environ["FORNECEDOR_INBOX_ADDRESS"]
    base_path = os.environ["FORNECEDOR_NOTAS_BASE_PATH"]
    sheet_path = os.environ["CONTROL_SHEET_PATH"]

    query = f'to:{address} -label:"{LABEL_FORNECEDOR_PROCESSADA}"'
    messages = gmail_client.list_messages(service, query, _max_results())
    print(f"  → {len(messages)} e-mail(s) novo(s) em {address}")

    processed = 0
    for stub in messages:
        message = gmail_client.get_message(service, stub["id"])
        info = gmail_client.message_summary(message)
        attachments = gmail_client.list_attachments(message)

        received = extract_email_received_date(info["date"])
        fornecedor = extract_sender_name(info["from"])
        body = gmail_client.get_body_text(message)
        emissao = extract_emission_date(info["subject"], body, fallback=received)
        month_folder = month_folder_name(received)
        mes_emissao = month_folder_name(emissao)
        folder = Path(base_path) / month_folder

        wb = load_or_create(sheet_path)
        if already_logged(wb, info["id"]):
            gmail_client.mark_processed(service, info["id"], LABEL_FORNECEDOR_PROCESSADA)
            continue

        if not attachments:
            print(f"  [AVISO] Sem anexo: '{info['subject']}' de {fornecedor} — marcado para verificação")
            append_row(
                wb, categoria=CATEGORIA_FORNECEDOR, mes_pasta=month_folder, nome=fornecedor,
                numero_nota="VERIFICAR",
                observacoes="E-mail sem anexo — verificar manualmente",
                assunto=info["subject"], gmail_message_id=info["id"],
            )
        else:
            numero = extract_invoice_number(
                info["subject"], body, *[a["filename"] for a in attachments]
            )
            nf_filename = ""
            boleto_filename = ""

            for attachment in attachments:
                ext = Path(attachment["filename"]).suffix or ".pdf"
                is_boleto = is_boleto_filename(attachment["filename"])
                filename = build_fornecedor_filename(fornecedor, numero, mes_emissao, ext, is_boleto)

                print(f"  → Fornecedor: {fornecedor} | {month_folder} | {filename}")
                if not dry_run:
                    folder.mkdir(parents=True, exist_ok=True)
                    data = gmail_client.download_attachment(service, info["id"], attachment["attachment_id"])
                    (folder / filename).write_bytes(data)

                if is_boleto:
                    boleto_filename = filename
                else:
                    nf_filename = filename

            obs = "" if numero != "VERIFICAR" else "Não foi possível identificar o número da nota"
            append_row(
                wb, categoria=CATEGORIA_FORNECEDOR, mes_pasta=month_folder, nome=fornecedor,
                numero_nota=numero, mes_emissao=mes_emissao, arquivo_nf=nf_filename,
                arquivo_boleto=boleto_filename, observacoes=obs,
                assunto=info["subject"], gmail_message_id=info["id"],
            )

        if not dry_run:
            save(wb, sheet_path)
            gmail_client.mark_processed(service, info["id"], LABEL_FORNECEDOR_PROCESSADA)
        processed += 1

    return processed


# ── Regra 3: assuntos diversos que exigem ação ───────────────────────────────

def process_diversos(service, dry_run: bool) -> tuple[int, int]:
    from email_classifier import classify_email
    from notifier import send_message

    pj_address = os.environ["PJ_INBOX_ADDRESS"]
    fornecedor_address = os.environ["FORNECEDOR_INBOX_ADDRESS"]

    query = (
        f'in:inbox -to:{pj_address} -to:{fornecedor_address} '
        f'-label:"{LABEL_DIVERSOS_REVISADO}"'
    )
    messages = gmail_client.list_messages(service, query, _max_results())
    print(f"  → {len(messages)} e-mail(s) novo(s) para triagem")

    scanned = 0
    notified = 0
    for stub in messages:
        message = gmail_client.get_message(service, stub["id"])
        info = gmail_client.message_summary(message)
        body = gmail_client.get_body_text(message)

        result = classify_email(info["subject"], info["from"], info["to"], body)
        scanned += 1

        if result["precisa_acao"]:
            print(f"  → AÇÃO NECESSÁRIA: {info['subject']}")
            texto = (
                f"📩 *Novo e-mail que pode precisar da sua atenção*\n\n"
                f"*De:* {info['from']}\n"
                f"*Assunto:* {info['subject']}\n\n"
                f"{result['resumo']}"
            )
            if not dry_run:
                send_message(texto)
                # Mantém como não lido: é um lembrete visual até você tratar.
                gmail_client.mark_processed(service, info["id"], LABEL_DIVERSOS_REVISADO, mark_as_read=False)
            notified += 1
        else:
            print(f"  → sem ação: {info['subject']}")
            if not dry_run:
                gmail_client.mark_processed(service, info["id"], LABEL_DIVERSOS_REVISADO, mark_as_read=True)

    return scanned, notified


# ── Main ──────────────────────────────────────────────────────────────────

def run(dry_run: bool, only: str):
    service = gmail_client.get_service()
    stamp = datetime.now()
    print(f"\n{'='*50}")
    print(f" AGENTE FINANCEIRO PERINITY  {stamp.strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*50}")

    if only in ("all", "pj"):
        print("\n[1/3] Notas fiscais de colaboradores PJ...")
        process_pj_inbox(service, dry_run)

    if only in ("all", "fornecedores"):
        print("\n[2/3] Notas e boletos de fornecedores...")
        process_fornecedor_inbox(service, dry_run)

    if only in ("all", "diversos"):
        print("\n[3/3] Triagem de assuntos diversos...")
        process_diversos(service, dry_run)

    if dry_run:
        print("\n[DRY RUN] Nenhum arquivo, planilha, label ou mensagem foi alterado.")
    print("\n✅ Concluído.\n")


def main():
    parser = argparse.ArgumentParser(description="Agente Financeiro Perinity (Gmail)")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem gravar nada")
    parser.add_argument(
        "--only", choices=["all", "pj", "fornecedores", "diversos"], default="all",
        help="Roda apenas uma das três rotinas",
    )
    args = parser.parse_args()

    _load_env()
    _check_env(dry_run=args.dry_run)
    run(dry_run=args.dry_run, only=args.only)


if __name__ == "__main__":
    main()
