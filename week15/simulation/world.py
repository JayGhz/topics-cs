"""World: orquesta el tick de simulación (fuego + personas) y expone
el estado como dicts listos para serializar a JSON hacia el frontend."""
import math
import random
from . import floorplan as fp
from .fire import FireField
from .agents import PersonAgent, STATUS_EVACUATED, STATUS_CASUALTY, STATUS_TRAPPED

SPAWN_ROOMS_GROUND = ["oficina_b", "cocina", "sala_a", "sala_c", "atrio_sur", "atrio_norte"]
SPAWN_ROOMS_UPPER = ["sala_reuniones", "oficina_c", "terraza", "archivo", "atrio_sur_alto", "atrio_norte_alto"]
HERD_RADIUS = 3.0


class World:
    def __init__(self, n_agents=48):
        self.n_agents = n_agents
        self.paused = False
        self.speed = 1.0
        self.fire = FireField()
        self.time = 0.0
        self.people = []
        self._spawn(n_agents)

    def _spawn(self, n):
        PersonAgent._next_id = 0
        self.people = []
        n_upper = n // 2
        n_ground = n - n_upper
        self._spawn_floor(n_ground, SPAWN_ROOMS_GROUND, fp.GROUND)
        self._spawn_floor(n_upper, SPAWN_ROOMS_UPPER, fp.UPPER)

    def _spawn_floor(self, n, rooms, floor):
        per_room = max(1, n // len(rooms))
        for room in rooms:
            x0, y0, x1, y1 = fp.ROOMS_BY_FLOOR[floor][room]["bounds"]
            for _ in range(per_room):
                xy = (x0 + 0.5, y0 + 0.5)
                for _ in range(20):
                    cand = (random.uniform(x0 + 0.4, x1 - 0.4), random.uniform(y0 + 0.4, y1 - 0.4))
                    if fp.is_free(*fp._cell(*cand), floor):
                        xy = cand
                        break
                self.people.append(PersonAgent(xy, floor=floor, world_time=0.0))

    def reset(self, n_agents=None):
        self.fire = FireField()
        self.time = 0.0
        if n_agents is not None:
            self.n_agents = max(1, min(200, n_agents))
        self._spawn(self.n_agents)

    def spark(self, room=None):
        if room is None:
            # dos focos a la vez: la cocina (rápido, el de siempre) y un
            # segundo, lento, justo afuera de la puerta del atrio_sur —
            # ahí sí pasa gente de verdad (baja por la escalera que da a
            # ese atrio) y tiene que decidir izquierda o derecha.
            self.fire.spark(fp.FIRE_ORIGIN_ROOM, slow=False)
            self.fire.spark(at=fp.SECONDARY_FIRE_POINT, slow=True)
        else:
            self.fire.spark(room)

    def set_agents(self, n):
        self.n_agents = max(1, min(200, n))
        self._spawn(self.n_agents)

    def set_paused(self, paused):
        self.paused = paused

    def set_speed(self, speed):
        self.speed = max(0.25, min(4.0, speed))

    def step(self, dt):
        if self.paused:
            return
        dt *= self.speed
        self.time += dt
        self.fire.step(dt)

        active = [p for p in self.people if p.status not in (STATUS_EVACUATED, STATUS_CASUALTY)]
        herd_dirs = self._herd_directions(active)
        random.shuffle(active)
        for p in active:
            p.step(dt, self.time, active, self.fire, herd_direction=herd_dirs.get(p.id))

    def _herd_directions(self, active):
        """Rumbo promedio de los vecinos en movimiento (contagio de pánico)."""
        dirs = {}
        for p in active:
            sx = sy = 0.0
            count = 0
            for q in active:
                if q is p or q.floor != p.floor:
                    continue
                speed = math.hypot(q.vx, q.vy)
                if speed < 0.2:
                    continue
                if math.dist((p.x, p.y), (q.x, q.y)) > HERD_RADIUS:
                    continue
                sx += q.vx / speed
                sy += q.vy / speed
                count += 1
            if count:
                norm = math.hypot(sx, sy)
                if norm > 1e-6:
                    dirs[p.id] = (sx / norm, sy / norm)
        return dirs

    def stats(self):
        evac = sum(1 for p in self.people if p.status == STATUS_EVACUATED)
        cas = sum(1 for p in self.people if p.status == STATUS_CASUALTY)
        trapped = sum(1 for p in self.people if p.status == STATUS_TRAPPED)
        return {
            "evacuated": evac, "casualties": cas, "trapped": trapped,
            "active": len(self.people) - evac - cas,
            "total": len(self.people),
            "elapsed": round(self.time, 1),
            "fire_ignited": self.fire.ignited,
        }

    def state_dict(self):
        return {
            "type": "state",
            "t": round(self.time, 2),
            "people": [p.to_dict() for p in self.people],
            "fire": self.fire.sparse(self.fire.intensity, 0.03),
            "smoke": self.fire.sparse(self.fire.smoke, 0.05),
            "stats": self.stats(),
        }

    def floorplan_dict(self):
        return {"type": "floorplan", **fp.to_json()}
