"""
Tipus per a trencaclosques de peces lliscants (sliding block puzzles).

Implementa els tipus Piece, State i Puzzle,
amb l'ordenació canònica i la conversió a JSON definides a l'especificació.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

# Una coordenada és una parella (x, y) de naturals (inclòs el 0).
# (0, 0) és la cantonada esquerra a dalt.
# L'ordenació és la de la tupla (x, y): primer per x, després per y.
Coord = tuple[int, int]


@dataclass(frozen=True, order=True)
class Piece:
    """
    Una peça és una llista de coordenades relatives a (0, 0),
    ordenades lexicogràficament i sense repeticions.

    La peça ha d'estar normalitzada: almenys una coordenada té x=0
    i almenys una té y=0 (la peça està el més a l'esquerra i amunt possible).

    L'ordre entre peces és l'ordre lexicogràfic de les seves seqüències
    de coordenades.
    """

    coords: tuple[Coord, ...]

    def __init__(self, *coords: Coord) -> None:
        object.__setattr__(self, "coords", coords)
        if len(self.coords) == 0:
            raise ValueError("Una peça ha de tenir almenys una coordenada")
        for x, y in self.coords:
            if x < 0 or y < 0:
                raise ValueError(f"Coordenada negativa: ({x}, {y})")
        if len(set(self.coords)) != len(self.coords):
            raise ValueError("Coordenades repetides")
        if self.coords != tuple(sorted(self.coords)):
            raise ValueError("Les coordenades no estan ordenades")
        xs = [x for x, y in self.coords]
        ys = [y for x, y in self.coords]
        if min(xs) != 0 or min(ys) != 0:
            raise ValueError("La peça no està normalitzada (min x o min y != 0)")

    @staticmethod
    def normalized(coords: list[Coord]) -> Piece:
        """Crea una peça normalitzada a partir de coordenades arbitràries."""
        if len(coords) == 0:
            raise ValueError("Una peça ha de tenir almenys una coordenada")
        min_x = min(x for x, y in coords)
        min_y = min(y for x, y in coords)
        norm = sorted(set((x - min_x, y - min_y) for x, y in coords))
        return Piece(*norm)

    def _to_obj(self) -> list[list[int]]:
        return [list(c) for c in self.coords]

    def to_json(self) -> str:
        """Retorna la representació JSON de la peça (llista de coordenades)."""
        return json.dumps(self._to_obj())


@dataclass(frozen=True)
class State:
    """
    Una configuració del trencaclosques: una posició per peça,
    en el mateix ordre que les peces del puzzle.
    """

    positions: tuple[Coord, ...]

    def _to_obj(self) -> list[list[int]]:
        return [list(p) for p in self.positions]

    def to_json(self) -> str:
        """Retorna la llista de posicions en JSON."""
        return json.dumps(self._to_obj())

    @classmethod
    def from_json(cls, s: str) -> "State":
        """Crea un State a partir d'un string JSON (llista de posicions)."""
        obj = json.loads(s)
        return cls(positions=tuple(tuple(p) for p in obj))


@dataclass(frozen=True)
class Puzzle:
    """
    Un trencaclosques: dimensions del taulell, parets, peces (formes),
    estat inicial i objectius.

    Les peces estan en ordre canònic: ordenades per (forma, posició_inicial).
    Les parets estan ordenades per coordenada.
    Els objectius estan ordenats per (índex_peça, posició).
    """

    W: int
    H: int
    walls: tuple[Coord, ...]
    pieces: tuple[Piece, ...]
    start: State
    goals: tuple[tuple[int, Coord], ...]

    def __post_init__(self) -> None:
        if self.W <= 0 or self.H <= 0:
            raise ValueError("W i H han de ser positius")
        # Parets ordenades i sense duplicats
        if self.walls != tuple(sorted(set(self.walls))):
            raise ValueError("Les parets no estan en ordre canònic o tenen duplicats")
        for x, y in self.walls:
            if x < 0 or x >= self.W or y < 0 or y >= self.H:
                raise ValueError(f"Paret fora del taulell: ({x}, {y})")
        # Nombre de posicions coincideix amb nombre de peces
        if len(self.start.positions) != len(self.pieces):
            raise ValueError(
                "El nombre de posicions no coincideix amb el nombre de peces"
            )
        # Peces en ordre canònic: (forma, posició_inicial)
        pairs = list(zip(self.pieces, self.start.positions))
        if pairs != sorted(pairs):
            raise ValueError("Les peces no estan en ordre canònic")
        # Objectius ordenats
        if self.goals != tuple(sorted(self.goals)):
            raise ValueError("Els objectius no estan en ordre canònic")
        # Índexs dels objectius vàlids
        n = len(self.pieces)
        for i, pos in self.goals:
            if i < 0 or i >= n:
                raise ValueError(f"Índex de peça invàlid: {i}")
        # Les peces no es poden solapar en l'estat inicial
        occupied: set[Coord] = set()
        for piece, (px, py) in zip(self.pieces, self.start.positions):
            cells = {(px + dx, py + dy) for dx, dy in piece.coords}
            if occupied & cells:
                raise ValueError("Les peces es solapen en l'estat inicial")
            occupied |= cells

    def _to_obj(self) -> dict:
        return {
            "W": self.W,
            "H": self.H,
            "walls": [list(c) for c in self.walls],
            "pieces": [p._to_obj() for p in self.pieces],
            "start": self.start._to_obj(),
            "goals": [{"i": i, "pos": list(pos)} for i, pos in self.goals],
        }

    def to_json(self, indent: int | None = None) -> str:
        """Retorna el JSON del trencaclosques."""
        return json.dumps(self._to_obj(), indent=indent)

    def hash(self) -> str:
        """Retorna el hash SHA256 en hexadecimal del JSON sense indentació."""
        return hashlib.sha256(self.to_json().encode()).hexdigest()

    @classmethod
    def from_json(cls, s: str) -> Puzzle:
        """Crea un Puzzle a partir d'un string JSON."""
        obj = json.loads(s)
        walls = tuple(tuple(c) for c in obj["walls"])
        pieces = tuple(Piece(*[tuple(c) for c in coords]) for coords in obj["pieces"])
        start = State(tuple(tuple(p) for p in obj["start"]))
        goals = tuple((g["i"], tuple(g["pos"])) for g in obj["goals"])
        return cls(
            W=obj["W"],
            H=obj["H"],
            walls=walls,
            pieces=pieces,
            start=start,
            goals=goals,
        )