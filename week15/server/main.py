import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from simulation.world import World

WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web"
HOST = "127.0.0.1"
PORT = 8000
TICK_DT = 1 / 30      
BROADCAST_EVERY = 2

app = FastAPI(title="Simulación de evacuación por incendio")
world = World(n_agents=48)
clients: set[WebSocket] = set()


async def simulation_loop():
    tick = 0
    while True:
        world.step(TICK_DT)
        tick += 1
        if tick % BROADCAST_EVERY == 0:
            await broadcast(world.state_dict())
        await asyncio.sleep(TICK_DT)


async def broadcast(message: dict):
    if not clients:
        return
    data = json.dumps(message)
    dead = []
    for ws in clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


def handle_command(raw: str):
    try:
        msg = json.loads(raw)
    except ValueError:
        return
    cmd = msg.get("cmd")
    if cmd == "reset":
        world.reset(msg.get("agents"))
    elif cmd == "spark":
        world.spark(msg.get("room"))
    elif cmd == "agents":
        world.set_agents(int(msg.get("n", world.n_agents)))
    elif cmd == "pause":
        world.set_paused(True)
    elif cmd == "resume":
        world.set_paused(False)
    elif cmd == "speed":
        world.set_speed(float(msg.get("value", 1.0)))


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(simulation_loop())
    print(f"\n  → Simulación lista en: http://{HOST}:{PORT}\n")


@app.middleware("http")
async def no_cache_static(request, call_next):
    # en desarrollo cambiamos web/ seguido; sin esto el navegador puede
    # seguir usando una copia vieja de index.html/style.css/main.js en caché.
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
async def health():
    return {"status": "ok", "clients": len(clients), "stats": world.stats()}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    await websocket.send_text(json.dumps(world.floorplan_dict()))
    await websocket.send_text(json.dumps(world.state_dict()))
    try:
        while True:
            raw = await websocket.receive_text()
            handle_command(raw)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host=HOST, port=PORT, reload=True)
