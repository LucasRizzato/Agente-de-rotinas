"""
Sends WhatsApp messages via Twilio.
"""
import os
from twilio.rest import Client


def _get_client() -> Client:
    return Client(
        os.environ["TWILIO_ACCOUNT_SID"],
        os.environ["TWILIO_AUTH_TOKEN"],
    )


def send_whatsapp(message: str, to_number: str | None = None) -> list[str]:
    """
    Send a WhatsApp message, splitting into chunks if needed.
    Numbers must be in E.164 format: +5511999999999
    Returns list of sent message SIDs.
    """
    client = _get_client()
    from_number = f"whatsapp:{os.environ['TWILIO_WHATSAPP_NUMBER']}"
    to_number = f"whatsapp:{to_number or os.environ['MY_WHATSAPP_NUMBER']}"

    # WhatsApp practical limit for Twilio is ~1600 chars per message
    chunk_size = 1500
    chunks = [message[i : i + chunk_size] for i in range(0, len(message), chunk_size)]

    sids = []
    for i, chunk in enumerate(chunks):
        prefix = f"[{i + 1}/{len(chunks)}]\n" if len(chunks) > 1 else ""
        msg = client.messages.create(
            body=prefix + chunk,
            from_=from_number,
            to=to_number,
        )
        sids.append(msg.sid)
        print(f"  → Mensagem {i + 1}/{len(chunks)} enviada: {msg.sid}")

    return sids
