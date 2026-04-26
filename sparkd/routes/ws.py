from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sparkd.db.engine import session_scope
from sparkd.db.models import Box
from sparkd.services.launch import LaunchService

router = APIRouter()


@router.websocket("/ws/launches/{launch_id}")
async def launch_log_stream(ws: WebSocket, launch_id: str) -> None:
    await ws.accept()
    ls: LaunchService = ws.app.state.launches
    pool = ws.app.state.pool
    rec = await ls.get(launch_id)
    async with session_scope() as s:
        row = await s.get(Box, rec.box_id)
        target = ws.app.state.boxes._target_for(row)
    log_path = rec.log_path or f"~/.sparkd-launches/{launch_id}.log"
    # If the log file doesn't exist yet, wait briefly for it to appear (the
    # `nohup ...` from launch starts asynchronously). After that, hand off to
    # `tail -F` which follows the file even if it's recreated. Older launch
    # records that predate the log-redirect change have no on-disk log; in
    # that case emit a clear message rather than tail's terse 'cannot open'.
    cmd = (
        f"if [ -f {log_path} ] || "
        f"( for i in 1 2 3 4 5; do sleep 0.4; [ -f {log_path} ] && exit 0; done; exit 1 ); "
        f"then tail -F {log_path} 2>&1; "
        f"else echo \"no log file for launch {launch_id}.\"; "
        f"echo \"this usually means the launch was created before the log-redirect fix, \"; "
        f"echo \"or ./run-recipe.sh failed before any output could be redirected.\"; "
        f"fi"
    )
    try:
        async for channel, line in pool.stream(target, cmd):
            await ws.send_json({"channel": channel, "line": line})
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        await ws.send_json({"channel": "error", "line": str(exc)})
        await ws.close(code=1011)


@router.websocket("/ws/boxes/{box_id}/status")
async def status_stream(ws: WebSocket, box_id: str) -> None:
    await ws.accept()
    svc = ws.app.state.status
    try:
        while True:
            snap = await svc.snapshot(box_id)
            await ws.send_json(
                {
                    "box_id": snap.box_id,
                    "connectivity": snap.connectivity,
                    "running_models": [m.__dict__ for m in snap.running_models],
                    "drift_missing_container": snap.drift_missing_container,
                    "captured_at": snap.captured_at.isoformat(),
                }
            )
            await asyncio.sleep(5.0)
    except WebSocketDisconnect:
        return


@router.websocket("/ws/advisor/{session_id}")
async def advisor_stream(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    svc = ws.app.state.advisor
    hf = ws.app.state.hf
    boxes = ws.app.state.boxes
    sess = await svc.get_session(session_id)
    try:
        if sess.kind == "recipe" and sess.hf_model_id:
            info = await hf.fetch(sess.hf_model_id)
            from sparkd.routes.advisor import _resolve_caps
            caps = await _resolve_caps(sess.target_box_id, boxes)
            stream = svc.generate_recipe(session_id, info=info, caps=caps)
        else:
            await ws.send_json({"type": "error", "message": "missing context"})
            await ws.close(code=1003)
            return
        async for ev in stream:
            await ws.send_json(ev)
        await ws.send_json({"type": "done"})
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        await ws.send_json({"type": "error", "message": str(exc)})
        await ws.close(code=1011)
