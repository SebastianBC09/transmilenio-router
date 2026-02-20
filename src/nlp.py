"""
LLM interface layer for natural language routing queries.

Wraps the routing engine with an Anthropic API call that:
1. Parses natural language input into structured origin/destination
2. Calls the routing engine
3. Explains the result in plain language

Requires ANTHROPIC_API_KEY in .env
"""

import os
import json
from dotenv import load_dotenv
import anthropic
import networkx as nx

from src.routing import find_route, search_station

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are a Transmilenio routing assistant for Bogotá, Colombia.

Your job is to extract origin and destination station names from user queries and return them as JSON.

Rules:
- Return ONLY valid JSON with keys "origin" and "destination"
- Use exact station names from the Transmilenio system when possible
- If you cannot identify origin or destination, set the value to null
- Do not include any explanation, only the JSON object

Example input: "How do I get from Portal Norte to Portal Sur?"
Example output: {"origin": "Portal Norte – Unicervantes", "destination": "Portal Sur - JFK Coop. Financiera"}"""


def parse_query(user_input: str) -> dict:
    """Use the LLM to extract origin and destination from natural language."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_input}],
    )
    text = response.content[0].text.strip()
    return json.loads(text)


def explain_route(result, user_input: str) -> str:
    """Use the LLM to explain a RouteResult in plain language."""
    if not result.found:
        prompt = f"The user asked: '{user_input}'. The routing engine returned this error: {result.error}. Explain this helpfully in 1-2 sentences."
    else:
        route_info = {
            "origin": result.origin,
            "destination": result.destination,
            "total_stops": result.total_stops,
            "stops": result.stops,
            "transfers": result.transfers,
            "routes_used": result.routes_used,
        }
        prompt = f"The user asked: '{user_input}'. Here is the route data: {json.dumps(route_info, ensure_ascii=False)}. Explain this route clearly in 2-3 sentences in the same language the user used."

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


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
        return "No pude identificar el origen o destino. Por favor intenta de nuevo con nombres de estaciones más específicos."

    # Try fuzzy match if exact names not found
    if origin not in G.nodes:
        candidates = search_station(G, origin)
        if len(candidates) == 1:
            origin = candidates[0]
        elif len(candidates) > 1:
            return f"Encontré varias estaciones similares a '{origin}': {', '.join(candidates)}. ¿Cuál es la correcta?"

    if destination not in G.nodes:
        candidates = search_station(G, destination)
        if len(candidates) == 1:
            destination = candidates[0]
        elif len(candidates) > 1:
            return f"Encontré varias estaciones similares a '{destination}': {', '.join(candidates)}. ¿Cuál es la correcta?"

    result = find_route(G, origin, destination)
    return explain_route(result, user_input)
