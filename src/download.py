"""
Eina per descarregar puzzles del repositori compartit.

Ús:
    python download.py                  # llista els 100 puzzles amb més puntuació
    python download.py <id>             # descarrega un puzzle pel seu ID
    python download.py <id> -o <fitxer> # descarrega i guarda amb un nom concret

El servidor base és https://klotski.pauek.dev.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import urllib.request

BASE_URL = "https://klotski.pauek.dev"


def get_puzzle_list() -> list[str]:
    """Retorna la llista dels IDs dels 100 puzzles amb votació més alta."""
    url = f"{BASE_URL}/api/puzzles"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


def get_puzzle(puzzle_id: str) -> dict:
    """Descarrega un puzzle pel seu ID i retorna el diccionari amb 'puzzle' i 'stars'."""
    url = f"{BASE_URL}/api/puzzles/{puzzle_id}"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


def download_puzzle(puzzle_id: str, output_path: Path | None = None) -> Path:
    """
    Descarrega un puzzle i el guarda en un fitxer JSON.

    Si output_path és None, guarda el fitxer com <id[:12]>.json a la carpeta puzzles/.
    Retorna el camí del fitxer guardat.
    """
    data = get_puzzle(puzzle_id)
    puzzle_json = json.dumps(data["puzzle"], indent=2)

    if output_path is None:
        puzzles_dir = Path("puzzles")
        puzzles_dir.mkdir(exist_ok=True)
        output_path = puzzles_dir / f"{puzzle_id[:12]}.json"

    output_path.write_text(puzzle_json)
    stars = data.get("stars", 0)
    print(f"Desat: {output_path}  ({stars:.2f} ★)")
    return output_path


def main() -> None:
    args = sys.argv[1:]

    # Sense arguments: llista els puzzles disponibles
    if len(args) == 0:
        print("Descarregant llista de puzzles...")
        ids = get_puzzle_list()
        print(f"{len(ids)} puzzles disponibles:")
        for i, puzzle_id in enumerate(ids, 1):
            print(f"  {i:3}. {puzzle_id}")
        return

    # Amb un ID: descarrega el puzzle
    puzzle_id = args[0]

    # Opció -o per especificar el fitxer de sortida
    output_path = None
    if "-o" in args:
        idx = args.index("-o")
        if idx + 1 >= len(args):
            print("Error: cal especificar un fitxer després de -o", file=sys.stderr)
            sys.exit(1)
        output_path = Path(args[idx + 1])

    download_puzzle(puzzle_id, output_path)


if __name__ == "__main__":
    main()