"""
Avaluació de l'interès d'un puzzle de peces lliscants.

Estratègia: BFS sobre l'espai d'estats canònic. Peces amb la mateixa
forma (i que no siguin objectiu) són intercanviables — ordenar les seves
posicions dins cada grup dóna un estat canònic equivalent. Això redueix
dràsticament l'espai: el klotski passa de >500k estats a ~26k.

Gràcies a aquesta reducció, s'explora l'espai COMPLET per a qualsevol
puzzle raonablement complex, sense truncar ni mostrar estimacions.
Per puzzles extremadament grans (>500k estats canònics) s'aplica un
límit de temps de 10s.

Mesures calculades:

  1. n_moves          : Nombre mínim de moviments per resoldre'l (exacte).
  2. indirection      : Ràtio entre el camí real i la distància Manhattan
                        de la peça objectiu ignorant obstacles. Mesura
                        quant de "rodeo" obliguen les peces secundàries.
  3. detour_fraction  : Fracció de passos en el camí òptim que allunyen
                        la peça objectiu de la seva meta. Captura la
                        "contraintuïció": per guanyar primer has d'anar
                        en sentit contrari.
  4. bottleneck_ratio : Fracció d'estats amb un sol veí nou (passadís).
                        Aproxima l'estructura en fases: passadissos =
                        decisions obligatòries sense alternatives.
  5. solution_rarity  : 1 - (n_goals / n_states). Quant de rar és trobar
                        un estat final dins l'espai explorat.

Ús:
  python src/eval.py <puzzle.json>
  python src/eval.py <puzzle.json> --verbose
"""

from __future__ import annotations

import math
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from puzzle import Puzzle

MAX_SECONDS = 10.0
DELTAS = ((0, -1), (0, 1), (1, 0), (-1, 0))


# ---------------------------------------------------------------------------
# Canonicalització per simetria
# ---------------------------------------------------------------------------

def _build_symmetry_groups(puzzle: Puzzle) -> list[list[int]]:
    """
    Retorna els grups de peces intercanviables (mateixa forma, no objectiu).
    Peces objectiu mai es reordenen perquè la seva identitat importa.
    """
    goal_pieces = {i for i, _ in puzzle.goals}
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, piece in enumerate(puzzle.pieces):
        if i not in goal_pieces:
            groups[tuple(piece.coords)].append(i)
    # Només grups amb més d'una peça aporten reducció
    return [g for g in groups.values() if len(g) > 1]


def _canonicalize(key: tuple, sym_groups: list[list[int]]) -> tuple:
    """
    Retorna la forma canònica d'un estat ordenant les posicions
    de les peces intercanviables dins cada grup.
    """
    if not sym_groups:
        return key
    lst = list(key)
    for group in sym_groups:
        positions = sorted((lst[i * 2], lst[i * 2 + 1]) for i in group)
        for rank, i in enumerate(sorted(group)):
            lst[i * 2], lst[i * 2 + 1] = positions[rank]
    return tuple(lst)


# ---------------------------------------------------------------------------
# BFS sobre l'espai canònic
# ---------------------------------------------------------------------------

def _get_moves(
    key: tuple, n: int, pieces: list, walls: set, W: int, H: int,
    sym_groups: list[list[int]],
) -> list[tuple]:
    """
    Calcula tots els moviments vàlids i retorna els estats resultants
    en forma canònica.
    """
    positions = [(key[i * 2], key[i * 2 + 1]) for i in range(n)]
    all_cells: set = set(walls)
    piece_cells: list[frozenset] = []
    for px, py in positions:
        cells = frozenset((px + dx, py + dy) for dx, dy in pieces[len(piece_cells)])
        piece_cells.append(cells)
        all_cells |= cells

    results = []
    for i in range(n):
        others = all_cells - piece_cells[i]
        px, py = positions[i]
        for ddx, ddy in DELTAS:
            if all(
                0 <= cx + ddx < W
                and 0 <= cy + ddy < H
                and (cx + ddx, cy + ddy) not in others
                for cx, cy in piece_cells[i]
            ):
                nk = list(key)
                nk[i * 2] += ddx
                nk[i * 2 + 1] += ddy
                results.append(_canonicalize(tuple(nk), sym_groups))
    return results


