"""Local FastAPI interface for the existing AI Organization agents."""

import asyncio
import json
import logging
import os
import re
import shutil
import threading
import unicodedata
import uuid
from pathlib import Path
from queue import Empty
from urllib.error import URLError
from urllib.request import Request as URLRequest, urlopen

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

if __package__:
    from . import storage
    from . import sources
else:
    import storage
    import sources


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

import config
from agents import rag
from orchestrator import handle


logger = logging.getLogger("ai_organization.web")
UPLOADS_DIR = ROOT / "uploads"
WEB_CHROMA_DIR = ROOT / "backend" / "data" / "chroma"
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def _use_web_chroma_copy():
    source = ROOT / config.CHROMA_DIR
    if not WEB_CHROMA_DIR.exists() and source.is_dir():
        WEB_CHROMA_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, WEB_CHROMA_DIR)
    rag.CHROMA_DIR = str(WEB_CHROMA_DIR)


_use_web_chroma_copy()

app = FastAPI(title="AI Organization API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatTitle(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=50_000)


def _ollama_status():
    request = URLRequest(
        f"{OLLAMA_BASE_URL}/api/tags", headers={"Accept": "application/json"}
    )
    try:
        with urlopen(request, timeout=1.5) as response:
            data = json.loads(response.read().decode("utf-8"))
        models = [
            item.get("name", "")
            for item in data.get("models", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        return True, models, None
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
        return False, [], str(error)


def _documents():
    try:
        return sources.list_documents(chroma_dir=rag.CHROMA_DIR, uploads_dir=UPLOADS_DIR)
    except Exception:
        logger.exception("Could not read the ingested document list.")
        raise HTTPException(
            status_code=503,
            detail="Document list is temporarily unavailable.",
        )


@app.get("/api/health")
async def health():
    connected, models, _ = await run_in_threadpool(_ollama_status)
    documents = _documents()
    return {
        "status": "ok" if connected else "degraded",
        "ollama_connected": connected,
        "ollama_message": "Ollama is ready." if connected else "Ollama is not reachable. Start Ollama to send tasks.",
        "models": models,
        "docs_count": len(documents),
    }


@app.get("/api/agents")
async def agents():
    return [
        {
            "id": "orchestrator",
            "name": "Orchestrator",
            "description": "Plans the work and routes it to the right specialists.",
            "model": config.ORCHESTRATOR_MODEL,
        },
        {
            "id": "coding",
            "name": "Coding",
            "description": "Writes, debugs, and tests code.",
            "model": config.CODING_MODEL,
        },
        {
            "id": "research",
            "name": "Research",
            "description": "Finds and verifies useful information.",
            "model": config.RESEARCH_MODEL,
        },
        {
            "id": "study",
            "name": "Study",
            "description": "Explains concepts and builds learning materials.",
            "model": config.STUDY_MODEL,
        },
        {
            "id": "rag",
            "name": "RAG",
            "description": "Answers questions using your ingested documents.",
            "model": f"{config.STUDY_MODEL} · {config.VISION_MODEL} · {config.EMBED_MODEL}",
        },
    ]


@app.get("/api/chats")
async def chats():
    return storage.list_chats()


@app.post("/api/chats", status_code=201)
async def create_chat():
    return storage.create_chat()


@app.get("/api/chats/{chat_id}")
async def get_chat(chat_id: str):
    chat = storage.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return chat


@app.patch("/api/chats/{chat_id}")
async def rename_chat(chat_id: str, payload: ChatTitle):
    chat = storage.rename_chat(chat_id, payload.title)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return chat


@app.delete("/api/chats/{chat_id}", status_code=204)
async def remove_chat(chat_id: str):
    if not storage.delete_chat(chat_id):
        raise HTTPException(status_code=404, detail="Chat not found.")


@app.delete("/api/chats", status_code=204)
async def remove_all_chats():
    storage.delete_all_chats()


def _sse(event_name, payload):
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/api/chats/{chat_id}/message")
async def send_message(chat_id: str, payload: MessageRequest, request: Request):
    chat = storage.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found.")
    connected, _, _ = await run_in_threadpool(_ollama_status)
    if not connected:
        raise HTTPException(
            status_code=503,
            detail="Ollama isn't running. Start Ollama, then try again.",
        )
    prompt = payload.content.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Message can't be empty.")
    history = [
        {"role": message["role"], "content": message["content"]}
        for message in chat["messages"][-6:]
        if message.get("role") in ("user", "assistant")
        and isinstance(message.get("content"), str)
    ]
    chat = storage.append_message(chat_id, {"role": "user", "content": prompt})
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found.")
    events = asyncio.Queue()
    stopped = threading.Event()
    loop = asyncio.get_running_loop()
    active_agents = []

    def report_step(message):
        if stopped.is_set():
            raise RuntimeError("The client stopped listening.")
        agent = "orchestrator"
        match = re.match(r"^\[([a-z]+)\]", message)
        if match:
            agent = match.group(1)
        if message.startswith("Agents:"):
            active_agents[:] = [
                name.strip()
                for name in message.partition(":")[2].split("->")
                if name.strip()
            ]
        loop.call_soon_threadsafe(
            events.put_nowait,
            {"event": "step", "data": {"message": message, "agent": agent}},
        )

    def run_task():
        return handle(prompt, on_step=report_step, history=history)

    worker = asyncio.create_task(run_in_threadpool(run_task))
    worker.add_done_callback(
        lambda task: task.exception() if not task.cancelled() else None
    )

    async def stream():
        try:
            while not worker.done():
                if await request_is_disconnected():
                    stopped.set()
                    return
                try:
                    item = await asyncio.wait_for(events.get(), timeout=0.25)
                    yield _sse(item["event"], item["data"])
                except asyncio.TimeoutError:
                    continue
            while not events.empty():
                item = events.get_nowait()
                yield _sse(item["event"], item["data"])

            try:
                answer, steps = worker.result()
            except Exception:
                logger.exception("Agent task failed for chat %s.", chat_id)
                answer = "I couldn't complete that task. Please retry, and check that Ollama is running."
                storage.append_message(
                    chat_id,
                    {"role": "assistant", "content": answer, "agents_used": [], "steps": []},
                )
                yield _sse("error", {"message": answer})
                return

            failed_step = next(
                (
                    (name, output)
                    for name, output in steps
                    if output.startswith(f"{name} agent mein error:")
                ),
                None,
            )
            if failed_step:
                logger.error("Agent %s returned an error: %s", failed_step[0], failed_step[1])
                answer = "One of the agents ran into a problem. Please check Ollama and try again."
                storage.append_message(
                    chat_id,
                    {"role": "assistant", "content": answer, "agents_used": active_agents, "steps": steps},
                )
                yield _sse("error", {"message": answer})
                return

            if not active_agents:
                active_agents.extend(name for name, _ in steps)
            serial_steps = [{"agent": name, "output": output} for name, output in steps]
            evidence = []
            if "rag" in active_agents:
                try:
                    evidence = await run_in_threadpool(
                        sources.retrieve_sources, prompt, rag.CHROMA_DIR
                    )
                except Exception:
                    logger.exception("Could not retrieve evidence for chat %s.", chat_id)
                    yield _sse(
                        "sources_error",
                        {"message": "The answer completed, but its document evidence could not be loaded."},
                    )
                yield _sse("sources", {"sources": evidence})
            for name, output in steps:
                yield _sse("agent_output", {"agent": name, "output": output})
            storage.append_message(
                chat_id,
                {
                    "role": "assistant",
                    "content": answer,
                    "agents_used": active_agents,
                    "steps": serial_steps,
                    "sources": evidence,
                },
            )
            yield _sse(
                "final",
                {
                    "answer": answer,
                    "agents_used": active_agents,
                    "steps": serial_steps,
                    "sources": evidence,
                },
            )
        finally:
            stopped.set()

    async def request_is_disconnected():
        return await request.is_disconnected()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _safe_filename(filename):
    basename = filename.replace("\\", "/").split("/")[-1]
    basename = unicodedata.normalize("NFKC", basename)
    basename = re.sub(r"[^A-Za-z0-9._-]", "_", basename).strip("._")
    if not basename or basename in (".", "..") or len(basename) > 160:
        raise HTTPException(status_code=400, detail="Please choose a valid file name.")
    if Path(basename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Allowed file types: PDF, PNG, JPG, JPEG, TXT, and Markdown.",
        )
    return basename


@app.post("/api/upload", status_code=201)
async def upload(file: UploadFile = File(...)):
    basename = _safe_filename(file.filename or "")
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPLOADS_DIR / f"{uuid.uuid4().hex}_{basename}"
    size = 0
    try:
        with destination.open("wb") as saved_file:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Files must be 50 MB or smaller.",
                    )
                saved_file.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        result = await run_in_threadpool(rag.ingest, str(destination))
        return {
            "name": basename,
            "size": size,
            "message": result,
            "documents": _documents(),
        }
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except Exception:
        destination.unlink(missing_ok=True)
        logger.exception("Could not ingest uploaded file %s.", basename)
        raise HTTPException(
            status_code=503,
            detail="The file could not be ingested. Check that Ollama is running and try again.",
        )
    finally:
        await file.close()


@app.get("/api/documents")
async def documents():
    return await run_in_threadpool(_documents)


@app.get("/api/documents/{file}/download")
async def download_document(file: str):
    try:
        source = sources.get_document(file, chroma_dir=rag.CHROMA_DIR)
        if source is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        path = (UPLOADS_DIR / file).resolve()
        if os.path.commonpath([str(UPLOADS_DIR.resolve()), str(path)]) != str(
            UPLOADS_DIR.resolve()
        ):
            raise HTTPException(status_code=400, detail="Invalid document path.")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Original file is unavailable.")
        from fastapi.responses import FileResponse

        return FileResponse(
            path, filename=source["name"], content_disposition_type="inline"
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document name.")


@app.get("/api/documents/{file}")
async def document(file: str):
    try:
        result = await run_in_threadpool(
            sources.get_document, file, rag.CHROMA_DIR
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document name.")
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


@app.delete("/api/documents/{file}", status_code=204)
async def remove_document(file: str):
    try:
        deleted = await run_in_threadpool(
            sources.delete_document, file, rag.CHROMA_DIR, UPLOADS_DIR
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document name.")
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")


@app.exception_handler(Exception)
async def unexpected_error_handler(request, error):
    logger.exception("Unhandled API error for %s %s.", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Check the server log and try again."},
    )
