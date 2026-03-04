"""
Pathfinding logic for the Transmilenio routing engine.

Uses Dijkstra's algorithm via NetworkX. Edge weights are stop counts (1 per edge in v1).
Transfer points are handled implicitly — any station in multiple routes is a natural transfer.
"""

import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

import networkx as nx
from networkx.algorithms.shortest_paths.generic import shortest_path
from networkx.exception import NetworkXNoPath

# How many extra stops is one transfer worth in the scoring function.
# Raise to prefer fewer transfers even at the cost of more stops.
# Lower to prefer fewer stops even at the cost of more transfers.
TRANSFER_WEIGHT = 2

# Penalty values to test — each produces a different candidate path.
# The best-scoring candidate wins.
PENALTY_SWEEP = [1, 2, 3, 4, 5]

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


def _build_transfer_graph(G: nx.MultiDiGraph, penalty: int) -> nx.DiGraph:
    """
    Build a transfer-aware DiGraph from the route MultiDiGraph.

    Each node is a (station, route_id) tuple.
    Moving along a route costs weight=1 per stop.
    Switching routes at the same station costs `penalty`.
    """
    TG = nx.DiGraph()
    edge_list = list(G.edges(data=True))

    for u, v, data in edge_list:
        TG.add_edge((u, data["route_id"]), (v, data["route_id"]), weight=1)

    station_routes: dict[str, set[str]] = {}
    for u, v, data in edge_list:
        for station in (u, v):
            station_routes.setdefault(station, set()).add(data["route_id"])

    transfer_edges = []
    for station, route_set in station_routes.items():
        route_list = list(route_set)
        for i in range(len(route_list)):
            for j in range(len(route_list)):
                if i != j:
                    transfer_edges.append(
                        ((station, route_list[i]), (station, route_list[j]), penalty)
                    )
    for src, dst, w in transfer_edges:
        TG.add_edge(src, dst, weight=w)

    return TG


def _extract_path(
    TG: nx.DiGraph, origin: str, destination: str
) -> tuple[list[str], list[str]] | tuple[None, None]:
    """
    Run Dijkstra on the transfer graph and extract station path and routes used.
    Returns (stops, routes_used) or (None, None) if no path exists.
    """
    vo, vd = "__origin__", "__dest__"
    tg_nodes = list(TG.nodes)

    for node in tg_nodes:
        if isinstance(node, tuple):
            if node[0] == origin:
                TG.add_edge(vo, node, weight=0)
            if node[0] == destination:
                TG.add_edge(node, vd, weight=0)

    try:
        raw = shortest_path(TG, source=vo, target=vd, weight="weight")
    except NetworkXNoPath:
        return None, None

    stops: list[str] = []
    routes_used: list[str] = []
    transfers: list[str] = []
    current_route: Optional[str] = None

    for node in raw:
        if node in (vo, vd):
            continue
        station, route_id = node
        if not stops or stops[-1] != station:
            stops.append(station)
        if route_id != current_route:
            if current_route is not None:
                transfers.append(station)
            routes_used.append(route_id)
            current_route = route_id

    return stops, routes_used


