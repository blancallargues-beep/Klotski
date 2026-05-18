"""
Descarrega tots els puzzles del repositori, els avalua automàticament
i envia les valoracions al servidor.

Útil per mantenir el rànking actualitzat quan apareixen puzzles nous
o quan es millora l'algorisme de puntuació.

Ús:
  python src/rate_all.py <token>                  # Avalua i valora tots els puzzles
  python src/rate_all.py <token> --dry-run        # Avalua però no envia res
  python src/rate_all.py <token> --min-score 2.0  # Només envia si supera el llindar
  python src/rate_all.py <token> --delay 1.5      # Espera entre peticions (segons)
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from download import list_puzzles, download_puzzle
from eval import compute_measures, score
from graph import build_graph
from puzzle import Puzzle

BASE_URL = "https://klotski.pauek.dev"


def send_rating(puzzle_id: str, rating: float, token: str) -> dict:
    """Envia la valoració d'un puzzle al repositori."""
    url = f"{BASE_URL}/api/puzzles/{puzzle_id}/votes"
    data = json.dumps({"stars": round(rating)}).encode()
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def evaluate_puzzle(puzzle: Puzzle, max_states: int = 3000) -> tuple[float, dict]:
    """Construeix el graf, calcula les mesures i retorna la puntuació."""
    g, state_index, goal_vertices, start_vertices = build_graph(puzzle, max_states=max_states)
    measures = compute_measures(puzzle, g, goal_vertices, start_vertices)
    s = score(measures)
    return s, measures


def rate_all(
    token: str,
    dry_run: bool = False,
    min_score: float = 0.0,
    delay: float = 1.0,
) -> None:
    """
    Descarrega tots els puzzles, els avalua i envia les valoracions.

    Args:
        token:     Token d'autenticació personal.
        dry_run:   Si True, avalua però no envia res al servidor.
        min_score: Només envia la valoració si supera aquest llindar.
        delay:     Segons d'espera entre peticions al servidor.
    """
    print("Descarregant llista de puzzles...")
    try:
        puzzles_info = list_puzzles()
    except urllib.error.URLError as e:
        print(f"Error de connexió: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # L'API pot retornar llista de strings (IDs) o de diccionaris
    if puzzles_info and isinstance(puzzles_info[0], str):
        puzzles_info = [{"id": pid, "rating": 0.0, "author": "desconegut"} for pid in puzzles_info]

    total = len(puzzles_info)
    print(f"Puzzles trobats: {total}\n")

    if dry_run:
        print("⚠️  Mode --dry-run actiu: no s'enviarà cap valoració.\n")

    results: list[dict] = []
    errors: list[str] = []

    for i, info in enumerate(puzzles_info, 1):
        pid = info.get("id", "?")
        current_rating = info.get("rating", 0.0)
        author = info.get("author", "desconegut")

        print(f"[{i:3d}/{total}] {pid[:16]}... (autor: {author}, "
              f"valoració actual: {current_rating:.2f})")

        # Descarreguem el puzzle
        try:
            puzzle, _ = download_puzzle(pid)
        except urllib.error.HTTPError as e:
            msg = f"  ✗ Error HTTP {e.code} en descarregar"
            print(msg)
            errors.append(f"{pid}: {msg}")
            time.sleep(delay)
            continue
        except urllib.error.URLError as e:
            msg = f"  ✗ Error de connexió: {e.reason}"
            print(msg)
            errors.append(f"{pid}: {msg}")
            time.sleep(delay)
            continue
        except Exception as e:
            msg = f"  ✗ Error inesperat: {e}"
            print(msg)
            errors.append(f"{pid}: {msg}")
            continue

        # Avaluem el puzzle
        try:
            s, measures = evaluate_puzzle(puzzle)
        except Exception as e:
            msg = f"  ✗ Error en avaluar: {e}"
            print(msg)
            errors.append(f"{pid}: {msg}")
            continue

        stars = "⭐" * round(s)
        bottleneck = measures.get("bottleneck_ratio", 0.0)
        print(f"  Puntuació: {stars} ({s:.2f}/5.00) | "
              f"estats={measures['n_states']}, "
              f"moviments={measures['n_moves']}, "
              f"ponts={bottleneck:.3f}")

        results.append({
            "id": pid,
            "score": s,
            "measures": measures,
            "author": author,
        })

        # Enviem la valoració
        if s < min_score:
            print(f"  → Omès (puntuació {s:.2f} < llindar {min_score:.2f})")
        elif dry_run:
            print(f"  → [dry-run] S'enviaria valoració {s:.2f}")
        else:
            try:
                send_rating(pid, s, token)
                print(f"  ✓ Valoració {s:.2f} enviada")
            except urllib.error.HTTPError as e:
                msg = f"  ✗ Error HTTP {e.code} en enviar valoració"
                print(msg)
                errors.append(f"{pid}: {msg}")
            except urllib.error.URLError as e:
                msg = f"  ✗ Error de connexió: {e.reason}"
                print(msg)
                errors.append(f"{pid}: {msg}")

        time.sleep(delay)

    # Resum final
    print("\n" + "=" * 60)
    print("RESUM FINAL")
    print("=" * 60)
    print(f"Puzzles processats: {len(results)}/{total}")
    if errors:
        print(f"Errors: {len(errors)}")
        for err in errors:
            print(f"  · {err}")

    if results:
        scores = [r["score"] for r in results]
        print(f"\nPuntuació mitjana: {sum(scores)/len(scores):.2f}/5.00")
        print(f"Puntuació màxima: {max(scores):.2f}/5.00")
        print(f"Puntuació mínima: {min(scores):.2f}/5.00")

        # Rànking dels millors
        top = sorted(results, key=lambda r: r["score"], reverse=True)[:5]
        print("\nTop 5 puzzles:")
        for rank, r in enumerate(top, 1):
            print(f"  {rank}. {r['id'][:20]:20s}  {r['score']:.2f}⭐  "
                  f"({r['measures']['n_moves']} moviments)")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    token = args[0]
    dry_run = "--dry-run" in args
    delay = 1.0
    min_score = 0.0

    i = 1
    while i < len(args):
        if args[i] == "--delay" and i + 1 < len(args):
            delay = float(args[i + 1])
            i += 2
        elif args[i] == "--min-score" and i + 1 < len(args):
            min_score = float(args[i + 1])
            i += 2
        else:
            i += 1

    rate_all(token=token, dry_run=dry_run, min_score=min_score, delay=delay)


if __name__ == "__main__":
    main()