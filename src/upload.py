"""
Envia un puzzle nou al repositori compartit.

Ús:
  python src/upload.py <puzzle.json> <token>

  <puzzle.json> : Fitxer del puzzle en format estàndar
  <token>       : Token d'autenticació personal

Exemple:
  python src/upload.py puzzles/el_meu_puzzle.json el_meu_token
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from puzzle import Puzzle

BASE_URL = "https://klotski.pauek.dev"


def upload_puzzle(puzzle: Puzzle, token: str) -> dict:
    """Envia un puzzle al repositori i retorna la resposta del servidor."""
    url = f"{BASE_URL}/api/puzzles"
    # Enviem el puzzle en el format JSON estàndar (sense indentació, compacte)
    data = puzzle.to_json().encode()
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


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    puzzle_path = Path(args[0])
    if not puzzle_path.exists():
        print(f"Error: no s'ha trobat '{puzzle_path}'", file=sys.stderr)
        sys.exit(1)

    token = args[1]

    puzzle = Puzzle.from_json(puzzle_path.read_text())

    print(f"Enviant '{puzzle_path.name}' al repositori...")
    print(f"  Taulell: {puzzle.W}x{puzzle.H}")
    print(f"  Peces: {len(puzzle.pieces)}")
    print(f"  Hash: {puzzle.hash()[:16]}...")

    try:
        result = upload_puzzle(puzzle, token)
        print("Puzzle enviat correctament!")
        if result:
            pid = result.get("id", "?")
            print(f"  ID assignat: {pid}")
            print(f"  URL: {BASE_URL}/api/puzzles/{pid}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"Error HTTP {e.code}: {e.reason}", file=sys.stderr)
        if body:
            print(f"Detalls: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error de connexió: {e.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()