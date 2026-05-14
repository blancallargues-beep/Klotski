"""
Construcció del graf de l'espai d'estats d'un puzzle de peces lliscants.

Cada node del graf és un estat (disposició de les peces), i dues
disposicions estan connectades per una aresta quan es pot passar
d'una a l'altra movent una sola peça un pas.

Ús:
  python src/graph.py <puzzle.json>              # Mostra estadístiques del graf
  python src/graph.py <puzzle.json> -o graf.graphml  # Guarda el graf en un fitxer
"""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

import graph_tool.all as gt

from logic import is_goal, possible_moves
from puzzle import Puzzle, State

# StateKey és la representació canònica d'un estat com a string JSON,
# que permet identificar un node del graf donat un objecte State.
StateKey = str


def state_key(puzzle: Puzzle, state_or_json: State | str) -> StateKey:
    """
    Retorna la clau canònica d'un estat.

    Accepta tant un objecte State com el JSON en string (tal com
    es guarda a la propietat 'state' dels vèrtexs del graf).
    """
    if isinstance(state_or_json, str):
        return state_or_json
    return state_or_json.to_json()


MAX_STATES = 10_000  # Límit per al generador; evita BFS infinits


def build_graph(
    puzzle: Puzzle,
    max_states: int | None = None,
) -> tuple[gt.Graph, dict[State, int], list[int], list[int]]:
    """
    Construeix el graf de l'espai d'estats del puzzle per BFS.

    Si max_states és un enter, el BFS s'atura quan s'arriba a aquest nombre
    d'estats (útil per al generador, que no necessita el graf complet).

    Retorna:
      - g: el graf (no dirigit)
      - state_index: diccionari de State -> índex de vèrtex
      - goal_vertices: llista d'índexs de vèrtexs que són estat final
      - start_vertices: llista d'1 element amb l'índex del vèrtex inicial
    """
    g = gt.Graph(directed=False)

    # Propietats dels vèrtexs
    vp_is_goal = g.new_vertex_property("bool")
    vp_is_start = g.new_vertex_property("bool")
    # Guardem l'estat serialitzat com a string per poder-lo recuperar
    vp_state = g.new_vertex_property("string")

    g.vp["is_goal"] = vp_is_goal
    g.vp["is_start"] = vp_is_start
    g.vp["state"] = vp_state

    # Propietat global: el puzzle serialitzat (necessari per a 3D_view.py)
    gp_puzzle = g.new_graph_property("string")
    g.gp["puzzle"] = gp_puzzle
    g.gp["puzzle"] = puzzle.to_json()

    state_index: dict[State, int] = {}
    goal_vertices: list[int] = []

    def get_or_create_vertex(state: State) -> int:
        if state in state_index:
            return state_index[state]
        v = int(g.add_vertex())
        state_index[state] = v
        vp_state[v] = state.to_json()
        vp_is_goal[v] = is_goal(puzzle, state)
        vp_is_start[v] = (state == puzzle.start)
        if vp_is_goal[v]:
            goal_vertices.append(v)
        return v

    # BFS des de l'estat inicial
    start_v = get_or_create_vertex(puzzle.start)
    queue: deque[State] = deque([puzzle.start])
    visited: set[State] = {puzzle.start}

    while queue:
        current_state = queue.popleft()
        current_v = state_index[current_state]

        for move in possible_moves(puzzle, current_state):
            piece_idx, direction, _ = move
            dx, dy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[direction]
            px, py = current_state.positions[piece_idx]
            new_positions = list(current_state.positions)
            new_positions[piece_idx] = (px + dx, py + dy)
            next_state = State(tuple(new_positions))

            next_v = get_or_create_vertex(next_state)

            if next_state not in visited:
                if max_states is None or len(visited) < max_states:
                    visited.add(next_state)
                    queue.append(next_state)

            # Afegim l'aresta si no existeix ja (graf no dirigit)
            if not g.edge(current_v, next_v):
                g.add_edge(current_v, next_v)

    return g, state_index, goal_vertices, [start_v]


def graph_stats(g: gt.Graph, goal_vertices: list[int], start_vertices: list[int]) -> None:
    """Mostra estadístiques bàsiques del graf."""
    n_vertices = g.num_vertices()
    n_edges = g.num_edges()
    start_v = start_vertices[0]

    print(f"Vèrtexs (estats): {n_vertices}")
    print(f"Arestes (moviments): {n_edges}")
    print(f"Vèrtex inicial: {start_v}")
    print(f"Vèrtexs finals: {len(goal_vertices)}")

    # Components connexes
    comp, hist = gt.label_components(g)
    print(f"Components connexes: {len(hist)}")

    # Distància mínima fins a un estat final (BFS)
    if goal_vertices:
        dist_map = gt.shortest_distance(g, source=g.vertex(start_v))
        min_dist = min(int(dist_map[g.vertex(gv)]) for gv in goal_vertices)
        print(f"Distància mínima fins la solució: {min_dist} moviments")
    else:
        print("El puzzle no té solució (cap estat final accessible).")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    puzzle_path = Path(args[0])
    if not puzzle_path.exists():
        print(f"Error: no s'ha trobat '{puzzle_path}'", file=sys.stderr)
        sys.exit(1)

    # Argument opcional -o per guardar el graf
    output_path: Path | None = None
    if "-o" in args:
        idx = args.index("-o")
        if idx + 1 >= len(args):
            print("Error: cal especificar un fitxer després de -o", file=sys.stderr)
            sys.exit(1)
        output_path = Path(args[idx + 1])

    puzzle = Puzzle.from_json(puzzle_path.read_text())
    print(f"Construint el graf per '{puzzle_path.name}'...")

    g, state_index, goal_vertices, start_vertices = build_graph(puzzle)

    print()
    graph_stats(g, goal_vertices, start_vertices)

    if output_path:
        g.save(str(output_path))
        print(f"\nGraf guardat a: {output_path}")


if __name__ == "__main__":
    main()