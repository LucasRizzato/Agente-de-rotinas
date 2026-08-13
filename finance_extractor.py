"""
Extração baseada em regras (sem IA) dos dados necessários para nomear
arquivos e preencher a planilha de controle: nome do remetente, número da
nota fiscal e mês de referência.

Quando um dado não pode ser identificado com confiança, retorna "VERIFICAR"
para que o Lucas complete manualmente — em vez de arriscar um nome errado.
"""
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')

_NOTA_PATTERNS = [
    re.compile(r"nota\s*fiscal\s*(?:eletr[ôo]nica)?\s*n?[ºo°.:]*\s*(\d{2,10})", re.I),
    re.compile(r"\bnf-?e?\s*n?[ºo°.:]*\s*(\d{2,10})", re.I),
    re.compile(r"\bn[ºo°]\s*(\d{2,10})", re.I),
    re.compile(r"\binvoice\s*(?:number|#)?\s*[:\-]?\s*(\d{2,10})", re.I),
]

_DATE_PATTERNS = [
    re.compile(r"emiss[ãa]o[:\s]*?(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", re.I),
    re.compile(r"emitid[ao]\s+em\s+(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", re.I),
    re.compile(r"data[:\s]*?(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", re.I),
]


def sanitize_filename(name: str) -> str:
    name = _INVALID_FILENAME_CHARS.sub("", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name or "VERIFICAR"


def month_folder_name(dt: datetime) -> str:
    return f"{dt.month:02d}. {MESES_PT[dt.month - 1]}"


def extract_sender_name(from_header: str) -> str:
    """'Fulano de Tal <fulano@empresa.com>' -> 'Fulano de Tal'"""
    match = re.match(r"^\s*\"?([^\"<]+?)\"?\s*<", from_header)
    if match:
        name = match.group(1).strip()
    else:
        name = from_header.split("@")[0].strip()
    name = name if name else "VERIFICAR"
    return sanitize_filename(name)


def extract_invoice_number(*texts: str) -> str:
    """Procura o número da nota no assunto, corpo e nome(s) de arquivo, nessa ordem."""
    for text in texts:
        if not text:
            continue
        for pattern in _NOTA_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1).lstrip("0") or match.group(1)
    # Último recurso: sequência de 3-8 dígitos isolada no nome do arquivo/assunto
    for text in texts:
        if not text:
            continue
        match = re.search(r"(?<!\d)(\d{3,8})(?!\d)", text)
        if match:
            return match.group(1)
    return "VERIFICAR"


def extract_email_received_date(date_header: str) -> datetime:
    try:
        return parsedate_to_datetime(date_header)
    except (TypeError, ValueError):
        return datetime.now()


def extract_emission_date(*texts: str, fallback: datetime) -> datetime:
    """Tenta achar a data de emissão da nota no corpo do e-mail; usa a data de
    recebimento do e-mail como fallback."""
    for text in texts:
        if not text:
            continue
        for pattern in _DATE_PATTERNS:
            match = pattern.search(text)
            if match:
                day, month, year = match.groups()
                if len(year) == 2:
                    year = f"20{year}"
                try:
                    return datetime(int(year), int(month), int(day))
                except ValueError:
                    continue
    return fallback


def build_pj_filename(colaborador: str, numero_nota: str, ext: str) -> str:
    return sanitize_filename(f"{colaborador} {numero_nota}") + ext


def build_fornecedor_filename(
    fornecedor: str, numero_nota: str, mes_emissao: str, ext: str, is_boleto: bool = False
) -> str:
    base = f"{fornecedor} {numero_nota} {mes_emissao}"
    if is_boleto:
        base += " - Boleto"
    return sanitize_filename(base) + ext


def is_boleto_filename(filename: str) -> bool:
    return bool(re.search(r"boleto", filename, re.I))
