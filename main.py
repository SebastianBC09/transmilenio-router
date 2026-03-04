"""
Transmilenio Router — CLI entry point

Usage:
    python main.py "Portal Norte" "Portal Sur"
    python main.py --nlp "Como llego de Heroes a Usme?"
"""

import sys

from src.graph import build_graph
from src.routing import find_route, search_station


def run_direct(G, origin_query: str, destination_query: str) -> None:
    """Direct routing mode — exact or fuzzy station names."""

    # Fuzzy match origin
    if origin_query not in G.nodes:
        candidates = search_station(G, origin_query)
        if len(candidates) == 0:
            print(f"Station not found: '{origin_query}'")
            sys.exit(1)
        elif len(candidates) == 1:
            origin_query = candidates[0]
        else:
            print(f"Multiple matches for '{origin_query}':")
            for i, c in enumerate(candidates, 1):
                print(f"  {i}. {c}")
            sys.exit(1)

    # Fuzzy match destination
    if destination_query not in G.nodes:
        candidates = search_station(G, destination_query)
        if len(candidates) == 0:
            print(f"Station not found: '{destination_query}'")
            sys.exit(1)
        elif len(candidates) == 1:
            destination_query = candidates[0]
        else:
            print(f"Multiple matches for '{destination_query}':")
            for i, c in enumerate(candidates, 1):
                print(f"  {i}. {c}")
            sys.exit(1)

    # Find route
    result = find_route(G, origin_query, destination_query)

    if not result.found:
        print(f"No route found: {result.error}")
        sys.exit(1)

    # Print result
    print(f"\nRoute: {result.origin} → {result.destination}")
    print(f"Total stops: {result.total_stops}")
    print(f"Routes used: {', '.join(result.routes_used)}")

    if result.transfers:
        print(f"Transfers at: {', '.join(result.transfers)}")
    else:
        print("No transfers needed")

    print("\nStop sequence:")
    for i, stop in enumerate(result.stops, 1):
        print(f"  {i}. {stop}")


def run_nlp(G, user_input: str) -> None:
    """Natural language mode — free-form query parsed by LLM."""
    from src.nlp import natural_language_route
    print(natural_language_route(G, user_input))


def main() -> None:
    G = build_graph()

    if len(sys.argv) < 2:
        print("Usage:")
        print('  python main.py "<origin>" "<destination>"')
        print('  python main.py --nlp "<natural language query>"')
        sys.exit(1)

    if sys.argv[1] == "--nlp":
        if len(sys.argv) != 3:
            print('Usage: python main.py --nlp "<query>"')
            sys.exit(1)
        run_nlp(G, sys.argv[2])
    else:
        if len(sys.argv) != 3:
            print('Usage: python main.py "<origin>" "<destination>"')
            sys.exit(1)
        run_direct(G, sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
