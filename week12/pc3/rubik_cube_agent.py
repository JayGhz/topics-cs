"""
RUBIK'S CUBE AGENT — AI SOLVER + 3D
Arquitectura: Modelo Logico (cerebro) + Vista 3D (Ursina)
Algoritmo: IDA* con heuristica Manhattan

Fixes aplicados:
  - macOS scroll: multiplica scroll_y x8 y usa -= (direccion correcta)
  - Sin emojis en textos (Ursina bitmap font no los soporta)
  - Sin luces ni shaders: todo unlit=True, colores directos (mas estable)
"""

import copy
import random
import math
from collections import deque

FACE_NAMES = ['U', 'D', 'F', 'B', 'L', 'R']
ALL_MOVES = ['U', "U'", 'D', "D'", 'F', "F'", 'B', "B'", 'L', "L'", 'R', "R'"]
OPPOSITE_MOVE = {
    'U': "U'", "U'": 'U', 'D': "D'", "D'": 'D',
    'F': "F'", "F'": 'F', 'B': "B'", "B'": 'B',
    'L': "L'", "L'": 'L', 'R': "R'", "R'": 'R',
}

SOLVED_COLORS = {
    'U': 'W', 'D': 'Y', 'F': 'B', 'B': 'G', 'L': 'O', 'R': 'R'
}


