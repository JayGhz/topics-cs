"""Geometría del edificio, grilla de ocupación y pathfinding A*.

El edificio tiene 2 pisos (mismo footprint de 30m x 18m):
- Planta baja (GROUND): 4 salas + pasillo + 2 salidas al exterior.
- Planta alta (UPPER): mismo trazado interior, pero el perímetro está
  cerrado (no hay salidas arriba). Solo se baja por las 2 escaleras.

Cada piso tiene su propia grilla de ocupación, así que el pathfinding y la
propagación del fuego son independientes por piso. Las escaleras son un
mismo punto (x, y) transitable en ambos pisos: para bajar, un agente
primero hace A* en su piso hasta ese punto y luego "aparece" en el mismo
punto de la planta baja para continuar hacia la salida.
"""
import heapq
import math

CELL = 0.4                    # tamaño de celda (m)
WIDTH, HEIGHT = 30.0, 18.0    # dimensiones del edificio (m)
NX, NY = int(WIDTH / CELL), int(HEIGHT / CELL)

GROUND, UPPER = 0, 1
FLOOR_HEIGHT = 3.2   # separación vertical entre pisos en la escena 3D (m)

# ── Salas por piso (solo para spawns/etiquetas/mobiliario, no afectan física) ──
ROOMS_GROUND = {
    "oficina_b":  {"bounds": (0, 0, 9, 7),   "label": "Oficina B", "kind": "office"},
    "cocina":     {"bounds": (21, 0, 30, 7), "label": "Cocina (origen del incendio)", "kind": "kitchen"},
    "sala_a":     {"bounds": (0, 11, 9, 18), "label": "Sala A", "kind": "lounge"},
    "sala_c":     {"bounds": (21, 11, 30, 18), "label": "Sala C", "kind": "office"},
    "atrio_sur":  {"bounds": (9, 0, 21, 7),  "label": "Atrio sur", "kind": "plants"},
    "atrio_norte": {"bounds": (9, 11, 21, 18), "label": "Atrio norte", "kind": "plants"},
    "pasillo":    {"bounds": (0, 7, 30, 11), "label": "Pasillo central", "kind": "plants"},
}

ROOMS_UPPER = {
    "sala_reuniones": {"bounds": (0, 0, 9, 7),   "label": "Sala de reuniones", "kind": "meeting"},
    "oficina_c":      {"bounds": (21, 0, 30, 7), "label": "Oficina C", "kind": "office"},
    "terraza":        {"bounds": (0, 11, 9, 18), "label": "Terraza", "kind": "plants"},
    "archivo":        {"bounds": (21, 11, 30, 18), "label": "Archivo", "kind": "office"},
    "atrio_sur_alto": {"bounds": (9, 0, 21, 7),  "label": "Atrio sur (2do piso)", "kind": "plants"},
    "atrio_norte_alto": {"bounds": (9, 11, 21, 18), "label": "Atrio norte (2do piso)", "kind": "plants"},
    "pasillo_alto":   {"bounds": (0, 7, 30, 11), "label": "Pasillo alto", "kind": "plants"},
}

# alias: el resto del código (agentes, notebook) trata "el edificio" como
# la planta baja por defecto.
ROOMS = ROOMS_GROUND
FIRE_ORIGIN_ROOM = "cocina"

# ── Paredes: segmentos (x1, y1, x2, y2), ya con los huecos de puertas ───
_DOOR = (4.0, 5.2)      # ancho de puerta ~1.2m, reutilizado en varias salas
_DOOR_R = (25.0, 26.2)
_ATRIO_DOOR = (13.0, 14.2)   # puerta única de cada atrio hacia el pasillo