def compute_measures(puzzle: Puzzle) -> dict:
    """
    BFS sobre l'espai d'estats canònic. Explora l'espai complet per
    a puzzles normals; s'atura per límit de temps per puzzles extrems.
    """
    if not puzzle.goals:
        return {"n_states": 0, "n_moves": -1, "sampled": False}

    W, H = puzzle.W, puzzle.H
    n = len(puzzle.pieces)
    pieces = [tuple(p.coords) for p in puzzle.pieces]
    walls = set(puzzle.walls)
    goals = puzzle.goals
    goal_piece_idx, goal_pos = goals[0]
    sym_groups = _build_symmetry_groups(puzzle)

    def to_key(positions) -> tuple:
        return _canonicalize(
            tuple(c for pos in positions for c in pos), sym_groups
        )

    def is_goal(key: tuple) -> bool:
        return all(key[i * 2] == px and key[i * 2 + 1] == py for i, (px, py) in goals)

    start_key = to_key(puzzle.start.positions)
    dist: dict[tuple, int] = {start_key: 0}
    parent: dict[tuple, tuple | None] = {start_key: None}
    queue: deque[tuple] = deque([start_key])

    n_goals_found = 0
    nearest_goal: tuple | None = None
    nearest_goal_dist = 10 ** 9
    n_corridor = 0
    sampled = False
    t0 = time.monotonic()

    while queue:
        if len(dist) % 5000 == 0 and time.monotonic() - t0 > MAX_SECONDS:
            sampled = True
            break

        key = queue.popleft()
        d = dist[key]

        if is_goal(key):
            n_goals_found += 1
            if d < nearest_goal_dist:
                nearest_goal_dist = d
                nearest_goal = key

        neighbors_new = 0
        for nk in _get_moves(key, n, pieces, walls, W, H, sym_groups):
            if nk not in dist:
                neighbors_new += 1
                dist[nk] = d + 1
                parent[nk] = key
                queue.append(nk)

        if neighbors_new == 1:
            n_corridor += 1

    n_states = len(dist)

    if nearest_goal is None:
        return {
            "n_states": n_states,
            "n_moves": -1,
            "indirection": 0.0,
            "detour_fraction": 0.0,
            "bottleneck_ratio": 0.0,
            "solution_rarity": 1.0,
            "n_goals": 0,
            "sampled": sampled,
        }

    n_moves = nearest_goal_dist

    # --- Indirection ---
    sx, sy = puzzle.start.positions[goal_piece_idx]
    gx, gy = goal_pos
    manhattan = max(abs(sx - gx) + abs(sy - gy), 1)
    indirection = n_moves / manhattan

    # --- Detour fraction ---
    path: list[tuple] = []
    cur: tuple | None = nearest_goal
    while cur is not None:
        path.append(cur)
        cur = parent.get(cur)
    path.reverse()

    detour_steps = 0
    for i in range(len(path) - 1):
        ax, ay = path[i][goal_piece_idx * 2], path[i][goal_piece_idx * 2 + 1]
        bx, by = path[i + 1][goal_piece_idx * 2], path[i + 1][goal_piece_idx * 2 + 1]
        d_cur = abs(ax - gx) + abs(ay - gy)
        d_next = abs(bx - gx) + abs(by - gy)
        if d_next > d_cur:
            detour_steps += 1
    detour_fraction = detour_steps / n_moves if n_moves > 0 else 0.0

    # --- Bottleneck ratio ---
    bottleneck_ratio = n_corridor / n_states if n_states > 0 else 0.0

    # --- Solution rarity ---
    solution_rarity = 1.0 - (n_goals_found / n_states) if n_states > 0 else 1.0

    return {
        "n_states": n_states,
        "n_moves": n_moves,
        "indirection": round(indirection, 3),
        "detour_fraction": round(detour_fraction, 3),
        "bottleneck_ratio": round(bottleneck_ratio, 3),
        "solution_rarity": round(solution_rarity, 4),
        "n_goals": n_goals_found,
        "sampled": sampled,
    }


# ---------------------------------------------------------------------------
# Puntuació
# ---------------------------------------------------------------------------