class CubeState:
    def __init__(self, state=None):
        if state is None:
            self.f = {face: [SOLVED_COLORS[face]] * 9 for face in FACE_NAMES}
        else:
            self.f = {face: lst[:] for face, lst in state.items()}

    def copy(self):
        return CubeState(self.f)

    def is_solved(self):
        for face in FACE_NAMES:
            if len(set(self.f[face])) != 1:
                return False
        return True

    def to_key(self):
        return tuple(tuple(self.f[face]) for face in FACE_NAMES)

    def __eq__(self, other):
        return self.to_key() == other.to_key()

    def __hash__(self):
        return hash(self.to_key())

    def _cw(self, face):
        s = self.f[face]
        self.f[face] = [s[6], s[3], s[0], s[7], s[4], s[1], s[8], s[5], s[2]]

    def _ccw(self, face):
        s = self.f[face]
        self.f[face] = [s[2], s[5], s[8], s[1], s[4], s[7], s[0], s[3], s[6]]

    def apply_move(self, move):
        fn = {
            'U': self._U, "U'": self._Ui,
            'D': self._D, "D'": self._Di,
            'F': self._F, "F'": self._Fi,
            'B': self._B, "B'": self._Bi,
            'R': self._R, "R'": self._Ri,
            'L': self._L, "L'": self._Li,
        }
        fn[move]()

    def apply_moves(self, moves):
        for m in moves:
            self.apply_move(m)

    def _U(self):
        self._cw('U')
        t = self.f['F'][0:3]
        self.f['F'][0:3] = self.f['R'][0:3]
        self.f['R'][0:3] = self.f['B'][0:3]
        self.f['B'][0:3] = self.f['L'][0:3]
        self.f['L'][0:3] = t

    def _Ui(self):
        self._ccw('U')
        t = self.f['F'][0:3]
        self.f['F'][0:3] = self.f['L'][0:3]
        self.f['L'][0:3] = self.f['B'][0:3]
        self.f['B'][0:3] = self.f['R'][0:3]
        self.f['R'][0:3] = t

    def _D(self):
        self._cw('D')
        t = self.f['F'][6:9]
        self.f['F'][6:9] = self.f['L'][6:9]
        self.f['L'][6:9] = self.f['B'][6:9]
        self.f['B'][6:9] = self.f['R'][6:9]
        self.f['R'][6:9] = t

    def _Di(self):
        self._ccw('D')
        t = self.f['F'][6:9]
        self.f['F'][6:9] = self.f['R'][6:9]
        self.f['R'][6:9] = self.f['B'][6:9]
        self.f['B'][6:9] = self.f['L'][6:9]
        self.f['L'][6:9] = t

    def _F(self):
        self._cw('F')
        t = [self.f['U'][6], self.f['U'][7], self.f['U'][8]]
        self.f['U'][6] = self.f['L'][8]; self.f['U'][7] = self.f['L'][5]; self.f['U'][8] = self.f['L'][2]
        self.f['L'][2] = self.f['D'][0]; self.f['L'][5] = self.f['D'][1]; self.f['L'][8] = self.f['D'][2]
        self.f['D'][0] = self.f['R'][6]; self.f['D'][1] = self.f['R'][3]; self.f['D'][2] = self.f['R'][0]
        self.f['R'][0] = t[0]; self.f['R'][3] = t[1]; self.f['R'][6] = t[2]

    def _Fi(self):
        self._ccw('F')
        t = [self.f['U'][6], self.f['U'][7], self.f['U'][8]]
        self.f['U'][6] = self.f['R'][0]; self.f['U'][7] = self.f['R'][3]; self.f['U'][8] = self.f['R'][6]
        self.f['R'][0] = self.f['D'][2]; self.f['R'][3] = self.f['D'][1]; self.f['R'][6] = self.f['D'][0]
        self.f['D'][0] = self.f['L'][2]; self.f['D'][1] = self.f['L'][5]; self.f['D'][2] = self.f['L'][8]
        self.f['L'][2] = t[2]; self.f['L'][5] = t[1]; self.f['L'][8] = t[0]

    def _B(self):
        self._cw('B')
        t = [self.f['U'][2], self.f['U'][1], self.f['U'][0]]
        self.f['U'][0] = self.f['R'][2]; self.f['U'][1] = self.f['R'][5]; self.f['U'][2] = self.f['R'][8]
        self.f['R'][2] = self.f['D'][8]; self.f['R'][5] = self.f['D'][7]; self.f['R'][8] = self.f['D'][6]
        self.f['D'][6] = self.f['L'][0]; self.f['D'][7] = self.f['L'][3]; self.f['D'][8] = self.f['L'][6]
        self.f['L'][0] = t[0]; self.f['L'][3] = t[1]; self.f['L'][6] = t[2]

    def _Bi(self):
        self._ccw('B')
        t = [self.f['U'][0], self.f['U'][1], self.f['U'][2]]
        self.f['U'][0] = self.f['L'][6]; self.f['U'][1] = self.f['L'][3]; self.f['U'][2] = self.f['L'][0]
        self.f['L'][0] = self.f['D'][6]; self.f['L'][3] = self.f['D'][7]; self.f['L'][6] = self.f['D'][8]
        self.f['D'][6] = self.f['R'][8]; self.f['D'][7] = self.f['R'][5]; self.f['D'][8] = self.f['R'][2]
        self.f['R'][2] = t[0]; self.f['R'][5] = t[1]; self.f['R'][8] = t[2]

    def _R(self):
        self._cw('R')
        t = [self.f['U'][2], self.f['U'][5], self.f['U'][8]]
        self.f['U'][2] = self.f['F'][2]; self.f['U'][5] = self.f['F'][5]; self.f['U'][8] = self.f['F'][8]
        self.f['F'][2] = self.f['D'][2]; self.f['F'][5] = self.f['D'][5]; self.f['F'][8] = self.f['D'][8]
        self.f['D'][2] = self.f['B'][6]; self.f['D'][5] = self.f['B'][3]; self.f['D'][8] = self.f['B'][0]
        self.f['B'][0] = t[2]; self.f['B'][3] = t[1]; self.f['B'][6] = t[0]

    def _Ri(self):
        self._ccw('R')
        t = [self.f['U'][2], self.f['U'][5], self.f['U'][8]]
        self.f['U'][2] = self.f['B'][6]; self.f['U'][5] = self.f['B'][3]; self.f['U'][8] = self.f['B'][0]
        self.f['B'][0] = self.f['D'][8]; self.f['B'][3] = self.f['D'][5]; self.f['B'][6] = self.f['D'][2]
        self.f['D'][2] = self.f['F'][2]; self.f['D'][5] = self.f['F'][5]; self.f['D'][8] = self.f['F'][8]
        self.f['F'][2] = t[0]; self.f['F'][5] = t[1]; self.f['F'][8] = t[2]

    def _L(self):
        self._cw('L')
        t = [self.f['U'][0], self.f['U'][3], self.f['U'][6]]
        self.f['U'][0] = self.f['B'][8]; self.f['U'][3] = self.f['B'][5]; self.f['U'][6] = self.f['B'][2]
        self.f['B'][2] = self.f['D'][6]; self.f['B'][5] = self.f['D'][3]; self.f['B'][8] = self.f['D'][0]
        self.f['D'][0] = self.f['F'][0]; self.f['D'][3] = self.f['F'][3]; self.f['D'][6] = self.f['F'][6]
        self.f['F'][0] = t[0]; self.f['F'][3] = t[1]; self.f['F'][6] = t[2]

    def _Li(self):
        self._ccw('L')
        t = [self.f['U'][0], self.f['U'][3], self.f['U'][6]]
        self.f['U'][0] = self.f['F'][0]; self.f['U'][3] = self.f['F'][3]; self.f['U'][6] = self.f['F'][6]
        self.f['F'][0] = self.f['D'][0]; self.f['F'][3] = self.f['D'][3]; self.f['F'][6] = self.f['D'][6]
        self.f['D'][0] = self.f['B'][8]; self.f['D'][3] = self.f['B'][5]; self.f['D'][6] = self.f['B'][2]
        self.f['B'][2] = t[2]; self.f['B'][5] = t[1]; self.f['B'][8] = t[0]

    def __repr__(self):
        lines = []
        u = self.f['U']
        lines.append(f"       {u[0]} {u[1]} {u[2]}")
        lines.append(f"       {u[3]} {u[4]} {u[5]}")
        lines.append(f"       {u[6]} {u[7]} {u[8]}")
        for row in range(3):
            l = self.f['L'][row*3:(row+1)*3]
            f = self.f['F'][row*3:(row+1)*3]
            r = self.f['R'][row*3:(row+1)*3]
            b = self.f['B'][row*3:(row+1)*3]
            lines.append(f"  {' '.join(l)}  {' '.join(f)}  {' '.join(r)}  {' '.join(b)}")
        d = self.f['D']
        lines.append(f"       {d[0]} {d[1]} {d[2]}")
        lines.append(f"       {d[3]} {d[4]} {d[5]}")
        lines.append(f"       {d[6]} {d[7]} {d[8]}")
        return '\n'.join(lines)


