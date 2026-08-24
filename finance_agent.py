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

# Quando a saída não vai para um console de verdade (ex: redirecionada para
# um arquivo de log pelo run_finance.bat, como acontece na tarefa agendada),
# o Windows usa a codificação antiga do sistema (cp1252) em vez de UTF-8, que
# não sabe representar caracteres como "→" usados nas mensagens — e quebra a
# execução inteira com UnicodeEncodeError antes de fazer qualquer trabalho.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

import gmail_client
from finance_extractor import (
    build_fornecedor_filename,
    build_pj_filename,
    extract_email_received_date,
    extract_invoice_number,
    extract_reference_period,
    extract_sender_name,
    extract_valor_liquido,
    is_boleto_filename,
    is_relevant_attachment,
    month_folder_name,
)
from pdf_reader import extract_pdf_text
from spreadsheet import (
    CATEGORIA_FORNECEDOR,
    CATEGORIA_PJ,
    already_logged,
    append_row,
    load_or_create,
    save,
)

LABEL_PJ_PROCESSADA = "Guardiao-NF-PJ-Processada"
LABEL_FORNECEDOR_PROCESSADA = "Guardiao-NF-Fornecedor-Processada"
LABEL_DIVERSOS_REVISADO = "Guardiao-Revisado"


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


def _download_attachments(service, message_id: str, attachments: list[dict]) -> dict:
    """Baixa todos os anexos de uma vez (precisamos do conteúdo do PDF antes
    de decidir em qual pasta de mês ele vai — não só na hora de gravar)."""
    return {
        a["filename"]: gmail_client.download_attachment(service, message_id, a)
        for a in attachments
    }


def _first_pdf_text(attachments: list[dict], attachment_data: dict) -> str:
    for a in attachments:
        if a["filename"].lower().endswith(".pdf"):
            text = extract_pdf_text(attachment_data[a["filename"]])
            if text:
                return text
    return ""


def _unique_path(folder: Path, filename: str) -> Path:
    """Evita sobrescrever silenciosamente quando dois anexos calculam o
    mesmo nome de arquivo (ex: mesmo colaborador, número da nota repetido)."""
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem, ext = Path(filename).stem, Path(filename).suffix
    n = 2
    while True:
        candidate = folder / f"{stem} ({n}){ext}"
        if not candidate.exists():
            return candidate
        n += 1


# ── Regra 1: colaboradores PJ ────────────────────────────────────────────────

