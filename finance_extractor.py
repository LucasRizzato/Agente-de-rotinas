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

_NOTA_FISCAL_LABEL = r"(?:nota\s*fiscal(?:\s+de\s+servi[cç]os)?(?:\s+eletr[ôo]nica)?|nfs?-?e)"
_NUM_LABEL = r"(?:n[uú]mero|n[ºo°])"

_NOTA_PATTERNS = [
    # "Número da Nota: 12345" / "Número da Nota Fiscal de Serviços
    # Eletrônica: 999" / "Nº da NFS-e: 998" — como a nota se identifica
    re.compile(
        rf"{_NUM_LABEL}\s*(?:da\s+)?(?:nota|{_NOTA_FISCAL_LABEL})\s*[:\-]?\s*(\d{{2,10}})", re.I
    ),
    # "Nota Fiscal de Serviços Eletrônica nº 771" / "NFS-e 12345" / "NF-e nº X"
    re.compile(rf"{_NOTA_FISCAL_LABEL}\s*{_NUM_LABEL}?\s*[:\-.]?\s*(\d{{2,10}})", re.I),
    re.compile(r"\binvoice\s*(?:number|#)?\s*[:\-]?\s*(\d{2,10})", re.I),
]

# Só datas explicitamente rotuladas como emissão. Existia uma 3ª regra
# genérica ("data" + qualquer data) que casava com QUALQUER campo de data
# do PDF — inclusive "Data de Vencimento", que cai um mês depois da
# emissão. Removida: é melhor cair na data de recebimento do e-mail do
# que arriscar pegar o vencimento achando que é a emissão.
_DATE_PATTERNS = [
    re.compile(r"emiss[ãa]o[^\d\n]{0,30}(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", re.I),
    re.compile(r"emitid[ao]\s+em\s+(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", re.I),
]

_YEAR_RE = re.compile(r"^(19|20)\d{2}$")

# Valor monetário no formato brasileiro: 1.234,56 / 234,56 / 1234
_VALOR_NUM = r"(\d+(?:\.\d{3})*(?:,\d{2})?)"

# Cada layout de NFS-e (varia de prefeitura para prefeitura) rotula o valor
# a receber de um jeito diferente — "Valor Líquido", "Valor a Receber",
# "Valor Total do Serviço"... Em ordem de confiança: prefere um rótulo que
# diga explicitamente "líquido"/"a receber" sobre um "total" genérico, que
# em alguns modelos pode incluir impostos ainda não descontados.
_VALOR_LABELS = [
    r"valor\s*l[ií]quido(?:\s*d[ao]\s*nfs?-?e)?",
    r"(?:valor\s*)?(?:a\s*receber|l[ií]quido\s*a\s*receber)",
    r"total\s*l[ií]quido",
    r"valor\s*total\s*(?:d[ao]\s*servi[cç]os?|d[ao]\s*nfs?-?e)?",
]
# [^\d] (em vez de [^\d\n]) porque em muitos modelos o valor vem numa linha
# separada do rótulo, não colado nela.
_VALOR_LIQUIDO_PATTERNS = [
    re.compile(rf"{label}[^\d]{{0,40}}{_VALOR_NUM}", re.I) for label in _VALOR_LABELS
]

_MES_NUM = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

# Padrões que indicam o mês/período a que a nota SE REFERE — geralmente
# diferente da data de emissão ou de recebimento do e-mail, e o que
# realmente importa para separar as pastas por competência.
_COMPETENCIA_PATTERNS = [
    re.compile(r"compet[eê]ncia\s*[:\-]?\s*(\d{1,2})[/\-](\d{4})", re.I),
    re.compile(
        r"per[ií]odo\s+de\s+presta[cç][aã]o\s+de\s+servi[cç]os?\s*[:\-]?\s*"
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})",
        re.I,
    ),
    re.compile(r"referente\s+(?:a|à|ao)\s*[:\-]?\s*(\d{1,2})[/\-](\d{4})", re.I),
]

_MES_NOME_ALT = (
    r"(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|"
    r"outubro|novembro|dezembro)(?:\s*(?:de|/)?\s*(\d{4}))?"
)

