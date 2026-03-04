"""
LLM interface layer for natural language routing queries.

Supports multiple providers via OpenAI-compatible APIs:
- Groq (default, generous free tier)
- Mistral
- OpenAI

Configure via .env:
    LLM_PROVIDER=groq
    LLM_API_KEY=your_key_here
    LLM_MODEL=llama-3.3-70b-versatile
"""

import json
import os
from pathlib import Path

import networkx as nx
from dotenv import load_dotenv
from openai import OpenAI

from src.routing import RouteResult, find_route, search_station

load_dotenv(Path(__file__).parent.parent / ".env")

PROVIDER_URLS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "openai": "https://api.openai.com/v1",
}

SYSTEM_PROMPT = """You are a Transmilenio routing assistant for Bogotá, Colombia.

Your job is to extract origin and destination station names from user queries and return them as JSON.

Rules:
- Return ONLY valid JSON with keys "origin" and "destination"
- Extract the station name EXACTLY as the user wrote it — do not translate, correct, expand, or invent names
- If the user writes "Heroes", return "Heroes" — not "Héroes", not "General Santos"
- If the user writes "Av El Dorado", return "Av El Dorado" exactly
- If the user writes "portal norte", return "portal norte" exactly
- If you cannot identify origin or destination, set the value to null
- Do not include any explanation, only the JSON object

Example input: "Como llego de Heroes a Usme?"
Example output: {"origin": "Heroes", "destination": "Usme"}

Example input: "Como puedo llegar desde Av El Dorado hasta Calle 106?"
Example output: {"origin": "Av El Dorado", "destination": "Calle 106"}

Example input: "How do I get from Portal Norte to Portal Sur?"
Example output: {"origin": "Portal Norte", "destination": "Portal Sur"}"""


def get_client() -> OpenAI:
    """Build the LLM client based on .env configuration."""
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    api_key = os.getenv("LLM_API_KEY")
    base_url = PROVIDER_URLS.get(provider)

    if not api_key:
        raise ValueError("LLM_API_KEY not set in .env")
    if not base_url:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")

    return OpenAI(api_key=api_key, base_url=base_url)


def parse_query(user_input: str) -> dict[str, str | None]:
    """Use the LLM to extract origin and destination from natural language."""
    client = get_client()
    model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=200,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
        )
        content = response.choices[0].message.content
        if content is None:
            return {"origin": None, "destination": None}
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return {"origin": None, "destination": None}


def explain_route(result: RouteResult, user_input: str) -> str:
    """Use the LLM to explain a RouteResult in plain language."""
    client = get_client()
    model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    if not result.found:
        prompt = (
            f"The user asked: '{user_input}'. The routing engine returned this error: "
            f"{result.error}. Explain this helpfully in 1-2 sentences."
        )
    else:
        route_info = {
            "origin": result.origin,
            "destination": result.destination,
            "total_stops": result.total_stops,
            "stops": result.stops,
            "transfers": result.transfers,
            "routes_used": result.routes_used,
        }
        prompt = (
            f"The user asked: '{user_input}'. Here is the route data: "
            f"{json.dumps(route_info, ensure_ascii=False)}. Explain this route clearly "
            "in 2-3 sentences in the same language the user used."
        )

    response = client.chat.completions.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content
    return content.strip() if content is not None else ""


def natural_language_route(G: nx.MultiDiGraph, user_input: str) -> str:
    """
    Full pipeline: parse query, find route, explain result.

    Args:
        G: The Transmilenio graph
        user_input: Free-form natural language query

    Returns:
        Plain language explanation of the route
    """
    parsed = parse_query(user_input)
    origin = parsed.get("origin")
    destination = parsed.get("destination")

    if not origin or not destination:
        return (
            "No pude identificar el origen o destino. "
            "Por favor intenta de nuevo con nombres de estaciones más específicos."
        )

    # Try fuzzy match if exact names not found
    if origin not in G.nodes:
        candidates = search_station(G, origin)
        if len(candidates) == 0:
            return f"No encontré ninguna estación similar a '{origin}'."
        elif len(candidates) == 1:
            origin = candidates[0]
        else:
            return (
                f"Encontré varias estaciones similares a '{origin}': "
                f"{', '.join(candidates)}. ¿Cuál es la correcta?"
            )

    if destination not in G.nodes:
        candidates = search_station(G, destination)
        if len(candidates) == 0:
            return f"No encontré ninguna estación similar a '{destination}'."
        elif len(candidates) == 1:
            destination = candidates[0]
        else:
            return (
                f"Encontré varias estaciones similares a '{destination}': "
                f"{', '.join(candidates)}. ¿Cuál es la correcta?"
            )

    result = find_route(G, origin, destination)
    return explain_route(result, user_input)
