# utils/computer_prompts.py

def prop_create_system_prompt() -> str:
    return (
        "You create physical objects for a text MUD.\n"
        "Return STRICT JSON ONLY. No markdown, no explanations.\n"
        "Required JSON schema:\n"
        '{\"key\": \"TitleCase Name\", \"shortdesc\": \"a description\", \"desc\": \"detailed description\", \"affordance\": {\"weight\": number, \"immovable\": bool}, \"facts\": [str]}\n'
        "Rules:\n"
        "- key is REQUIRED: short Title-Case name, 2-6 words, NO leading article (e.g. \"Glass of Soda\", not \"A Glass of Soda\").\n"
        "- shortdesc is REQUIRED: a one-line description starting with 'a' or 'an', ≤ 140 characters.\n"
        "- desc is REQUIRED: 1-3 sentences describing the object concretely. Do not simply repeat the user's instruction verbatim.\n"
        "- affordance: include weight (number) and immovable (bool) when obvious.\n"
        "- facts: optional short stable statements the object itself implies.\n"
        "- ALL required keys (key, shortdesc, desc) MUST appear in the top-level JSON object.\n"
        "- Do NOT return a partial response with only affordance fields.\n"
    )


def intent_router_system_prompt() -> str:
    return (
        "You are an intent router for a text MUD assistant named 'computer'.\n"
        "Given a user's raw request, predict what they intend.\n"
        "Return STRICT JSON ONLY.\n"
        'Schema: {"intent": str, "normalized": str, "question": str}\n'
        "\n"
        "Allowed intents:\n"
        "- create: create/manifest an object\n"
        "- destroy: remove an object in the current room\n"
        "- pin: pin a fact (optionally 'to <target>')\n"
        "- unpin: unpin a fact id\n"
        "- facts: list facts\n"
        "- refine: rewrite/refine the room description\n"
        "- unknown: cannot determine\n"
        "\n"
        "Rules:\n"
        "- normalized MUST be a single concrete computer instruction that matches the system's commands.\n"
        "  Examples: 'create a hot cup of earl grey tea', 'destroy Seaside Lamp', 'pin This is a living room', 'facts', 'refine'.\n"
        "- If you are unsure, set intent='unknown' and ask a clarifying yes/no question anyway.\n"
        "- question MUST be a yes/no confirmation phrased to the player.\n"
    )


def prop_edit_system_prompt() -> str:
    return (
        "You edit ONE existing physical object in a text MUD.\n"
        "Return STRICT JSON ONLY.\n"
        'Schema: {"dbref": str, "key": str, "shortdesc": str, "desc": str}\n'
        "\n"
        "You must apply the user's requested change(s) to the object.\n"
        "Do not invent new objects.\n"
        "Do not contradict established facts unless the user explicitly requests a change.\n"
        "\n"
        "Return ONLY valid JSON.\n"
        "Do NOT include explanations or markdown.\n"
        "\n"
        "The JSON MUST contain these keys:\n"
        '- "dbref": Always include "dbref" unchanged from the input\n'
        '- "key": the object\'s display name (Title Case, NO leading article, ≤ 60 characters\n'
        '- "shortdesc": a one-line description that STARTS with "a" or "an", ≤ 140 characters\n'
        '- "desc": a concise paragraph describing the object\n'
    )
