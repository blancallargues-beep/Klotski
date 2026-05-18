"""
Envia la valoració d'un puzzle al repositori compartit.

Ús:
  python src/rate.py <id> <valoració> <token>

  <id>        : Identificador del puzzle al repositori
  <valoració> : Puntuació entre 0 i 5 (enter)
  <token>     : Token d'autenticació personal

Exemple:
  python src/rate.py abc123 4 el_meu_token
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "https://klotski.pauek.dev"


def send_rating(puzzle_id: str, rating: float, token: str) -> None:
    """Envia la valoració d'un puzzle al repositori."""
    url = f"{BASE_URL}/api/puzzles/{puzzle_id}/votes"
    data = json.dumps({"stars": round(rating)}).encode()  # ✅ FIX: stars (int) en lloc de rating
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
    if len(args) < 3:
        print(__doc__)
        sys.exit(1)

    puzzle_id = args[0]
    try:
        rating = float(args[1])
    except ValueError:
        print(f"Error: la valoració ha de ser un número (0–5), rebut: '{args[1]}'",
              file=sys.stderr)
        sys.exit(1)

    if not 0.0 <= rating <= 5.0:
        print(f"Error: la valoració ha d'estar entre 0 i 5, rebut: {rating}",
              file=sys.stderr)
        sys.exit(1)

    token = args[2]
    print(f"Enviant valoració {round(rating)} per al puzzle '{puzzle_id}'...")
    try:
        result = send_rating(puzzle_id, rating, token)
        print(f"Valoració enviada correctament.")
        if result:
            print(f"Resposta del servidor: {result}")
    except urllib.error.HTTPError as e:
        print(f"Error HTTP {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error de connexió: {e.reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()