"""
Usa Claude para decidir se um e-mail "diverso" (que não é nota/boleto)
exige uma ação do Lucas ou se ele só está copiado/em uma thread informativa.
"""
import json
import os

import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


_SYSTEM_PROMPT = """\
Você é um triador de e-mails para o Lucas, que recebe muitos e-mails de \
trabalho na Perinity. Sua tarefa é decidir, para cada e-mail, se ele PRECISA \
que o Lucas tome alguma ação (responder, decidir, aprovar, revisar algo \
endereçado a ele) ou se ele está apenas copiado (CC), em uma thread \
informativa, ou recebendo uma notificação automática sem ação necessária.

Responda SEMPRE em JSON puro (sem markdown, sem texto fora do JSON), no formato:
{"precisa_acao": true ou false, "resumo": "resumo objetivo em 1-2 frases em português"}

O resumo deve ser curto, direto, e mencionar quem enviou e o que está sendo pedido \
(se houver). Se não precisar de ação, ainda assim escreva um resumo breve do assunto.
"""


def classify_email(subject: str, sender: str, to: str, body_snippet: str) -> dict:
    client = _get_client()

    payload = json.dumps(
        {"remetente": sender, "para": to, "assunto": subject, "corpo": body_snippet[:2000]},
        ensure_ascii=False,
    )

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": payload}],
    )

    text = response.content[0].text.strip()
    try:
        data = json.loads(text)
        return {
            "precisa_acao": bool(data.get("precisa_acao", True)),
            "resumo": str(data.get("resumo", "")).strip() or subject,
        }
    except (json.JSONDecodeError, AttributeError):
        return {"precisa_acao": True, "resumo": text[:400] or subject}