class RubikSolver:
    def __init__(self):
        self.solution = []
        self.max_search_depth = 8

    @staticmethod
    def heuristic(state):
        misplaced = 0
        for face in FACE_NAMES:
            center = state.f[face][4]
            for i in range(9):
                if state.f[face][i] != center:
                    misplaced += 1
        return math.ceil(misplaced / 8)

    def solve(self, cube_state):
        if cube_state.is_solved():
            return []

        for max_depth in range(1, self.max_search_depth + 1):
            self.solution = []
            result = self._dfs(cube_state, 0, max_depth, None)
            if result:
                return self.solution[:]
            print(f"  IDA* depth {max_depth}: not found, expanding...")

        print("  No solution found at max depth. Trying BFS fallback...")
        return self._bfs_fallback(cube_state)

    def _dfs(self, state, depth, max_depth, last_move):
        h = self.heuristic(state)
        if depth + h > max_depth:
            return False
        if state.is_solved():
            return True
        if depth >= max_depth:
            return False

        for move in ALL_MOVES:
            if last_move and move == OPPOSITE_MOVE.get(last_move):
                continue
            if last_move and move[0] == last_move[0]:
                continue

            new_state = state.copy()
            new_state.apply_move(move)
            self.solution.append(move)

            if self._dfs(new_state, depth + 1, max_depth, move):
                return True

            self.solution.pop()

        return False

    def _bfs_fallback(self, cube_state):
        queue = deque()
        queue.append((cube_state, []))
        visited = {cube_state.to_key()}
        max_bfs = 6

        while queue:
            state, moves = queue.popleft()
            if len(moves) >= max_bfs:
                continue
            for move in ALL_MOVES:
                if moves and move == OPPOSITE_MOVE.get(moves[-1]):
                    continue
                new_state = state.copy()
                new_state.apply_move(move)
                key = new_state.to_key()
                if key in visited:
                    continue
                visited.add(key)
                new_moves = moves + [move]
                if new_state.is_solved():
                    return new_moves
                queue.append((new_state, new_moves))

        return []


