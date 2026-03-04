"""
Pathfinding logic for the Transmilenio routing engine.

Uses Dijkstra's algorithm via NetworkX. Edge weights are stop counts (1 per edge in v1).
Transfer points are handled implicitly — any station in multiple routes is a natural transfer.
"""

from dataclasses import dataclass
from typing import Optional
import unicodedata

import networkx as nx
from networkx.algorithms.shortest_paths.generic import shortest_path
from networkx.exception import NetworkXNoPath

@dataclass
class RouteResult:
    origin: str
    destination: str
    stops: list[str]
    total_stops: int
    transfers: list[str]
    routes_used: list[str]
    found: bool
    error: Optional[str] = None


def find_route(G: nx.MultiDiGraph, origin: str, destination: str) -> RouteResult:
    """
    Find the shortest path between two stations by stop count.

    Args:
        G: The Transmilenio graph built by build_graph()
        origin: Exact station name (case-sensitive)
        destination: Exact station name (case-sensitive)

    Returns:
        RouteResult with path details, transfer points, and routes used.
    """
    if origin not in G:
        return RouteResult(
            origin, destination, [], 0, [], [], False, f"Station not found: {origin}"
        )
    if destination not in G:
        return RouteResult(
            origin, destination, [], 0, [], [], False, f"Station not found: {destination}",
        )
    if origin == destination:
        return RouteResult(origin, destination, [origin], 0, [], [], True)

    try:
        path = shortest_path(G, source=origin, target=destination, weight="weight")
    except NetworkXNoPath:
        return RouteResult(
            origin, destination, [], 0, [], [], False, "No path found between these stations.",
        )

    # Identify which routes are used along the path and where transfers occur
    routes_used = []
    transfers = []
    current_route = None

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge_data = G.get_edge_data(u, v)
        edge = list(edge_data.values())[0]
        route_id = edge["route_id"]

        if route_id != current_route:
            if current_route is not None:
                transfers.append(path[i])
            routes_used.append(route_id)
            current_route = route_id

    return RouteResult(
        origin=origin,
        destination=destination,
        stops=path,
        total_stops=len(path) - 1,
        transfers=transfers,
        routes_used=routes_used,
        found=True,
    )


def normalize(text: str) -> str:
    """Remove accents for fuzzy matching."""
    return (
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def search_station(G: nx.MultiDiGraph, query: str) -> list[str]:
    """
    Fuzzy station search. Case and accent insensitive.
    Returns station names containing the query string.
    """
    query_normalized = normalize(query)
    return [node for node in G.nodes if query_normalized in normalize(node)]
