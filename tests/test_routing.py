"""
Basic routing tests. Run with: pytest tests/
"""

import pytest
import networkx as nx
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
    result = find_route(graph, "Portal Norte – Unicervantes", "Portal Sur - JFK Coop. Financiera")
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

