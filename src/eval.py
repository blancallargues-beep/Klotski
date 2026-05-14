"""
Avaluació de l'interès d'un puzzle de peces lliscants (Versió Millorada).
Analitza la dificultat cognitiva, l'engany i l'estructura estratègica.
"""

from __future__ import annotations
import math
import sys
from pathlib import Path
import graph_tool.all as gt

from graph import build_graph
from puzzle import Puzzle, State

# ---------------------------------------------------------------------------
# Mesures auxiliars
# ---------------------------------------------------------------------------

def _goal_distance_lower_bound(puzzle: Puzzle) -> int:
    """
    Calcula la cota inferior (Manhattan) de la peça objectiu principal.
    Ignora obstacles per saber la distància 'ideal'.
    """
    if not puzzle.goals:
        return 1
    # Prenem el primer objectiu com a referència principal
    idx, g_pos = puzzle.goals[0]
    s_pos = puzzle.start.positions[idx]
    dist = abs(s_pos[0] - g_pos[0]) + abs(s_pos[1] - g_pos[1])
    return max(dist, 1)

def compute_measures(puzzle: Puzzle, g: gt.Graph, goal_vertices: list[int], start_vertices: list[int]) -> dict:
    """Calcula les mètriques d'interès basades en el disseny del joc."""
    n_states = g.num_vertices()
    if n_states == 0:
        return {"n_states": 0, "n_moves": -1}

    start_v = start_vertices[0]
    
    # --- 1. Resolució i Distància ---
    dist_map = gt.shortest_distance(g, source=g.vertex(start_v))
    
    # Trobem el node final més proper accessible
    valid_goals = [gv for gv in goal_vertices if dist_map[gv] < 2**30]
    if not valid_goals:
        return {"n_states": n_states, "n_moves": -1}
    
    nearest_goal_v = min(valid_goals, key=lambda gv: dist_map[gv])
    n_moves = int(dist_map[nearest_goal_v])

    # --- 2. Indirection (Dificultat per obstrucció) ---
    lower_bound = _goal_distance_lower_bound(puzzle)
    indirection = n_moves / lower_bound

    # --- 3. Bottleneck Ratio (Estructura de fases) ---
    # Un node és un 'cut vertex' si la seva eliminació augmenta el nombre de components
    articulation_map = gt.articulation_points(g)
    n_articulation = sum(1 for v in g.vertices() if articulation_map[v])
    bottleneck_ratio = n_articulation / n_states if n_states > 0 else 0.0

    # --- 4. Detour Fraction (Engany / Contraintuïció) ---
    # Analitzem el camí òptim pas a pas
    v_path, e_path = gt.shortest_path(g, g.vertex(start_v), g.vertex(nearest_goal_v))
    detour_steps = 0
    if len(v_path) > 1 and puzzle.goals:
        goal_idx, (gx, gy) = puzzle.goals[0]
        state_prop = g.vp["state"]
        
        for i in range(len(v_path) - 1):
            curr_s = State.from_json(state_prop[v_path[i]])
            next_s = State.from_json(state_prop[v_path[i+1]])
            
            c_pos = curr_s.positions[goal_idx]
            n_pos = next_s.positions[goal_idx]
            
            d_curr = abs(c_pos[0] - gx) + abs(c_pos[1] - gy)
            d_next = abs(n_pos[0] - gx) + abs(n_pos[1] - gy)
            
            if d_next > d_curr: # La peça objectiu s'allunya de la meta
                detour_steps += 1
                
    detour_fraction = detour_steps / n_moves if n_moves > 0 else 0.0

    # --- 5. Solution Rarity (Precisió) ---
    solution_rarity = 1.0 - (len(valid_goals) / n_states)

    return {
        "n_states": n_states,
        "n_moves": n_moves,
        "indirection": round(indirection, 3),
        "bottleneck_ratio": round(bottleneck_ratio, 3),
        "detour_fraction": round(detour_fraction, 3),
        "solution_rarity": round(solution_rarity, 4),
        "n_goals": len(valid_goals)
    }

# ---------------------------------------------------------------------------
# Puntuació Final
# ---------------------------------------------------------------------------

def score(m: dict) -> float:
    """Combina les mètriques en una nota de 0 a 5."""
    if m.get("n_moves", -1) < 0: return 0.0

    # Normalitzacions (ajustades per puzzles reals)
    f_indirection = min(1.0, (m["indirection"] - 1.0) / 5.0) # 6x indirection és ja molt alt
    f_detour = min(1.0, m["detour_fraction"] / 0.4)          # 40% de passos enrere és brutal
    f_bottleneck = min(1.0, m["bottleneck_ratio"] / 0.2)     # 20% de nodes crítics és molta estructura
    f_rarity = m["solution_rarity"]**2                       # Accentua la raresa
    f_moves = min(1.0, math.log1p(m["n_moves"]) / math.log1p(100))

    raw_score = (
        0.35 * f_indirection + 
        0.30 * f_detour + 
        0.20 * f_bottleneck + 
        0.10 * f_rarity + 
        0.05 * f_moves
    )
    return round(min(5.0, raw_score * 5.0), 2)

# ---------------------------------------------------------------------------
# Interfície de sortida
# ---------------------------------------------------------------------------

def print_results(m: dict, rating: float, verbose: bool):
    stars = "⭐" * int(round(rating))
    print(f"\n{'='*40}")
    print(f"ANÀLISI ESTRATÈGIC: {stars} ({rating}/5.0)")
    print(f"{'='*40}")
    print(f"• Complexitat: {m['n_states']} estats, {m['n_moves']} moviments.")
    print(f"• Indirecció:  {m['indirection']}x (esforç vs distància directa)")
    print(f"• Engany:      {m['detour_fraction']:.1%} dels passos són contraintuïtius.")
    print(f"• Estructura:  {m['bottleneck_ratio']:.1%} de punts crítics (fases).")
    print(f"• Precisió:    {m['n_goals']} estats de solució trobats.")

    if verbose:
        print("\nInterpretació:")
        if m['detour_fraction'] > 0.2:
            print("  -> Puzzle ALTAMENT ENGANYÓS. Requereix moure la peça contra la teva intuïció.")
        if m['indirection'] > 4:
            print("  -> Puzzle d'OBSTRUCCIÓ COMPLEXA. Les peces secundàries són el repte real.")
        if m['bottleneck_ratio'] > 0.1:
            print("  -> Estructura NARRATIVA. El puzzle té passos obligatoris molt marcats.")

def main():
    if len(sys.argv) < 2:
        print("Ús: python src/eval.py <puzzle.json> [--verbose]")
        return

    path = Path(sys.argv[1])
    verbose = "--verbose" in sys.argv
    
    puzzle = Puzzle.from_json(path.read_text())
    g, _, goal_v, start_v = build_graph(puzzle)
    
    m = compute_measures(puzzle, g, goal_v, start_v)
    rating = score(m)
    print_results(m, rating, verbose)

if __name__ == "__main__":
    main()
    