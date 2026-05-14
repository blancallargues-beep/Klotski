"""
Generador de puzzles de peces lliscants a l'atzar.

Estratègia:
  1. Escull dimensions del taulell (entre 3x3 i 5x5).
  2. Col·loca peces aleatòries (poliominós de fins a mida 4) fins que
     omplim un percentatge del taulell.
  3. Assegura que la primera peça (la peça objectiu) tingui una
     posició final accessible.
  4. Avalua el puzzle generat i descarta els que no arribin a un
     llindar mínim de qualitat.
  5. Guarda el millor puzzle trobat.

Ús:
  python src/generate.py                         # Genera 1 puzzle i el mostra
  python src/generate.py -n 20                   # Intenta 20 i guarda el millor
  python src/generate.py -n 20 -o puzzle.json    # Guarda el millor en un fitxer
  python src/generate.py -n 20 --min-score 2.0   # Llindar mínim de qualitat
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from eval import compute_measures, score
from graph import build_graph
from logic import is_goal, valid_placement
from puzzle import Piece, Puzzle, State

# Poliominós canònics de mida 1 a 4 (coordenades relatives)
POLYOMINOES: list[tuple[tuple[int, int], ...]] = [
    # Mida 1
    ((0, 0),),
    # Mida 2
    ((0, 0), (0, 1)),   # vertical
    ((0, 0), (1, 0)),   # horitzontal
    # Mida 3
    ((0, 0), (0, 1), (0, 2)),   # I vertical
    ((0, 0), (1, 0), (2, 0)),   # I horitzontal
    ((0, 0), (0, 1), (1, 1)),   # L
    ((0, 0), (1, 0), (1, 1)),   # J
    ((0, 0), (0, 1), (1, 0)),   # T
    # Mida 4
    ((0, 0), (0, 1), (0, 2), (0, 3)),   # I vertical
    ((0, 0), (1, 0), (2, 0), (3, 0)),   # I horitzontal
    ((0, 0), (0, 1), (1, 0), (1, 1)),   # quadrat
    ((0, 0), (0, 1), (0, 2), (1, 2)),   # L
    ((0, 0), (0, 1), (0, 2), (1, 0)),   # J mirall
    ((0, 0), (1, 0), (1, 1), (1, 2)),   # L girada
    ((0, 1), (1, 0), (1, 1), (2, 0)),   # S
    ((0, 0), (1, 0), (1, 1), (2, 1)),   # Z
    ((0, 1), (1, 0), (1, 1), (1, 2)),   # T
]


def random_piece() -> Piece:
    """Escull un poliominó canònic a l'atzar."""
    coords = random.choice(POLYOMINOES)
    return Piece(*coords)


def piece_fits(W: int, H: int, piece: Piece, pos: tuple[int, int],
               occupied: set[tuple[int, int]]) -> bool:
    """Comprova si una peça cap al taulell en la posició donada."""
    px, py = pos
    cells = {(px + dx, py + dy) for dx, dy in piece.coords}
    for x, y in cells:
        if x < 0 or x >= W or y < 0 or y >= H:
            return False
    if cells & occupied:
        return False
    return True


