# utils/computer_prompts.py

def intent_router_system_prompt() -> str:
    return (
        "You classify a player's 'computer' utterance into an intent.\n"
        "Return STRICT JSON ONLY. No markdown, no explanations.\n"
        "Schema: {\"intent\": \"<category>\", \"normalized\": \"<instruction>\", \"question\": \"<yes/no?>\"}\n"
        "Intent categories: create, destroy, pin, unpin, facts, refine, unknown.\n"
        "\"normalized\" is the instruction to run if confirmed (without 'computer,' prefix).\n"
        "\"question\" is a yes/no confirmation question for the player.\n"
    )

def prop_edit_system_prompt() -> str:
    return (
        "You edit properties of an existing MUD object based on a player's instruction.\n"
        "Return STRICT JSON ONLY. No markdown, no explanations.\n"
        "Required schema: {\"dbref\": \"<target dbref>\", \"key\": \"<new key>\", \"shortdesc\": \"<new shortdesc>\", \"desc\": \"<new desc>\"}\n"
        "Rules:\n"
        "- dbref MUST match the target object's dbref.\n"
        "- Only change fields that the instruction affects.\n"
        "- key: short Title-Case name, NO leading article.\n"
        "- shortdesc: one-line description starting with 'a' or 'an', ≤ 140 chars.\n"
        "- desc: 1-3 sentences describing the object concretely.\n"
    )

def prop_create_system_prompt() -> str:
    return (
        "You create physical objects for a text MUD.\n"
        "Return STRICT JSON ONLY. No markdown, no explanations.\n"
        "Required JSON schema:\n"
        '{"key": "TitleCase Name", "shortdesc": "a description", "desc": "detailed description", "affordance": {"weight": number, "immovable": bool}, "facts": [str], "object_type": str, "properties": {}}\n'
        "Rules:\n"
        "- key is REQUIRED: short Title-Case name, 2-6 words, NO leading article (e.g. \"Glass of Soda\", not \"A Glass of Soda\").\n"
        "- shortdesc is REQUIRED: a one-line description starting with 'a' or 'an', ≤ 140 characters.\n"
        "- desc is REQUIRED: 1-3 sentences describing the object concretely. Do not simply repeat the user's instruction verbatim.\n"
        "- affordance: include weight (number) and immovable (bool) when obvious.\n"
        "- facts: optional short stable statements the object itself implies.\n"
        "- object_type: Classify the object into ONE of: \"drinkable\", \"food\", \"wearable\", \"light_source\", \"container\", \"furniture\", \"decoration\", \"tool\", \"weapon\", \"misc\". This determines what abilities apply to it.\n"
        "- properties: Object properties that enable abilities. If the object is a drinkable liquid container, include:\n"
        "  {\"is_drinkable\": true, \"is_liquid\": true, \"liquid_name\": \"soda\", \"current_volume_ml\": 240, \"capacity_ml\": 240}\n"
        "  For food: {\"is_food\": true, \"nutrition\": 1, \"is_eaten\": false}\n"
        "  For wearables: {\"is_wearable\": true, \"wear_slot\": \"head\", \"is_worn\": true}\n"
        "  If no special properties, return an empty dict.\n"
        "- ALL required keys (key, shortdesc, desc, object_type, properties) MUST appear in the top-level JSON object.\n"
        "- Do NOT return a partial response with only affordance fields.\n"
    )