# ─── VISUALIZACION 3D ───
from ursina import *

# FIX macOS: Custom shader con iluminacion especular (Brillo plastico moderno) y texturas (OpenGL 120)
basic_lit_shader = Shader(language=Shader.GLSL, vertex='''
#version 120
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec2 p3d_MultiTexCoord0;

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat3 p3d_NormalMatrix;
uniform vec4 p3d_ColorScale;

varying vec4 v_color;
varying vec2 v_texcoord;
varying vec3 v_normal;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_color = p3d_ColorScale;
    v_texcoord = p3d_MultiTexCoord0;
    v_normal = normalize(p3d_NormalMatrix * p3d_Normal);
}
''', fragment='''
#version 120
uniform sampler2D p3d_Texture0;
varying vec4 v_color;
varying vec2 v_texcoord;
varying vec3 v_normal;

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(vec3(0.5, 0.8, 1.0));
    vec3 V = vec3(0.0, 0.0, 1.0); // Vista hacia el frente
    vec3 H = normalize(L + V);

    // Iluminacion ambiental oscura para aumentar contraste 3D
    float ambient = 0.35;
    
    // Iluminacion difusa (volumen intenso)
    float diff = max(abs(dot(N, L)), 0.0);
    
    // Brillo especular (look de plastico brillante)
    float spec = pow(max(abs(dot(N, H)), 0.0), 48.0);

    vec4 texColor = texture2D(p3d_Texture0, v_texcoord);
    vec3 baseColor = (texColor * v_color).rgb;
    
    // Mezcla de colores (base * luz + brillo especular blanco)
    vec3 finalColor = baseColor * (ambient + diff * 0.8) + vec3(spec * 0.4);
    
    gl_FragColor = vec4(finalColor, 1.0);
}
''')

# FIX: colores super vivos estilo Rubik's moderno y neon
COLOR_MAP = {
    'W': color.white,
    'Y': color.Color(1.0, 1.0, 0.0, 1),   # Amarillo puro
    'B': color.Color(0.0, 0.3, 1.0, 1),   # Azul vibrante
    'G': color.Color(0.0, 0.9, 0.2, 1),   # Verde brillante
    'O': color.Color(1.0, 0.4, 0.0, 1),   # Naranja fosforito
    'R': color.Color(0.9, 0.0, 0.1, 1),   # Rojo puro intenso
}

INNER_COLOR = color.Color(0.08, 0.08, 0.08, 1)


