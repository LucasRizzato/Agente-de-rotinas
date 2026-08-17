"""
Cliente Gmail API (OAuth2) — autentica, lista mensagens, baixa anexos e
gerencia labels de controle (evita reprocessar o mesmo e-mail).
"""
import base64
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _resolve_path(value: str) -> Path:
    """Caminhos relativos são resolvidos a partir da pasta deste arquivo, não
    da pasta de trabalho atual — que pode não ser a pasta do agente quando
    ele roda via Agendador de Tarefas do Windows (o padrão lá é
    C:\\Windows\\System32)."""
    path = Path(value)
    return path if path.is_absolute() else Path(__file__).parent / path


def _credentials_path() -> Path:
    return _resolve_path(os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json"))


def _token_path() -> Path:
    return _resolve_path(os.environ.get("GMAIL_TOKEN_PATH", "token.json"))


def get_service():
    """Autentica via OAuth2 (fluxo local) e retorna o client da Gmail API."""
    creds = None
    token_path = _token_path()

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds_path = _credentials_path()
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"Arquivo de credenciais OAuth não encontrado: {creds_path}\n"
                    "Baixe-o no Google Cloud Console (APIs & Services > Credentials) "
                    "e aponte GMAIL_CREDENTIALS_PATH no .env para ele."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def _get_or_create_label(service, name: str) -> str:
    """Retorna o ID de um label, criando-o (com hierarquia via '/') se necessário."""
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == name:
            return label["id"]

    created = (
        service.users()
        .labels()
        .create(
            userId="me",
            body={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        .execute()
    )
    return created["id"]


_label_cache: dict[str, str] = {}


def label_id(service, name: str) -> str:
    if name not in _label_cache:
        _label_cache[name] = _get_or_create_label(service, name)
    return _label_cache[name]


def list_messages(service, query: str, max_results: int = 50) -> list[dict]:
    """Lista mensagens que casam com uma query de busca do Gmail."""
    messages: list[dict] = []
    request = service.users().messages().list(
        userId="me", q=query, maxResults=min(max_results, 500)
    )
    while request is not None and len(messages) < max_results:
        response = request.execute()
        messages.extend(response.get("messages", []))
        request = service.users().messages().list_next(request, response)
    return messages[:max_results]


def get_message(service, message_id: str) -> dict:
    return (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )


def _header(message: dict, name: str) -> str:
    headers = message.get("payload", {}).get("headers", [])
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def message_summary(message: dict) -> dict:
    return {
        "id": message["id"],
        "thread_id": message.get("threadId", ""),
        "from": _header(message, "From"),
        "to": _header(message, "To"),
        "subject": _header(message, "Subject"),
        "date": _header(message, "Date"),
        "snippet": message.get("snippet", ""),
    }


def _walk_parts(payload: dict):
    if not payload:
        return
    body = payload.get("body", {})
    # Anexos pequenos vêm com o conteúdo já embutido em body.data; só os
    # maiores exigem uma segunda chamada via attachmentId. Sem checar os
    # dois casos, anexos pequenos (ex: um boleto de poucos KB) somem
    # silenciosamente, como se o e-mail não tivesse anexo nenhum.
    if payload.get("filename") and (body.get("attachmentId") or body.get("data")):
        yield payload
    for part in payload.get("parts", []) or []:
        yield from _walk_parts(part)


def list_attachments(message: dict) -> list[dict]:
    """Retorna [{filename, mime_type, attachment_id, inline_data}] para cada
    anexo da mensagem. attachment_id é None quando o conteúdo já veio
    embutido em inline_data (anexos pequenos)."""
    attachments = []
    for part in _walk_parts(message.get("payload", {})):
        body = part.get("body", {})
        attachments.append(
            {
                "filename": part["filename"],
                "mime_type": part.get("mimeType", "application/octet-stream"),
                "attachment_id": body.get("attachmentId"),
                "inline_data": body.get("data"),
            }
        )
    return attachments


def download_attachment(service, message_id: str, attachment: dict) -> bytes:
    """Baixa o conteúdo de um anexo — usa o dado já embutido quando presente
    (anexo pequeno) para evitar uma chamada de API desnecessária."""
    if attachment.get("inline_data"):
        return base64.urlsafe_b64decode(attachment["inline_data"])
    result = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment["attachment_id"])
        .execute()
    )
    return base64.urlsafe_b64decode(result["data"])


def get_body_text(message: dict) -> str:
    """Extrai o texto simples do corpo do e-mail (melhor esforço)."""

    def _decode(data: str) -> str:
        try:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def _find_text(payload: dict) -> str:
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return _decode(payload["body"]["data"])
        for part in payload.get("parts", []) or []:
            text = _find_text(part)
            if text:
                return text
        return ""

    text = _find_text(message.get("payload", {}))
    if not text:
        text = message.get("snippet", "")
    return text


def mark_processed(service, message_id: str, label_name: str, mark_as_read: bool = True):
    """Aplica um label de controle e opcionalmente marca a mensagem como lida."""
    add_labels = [label_id(service, label_name)]
    remove_labels = ["UNREAD"] if mark_as_read else []
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": add_labels, "removeLabelIds": remove_labels},
        ).execute()
    except HttpError as e:
        print(f"  [AVISO] Falha ao marcar mensagem {message_id} como processada: {e}")
