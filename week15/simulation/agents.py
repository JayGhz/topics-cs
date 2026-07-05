"""PersonAgent: modelo de fuerzas sociales para evacuación bajo pánico.

Basado en Helbing, Farkas & Vicsek, "Simulating dynamical features of
escape panic" (Nature, 2000). Cada persona es empujada por:
  1. una fuerza de "impulso" hacia su siguiente punto de ruta (A*),
  2. repulsión de otras personas (+ fuerza de contacto físico si se tocan),
  3. repulsión de paredes,
  4. repulsión del fuego (y el humo aumenta el pánico / reduce visibilidad).
El pánico sube la velocidad deseada pero también induce "manada": con
pánico alto la persona se deja llevar por el rumbo promedio de sus vecinos
en vez de seguir su ruta óptima (comportamiento documentado en la
literatura de evacuación).
"""
import math
import random
from . import floorplan as fp

# Parámetros físicos (valores canónicos del paper de Helbing et al. 2000)
A_SOC, B_SOC = 2.0e3, 0.08        # repulsión social (N, m)
A_WALL, B_WALL = 2.0e3, 0.08      # repulsión de paredes
K_BODY = 1.2e5                    # rigidez de contacto (kg/s^2)
KAPPA = 2.4e5                     # fricción tangencial (kg/(m s))

RADIUS = 0.25          # m
MASS = 80.0            # kg
TAU = 0.5              # s, tiempo de relajación
BASE_SPEED = 1.3        # m/s caminando normal (evacuando)
WANDER_SPEED = 0.85      # m/s, paso tranquilo mientras no hay alarma
PANIC_SPEED_BOOST = 0.9  # m/s extra a pánico máximo
MAX_SPEED = 2.4

REPLAN_INTERVAL = 1.5   # s entre recálculos de ruta A*
TRAPPED_REPLAN_INTERVAL = 4.0  # s: si ya está atrapado, reintenta más
                               # espaciado (un A* sin salida explora casi
                               # toda la grilla, y con varios atrapados a
                               # la vez sale caro repetirlo cada 1.5s)
LOOKAHEAD = 0.9          # m, distancia al siguiente waypoint antes de avanzar

MODE_WANDER, MODE_EVACUATE = "wander", "evacuate"

FIRE_FORCE_COEF = 6.0e3
FIRE_SENSE_RADIUS = 1.6
LETHAL_EXPOSURE_TIME = 1.0   # s de exposición letal antes de convertirse en víctima

PANIC_FIRE_GAIN = 0.9
PANIC_CROWD_GAIN = 0.15
PANIC_DECAY = 0.12
HERDING_PANIC_THRESHOLD = 0.55

STATUS_NORMAL, STATUS_PANIC, STATUS_TRAPPED, STATUS_EVACUATED, STATUS_CASUALTY = (
    "normal", "panic", "trapped", "evacuated", "casualty")