# Mês por extenso "solto" (ex: "NF Julho" no assunto) — só é seguro usar em
# textos curtos e focados como o assunto do e-mail. Num texto longo como o
# PDF da nota ou o corpo do e-mail, a primeira menção de mês costuma ser a
# data de emissão ou de vencimento, não a competência.
_MES_NOME_RE = re.compile(rf"\b{_MES_NOME_ALT}\b", re.I)

# Mês por extenso com uma palavra-chave de competência por perto (ex:
# "referente ao mês de Julho de 2026") — esse sim é seguro usar em qualquer
# texto, incluindo o PDF, porque a palavra-chave deixa a intenção clara.
_MES_NOME_QUALIFICADO_RE = re.compile(
    rf"(?:referente|compet[eê]ncia|per[ií]odo)\D{{0,20}}{_MES_NOME_ALT}", re.I
)

# Documentos que de fato costumam ser a nota/boleto em si. Só PDF — o Lucas
# não precisa do XML da NFe. Imagens só contam quando o nome sugere
# boleto/comprovante — do contrário quase sempre são logo/assinatura de
# e-mail, não o documento fiscal.
_DOCUMENT_EXTENSIONS = {".pdf"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
_BOLETO_HINT_RE = re.compile(r"boleto|comprovante|recibo", re.I)

# ── Reconhecimento do conteúdo do PDF ───────────────────────────────────
# A extensão .pdf sozinha não diz nada: contrato, proposta, apresentação e
# assinatura de e-mail também são PDF. Estes marcadores identificam o que é
# de fato um documento fiscal, olhando o texto de dentro do arquivo.

_NOTA_MARCADORES = [
    re.compile(r"nota\s*fiscal", re.I),
    re.compile(r"\bnfs?-?e\b", re.I),
    re.compile(r"danfe", re.I),
    re.compile(r"recibo\s+provis[óo]rio\s+de\s+servi[cç]os", re.I),  # RPS
    re.compile(r"\brps\b", re.I),
]

# Um documento fiscal de serviço praticamente sempre tem prestador/tomador
# ou menção ao ISS — reforça a identificação e evita falso positivo de um
# e-mail que só cita "nota fiscal" de passagem no corpo do documento.
_NOTA_MARCADORES_APOIO = [
    re.compile(r"prestador\s+d[eo]\s+servi[cç]os?", re.I),
    re.compile(r"tomador\s+d[eo]\s+servi[cç]os?", re.I),
    re.compile(r"\biss(?:qn)?\b", re.I),
    re.compile(r"c[óo]digo\s+de\s+verifica[cç][ãa]o", re.I),
    re.compile(r"discrimina[cç][ãa]o\s+d[oa]s?\s+servi[cç]os?", re.I),
    re.compile(r"munic[íi]pio\s+prestador", re.I),
]

_BOLETO_MARCADORES = [
    re.compile(r"linha\s+digit[áa]vel", re.I),
    re.compile(r"c[óo]digo\s+de\s+barras", re.I),
    re.compile(r"benefici[áa]rio", re.I),
    re.compile(r"nosso\s+n[úu]mero", re.I),
    re.compile(r"cedente", re.I),
    re.compile(r"sacado", re.I),
    re.compile(r"ficha\s+de\s+compensa[cç][ãa]o", re.I),
    re.compile(r"vencimento", re.I),
]


def looks_like_invoice(pdf_text: str) -> bool:
    """O texto do PDF parece ser uma nota fiscal de serviço?

    Exige um marcador forte (o documento se identifica como nota/NFS-e/
    DANFE/RPS) E um de apoio (prestador/tomador/ISS/código de verificação),
    para não confundir com um contrato ou e-mail que apenas menciona a
    palavra "nota fiscal" no meio do texto.
    """
    if not pdf_text:
        return False
    tem_marcador = any(p.search(pdf_text) for p in _NOTA_MARCADORES)
    tem_apoio = any(p.search(pdf_text) for p in _NOTA_MARCADORES_APOIO)
    return tem_marcador and tem_apoio


def looks_like_boleto(pdf_text: str) -> bool:
    """O texto do PDF parece ser um boleto bancário? Exige pelo menos dois
    marcadores típicos, já que palavras como "vencimento" e "beneficiário"
    aparecem isoladas em outros documentos."""
    if not pdf_text:
        return False
    return sum(1 for p in _BOLETO_MARCADORES if p.search(pdf_text)) >= 2


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


def extract_invoice_number(
    subject: str, body: str, filenames: list[str], pdf_text: str = ""
) -> str:
    """Procura o número da nota no assunto, corpo, texto do PDF e nome(s) de
    arquivo, nessa ordem. Descarta matches que sejam só um ano (ex: '2026'
    vindo de "NF Agosto 2026") para não confundir ano com número da nota."""
    for text in (subject, body, pdf_text, *filenames):
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


def _parse_brl_number(raw: str) -> float | None:
    """'1.234,56' -> 1234.56. Detecta o formato pelo separador mais à
    direita (esse é sempre o decimal); se só houver um tipo de separador,
    assume vírgula como decimal (padrão brasileiro)."""
    s = raw.strip()
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def extract_valor_liquido(pdf_text: str, subject: str = "", body: str = "") -> float | None:
    """Procura o valor líquido da nota no texto do PDF (prioridade) e,
    como fallback, no assunto/corpo do e-mail. Retorna None quando não
    encontra — melhor deixar a célula em branco do que arriscar um valor
    errado numa coluna que o Lucas provavelmente vai somar."""
    for text in (pdf_text, subject, body):
        if not text:
            continue
        for pattern in _VALOR_LIQUIDO_PATTERNS:
            match = pattern.search(text)
            if match:
                valor = _parse_brl_number(match.group(1))
                if valor is not None:
                    return valor
    return None


def extract_email_received_date(date_header: str) -> datetime:
    try:
        return parsedate_to_datetime(date_header)
    except (TypeError, ValueError):
        return datetime.now()


def extract_reference_period(pdf_text: str, subject: str, body: str, *, fallback: datetime) -> datetime:
    """Descobre o mês/ano a que a nota SE REFERE (competência), priorizando o
    texto lido de dentro do PDF — que é a própria nota — sobre o assunto e o
    corpo do e-mail. Cai na data de recebimento do e-mail só se nada for
    encontrado (ex: PDF escaneado sem texto, ou nota sem essa informação).
    """
    texts_in_priority = (pdf_text, subject, body)

    # 1) Padrões explícitos de competência/período/"referente a"
    for text in texts_in_priority:
        if not text:
            continue
        for pattern in _COMPETENCIA_PATTERNS:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                month, year = (groups[0], groups[1]) if len(groups) == 2 else (groups[1], groups[2])
                try:
                    month_i, year_i = int(month), int(year)
                    if year_i < 100:
                        year_i += 2000
                    if 1 <= month_i <= 12:
                        return datetime(year_i, month_i, 1)
                except ValueError:
                    continue

    # 2a) Nome do mês por extenso com palavra-chave de competência por perto
    #     (ex: "referente ao mês de Agosto/2026") — seguro em qualquer texto
    for text in texts_in_priority:
        if not text:
            continue
        match = _MES_NOME_QUALIFICADO_RE.search(text)
        if match:
            month_i = _MES_NUM.get(match.group(1).lower())
            year_i = int(match.group(2)) if match.group(2) else fallback.year
            if month_i:
                return datetime(year_i, month_i, 1)

    # 2b) Nome do mês "solto" (ex: "NF Agosto" no assunto) — só no assunto do
    #     e-mail, que é curto e focado na própria nota. No corpo do e-mail ou
    #     no texto do PDF (longos) isso arriscaria pegar a data de emissão ou
    #     de vencimento em vez da competência.
    if subject:
        match = _MES_NOME_RE.search(subject)
        if match:
            month_i = _MES_NUM.get(match.group(1).lower())
            year_i = int(match.group(2)) if match.group(2) else fallback.year
            if month_i:
                return datetime(year_i, month_i, 1)

    # 3) Data de emissão explícita (menos confiável que competência, mas
    #    melhor que só a data de recebimento do e-mail)
    for text in texts_in_priority:
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


