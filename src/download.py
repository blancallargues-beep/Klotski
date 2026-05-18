"""
Eina per descarregar puzzles del repositori compartit.

Ús:
  python src/download.py                  # Llista els 100 puzzles millor valorats
  python src/download.py <id>             # Descarrega un puzzle per ID
  python src/download.py <id> -o fitxer  # Descarrega i guarda en un fitxer concret
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from puzzle import Puzzle

BASE_URL = "https://klotski.pauek.dev"


def list_puzzles() -> list[dict]:
    """Retorna la llista dels 100 puzzles amb millor valoració."""
    url = f"{BASE_URL}/api/puzzles"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


def download_puzzle(puzzle_id: str) -> tuple[Puzzle, str]:
    """Descarrega un puzzle per ID i el retorna com a objecte Puzzle."""
    url = f"{BASE_URL}/api/puzzles/{puzzle_id}"
    with urllib.request.urlopen(url) as response:
        data = response.read().decode()

    # ✅ FIX: l'API retorna {"puzzle": {...}, "stars": ...}
    # cal extreure el camp "puzzle" abans de passar-ho a Puzzle.from_json
    parsed = json.loads(data)
    if isinstance(parsed, dict) and "puzzle" in parsed:
        puzzle_json = json.dumps(parsed["puzzle"])
    else:
        puzzle_json = data  # format antic sense wrapper

    return Puzzle.from_json(puzzle_json), puzzle_json


def main() -> None:
    args = sys.argv[1:]

    # Sense arguments: llista els puzzles disponibles
    if not args:
        print("Descarregant llista de puzzles...\n")
        puzzles = list_puzzles()
        # L'API pot retornar llista de strings (IDs) o de diccionaris
        if puzzles and isinstance(puzzles[0], str):
            print(f"{'ID':>40}")
            print("-" * 42)
            for pid in puzzles:
                print(f"{pid:>40}")
        else:
            print(f"{'ID':>20}  {'Valoració':>10}  {'Autor'}")
            print("-" * 60)
            for p in puzzles:
                pid = p.get("id", "?")
                rating = p.get("rating", 0.0)
                author = p.get("author", "desconegut")
                print(f"{pid:>20}  {rating:>10.2f}  {author}")
        print(f"\nTotal: {len(puzzles)} puzzles")
        return

    # Primer argument: ID del puzzle
    puzzle_id = args[0]

    # Argument opcional -o per especificar el fitxer de sortida
    output_path: Path | None = None
    if "-o" in args:
        idx = args.index("-o")
        if idx + 1 >= len(args):
            print("Error: cal especificar un fitxer després de -o", file=sys.stderr)
            sys.exit(1)
        output_path = Path(args[idx + 1])
    else:
        output_path = Path("puzzles") / f"{puzzle_id}.json"

    print(f"Descarregant puzzle '{puzzle_id}'...")
    try:
        puzzle, puzzle_json = download_puzzle(puzzle_id)
    except urllib.error.HTTPError as e:
        print(f"Error HTTP {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error de connexió: {e.reason}", file=sys.stderr)
        sys.exit(1)

    # Guardem el JSON formatat per llegibilitat
    formatted = json.dumps(json.loads(puzzle_json), indent=2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(formatted)

    print(f"Puzzle guardat a: {output_path}")
    print(f"  Taulell: {puzzle.W}x{puzzle.H}")
    print(f"  Peces: {len(puzzle.pieces)}")
    print(f"  Parets: {len(puzzle.walls)}")
    print(f"  Objectius: {len(puzzle.goals)}")


if __name__ == "__main__":
    main()