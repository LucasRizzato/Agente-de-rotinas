"""
Uses Claude API with prompt caching to analyze vault data and generate insights.
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
Você é o Guardião — um assistente pessoal inteligente especializado em analisar \
notas do Obsidian e transformar informação bruta em insights acionáveis.

Seu papel:
- Identificar tarefas urgentes, vencidas ou próximas do prazo
- Encontrar padrões, temas recorrentes e conexões entre notas
- Surfaçar ideias importantes que merecem desenvolvimento
- Gerar um briefing claro, útil e direto ao ponto

Regras de formatação:
- Responda SEMPRE em português do Brasil
- Use emojis para facilitar a leitura no WhatsApp
- Seja específico: cite trechos ou títulos de notas reais
- Evite frases genéricas — cada insight deve ser concreto e acionável
- Limite a resposta a no máximo 1800 caracteres no total (o WhatsApp tem limite)
"""

_ANALYSIS_PROMPT = """\
Analise os dados do meu vault Obsidian abaixo e gere um relatório com 4 seções:

📋 *TAREFAS URGENTES*
Liste as 3 tarefas mais importantes ou vencidas. Se não houver, diga que está limpo.

💡 *INSIGHTS DO DIA*
2-3 observações sobre o que estou pensando/trabalhando com base nas notas recentes.

🔗 *CORRELAÇÕES*
1-2 conexões interessantes entre notas que merecem atenção ou exploração.

📌 *RESUMO*
1 parágrafo curto resumindo o estado atual do vault e o que precisa de foco.

---
DADOS DO VAULT:
"""


def analyze_vault(vault_data: dict) -> str:
    """
    Send vault data to Claude and return the analysis text.
    Uses prompt caching on the system prompt and vault context to reduce costs.
    """
    client = _get_client()

    vault_context = json.dumps(
        {
            "total_notes": vault_data["total_notes"],
            "recent_notes": vault_data["recent_notes"],
            "all_tasks": vault_data["all_tasks"],
            "older_notes_count": len(vault_data.get("older_notes", [])),
        },
        ensure_ascii=False,
        indent=2,
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": vault_context,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": _ANALYSIS_PROMPT,
                    },
                ],
            }
        ],
    )

    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0)
    cache_created = getattr(usage, "cache_creation_input_tokens", 0)
    print(
        f"  → Tokens: input={usage.input_tokens}, output={usage.output_tokens}, "
        f"cache_read={cache_read}, cache_created={cache_created}"
    )

    return response.content[0].text
