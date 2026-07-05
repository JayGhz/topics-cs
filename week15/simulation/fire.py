"""Incendio y humo como autómata celular sobre la grilla de floorplan.

Reglas:
- Cada celda libre tiene combustible (fuel). Una celda "prende" si un vecino
  arde con intensidad suficiente y el sorteo aleatorio lo permite.
- Mientras arde, la intensidad crece hasta 1.0 consumiendo combustible;
  al agotarse el combustible, la intensidad decae (brasas) hasta apagarse.
- El humo se difunde independientemente del fuego (llega más lejos, más
  rápido, y es lo que primero reduce la visibilidad/aumenta el pánico).
- Como el fuego solo vive en celdas libres de OCCUPANCY, nunca "atraviesa"
  una pared salvo por el hueco de una puerta: la física de propagación es
  la misma grilla que ya respeta la geometría del edificio.
"""
import random
from . import floorplan as fp

GROWTH_RATE = 1.3          # 1/s, velocidad de crecimiento de intensidad
FUEL_CONSUMPTION = 0.15    # 1/s
DECAY_RATE = 0.25          # 1/s, apagado tras consumir combustible
SPREAD_PROB_BASE = 0.6     # prob/seg de contagiar a un vecino libre
SMOKE_DIFFUSION = 0.35     # coeficiente de difusión de humo
SMOKE_SOURCE = 1.4         # cuánto humo emite una celda ardiendo
SMOKE_DECAY = 0.02

LETHAL_INTENSITY = 0.75    # intensidad a partir de la cual el fuego mata
SLOW_FACTOR = 0.16         # foco "lento": crece/contagia a una fracción de
                           # la velocidad normal, para que sí avance y se
                           # note, sin llegar a tragarse todo el pasillo
SLOW_MAX_INTENSITY = 0.35  # tope de intensidad de un foco lento: apenas
                           # arriba del umbral de A* (>0.3, lo trata como
                           # intransitable) pero bien por debajo del letal
                           # (>0.5) — bloquea la ruta sin matar a nadie ahí


class FireField:
    def __init__(self):
        self.nx, self.ny = fp.NX, fp.NY
        self.intensity = [[0.0] * self.ny for _ in range(self.nx)]
        self.fuel = [[1.0 if fp.is_free(i, j) else 0.0 for j in range(self.ny)]
                     for i in range(self.nx)]
        self.smoke = [[0.0] * self.ny for _ in range(self.nx)]
        # celdas de un foco "lento" (p.ej. un pasillo clave): mismo modelo,
        # pero crecen/contagian a SLOW_FACTOR de la velocidad normal. Un
        # foco lento en un pasillo bloquea la circulación poco a poco, en
        # vez de sellar de golpe la ruta principal de evacuación.
        self.slow = [[False] * self.ny for _ in range(self.nx)]
        self.ignited = False

    def spark(self, room=None, at=None, slow=False):
        """Enciende la sala indicada (o el origen por defecto), o un punto
        exacto (x, y) si se pasa `at`. `slow=True` para un foco secundario
        que arde más despacio y no llega a ser letal (ver SLOW_FACTOR)."""
        if at is not None:
            cx, cy = at
        else:
            room = room or fp.FIRE_ORIGIN_ROOM
            x0, y0, x1, y1 = fp.ROOMS[room]["bounds"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        i, j = fp._cell(cx, cy)
        if not fp.is_free(i, j):
            i, j = fp._cell(*fp.nearest_free_cell((cx, cy)))
        self.intensity[i][j] = 0.4
        self.slow[i][j] = slow
        self.ignited = True

    def step(self, dt):
        if not self.ignited:
            self._diffuse_smoke(dt)
            return
        nx, ny = self.nx, self.ny
        new_intensity = [row[:] for row in self.intensity]
        new_slow = [row[:] for row in self.slow]
        for i in range(nx):
            for j in range(ny):
                if not fp.is_free(i, j):
                    continue
                inten = self.intensity[i][j]
                if inten > 0:
                    is_slow = self.slow[i][j]
                    mult = SLOW_FACTOR if is_slow else 1.0
                    cap = SLOW_MAX_INTENSITY if is_slow else 1.0
                    if self.fuel[i][j] > 0:
                        inten = min(cap, inten + GROWTH_RATE * mult * dt)
                        self.fuel[i][j] = max(0.0, self.fuel[i][j] - FUEL_CONSUMPTION * mult * dt)
                    else:
                        inten = max(0.0, inten - DECAY_RATE * dt)
                    new_intensity[i][j] = inten
                    # contagio a vecinos libres con combustible (a
                    # SLOW_FACTOR de la probabilidad si es un foco lento)
                    if inten > 0.25:
                        for di, dj in fp._NEIGHBORS:
                            ni, nj = i + di, j + dj
                            if fp.is_free(ni, nj) and self.intensity[ni][nj] == 0 and self.fuel[ni][nj] > 0:
                                p = SPREAD_PROB_BASE * mult * inten * dt
                                if random.random() < p:
                                    new_intensity[ni][nj] = 0.05
                                    new_slow[ni][nj] = self.slow[i][j]
        self.intensity = new_intensity
        self.slow = new_slow
        self._diffuse_smoke(dt)

    def _diffuse_smoke(self, dt):
        nx, ny = self.nx, self.ny
        new_smoke = [row[:] for row in self.smoke]
        for i in range(nx):
            for j in range(ny):
                if not fp.is_free(i, j):
                    continue
                neighbors = [self.smoke[i + di][j + dj]
                             for di, dj in fp._NEIGHBORS
                             if fp.is_free(i + di, j + dj)]
                avg = sum(neighbors) / len(neighbors) if neighbors else 0.0
                s = self.smoke[i][j]
                s += SMOKE_DIFFUSION * dt * (avg - s)
                s += SMOKE_SOURCE * self.intensity[i][j] * dt
                s -= SMOKE_DECAY * dt
                new_smoke[i][j] = max(0.0, min(1.0, s))
        self.smoke = new_smoke

    def intensity_at(self, xy):
        i, j = fp._cell(*xy)
        if not fp.in_bounds(i, j):
            return 0.0
        return self.intensity[i][j]

    def smoke_at(self, xy):
        i, j = fp._cell(*xy)
        if not fp.in_bounds(i, j):
            return 0.0
        return self.smoke[i][j]

    def hazard_cost(self, i, j):
        """Costo extra para A*: evita el fuego, penaliza el humo espeso."""
        inten = self.intensity[i][j]
        if inten > 0.3:
            return 1e5  # efectivamente intransitable
        return inten * 40 + self.smoke[i][j] * 4

    def sparse(self, field, threshold=0.02):
        out = []
        for i in range(self.nx):
            for j in range(self.ny):
                v = field[i][j]
                if v > threshold:
                    out.append((i, j, round(v, 2)))
        return out
