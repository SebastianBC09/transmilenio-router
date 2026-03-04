# Transmilenio Router

A graph-based routing engine for Bogotá's Transmilenio BRT system. Finds optimal routes across the network using Dijkstra's algorithm — outperforming official apps by treating the entire network as a graph rather than doing simple route lookups.

## Why This Exists

The official Transmilenio apps use rigid, route-based navigation. When no single route connects two stations, they either fail or return suboptimal paths of 14+ stops. This engine models the full network as a directed graph and finds the globally shortest path across all routes simultaneously — consistently returning 6-stop routes where official apps return 14+.

## How It Works

- **Stations** are graph nodes (141 total)
- **Consecutive stops** within a route are directed edges with weight = 1
- **Transfers** are implicit — any station served by multiple routes is automatically a transfer point
- **Dijkstra's algorithm** finds the shortest path by stop count across the entire network

## Graph Stats

| Metric | Value |
|---|---|
| Stations (nodes) | 141 |
| Trunk lines | 12 |
| Routes (edges) | 89 |
| Network | Weakly connected |

## Project Structure

```
transmilenio-router/
├── data/
│   ├── raw/                  # Original CSVs — never modify
│   └── processed/            # Cleaned data used by the app
│       ├── trunk_lines.csv
│       ├── stations.csv
│       └── routes.csv
├── notebooks/
│   └── 01_eda.ipynb          # Network analysis and visualizations
├── src/
│   ├── __init__.py
│   ├── graph.py              # Graph construction (MultiDiGraph)
│   ├── routing.py            # Dijkstra pathfinding + fuzzy search
│   └── nlp.py                # LLM interface layer (v2)
├── tests/
│   └── test_routing.py       # 14 tests covering edge cases
├── main.py                   # CLI entry point
├── pyproject.toml
└── requirements.txt
```

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/transmilenio-router.git
cd transmilenio-router

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

## Usage

```bash
# Basic route
python main.py "Portal Norte" "Portal Sur"

# Accent-insensitive fuzzy matching
python main.py "Heroes" "Usme"

# Lowercase works too
python main.py "portal norte" "portal sur"
```

Example output:
```
Route: Héroes → Portal Usme
Total stops: 5
Routes used: H27, H20
Transfers at: Calle 40 Sur

Stop sequence:
  1. Héroes
  2. Calle 34
  3. AV. Jiménez - Caracas
  4. Calle 40 Sur
  5. Molinos
  6. Portal Usme
```

## Technical Decisions

**Why Dijkstra over A\*?**
The graph has 141 nodes and 89 routes. At this scale Dijkstra's O((V+E) log V) is fast enough that a heuristic offers no meaningful gain. A* requires a spatial heuristic (geographic distance) which adds complexity without benefit.

**Why MultiDiGraph?**
Multiple routes can serve the same station pair (parallel corridors). MultiDiGraph preserves all route options as separate edges, giving Dijkstra more paths to evaluate.

**Why stop count as edge weight?**
Schedule data would produce more realistic weights but requires a separate data pipeline. Stop count is a reasonable proxy for travel time and keeps v1 simple. v3 will replace this with time-based weights.

**Why NetworkX?**
v1 priority is correctness and data modeling, not performance. NetworkX is battle-tested and sufficient for this graph size.

## Running Tests

```bash
pytest tests/ -v
```

14 tests covering: graph construction, known routes, fuzzy search, accent-insensitive matching, transfer detection, edge cases (same station, invalid station, no path).

## Data Source

Open data published by the Distrito de Bogotá. Street-level non-system stops were excluded. Routes D81, K86, L81, L82, M82, M84, M85, M86, C84, P85, A61 excluded as feeder/street-stop routes outside the trunk system.

## Roadmap

| Version | Description | Status |
|---|---|---|
| v1 | Static graph, stop-count weights, CLI | ✅ Complete |
| v2 | NLP natural language interface (Groq/Mistral) | 🔜 Next |
| v3 | Time-based edge weights from schedule data | Planned |
| v4 | Frontend — Angular + NestJS API | Planned |
| v5 | SITP integration | Planned |

## What I Would Do Differently

- Use GTFS format from the start — it provides stop sequences, schedules, and coordinates in a standardized schema
- Add geographic coordinates to nodes for spatial queries and map visualization
- Model transfer penalties explicitly (e.g. +2 stop equivalents per transfer) to discourage unnecessarily transfer-heavy routes