def process_pj_inbox(service, dry_run: bool) -> int:
    address = os.environ["PJ_INBOX_ADDRESS"]
    base_path = os.environ["PJ_NOTAS_BASE_PATH"]
    sheet_path = os.environ["CONTROL_SHEET_PATH"]

    query = f'to:{address} -label:"{LABEL_PJ_PROCESSADA}"'
    print(f"  → busca no Gmail: {query}")
    messages = gmail_client.list_messages(service, query, _max_results())
    print(f"  → {len(messages)} e-mail(s) novo(s) em {address}")

    # Carrega a planilha uma única vez para toda a rotina, não a cada
    # e-mail — reabrir e reler um .xlsx que só cresce, 50 vezes por
    # execução, fica cada vez mais lento (e ainda mais estando no OneDrive).
    wb = load_or_create(sheet_path)

    processed = 0
    for stub in messages:
        message = gmail_client.get_message(service, stub["id"])
        info = gmail_client.message_summary(message)
        attachments = [
            a for a in gmail_client.list_attachments(message)
            if is_relevant_attachment(a["filename"])
        ]

        received = extract_email_received_date(info["date"])
        colaborador = extract_sender_name(info["from"])

        if already_logged(wb, info["id"]):
            gmail_client.mark_processed(service, info["id"], LABEL_PJ_PROCESSADA)
            continue

        body = gmail_client.get_body_text(message)

        if not attachments:
            month_folder = month_folder_name(received)
            print(f"  [AVISO] Sem anexo relevante: '{info['subject']}' de {colaborador} — marcado para verificação")
            append_row(
                wb, categoria=CATEGORIA_PJ, mes_pasta=month_folder, nome=colaborador,
                numero_nota="VERIFICAR", data_recebimento=received,
                observacoes="E-mail sem anexo (PDF/XML) — verificar manualmente",
                assunto=info["subject"], gmail_message_id=info["id"],
            )
        else:
            # baixa antes de decidir a pasta: o mês vem de dentro da nota
            attachment_data = _download_attachments(service, info["id"], attachments)
            pdf_text = _first_pdf_text(attachments, attachment_data)

            referencia = extract_reference_period(pdf_text, info["subject"], body, fallback=received)
            month_folder = month_folder_name(referencia)
            folder = Path(base_path) / month_folder

            numero = extract_invoice_number(
                info["subject"], body, [a["filename"] for a in attachments], pdf_text=pdf_text
            )
            valor_liquido = extract_valor_liquido(pdf_text, info["subject"], body)
            obs = "" if numero != "VERIFICAR" else "Não foi possível identificar o número da nota"

            for attachment in attachments:
                ext = Path(attachment["filename"]).suffix or ".pdf"
                filename = build_pj_filename(colaborador, numero, ext)

                print(f"  → PJ: {colaborador} | {month_folder} | {filename}")
                if not dry_run:
                    folder.mkdir(parents=True, exist_ok=True)
                    target = _unique_path(folder, filename)
                    target.write_bytes(attachment_data[attachment["filename"]])
                    filename = target.name

                append_row(
                    wb, categoria=CATEGORIA_PJ, mes_pasta=month_folder, nome=colaborador,
                    numero_nota=numero, valor_liquido=valor_liquido, data_recebimento=received,
                    mes_emissao=month_folder, arquivo_nf=filename,
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
    print(f"  → busca no Gmail: {query}")
    messages = gmail_client.list_messages(service, query, _max_results())
    print(f"  → {len(messages)} e-mail(s) novo(s) em {address}")

    # Carrega a planilha uma única vez para toda a rotina — ver comentário
    # equivalente em process_pj_inbox.
    wb = load_or_create(sheet_path)

    processed = 0
    for stub in messages:
        message = gmail_client.get_message(service, stub["id"])
        info = gmail_client.message_summary(message)
        attachments = [
            a for a in gmail_client.list_attachments(message)
            if is_relevant_attachment(a["filename"])
        ]

        received = extract_email_received_date(info["date"])
        fornecedor = extract_sender_name(info["from"])

        if already_logged(wb, info["id"]):
            gmail_client.mark_processed(service, info["id"], LABEL_FORNECEDOR_PROCESSADA)
            continue

        body = gmail_client.get_body_text(message)

        if not attachments:
            month_folder = month_folder_name(received)
            print(f"  [AVISO] Sem anexo relevante: '{info['subject']}' de {fornecedor} — marcado para verificação")
            append_row(
                wb, categoria=CATEGORIA_FORNECEDOR, mes_pasta=month_folder, nome=fornecedor,
                numero_nota="VERIFICAR", data_recebimento=received,
                observacoes="E-mail sem anexo (PDF/XML) — verificar manualmente",
                assunto=info["subject"], gmail_message_id=info["id"],
            )
        else:
            # baixa antes de decidir a pasta: o mês vem de dentro da nota
            attachment_data = _download_attachments(service, info["id"], attachments)
            pdf_text = _first_pdf_text(attachments, attachment_data)

            referencia = extract_reference_period(pdf_text, info["subject"], body, fallback=received)
            month_folder = month_folder_name(referencia)
            mes_emissao = month_folder
            folder = Path(base_path) / month_folder

            numero = extract_invoice_number(
                info["subject"], body, [a["filename"] for a in attachments], pdf_text=pdf_text
            )
            valor_liquido = extract_valor_liquido(pdf_text, info["subject"], body)
            nf_filename = ""
            boleto_filename = ""

            for attachment in attachments:
                ext = Path(attachment["filename"]).suffix or ".pdf"
                is_boleto = is_boleto_filename(attachment["filename"])
                filename = build_fornecedor_filename(fornecedor, numero, mes_emissao, ext, is_boleto)

                print(f"  → Fornecedor: {fornecedor} | {month_folder} | {filename}")
                if not dry_run:
                    folder.mkdir(parents=True, exist_ok=True)
                    target = _unique_path(folder, filename)
                    target.write_bytes(attachment_data[attachment["filename"]])
                    filename = target.name

                if is_boleto:
                    boleto_filename = filename
                else:
                    nf_filename = filename

            obs = "" if numero != "VERIFICAR" else "Não foi possível identificar o número da nota"
            append_row(
                wb, categoria=CATEGORIA_FORNECEDOR, mes_pasta=month_folder, nome=fornecedor,
                numero_nota=numero, valor_liquido=valor_liquido, data_recebimento=received,
                mes_emissao=mes_emissao, arquivo_nf=nf_filename,
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
    import anthropic

    from email_classifier import classify_email
    from notifier import send_message

    pj_address = os.environ["PJ_INBOX_ADDRESS"]
    fornecedor_address = os.environ["FORNECEDOR_INBOX_ADDRESS"]

    query = (
        f'in:inbox -to:{pj_address} -to:{fornecedor_address} '
        f'-label:"{LABEL_DIVERSOS_REVISADO}"'
    )
    print(f"  → busca no Gmail: {query}")
    messages = gmail_client.list_messages(service, query, _max_results())
    print(f"  → {len(messages)} e-mail(s) novo(s) para triagem")

    scanned = 0
    notified = 0
    for stub in messages:
        message = gmail_client.get_message(service, stub["id"])
        info = gmail_client.message_summary(message)
        body = gmail_client.get_body_text(message)

        try:
            result = classify_email(info["subject"], info["from"], info["to"], body)
        except anthropic.AuthenticationError:
            print(
                "  [ERRO] Chave da Anthropic invalida/revogada — parando a triagem de "
                "assuntos diversos aqui (confira ANTHROPIC_API_KEY no .env). "
                "As notas fiscais de PJ e fornecedores ja processadas continuam válidas."
            )
            break
        except Exception as e:
            print(f"  [AVISO] Falha ao classificar '{info['subject']}': {e} — pulando, tenta de novo na próxima execução")
            continue
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

def _run_routine(nome: str, fn):
    """Roda uma rotina isolada das outras: se uma falhar (ex: planilha
    aberta no Excel, erro de rede), as outras duas continuam rodando
    normalmente em vez do programa inteiro parar."""
    try:
        fn()
    except PermissionError as e:
        print(
            f"  [ERRO] Não foi possível abrir a planilha de controle — ela "
            f"provavelmente está aberta no Excel (ou outro programa) agora. "
            f"Feche o arquivo; esta rotina tenta de novo na próxima execução."
        )
        print(f"          Detalhe técnico: {e}")
    except Exception as e:
        print(f"  [ERRO] {nome} falhou de forma inesperada: {e}")


def run(dry_run: bool, only: str):
    service = gmail_client.get_service()
    stamp = datetime.now()
    print(f"\n{'='*50}")
    print(f" AGENTE FINANCEIRO PERINITY  {stamp.strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*50}")

    if only in ("all", "pj"):
        print("\n[1/3] Notas fiscais de colaboradores PJ...")
        _run_routine("Notas fiscais de colaboradores PJ", lambda: process_pj_inbox(service, dry_run))

    if only in ("all", "fornecedores"):
        print("\n[2/3] Notas e boletos de fornecedores...")
        _run_routine("Notas e boletos de fornecedores", lambda: process_fornecedor_inbox(service, dry_run))

    if only in ("all", "diversos"):
        print("\n[3/3] Triagem de assuntos diversos...")
        _run_routine("Triagem de assuntos diversos", lambda: process_diversos(service, dry_run))

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
