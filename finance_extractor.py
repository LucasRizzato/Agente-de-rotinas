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

_YEAR_RE = re.compile(r"^(19|20)\d{2}$")

# Documentos que de fato costumam ser a nota/boleto em si. Imagens só contam
# quando o nome sugere boleto/comprovante — do contrário quase sempre são
# logo/assinatura de e-mail, não o documento fiscal.
_DOCUMENT_EXTENSIONS = {".pdf", ".xml"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
_BOLETO_HINT_RE = re.compile(r"boleto|comprovante|recibo", re.I)


def sanitize_filename(name: str) -> str:
    name = _INVALID_FILENAME_CHARS.sub("", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name or "VERIFICAR"


def month_folder_name(dt: datetime) -> str:
    return f"{dt.month:02d}. {MESES_PT[dt.month - 1]}"


def extract_sender_name(from_header: str) -> str:
    """'Fulano de Tal <fulano@empresa.com>' -> 'Fulano de Tal'

    Também limpa o formato que o Gmail usa para envios via sistemas
    automáticos de emissão de nota, ex: '"\\'Fulano de Tal\\' via NFE" <...>'
    vira só 'Fulano de Tal'.
    """
    match = re.match(r"^\s*\"?([^\"<]+?)\"?\s*<", from_header)
    if match:
        name = match.group(1).strip()
    else:
        name = from_header.split("@")[0].strip()
    name = re.sub(r"\s+via\s+\S.*$", "", name, flags=re.I).strip()
    name = name.strip("'\" ")
    name = name if name else "VERIFICAR"
    return sanitize_filename(name)


def is_relevant_attachment(filename: str) -> bool:
    """Filtra anexos que provavelmente são a nota/boleto de fato, descartando
    logos de assinatura de e-mail, .txt/.csv de sistemas automáticos etc."""
    suffix = re.search(r"(\.[A-Za-z0-9]+)$", filename)
    ext = suffix.group(1).lower() if suffix else ""
    if ext in _DOCUMENT_EXTENSIONS:
        return True
    if ext in _IMAGE_EXTENSIONS:
        return bool(_BOLETO_HINT_RE.search(filename))
    return False


def _numeric_filename_number(filename: str) -> str | None:
    """Se o nome do arquivo (sem extensão) for só dígitos, curto o bastante
    para ser um número de nota (não a chave de acesso de 44 dígitos da NFe)
    e não parecer um ano, usa isso como número da nota — comum em sistemas
    de emissão que já nomeiam o arquivo com o número (ex: '98464.pdf')."""
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filename)
    stem = re.sub(r"[\s_\-]+", "", stem)
    if not stem.isdigit() or not (1 <= len(stem) <= 10):
        return None
    if _YEAR_RE.fullmatch(stem):
        return None
    return stem.lstrip("0") or stem


def extract_invoice_number(subject: str, body: str, filenames: list[str]) -> str:
    """Procura o número da nota no assunto, corpo e nome(s) de arquivo, nessa
    ordem. Descarta matches que sejam só um ano (ex: '2026' vindo de "NF
    Agosto 2026") para não confundir ano com número da nota."""
    for text in (subject, body, *filenames):
        if not text:
            continue
        for pattern in _NOTA_PATTERNS:
            match = pattern.search(text)
            if match:
                number = match.group(1)
                if not _YEAR_RE.fullmatch(number):
                    return number.lstrip("0") or number
    for filename in filenames:
        number = _numeric_filename_number(filename)
        if number:
            return number
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