_INTERIOR_WALLS = [
    # separación salas <-> pasillo, con puerta (idéntico en ambos pisos)
    (0, 7, _DOOR[0], 7), (_DOOR[1], 7, 9, 7),
    (21, 7, _DOOR_R[0], 7), (_DOOR_R[1], 7, 30, 7),
    (0, 11, _DOOR[0], 11), (_DOOR[1], 11, 9, 11),
    (21, 11, _DOOR_R[0], 11), (_DOOR_R[1], 11, 30, 11),

    # separación oficina_b/sala_a <-> atrio (antes quedaba abierta, dejando
    # "atajos" que evitaban por completo la puerta de cada sala)
    (9, 0, 9, 7), (9, 11, 9, 18),
    # separación atrio <-> cocina/sala_c
    (21, 0, 21, 7), (21, 11, 21, 18),

    # los atrios pasan a ser salas cerradas con una sola puerta al pasillo
    # (antes eran una extensión abierta del pasillo: demasiadas rutas)
    (9, 7, _ATRIO_DOOR[0], 7), (_ATRIO_DOOR[1], 7, 21, 7),
    (9, 11, _ATRIO_DOOR[0], 11), (_ATRIO_DOOR[1], 11, 21, 11),
]

WALLS_GROUND = [
    # perímetro, con huecos de 2m para las dos salidas (y: 8-10)
    (0, 0, WIDTH, 0),
    (0, HEIGHT, WIDTH, HEIGHT),
    (0, 0, 0, 8), (0, 10, 0, HEIGHT),
    (WIDTH, 0, WIDTH, 8), (WIDTH, 10, WIDTH, HEIGHT),
    *_INTERIOR_WALLS,
]

WALLS_UPPER = [
    # perímetro cerrado: arriba no hay salida al exterior
    (0, 0, WIDTH, 0),
    (0, HEIGHT, WIDTH, HEIGHT),
    (0, 0, 0, HEIGHT),
    (WIDTH, 0, WIDTH, HEIGHT),
    *_INTERIOR_WALLS,
]

WALLS = WALLS_GROUND
WALLS_BY_FLOOR = {GROUND: WALLS_GROUND, UPPER: WALLS_UPPER}
ROOMS_BY_FLOOR = {GROUND: ROOMS_GROUND, UPPER: ROOMS_UPPER}

EXIT_LEFT = (0.6, 9.0)
EXIT_RIGHT = (WIDTH - 0.6, 9.0)
EXITS = [EXIT_LEFT, EXIT_RIGHT]

# escaleras: mismo punto transitable en planta baja y alta.
# La del sur baja DENTRO del atrio_sur (no directo al pasillo): la gente
# que estaba arriba en el atrio tiene que cruzar su única puerta al pasillo
# y ahí decidir si sale por la izquierda o la derecha. La otra baja directo
# al pasillo, como antes.
STAIRS = [(15.0, 3.5), (20.6, 9.0)]

# punto donde arranca el foco de incendio secundario (lento): en pleno
# pasillo abierto, lejos de cualquier puerta (ni el centro muerto x=15, ni
# pegado a la entrada de un atrio/escalera) — a mitad de camino entre la
# zona de atrios/escaleras y la salida derecha, para que sí lo cruce gente
# de verdad sin sellarle la puerta a nadie.
SECONDARY_FIRE_POINT = (18.0, 8.5)


def _cell(x, y):
    return int(x / CELL), int(y / CELL)


def build_occupancy_grid(walls):
    """True = celda bloqueada por una pared."""
    blocked = [[False] * NY for _ in range(NX)]
    for (x1, y1, x2, y2) in walls:
        length = math.hypot(x2 - x1, y2 - y1)
        steps = max(2, int(length / (CELL * 0.4)))
        for s in range(steps + 1):
            t = s / steps
            x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            i, j = _cell(x, y)
            if 0 <= i < NX and 0 <= j < NY:
                blocked[i][j] = True
    return blocked


OCCUPANCY_BY_FLOOR = {
    GROUND: build_occupancy_grid(WALLS_GROUND),
    UPPER: build_occupancy_grid(WALLS_UPPER),
}
OCCUPANCY = OCCUPANCY_BY_FLOOR[GROUND]

