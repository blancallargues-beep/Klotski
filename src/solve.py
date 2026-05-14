"""
Resolució d'un puzzle de peces lliscants.

Fa un BFS des de l'estat inicial i troba el camí més curt fins
a un estat que satisfaci tots els objectius. Guarda la solució
en format JSON (llista de moviments).

Ús:
  python src/solve.py <puzzle.json>              # Mostra la solució per pantalla
  python src/solve.py <puzzle.json> -o sol.json  # Guarda la solució en un fitxer
"""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

from logic import is_goal, possible_moves, apply_move
from puzzle import Puzzle, State

Move = tuple[int, str, int]  # (peça, direcció, distància)


def solve(puzzle: Puzzle) -> list[Move] | None:
    """
    Troba la seqüència de moviments més curta (BFS) per resoldre el puzzle.

    Retorna la llista de moviments o None si el puzzle no té solució.
    """
    if is_goal(puzzle, puzzle.start):
        return []

    # BFS: cua de (estat, moviments_fets)
    # Per estalviar memòria, guardem el pare i el moviment que ha portat fins aquí
    parent: dict[State, tuple[State, Move] | None] = {puzzle.start: None}
    queue: deque[State] = deque([puzzle.start])

    while queue:
        current = queue.popleft()

        for move in possible_moves(puzzle, current):
            next_state = apply_move(puzzle, current, move)

            if next_state in parent:
                continue

            parent[next_state] = (current, move)

            if is_goal(puzzle, next_state):
                # Reconstruïm el camí cap enrere
                path: list[Move] = []
                state = next_state
                while parent[state] is not None:
                    prev, mv = parent[state]
                    path.append(mv)
                    state = prev
                path.reverse()
                return path

            queue.append(next_state)

    return None  # Sense solució


def moves_to_json(moves: list[Move]) -> str:
    """Converteix la llista de moviments al format JSON de l'especificació."""
    return json.dumps([[piece_idx, direction] for piece_idx, direction, _ in moves], indent=2)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    puzzle_path = Path(args[0])
    if not puzzle_path.exists():
        print(f"Error: no s'ha trobat '{puzzle_path}'", file=sys.stderr)
        sys.exit(1)

    output_path: Path | None = None
    if "-o" in args:
        idx = args.index("-o")
        if idx + 1 >= len(args):
            print("Error: cal especificar un fitxer després de -o", file=sys.stderr)
            sys.exit(1)
        output_path = Path(args[idx + 1])

    puzzle = Puzzle.from_json(puzzle_path.read_text())
    print(f"Resolent '{puzzle_path.name}'...")

    solution = solve(puzzle)

    if solution is None:
        print("No s'ha trobat solució.")
        sys.exit(1)

    print(f"Solució trobada en {len(solution)} moviments.")

    sol_json = moves_to_json(solution)

    if output_path:
        output_path.write_text(sol_json)
        print(f"Solució guardada a: {output_path}")
    else:
        print("\nMoviments:")
        for i, (piece_idx, direction, _) in enumerate(solution):
            print(f"  {i+1:3d}. Peça {piece_idx} -> {direction}")


if __name__ == "__main__":
    main()