class PersonAgent:
    _next_id = 0

    def __init__(self, xy, floor=fp.GROUND, world_time=0.0):
        self.id = PersonAgent._next_id
        PersonAgent._next_id += 1
        self.x, self.y = xy
        self.floor = floor
        self.vx = self.vy = 0.0
        self.panic = 0.0
        self.status = STATUS_NORMAL
        self.mode = MODE_WANDER
        self.path = []
        self.destination = None
        self._last_replan = -999.0
        self._lethal_exposure = 0.0
        self._new_wander_target()
        self._replan(world_time, force=True)

    # ── planeación de ruta ──────────────────────────────────────────
    def _new_wander_target(self):
        """Punto aleatorio transitable en el piso donde está la persona.
        La mayoría de las veces el punto se sortea dentro de TODA su sala
        actual (esquinas incluidas, no solo el centro); de vez en cuando
        sale a caminar a otra parte del edificio."""
        room = fp.room_of((self.x, self.y), self.floor)
        room_data = fp.ROOMS_BY_FLOOR[self.floor].get(room)
        if room_data and random.random() < 0.75:
            x0, y0, x1, y1 = room_data["bounds"]
        else:
            x0, y0, x1, y1 = 0.0, 0.0, fp.WIDTH, fp.HEIGHT
        for _ in range(20):
            x = random.uniform(x0 + fp.CELL, x1 - fp.CELL)
            y = random.uniform(y0 + fp.CELL, y1 - fp.CELL)
            if fp.is_free(*fp._cell(x, y), self.floor):
                self._pending_wander = (x, y)
                return
        self._pending_wander = (self.x, self.y)

    def _replan(self, world_time, fire=None, force=False):
        interval = TRAPPED_REPLAN_INTERVAL if self.status == STATUS_TRAPPED else REPLAN_INTERVAL
        if not force and world_time - self._last_replan < interval:
            return
        self._last_replan = world_time
        hazard = fire.hazard_cost if (fire and self.floor == fp.GROUND) else None

        if self.mode == MODE_EVACUATE:
            # en el piso alto primero hay que bajar por una escalera; ya en
            # planta baja, el objetivo son las salidas (con costo de fuego)
            candidates = fp.STAIRS if self.floor == fp.UPPER else fp.EXITS
            best_path, best_len, best_dest = None, math.inf, None
            for cand in candidates:
                path = fp.a_star((self.x, self.y), cand, self.floor, hazard_cost=hazard)
                if path is None:
                    continue
                length = sum(math.dist(path[k], path[k + 1]) for k in range(len(path) - 1))
                if length < best_len:
                    best_len, best_path, best_dest = length, path, cand
            if best_path is None:
                self.status = STATUS_TRAPPED
                self.path = []
            else:
                self.path = best_path
                self.destination = best_dest
                if self.status == STATUS_TRAPPED:
                    self.status = STATUS_PANIC if self.panic > HERDING_PANIC_THRESHOLD else STATUS_NORMAL
        else:
            dest = self._pending_wander
            path = fp.a_star((self.x, self.y), dest, self.floor)
            if path is not None:
                self.path = path
                self.destination = dest
            self._new_wander_target()

    def _next_waypoint(self, world_time):
        while len(self.path) > 1 and math.dist((self.x, self.y), self.path[0]) < LOOKAHEAD:
            self.path.pop(0)
        if not self.path and self.mode == MODE_WANDER:
            self._replan(world_time, force=True)
        return self.path[0] if self.path else None

    # ── paso de simulación ───────────────────────────────────────────
    def step(self, dt, world_time, neighbors, fire, herd_direction=None):
        if self.status in (STATUS_EVACUATED, STATUS_CASUALTY):
            return

        # suena la alarma: a partir de aquí, siempre a evacuar (no hay vuelta a wander)
        if fire.ignited and self.mode != MODE_EVACUATE:
            self.mode = MODE_EVACUATE
            self._replan(world_time, fire=fire, force=True)

        if self.mode == MODE_EVACUATE and math.dist((self.x, self.y), self.destination or (-999, -999)) < 0.55:
            if self.floor == fp.UPPER:
                self.floor = fp.GROUND        # bajó la escalera
                self._replan(world_time, fire=fire, force=True)
            else:
                self.status = STATUS_EVACUATED
                return

        if self.floor == fp.GROUND:
            fire_intensity = fire.intensity_at((self.x, self.y))
            smoke = fire.smoke_at((self.x, self.y))
        else:
            fire_intensity = smoke = 0.0

        # exposición letal acumulada
        if fire_intensity > 0.5:
            self._lethal_exposure += dt
            if self._lethal_exposure > LETHAL_EXPOSURE_TIME:
                self.status = STATUS_CASUALTY
                return
        else:
            self._lethal_exposure = max(0.0, self._lethal_exposure - dt)

        self._replan(world_time, fire=fire)
        if self.status == STATUS_TRAPPED:
            return

        if self.mode == MODE_EVACUATE:
            local_density = sum(1 for n in neighbors if math.dist((n.x, n.y), (self.x, self.y)) < 1.0)
            fire_exposure = max(fire_intensity, smoke * 0.4)
            self.panic += dt * (PANIC_FIRE_GAIN * fire_exposure +
                                 PANIC_CROWD_GAIN * max(0, local_density - 4))
            self.panic -= dt * PANIC_DECAY * self.panic
            self.panic = max(0.0, min(1.0, self.panic))
            self.status = STATUS_PANIC if self.panic > HERDING_PANIC_THRESHOLD else STATUS_NORMAL

        # ── 1. fuerza de impulso hacia la ruta (o hacia la manada si hay pánico/humo) ──
        waypoint = self._next_waypoint(world_time)
        if waypoint is None:
            return
        gx, gy = waypoint[0] - self.x, waypoint[1] - self.y
        dist = math.hypot(gx, gy) or 1e-6
        desired_dir = (gx / dist, gy / dist)

        if herd_direction is not None and self.mode == MODE_EVACUATE and (
                self.panic > HERDING_PANIC_THRESHOLD or smoke > 0.5):
            blend = min(0.6, self.panic)
            desired_dir = (
                desired_dir[0] * (1 - blend) + herd_direction[0] * blend,
                desired_dir[1] * (1 - blend) + herd_direction[1] * blend,
            )
            norm = math.hypot(*desired_dir) or 1e-6
            desired_dir = (desired_dir[0] / norm, desired_dir[1] / norm)

        if self.mode == MODE_EVACUATE:
            desired_speed = min(MAX_SPEED, BASE_SPEED + PANIC_SPEED_BOOST * self.panic)
        else:
            desired_speed = WANDER_SPEED
        fx = MASS * (desired_speed * desired_dir[0] - self.vx) / TAU
        fy = MASS * (desired_speed * desired_dir[1] - self.vy) / TAU

        # ── 2. repulsión social + contacto físico ──────────────────
        for n in neighbors:
            if n is self or n.floor != self.floor or n.status in (STATUS_EVACUATED, STATUS_CASUALTY):
                continue
            dx, dy = self.x - n.x, self.y - n.y
            d = math.hypot(dx, dy) or 1e-6
            if d > 2.5:
                continue
            nx_, ny_ = dx / d, dy / d
            overlap = 2 * RADIUS - d
            f_soc = A_SOC * math.exp((2 * RADIUS - d) / B_SOC)
            fx += f_soc * nx_
            fy += f_soc * ny_
            if overlap > 0:
                fx += K_BODY * overlap * nx_
                fy += K_BODY * overlap * ny_
                tvx, tvy = n.vx - self.vx, n.vy - self.vy
                tangent = (-ny_, nx_)
                tvel = tvx * tangent[0] + tvy * tangent[1]
                fx += KAPPA * overlap * tvel * tangent[0]
                fy += KAPPA * overlap * tvel * tangent[1]

        # ── 3. repulsión de paredes (muestreo de celdas bloqueadas vecinas) ──
        wx, wy = self._wall_repulsion()
        fx += wx
        fy += wy

        # ── 4. repulsión del fuego ───────────────────────────────────
        gxf, gyf = self._fire_gradient(fire)
        fx += FIRE_FORCE_COEF * gxf
        fy += FIRE_FORCE_COEF * gyf

        ax, ay = fx / MASS, fy / MASS
        self.vx += ax * dt
        self.vy += ay * dt
        speed = math.hypot(self.vx, self.vy)
        if speed > MAX_SPEED:
            self.vx, self.vy = self.vx / speed * MAX_SPEED, self.vy / speed * MAX_SPEED
        old_x, old_y = self.x, self.y
        new_x = max(RADIUS, min(fp.WIDTH - RADIUS, self.x + self.vx * dt))
        new_y = max(RADIUS, min(fp.HEIGHT - RADIUS, self.y + self.vy * dt))

        # tope duro anti-tunneling: la repulsión de paredes es una fuerza
        # suave y en un cuello de botella (mucha gente empujando) puede no
        # alcanzar a frenar a alguien antes de que "atraviese" la pared en
        # un solo tick. Antes de aceptar el movimiento, se verifica que la
        # celda destino sea transitable; si no, se intenta deslizar por un
        # solo eje (como rozar la pared) en vez de teletransportarse dentro.
        if fp.is_free(*fp._cell(new_x, new_y), self.floor):
            self.x, self.y = new_x, new_y
        elif fp.is_free(*fp._cell(new_x, old_y), self.floor):
            self.x = new_x
        elif fp.is_free(*fp._cell(old_x, new_y), self.floor):
            self.y = new_y

    def _wall_repulsion(self):
        i0, j0 = fp._cell(self.x, self.y)
        fx = fy = 0.0
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                i, j = i0 + di, j0 + dj
                if fp.in_bounds(i, j) and not fp.is_free(i, j, self.floor):
                    cx, cy = fp.cell_center(i, j)
                    dx, dy = self.x - cx, self.y - cy
                    d = math.hypot(dx, dy) or 1e-6
                    f = A_WALL * math.exp((RADIUS - d) / B_WALL)
                    fx += f * dx / d
                    fy += f * dy / d
        return fx, fy

    def _fire_gradient(self, fire):
        if self.floor != fp.GROUND:
            return 0.0, 0.0
        i0, j0 = fp._cell(self.x, self.y)
        gx = gy = 0.0
        cells = int(FIRE_SENSE_RADIUS / fp.CELL)
        for di in range(-cells, cells + 1):
            for dj in range(-cells, cells + 1):
                i, j = i0 + di, j0 + dj
                if not fp.in_bounds(i, j):
                    continue
                inten = fire.intensity[i][j] if fire.ignited else 0.0
                if inten <= 0.01:
                    continue
                cx, cy = fp.cell_center(i, j)
                dx, dy = self.x - cx, self.y - cy
                d = math.hypot(dx, dy) or 1e-6
                if d > FIRE_SENSE_RADIUS:
                    continue
                weight = inten * (1 - d / FIRE_SENSE_RADIUS)
                gx += weight * dx / d
                gy += weight * dy / d
        return gx, gy

    def to_dict(self):
        return {
            "id": self.id,
            "x": round(self.x, 2), "y": round(self.y, 2),
            "floor": self.floor,
            "status": self.status,
            "panic": round(self.panic, 2),
        }
