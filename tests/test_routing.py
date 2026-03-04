"""
Basic routing tests. Run with: pytest tests/
"""

import networkx as nx # pyrefly: ignore
import pytest

from src.graph import build_graph
from src.routing import find_route, search_station

@pytest.fixture(scope="module")
def graph():
    return build_graph()


def test_graph_builds(graph):
    assert graph.number_of_nodes() > 0
    assert graph.number_of_edges() > 0


def test_same_station(graph):
    result = find_route(graph, "Héroes", "Héroes")
    assert result.found
    assert result.total_stops == 0


def test_known_route(graph):
    # Portal Norte to Portal Sur — should find a path
    result = find_route(
        graph, "Portal Norte – Unicervantes", "Portal Sur - JFK Coop. Financiera"
    )
    assert result.found
    assert result.total_stops > 0
    assert len(result.stops) >= 2


def test_invalid_station(graph):
    result = find_route(graph, "Estacion Fantasma", "Héroes")
    assert not result.found
    assert result.error is not None


def test_fuzzy_search(graph):
    results = search_station(graph, "Portal")
    assert len(results) > 0
    assert all("Portal" in r or "portal" in r.lower() for r in results)


def test_all_stations_reachable(graph):
    # Verify graph is weakly connected (all stations reachable ignoring direction)
    assert nx.is_weakly_connected(graph)

def test_accent_insensitive_search(graph):
    # "Heroes" without accent should find "Héroes"
    results = search_station(graph, "Heroes")
    assert any("Héroes" in r for r in results)


def test_lowercase_search(graph):
    # All lowercase should still match
    results = search_station(graph, "portal norte")
    assert len(results) > 0


def test_partial_name_search(graph):
    # Partial name should return multiple matches
    results = search_station(graph, "Portal")
    assert len(results) > 1


def test_no_match_search(graph):
    # Completely made up station should return empty
    results = search_station(graph, "Estacion Fantasma XYZ")
    assert len(results) == 0


def test_same_origin_destination(graph):
    result = find_route(graph, "Héroes", "Héroes")
    assert result.found
    assert result.total_stops == 0
    assert result.transfers == []


def test_no_path(graph):
    # Force a disconnected scenario with a fake station
    result = find_route(graph, "Estacion Fantasma", "Héroes")
    assert not result.found
    assert result.error is not None


def test_transfer_detection(graph):
    # Portal Norte to Portal Sur requires transfers
    result = find_route(
        graph,
        "Portal Norte – Unicervantes",
        "Portal Sur - JFK Coop. Financiera"
    )
    assert result.found
    assert len(result.transfers) > 0
    assert len(result.routes_used) > 1


def test_route_result_fields(graph):
    # Verify RouteResult has all expected fields populated
    result = find_route(graph, "Héroes", "Portal Usme")
    assert result.found
    assert result.origin == "Héroes"
    assert result.destination == "Portal Usme"
    assert len(result.stops) == result.total_stops + 1
    assert result.routes_used != []