class RubikCube3D:
    def __init__(self):
        self.cubies = {}
        self.animating = False
        self.move_queue = []
        self.on_done = None
        self.pivot = None
        self.anim_cubies = []
        self.anim_axis = None
        self.anim_angle = 0
        self.anim_progress = 0
        self.anim_speed = 120
        self._create_cube()

    def _create_cube(self):
        gap = 0.04
        cubie_scale = 1.0 - gap

        for x in range(-1, 2):
            for y in range(-1, 2):
                for z in range(-1, 2):
                    if x == 0 and y == 0 and z == 0:
                        continue

                    cubie = Entity(position=Vec3(x, y, z), model=None)

                    # FIX shader macos: aplicamos el custom shader con iluminacion
                    body = Entity(
                        parent=cubie,
                        model='cube',
                        color=INNER_COLOR,
                        scale=cubie_scale,
                        shader=basic_lit_shader,
                    )

                    s = 0.82
                    o = 0.501

                    if y ==  1: self._sticker(cubie, Vec3(0, o, 0),  Vec3(-90,0,0), s, COLOR_MAP['W'])
                    if y == -1: self._sticker(cubie, Vec3(0,-o, 0),  Vec3( 90,0,0), s, COLOR_MAP['Y'])
                    if z ==  1: self._sticker(cubie, Vec3(0, 0, o),  Vec3(  0,0,0), s, COLOR_MAP['B'])
                    if z == -1: self._sticker(cubie, Vec3(0, 0,-o),  Vec3(180,0,0), s, COLOR_MAP['G'])
                    if x ==  1: self._sticker(cubie, Vec3( o,0, 0),  Vec3(0, 90,0), s, COLOR_MAP['R'])
                    if x == -1: self._sticker(cubie, Vec3(-o,0, 0),  Vec3(0,-90,0), s, COLOR_MAP['O'])

                    self.cubies[(x, y, z)] = cubie

    def _sticker(self, parent, pos, rot, size, col):
        return Entity(
            parent=parent,
            model='quad',
            texture='white_cube',
            color=col,
            position=pos,
            rotation=rot,
            scale=size,
            shader=basic_lit_shader,
            double_sided=True,
        )

    def _get_face_cubies(self, face):
        result = []
        for pos, cubie in self.cubies.items():
            wp = self._snap_pos(cubie.world_position)
            if   face == 'U' and wp.y ==  1: result.append(cubie)
            elif face == 'D' and wp.y == -1: result.append(cubie)
            elif face == 'F' and wp.z ==  1: result.append(cubie)
            elif face == 'B' and wp.z == -1: result.append(cubie)
            elif face == 'R' and wp.x ==  1: result.append(cubie)
            elif face == 'L' and wp.x == -1: result.append(cubie)
        return result

    def _snap_pos(self, pos):
        return Vec3(round(pos.x), round(pos.y), round(pos.z))

    def _snap_rotation(self, rot):
        return Vec3(
            round(rot.x / 90) * 90,
            round(rot.y / 90) * 90,
            round(rot.z / 90) * 90,
        )

    def enqueue_moves(self, moves, on_done=None):
        self.move_queue.extend(moves)
        if on_done:
            self.on_done = on_done
        if not self.animating:
            self._next_move()

    def _next_move(self):
        if not self.move_queue:
            self.animating = False
            if self.on_done:
                cb = self.on_done
                self.on_done = None
                cb()
            return
        move = self.move_queue.pop(0)
        self._start_animation(move)

    def _start_animation(self, move):
        self.animating = True
        face = move[0]
        is_prime = "'" in move

        self.anim_cubies = self._get_face_cubies(face)
        self.pivot = Entity()

        for c in self.anim_cubies:
            c.world_parent = self.pivot

        axis_map = {
            'U': Vec3(0, 1, 0), 'D': Vec3(0,-1, 0),
            'F': Vec3(0, 0, 1), 'B': Vec3(0, 0,-1),
            'R': Vec3(1, 0, 0), 'L': Vec3(-1,0, 0),
        }
        self.anim_axis = axis_map[face]
        self.anim_angle = 90 if is_prime else -90
        self.anim_progress = 0

    def update_animation(self, dt):
        if not self.animating or self.pivot is None:
            return

        step = self.anim_speed * dt
        remaining = abs(self.anim_angle) - self.anim_progress

        if step >= remaining:
            self.pivot.rotation += self.anim_axis * remaining * (1 if self.anim_angle > 0 else -1)
            self._finish_animation()
        else:
            self.pivot.rotation += self.anim_axis * step * (1 if self.anim_angle > 0 else -1)
            self.anim_progress += step

    def _finish_animation(self):
        for c in self.anim_cubies:
            wp = c.world_position
            wr = c.world_rotation
            c.world_parent = scene
            c.position = self._snap_pos(wp)
            c.rotation = self._snap_rotation(wr)

        destroy(self.pivot)
        self.pivot = None
        self.anim_cubies = []
        self._next_move()

    def is_busy(self):
        return self.animating or len(self.move_queue) > 0