def generate_puzzle(
    W: int,
    H: int,
    n_pieces: int,
    rng: random.Random,
) -> Puzzle | None:
    """
    Intenta generar un puzzle vàlid amb les dimensions i nombre de peces donats.
    Retorna None si no aconsegueix col·locar totes les peces.
    """
    pieces: list[Piece] = []
    positions: list[tuple[int, int]] = []
    occupied: set[tuple[int, int]] = set()

    for _ in range(n_pieces):
        # Intentem col·locar una peça a l'atzar en 50 posicions
        placed = False
        for _ in range(50):
            piece = random_piece()
            px = rng.randint(0, W - 1)
            py = rng.randint(0, H - 1)
            pos = (px, py)
            if piece_fits(W, H, piece, pos, occupied):
                pieces.append(piece)
                positions.append(pos)
                cells = {(px + dx, py + dy) for dx, dy in piece.coords}
                occupied |= cells
                placed = True
                break
        if not placed:
            return None

    # L'objectiu és la primera peça: l'ha de poder arribar a alguna cantonada
    goal_candidates = [(0, 0), (W - 2, 0), (0, H - 2), (W - 2, H - 2)]
    rng.shuffle(goal_candidates)

    # Ordenem (forma, posició) per canonicalitzar
    pairs = sorted(zip(pieces, positions))
    pieces_sorted = [p for p, _ in pairs]
    positions_sorted = [pos for _, pos in pairs]

    start = State(tuple(positions_sorted))

    # Intentem trobar un objectiu vàlid (que no solapin ni surti del taulell)
    primary_piece = pieces_sorted[0]
    for gx, gy in goal_candidates:
        goal_pos = (gx, gy)
        cells = {(gx + dx, gy + dy) for dx, dy in primary_piece.coords}
        if all(0 <= x < W and 0 <= y < H for x, y in cells):
            goals = ((0, goal_pos),)
            try:
                puzzle = Puzzle(
                    W=W, H=H,
                    walls=(),
                    pieces=tuple(pieces_sorted),
                    start=start,
                    goals=goals,
                )
                return puzzle
            except ValueError:
                continue

    return None


def try_generate(
    n_attempts: int,
    min_score: float,
    rng: random.Random,
) -> tuple[Puzzle | None, float]:
    """
    Intenta generar puzzles i retorna el millor que superi el llindar de qualitat.
    """
    best_puzzle: Puzzle | None = None
    best_score: float = -1.0

    for attempt in range(n_attempts):
        W = rng.randint(3, 5)
        H = rng.randint(3, 5)
        n_pieces = rng.randint(2, max(2, (W * H) // 3))

        puzzle = generate_puzzle(W, H, n_pieces, rng)
        if puzzle is None:
            continue

        # Avaluem
        try:
            g, state_index, goal_vertices, start_vertices = build_graph(puzzle)
            if not goal_vertices:
                continue  # Irressoluble
            measures = compute_measures(g, goal_vertices, start_vertices)
            if measures["n_moves"] < 2:
                continue  # Massa fàcil
            s = score(measures)
        except Exception:
            continue

        print(f"  Intent {attempt+1}/{n_attempts}: "
              f"{puzzle.W}x{puzzle.H}, {len(puzzle.pieces)} peces, "
              f"puntuació={s:.2f}")

        if s > best_score:
            best_score = s
            best_puzzle = puzzle

        if best_score >= min_score and attempt >= n_attempts // 2:
            break

    return best_puzzle, best_score


def main() -> None:
    args = sys.argv[1:]

    n_attempts = 10
    output_path: Path | None = None
    min_score = 1.0
    seed: int | None = None

    i = 0
    while i < len(args):
        if args[i] == "-n" and i + 1 < len(args):
            n_attempts = int(args[i + 1])
            i += 2
        elif args[i] == "-o" and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        elif args[i] == "--min-score" and i + 1 < len(args):
            min_score = float(args[i + 1])
            i += 2
        elif args[i] == "--seed" and i + 1 < len(args):
            seed = int(args[i + 1])
            i += 2
        else:
            i += 1

    rng = random.Random(seed)

    print(f"Generant puzzles ({n_attempts} intents, llindar={min_score:.1f})...\n")
    puzzle, best = try_generate(n_attempts, min_score, rng)

    if puzzle is None:
        print("\nNo s'ha pogut generar cap puzzle vàlid.")
        sys.exit(1)

    print(f"\nMillor puzzle trobat: {puzzle.W}x{puzzle.H}, "
          f"{len(puzzle.pieces)} peces, puntuació={best:.2f}")

    puzzle_json = json.dumps(json.loads(puzzle.to_json()), indent=2)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(puzzle_json)
        print(f"Puzzle guardat a: {output_path}")
    else:
        print("\nPuzzle generat:")
        print(puzzle_json)


if __name__ == "__main__":
    main()