"""
Extração de texto de notas fiscais em PDF, usando pypdf (sem dependências
de sistema). Se o PDF for uma imagem escaneada sem camada de texto, ou vier
corrompido/protegido, retorna string vazia — quem chama cai de volta no
e-mail como fonte da data.
"""
from io import BytesIO


def extract_pdf_text(data: bytes, max_pages: int = 3) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        # Nunca deixa um problema de instalação da biblioteca de PDF derrubar
        # o agente inteiro — só perde a leitura do conteúdo da nota.
        return ""

    try:
        reader = PdfReader(BytesIO(data))
        pages = reader.pages[:max_pages]
        return "\n".join(page.extract_text() or "" for page in pages)
    except Exception:
        return ""
