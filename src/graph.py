"""
Graph construction for the Transmilenio routing engine.

Builds a directed multigraph where:
- Nodes represent stations
- Edges connect consecutive stops within a route direction
- Edge attributes store route_id and weight (stop count = 1 per edge in v1)
"""

import pandas as pd
import networkx as nx
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "processed"


def load_data():
    """Load cleaned CSVs from processed data directory."""
    routes = pd.read_csv(DATA_DIR / "routes.csv")
    stations = pd.read_csv(DATA_DIR / "stations.csv")
    return routes, stations


def build_graph() -> nx.MultiDiGraph:
    """
    Build a directed multigraph from processed route data.

    Returns a NetworkX MultiDiGraph where:
    - Each node is a station name (string)
    - Each edge (u, v) represents a direct connection between consecutive stops
    - Edge attributes: route_id (str), weight (int, default=1)

    Using MultiDiGraph allows multiple routes between the same pair of stations,
    which is common in Transmilenio where parallel routes serve the same corridor.
    """
    routes, stations = load_data()

    G = nx.MultiDiGraph()

    # Add all stations as nodes with zone metadata
    station_meta = stations.set_index("Station_Name")[["Zone_ID", "Zone_Name"]].to_dict("index")
    for station, meta in station_meta.items():
        G.add_node(station, zone_id=meta["Zone_ID"], zone_name=meta["Zone_Name"])

    # Add edges from route stop sequences
    for (route_id, direction), group in routes.groupby(["Route_ID", "Final_Destination"]):
        stops = group.sort_values("Stop_Order")["Station_Name"].tolist()
        for i in range(len(stops) - 1):
            G.add_edge(
                stops[i],
                stops[i + 1],
                route_id=route_id,
                direction=direction,
                weight=1,
            )

    return G


def graph_summary(G: nx.MultiDiGraph) -> dict:
    """Return basic statistics about the graph."""
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "is_connected": nx.is_weakly_connected(G),
        "components": nx.number_weakly_connected_components(G),
    }