def find_route(G: nx.MultiDiGraph, origin: str, destination: str) -> RouteResult:
    """
    Find the optimal path between two stations.

    Runs Dijkstra with multiple transfer penalty values and picks the
    candidate with the best combined score:

        score = stops + (transfers * TRANSFER_WEIGHT)

    This simultaneously minimizes stops and transfers without hard-coding
    a preference for either — the scoring function balances both.

    Args:
        G: The Transmilenio graph built by build_graph()
        origin: Exact station name (case-sensitive)
        destination: Exact station name (case-sensitive)

    Returns:
        RouteResult with path details, transfer points, and routes used.
    """
    if origin not in G:
        return RouteResult(
            origin, destination, [], 0, [], [], False,
            f"Station not found: {origin}"
        )
    if destination not in G:
        return RouteResult(
            origin, destination, [], 0, [], [], False,
            f"Station not found: {destination}"
        )
    if origin == destination:
        return RouteResult(origin, destination, [origin], 0, [], [], True)

    best_stops: Optional[list[str]] = None
    best_routes: Optional[list[str]] = None
    best_score = float("inf")

    for penalty in PENALTY_SWEEP:
        TG = _build_transfer_graph(G, penalty)
        stops, routes_used = _extract_path(TG, origin, destination)
        if stops is None or routes_used is None:
            continue
        n_stops = len(stops) - 1
        n_transfers = len(routes_used) - 1
        score = n_stops + (n_transfers * TRANSFER_WEIGHT)
        if score < best_score:
            best_score = score
            best_stops = stops
            best_routes = routes_used

    if best_stops is None or best_routes is None:
        return RouteResult(
            origin, destination, [], 0, [], [], False,
            "No path found between these stations."
        )

    # Reconstruct transfer points from the winning path
    transfers: list[str] = []
    current_route: Optional[str] = None
    stop_route_map: list[str] = []

    # Re-derive transfer stations from routes_used and stops
    # Walk stops and assign routes segment by segment
    transfer_stations: list[str] = []
    if len(best_routes) > 1:
        # We know transfer happened somewhere — re-run winning path to get exact points
        for penalty in PENALTY_SWEEP:
            TG = _build_transfer_graph(G, penalty)
            tg_nodes = list(TG.nodes)
            vo, vd = "__origin__", "__dest__"
            for node in tg_nodes:
                if isinstance(node, tuple):
                    if node[0] == origin: TG.add_edge(vo, node, weight=0)
                    if node[0] == destination: TG.add_edge(node, vd, weight=0)
            try:
                raw = shortest_path(TG, source=vo, target=vd, weight="weight")
            except NetworkXNoPath:
                continue
            # Check if this penalty produced the winning path
            test_stops: list[str] = []
            test_routes: list[str] = []
            test_transfers: list[str] = []
            cur_r = None
            for node in raw:
                if node in (vo, vd): continue
                s, r = node
                if not test_stops or test_stops[-1] != s:
                    test_stops.append(s)
                if r != cur_r:
                    if cur_r is not None:
                        test_transfers.append(s)
                    test_routes.append(r)
                    cur_r = r
            if test_stops == best_stops and test_routes == best_routes:
                transfer_stations = test_transfers
                break

    return RouteResult(
        origin=origin,
        destination=destination,
        stops=best_stops,
        total_stops=len(best_stops) - 1,
        transfers=transfer_stations,
        routes_used=best_routes,
        found=True,
    )


# Abbreviation expansions — maps common user shorthand to canonical forms.
# Order matters: more specific patterns first.
ABBREVIATION_MAP: list[tuple[str, str]] = [
    (r"\bel\s*dorado\b", "el dorado"),
    (r"\beldorado\b", "el dorado"),
    (r"\bav\.?\b", "avenida"),
    (r"\bcl\.?\b", "calle"),
    (r"\bcr\.?\b", "carrera"),
    (r"\bkr\.?\b", "carrera"),
    (r"\bcra\.?\b", "carrera"),
]


def normalize(text: str) -> str:
    """Remove accents and lowercase for fuzzy matching."""
    return (
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def expand_abbreviations(text: str) -> str:
    """
    Normalize and expand common abbreviations for consistent matching.
    Removes dots to avoid artifacts like 'avenida.' after substitution.
    """
    result = normalize(text)
    result = result.replace(".", " ")
    for pattern, replacement in ABBREVIATION_MAP:
        result = re.sub(pattern, replacement, result)
    return re.sub(r"\s+", " ", result).strip()


def search_station(G: nx.MultiDiGraph, query: str) -> list[str]:
    """
    Fuzzy station search with four strategies in order of precision:

    1. Substring match — handles partial names and simple abbreviations
    2. Primary name match — matches only the part before the dash separator
    3. difflib close match on full expanded names — handles typos
    4. difflib close match on primary names only — last resort fallback

    All matching is case and accent insensitive with abbreviation expansion.
    """
    nodes = list(G.nodes)
    query_normalized = normalize(query)
    query_expanded = expand_abbreviations(query)

    # Strategy 1 — substring match
    substring_matches = [
        node for node in nodes
        if query_normalized in normalize(node)
        or query_expanded in expand_abbreviations(node)
    ]
    if substring_matches:
        return substring_matches

    # Strategy 2 — primary name match (before dash separator)
    primary_matches = []
    for node in nodes:
        primary = re.split(r"\s[-–]\s", node)[0]
        if (
            query_normalized in normalize(primary)
            or query_expanded in expand_abbreviations(primary)
        ):
            primary_matches.append(node)
    if primary_matches:
        return primary_matches

    # Strategy 3 — difflib on full expanded names
    expanded_nodes = {expand_abbreviations(node): node for node in nodes}
    close = difflib.get_close_matches(
        query_expanded, expanded_nodes.keys(), n=3, cutoff=0.55
    )
    if close:
        return [expanded_nodes[c] for c in close]

    # Strategy 4 — difflib on primary names only
    primary_map = {
        expand_abbreviations(re.split(r"\s[-–]\s", node)[0]): node
        for node in nodes
    }
    close_primary = difflib.get_close_matches(
        query_expanded, primary_map.keys(), n=3, cutoff=0.55
    )
    return [primary_map[c] for c in close_primary]