def main():
    app = Ursina(
        title="Rubik's Cube Agent",
        borderless=False,
        fullscreen=False,
        development_mode=False,
        size=(1100, 750),
    )

    cube_logic = CubeState()
    solver = RubikSolver()
    cube_3d = RubikCube3D()

    camera.orthographic = False
    camera.fov = 50
    # Inicializamos la camara orbital nativa de Ursina (EditorCamera)
    # distance establece que tan lejos arranca el zoom
    ec = EditorCamera(rotation=(30, -45, 0))
    camera.z = -18  # Reemplaza el cam_distance, mas lejos segun lo pedido

    # Ya no necesitamos luces porque el custom_shader es unlit
    window.color = color.black

    # FIX: textos sin emojis
    Text(
        text="Rubik's Cube Agent",
        scale=2, origin=(0,0), y=0.40, color=color.white,
    )
    status_text = Text(
        text='Cubo resuelto',
        scale=1, origin=(0,0), y=-0.30,
        color=color.Color(0.4, 1, 0.5, 1),
    )
    moves_text = Text(
        text='', scale=0.8, origin=(0,0), y=-0.40,
        color=color.Color(0.8, 0.8, 0.86, 1),
    )

    scramble_count = [0]
    solving = [False]

    def on_shuffle():
        if cube_3d.is_busy() or solving[0]:
            return

        status_text.text = 'Desordenando...'
        status_text.color = color.Color(1, 0.78, 0.31, 1)
        moves_text.text = ''

        num_moves = random.randint(5, 7)
        scramble_moves = []
        last = None
        for _ in range(num_moves):
            candidates = [m for m in ALL_MOVES if (not last or m[0] != last[0])]
            move = random.choice(candidates)
            scramble_moves.append(move)
            last = move

        cube_logic.apply_moves(scramble_moves)
        scramble_count[0] = num_moves

        print(f"\nScramble: {' '.join(scramble_moves)}")
        print(cube_logic)

        old_speed = cube_3d.anim_speed
        cube_3d.anim_speed = 180

        def after_scramble():
            cube_3d.anim_speed = old_speed
            status_text.text = f'Desordenado ({num_moves} movimientos)'
            status_text.color = color.Color(1, 0.78, 0.31, 1)

        cube_3d.enqueue_moves(scramble_moves, on_done=after_scramble)

    def on_solve():
        if cube_3d.is_busy() or solving[0]:
            return
        if cube_logic.is_solved():
            status_text.text = 'El cubo ya esta resuelto!'
            status_text.color = color.Color(0.4, 1, 0.5, 1)
            return

        solving[0] = True
        status_text.text = 'Buscando solucion con IDA*...'
        status_text.color = color.Color(0.4, 0.7, 1, 1)
        moves_text.text = ''

        print("\nIniciando IDA*...")
        solution = solver.solve(cube_logic.copy())

        if not solution:
            status_text.text = 'No se encontro solucion'
            status_text.color = color.Color(1, 0.31, 0.31, 1)
            solving[0] = False
            return

        print(f"Solucion: {' '.join(solution)} ({len(solution)} movimientos)")
        cube_logic.apply_moves(solution)
        moves_text.text = 'Mov: ' + ' > '.join(solution)
        status_text.text = f'Ejecutando {len(solution)} movimientos...'
        status_text.color = color.Color(0.4, 0.7, 1, 1)
        cube_3d.anim_speed = 180

        def after_solve():
            solving[0] = False
            status_text.text = f'Resuelto ({len(solution)} movimientos)'
            status_text.color = color.Color(0.4, 1, 0.5, 1)

        cube_3d.enqueue_moves(solution, on_done=after_solve)

    btn_w, btn_h = 0.25, 0.06

    Button(
        text='Desordenar',
        scale=(btn_w, btn_h), position=(-0.18, 0.30),
        color=color.Color(0.2, 0.2, 0.27, 1),
        highlight_color=color.Color(0.31, 0.31, 0.43, 1),
        pressed_color=color.Color(0.16, 0.16, 0.22, 1),
        text_color=color.white, on_click=on_shuffle,
    )

    Button(
        text='Resolver (IDA*)',
        scale=(btn_w, btn_h), position=(0.18, 0.30),
        color=color.Color(0.12, 0.35, 0.2, 1),
        highlight_color=color.Color(0.16, 0.51, 0.27, 1),
        pressed_color=color.Color(0.08, 0.27, 0.16, 1),
        text_color=color.white, on_click=on_solve,
    )

    # Usamos update() solo para las animaciones, la camara ya es manejada por EditorCamera()
    def update():
        cube_3d.update_animation(time.dt)

    scene_updater = Entity()
    scene_updater.update = update

    # FIX macOS UI bug: forzar un ligero cambio de tamano para refrescar textos y botones
    def fix_mac_ui():
        window.size = (window.size[0] + 1, window.size[1])
        invoke(setattr, window, 'size', (window.size[0] - 1, window.size[1]), delay=0.05)
    
    invoke(fix_mac_ui, delay=0.1)

    app.run()


if __name__ == '__main__':
    main()