def score(m: dict) -> float:
    """
    Puntua el puzzle de 0.0 a 5.0.

    Justificació dels pesos:
      - indirection (35%): mesura directa de quant les peces secundàries
        obstaculitzen. Un puzzle amb alta indirecció obliga a pensar
        globalment, no només en la peça objectiu.
      - detour_fraction (30%): captura la contraintuïció. Si el camí òptim
        inclou passos que allunyen l'objectiu, el jugador no pot seguir
        la seva intuïció i necessita planificar endavant.
      - bottleneck_ratio (20%): estructura en fases. Passadissos obligatoris
        donen al puzzle una narrativa clara.
      - solution_rarity (10%): puzzles on la solució és rara dins l'espai
        explorat són més precisos i difícils de trobar per intuïció.
      - n_moves logarítmic (5%): complexitat bruta, amb poc pes perquè
        n_moves sense context no diu res de l'experiència de joc.
    """
    if m.get("n_moves", -1) < 0:
        return 0.0

    f_indirection = min(1.0, (m["indirection"] - 1.0) / 3.0)
    f_detour      = min(1.0, m["detour_fraction"] / 0.3)
    f_bottleneck  = min(1.0, m["bottleneck_ratio"] / 0.15)
    f_rarity      = m["solution_rarity"] ** 2
    f_moves       = min(1.0, math.log1p(m["n_moves"]) / math.log1p(100))

    raw = (
        0.35 * f_indirection
        + 0.30 * f_detour
        + 0.20 * f_bottleneck
        + 0.10 * f_rarity
        + 0.05 * f_moves
    )
    return round(min(5.0, raw * 5.0), 2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    verbose = "--verbose" in args
    args = [a for a in args if a != "--verbose"]

    puzzle_path = Path(args[0])
    if not puzzle_path.exists():
        print(f"Error: no s'ha trobat '{puzzle_path}'", file=sys.stderr)
        sys.exit(1)

    puzzle = Puzzle.from_json(puzzle_path.read_text())
    print(f"Avaluant '{puzzle_path.name}'...")

    t0 = time.monotonic()
    m = compute_measures(puzzle)
    elapsed = time.monotonic() - t0

    rating = score(m)
    note = f" (mostrejat {m['n_states']} estats en {elapsed:.1f}s)" if m.get("sampled") else f" ({elapsed:.2f}s)"
    stars = "⭐" * int(round(rating))

    print(f"\n{'='*44}")
    print(f"ANÀLISI: {stars} ({rating}/5.0){note}")
    print(f"{'='*44}")
    print(f"  Estats canònics   : {m['n_states']}")
    print(f"  Moviments mínims  : {m['n_moves']}")
    print(f"  Indirecció        : {m['indirection']:.3f}  (1.0 = directe, >3.0 = molt obstaculitzat)")
    print(f"  Engany (detour)   : {m['detour_fraction']:.1%}  (passos que allunyen l'objectiu)")
    print(f"  Passadissos       : {m['bottleneck_ratio']:.1%}  (estats sense alternatives)")
    print(f"  Raresa solució    : {m['solution_rarity']:.3f}  (1.0 = solució molt rara)")
    print(f"  Estats finals     : {m['n_goals']}")

    if verbose:
        print("\nInterpretació:")
        if m["n_moves"] < 0:
            print("  ✗ Puzzle irresoluble (o solució fora del temps explorat).")
        else:
            ind = m["indirection"]
            if ind < 1.5:
                print(f"  · Molt directe ({ind:.1f}x): el camí quasi no requereix peces secundàries.")
            elif ind < 3.0:
                print(f"  · Moderadament indirecte ({ind:.1f}x): algunes peces obstaculitzen.")
            else:
                print(f"  · Molt indirecte ({ind:.1f}x): cal reorganitzar molt per resoldre'l.")

            det = m["detour_fraction"]
            if det < 0.1:
                print(f"  · Poc enganyós ({det:.0%}): l'objectiu quasi sempre avança cap a la meta.")
            elif det < 0.3:
                print(f"  · Moderadament enganyós ({det:.0%}): alguns passos van en sentit contrari.")
            else:
                print(f"  · Molt enganyós ({det:.0%}): la peça objectiu s'ha d'allunyar per resoldre'l.")

            bn = m["bottleneck_ratio"]
            if bn < 0.05:
                print(f"  · Sense fases clares ({bn:.0%}): l'espai d'estats és obert.")
            else:
                print(f"  · Estructura en fases ({bn:.0%} de passadissos obligatoris).")

        if m.get("sampled"):
            print(f"\n  ℹ️  Puzzle molt gran: mesures calculades sobre {m['n_states']} estats.")
    print()


if __name__ == "__main__":
    main()