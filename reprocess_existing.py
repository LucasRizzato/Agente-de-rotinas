"""
Reprocessa notas já registradas na planilha de controle, para preencher
retroativamente colunas adicionadas depois do processamento original (por
enquanto: Valor Líquido) — sem duplicar linha nem gravar o PDF de novo.

Também recalcula o mês de referência com a lógica atual e avisa quando ele
diverge do que está gravado na planilha (ex: pasta criada com base na data
de vencimento por engano, já corrigido no código) — mas NÃO move nenhum
arquivo nem altera a coluna "Mês" sozinho, só avisa, porque mover exige
decidir junto com você.

Uso:
    python reprocess_existing.py              # aplica de verdade
    python reprocess_existing.py --dry-run    # só mostra o que faria
"""
import argparse
import os
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

import gmail_client
from finance_extractor import (
    extract_email_received_date,
    extract_reference_period,
    extract_valor_liquido,
    is_relevant_attachment,
    month_folder_name,
)
from pdf_reader import extract_pdf_text
from spreadsheet import COLUMNS, load_or_create, save

_VALOR_LIQUIDO_FORMAT = "R$ #,##0.00"


def _load_env():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()


def _first_pdf_text(service, message_id: str, attachments: list[dict]) -> str:
    for a in attachments:
        if a["filename"].lower().endswith(".pdf"):
            data = gmail_client.download_attachment(service, message_id, a)
            text = extract_pdf_text(data)
            if text:
                return text
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Reprocessa notas já registradas para preencher Valor Líquido e conferir o mês"
    )
    parser.add_argument("--dry-run", action="store_true", help="Só mostra o que faria, não grava nada")
    args = parser.parse_args()

    _load_env()
    sheet_path = os.environ["CONTROL_SHEET_PATH"]

    service = gmail_client.get_service()
    wb = load_or_create(sheet_path)
    ws = wb["Controle"]

    id_col = COLUMNS.index("Gmail Message ID") + 1
    valor_col = COLUMNS.index("Valor Líquido") + 1
    mes_col = COLUMNS.index("Mês") + 1
    nome_col = COLUMNS.index("Nome") + 1

    linhas = [row for row in ws.iter_rows(min_row=2) if row[id_col - 1].value]
    print(f"Conferindo {len(linhas)} linha(s) já registradas...\n")

    atualizados = 0
    erros = 0
    mes_divergente = []

    for row in linhas:
        message_id = row[id_col - 1].value
        nome_atual = row[nome_col - 1].value or ""
        mes_atual = row[mes_col - 1].value
        valor_atual = row[valor_col - 1].value

        try:
            message = gmail_client.get_message(service, message_id)
        except Exception as e:
            print(f"  [ERRO] {nome_atual} ({message_id}): não consegui buscar o e-mail — {e}")
            erros += 1
            continue

        info = gmail_client.message_summary(message)
        body = gmail_client.get_body_text(message)
        attachments = [
            a for a in gmail_client.list_attachments(message)
            if is_relevant_attachment(a["filename"])
        ]
        pdf_text = _first_pdf_text(service, message_id, attachments)

        received = extract_email_received_date(info["date"])
        referencia = extract_reference_period(pdf_text, info["subject"], body, fallback=received)
        mes_recalculado = month_folder_name(referencia)
        valor_novo = extract_valor_liquido(pdf_text, info["subject"], body)

        if mes_atual and mes_recalculado != mes_atual:
            mes_divergente.append((nome_atual, mes_atual, mes_recalculado, message_id))

        if valor_atual in (None, "") and valor_novo is not None:
            print(f"  → {nome_atual} | {mes_atual}: Valor Líquido = R$ {valor_novo:.2f}")
            if not args.dry_run:
                cell = ws.cell(row=row[0].row, column=valor_col, value=valor_novo)
                cell.number_format = _VALOR_LIQUIDO_FORMAT
            atualizados += 1

    if not args.dry_run:
        save(wb, sheet_path)

    print(f"\n{'=' * 50}")
    print(f"Valor Líquido preenchido em {atualizados} linha(s).")
    if erros:
        print(f"{erros} linha(s) com erro ao buscar o e-mail.")
    if mes_divergente:
        print(f"\n{len(mes_divergente)} linha(s) com mês possivelmente errado (nada foi movido, só um aviso):")
        for nome, mes_antigo, mes_novo, mid in mes_divergente:
            print(f"  - {nome}: planilha diz '{mes_antigo}', deveria ser '{mes_novo}' (mensagem {mid})")
    if args.dry_run:
        print("\n[DRY RUN] Nada foi gravado.")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
