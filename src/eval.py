"""
Avaluació de l'interès d'un puzzle de peces lliscants.

Mesures sobre el graf que permeten estimar la dificultat i interès del puzzle:

  1. n_states      : Nombre total d'estats accessibles (mida de l'espai).
  2. n_moves       : Nombre mínim de moviments per resoldre'l.
  3. branching_avg : Mitjana de moviments possibles per estat (ramificació).
  4. n_goals       : Nombre d'estats finals (menys = més precís/difícil).
  5. diameter      : Diàmetre del graf (màxim de les distàncies mínimes, aproximat).
  6. n_bridges     : Nombre de ponts (arestes la supressió de les quals desconnecta el graf).

La puntuació final (0.0 a 5.0) combina aquestes mesures:
  - Puzzles grans i amb poques solucions alternatives puntuen més.
  - Puzzles amb molts ponts (estructura lineal) puntuen més.
  - Puzzles on el camí mínim és llarg respecte al total puntuen més.

Ús:
  python src/eval.py <puzzle.json>
"""

from __future__ import annotations

import sys
from pathlib import Path

import graph_tool.all as gt

from graph import build_graph
from puzzle import Puzzle


def compute_measures(
    g: gt.Graph,
    goal_vertices: list[int],
    start_vertices: list[int],
) -> dict:
    """Calcula les mesures sobre el graf del puzzle."""
    n_states = g.num_vertices()
    n_edges = g.num_edges()
    start_v = start_vertices[0]

    # Distàncies des de l'estat inicial
    dist_map = gt.shortest_distance(g, source=g.vertex(start_v))
    all_dists = [int(dist_map[v]) for v in g.vertices()]
    # Distància a la solució més propera
    n_moves = (
        min(int(dist_map[g.vertex(gv)]) for gv in goal_vertices)
        if goal_vertices
        else -1
    )

    # Ramificació mitjana = 2 * arestes / vèrtexs (grau mig)
    branching_avg = (2 * n_edges / n_states) if n_states > 0 else 0.0

    # Nombre d'estats finals
    n_goals = len(goal_vertices)

    # Diàmetre: màxim de les distàncies mínimes (exclou infinits)
    finite_dists = [d for d in all_dists if d < 2**30]
    diameter = max(finite_dists) if finite_dists else 0

    # Nombre de ponts (arestes que desconnecten el graf si s'eliminen)
    bridges = list(gt.label_biconnected_components(g)[1])
    n_bridges = sum(1 for e in g.edges() if bridges[e] == 1)

    return {
        "n_states": n_states,
        "n_moves": n_moves,
        "branching_avg": round(branching_avg, 3),
        "n_goals": n_goals,
        "diameter": diameter,
        "n_bridges": n_bridges,
    }


def score(measures: dict) -> float:
    """
    Puntua el puzzle de 0.0 a 5.0 combinant les mesures.

    Criteris:
      - Molts estats i camí llarg indiquen complexitat.
      - Pocs estats finals (solucions úniques) indica precisió.
      - Molts ponts indica una estructura amb fases ben definides.
    """
    n_states = measures["n_states"]
    n_moves = measures["n_moves"]
    n_goals = measures["n_goals"]
    diameter = measures["diameter"]
    n_bridges = measures["n_bridges"]

    if n_moves < 0:
        return 0.0  # Puzzle irressoluble

    # Normalitzem cada factor entre 0 i 1 amb funcions suaus

    # Factor 1: complexitat (n_states) - logarítmica
    import math
    f_states = min(1.0, math.log1p(n_states) / math.log1p(5000))

    # Factor 2: camí mínim llarg
    f_moves = min(1.0, n_moves / 50.0)

    # Factor 3: pocs estats finals (menys = millor)
    f_goals = 1.0 / (1.0 + math.log1p(n_goals))

    # Factor 4: ponts (estructura de fases)
    f_bridges = min(1.0, n_bridges / 20.0)

    # Factor 5: camí llarg respecte al diàmetre (eficiència)
    f_path_ratio = (n_moves / diameter) if diameter > 0 else 0.0

    # Pesos de cada factor
    score_raw = (
        0.35 * f_states
        + 0.30 * f_moves
        + 0.15 * f_goals
        + 0.10 * f_bridges
        + 0.10 * f_path_ratio
    )

    return round(min(5.0, score_raw * 5.0), 2)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    puzzle_path = Path(args[0])
    if not puzzle_path.exists():
        print(f"Error: no s'ha trobat '{puzzle_path}'", file=sys.stderr)
        sys.exit(1)

    puzzle = Puzzle.from_json(puzzle_path.read_text())
    print(f"Avaluant '{puzzle_path.name}'...")

    g, state_index, goal_vertices, start_vertices = build_graph(puzzle)
    measures = compute_measures(g, goal_vertices, start_vertices)
    rating = score(measures)

    print()
    print("Mesures del graf:")
    print(f"  Estats accessibles  : {measures['n_states']}")
    print(f"  Moviments mínims    : {measures['n_moves']}")
    print(f"  Ramificació mitjana : {measures['branching_avg']:.3f}")
    print(f"  Estats finals       : {measures['n_goals']}")
    print(f"  Diàmetre (aprox.)   : {measures['diameter']}")
    print(f"  Ponts               : {measures['n_bridges']}")
    print()
    print(f"Puntuació estimada: {'⭐' * round(rating)} ({rating:.2f}/5.00)")


if __name__ == "__main__":
    main()