_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1),
              (-1, -1), (-1, 1), (1, -1), (1, 1)]


def in_bounds(i, j):
    return 0 <= i < NX and 0 <= j < NY


def is_free(i, j, floor=GROUND):
    return in_bounds(i, j) and not OCCUPANCY_BY_FLOOR[floor][i][j]


def cell_center(i, j):
    return (i + 0.5) * CELL, (j + 0.5) * CELL


def a_star(start_xy, goal_xy, floor=GROUND, hazard_cost=None):
    """A* sobre la grilla de `floor`. hazard_cost(i, j) -> costo extra >=0
    por celda (usado para que el fuego "empuje" las rutas, no solo las
    bloquee). Solo tiene sentido para la planta baja, donde vive el fuego."""
    start = _cell(*start_xy)
    goal = _cell(*goal_xy)
    if not is_free(*start, floor) or not is_free(*goal, floor):
        return None

    def h(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1]) * CELL

    hazard_cost = hazard_cost or (lambda i, j: 0.0)
    frontier = [(0.0, start)]
    came_from = {start: None}
    cost_so_far = {start: 0.0}

    # tope de nodos expandidos: si no hay ruta (p.ej. alguien realmente
    # atrapado), sin esto A* explora toda la grilla libre antes de darse
    # por vencido; con varios agentes atrapados a la vez eso sale caro si
    # se repite cada pocos segundos.
    max_expansions = NX * NY // 2
    expansions = 0

    while frontier:
        _, current = heapq.heappop(frontier)
        expansions += 1
        if expansions > max_expansions:
            return None
        if current == goal:
            break
        ci, cj = current
        for di, dj in _NEIGHBORS:
            ni, nj = ci + di, cj + dj
            if not is_free(ni, nj, floor):
                continue
            if di != 0 and dj != 0:
                # evita cortar esquinas de pared en diagonal
                if not is_free(ci + di, cj, floor) or not is_free(ci, cj + dj, floor):
                    continue
            extra = hazard_cost(ni, nj)
            if extra >= 1e4:
                # el fuego marca esta celda como intransitable de verdad
                # (no solo cara): si es la única ruta, A* debe fallar y la
                # persona queda "atrapada" en vez de caminar directo al fuego.
                continue
            step = CELL * (math.sqrt(2) if di and dj else 1.0)
            step += extra * CELL
            new_cost = cost_so_far[current] + step
            neighbor = (ni, nj)
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                priority = new_cost + h(neighbor, goal)
                heapq.heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current

    if goal not in came_from:
        return None

    path = []
    node = goal
    while node is not None:
        path.append(cell_center(*node))
        node = came_from[node]
    path.reverse()
    return path


def nearest_free_cell(xy, floor=GROUND):
    i, j = _cell(*xy)
    if is_free(i, j, floor):
        return cell_center(i, j)
    for radius in range(1, 6):
        for di in range(-radius, radius + 1):
            for dj in range(-radius, radius + 1):
                if is_free(i + di, j + dj, floor):
                    return cell_center(i + di, j + dj)
    return xy


def room_of(xy, floor=GROUND):
    x, y = xy
    for name, data in ROOMS_BY_FLOOR[floor].items():
        x0, y0, x1, y1 = data["bounds"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            return name
    return "pasillo"


def to_json():
    """Geometría estática que el frontend necesita para construir la escena."""
    return {
        "width": WIDTH, "height": HEIGHT, "cell": CELL,
        "nx": NX, "ny": NY,
        "floor_height": FLOOR_HEIGHT,
        "floors": [
            {
                "walls": WALLS_BY_FLOOR[f],
                "rooms": {k: {"bounds": v["bounds"], "kind": v["kind"]}
                          for k, v in ROOMS_BY_FLOOR[f].items()},
            }
            for f in (GROUND, UPPER)
        ],
        "exits": EXITS,
        "stairs": STAIRS,
    }
