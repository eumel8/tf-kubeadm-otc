#!/usr/bin/env python3
"""Web UI for German prompt-driven stories and upstream NCM TinyStories."""

import argparse
from datetime import datetime, timezone
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
from urllib.parse import parse_qs, urlencode, urlsplit

RESULTS = Path("/opt/ncm/results")
RUNNER = "/usr/local/bin/ncm-tinystories"
GERMAN_SCRIPT = "/opt/ncm/deutsche-geschichte.py"
PYTHON = "/opt/ncm/venv/bin/python"
DEFAULT_PROMPT = "Eine Geschichte über wildgewordene Roboter, die eine Stadt auf den Kopf stellen."
RUN_NAME = re.compile(r"^[0-9]{8}T[0-9]{6}-[A-Za-z0-9]{6}$")
STORY_NAME = re.compile(r"^geschichte-[0-9]{8}T[0-9]{12}Z-[a-f0-9]{8}\.txt$")
# Use the same default topic as the installed German CLI/TUI.
spec = importlib.util.spec_from_file_location("deutsche_geschichte", Path(__file__).with_name("deutsche-geschichte.py"))
if spec and spec.origin and Path(spec.origin).is_file():
    german_cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(german_cli)
    DEFAULT_PROMPT = german_cli.DEFAULT_PROMPT
CSS = """
body{font:16px/1.5 system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;
background:#111827;color:#e5e7eb}a{color:#93c5fd}header{display:flex;justify-content:space-between;
align-items:baseline;gap:1rem}main{display:grid;gap:1rem}section,article{background:#1f2937;
padding:1rem;border-radius:.6rem}input,button{padding:.5rem;border-radius:.3rem;font:inherit}
input{max-width:6rem}button{cursor:pointer}form{display:flex;gap:.8rem;align-items:end;flex-wrap:wrap}
label{display:grid;gap:.2rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:22rem;
overflow:auto;background:#111827;padding:1rem}article{margin:.5rem 0}article p{white-space:pre-wrap}
.notice{color:#fbbf24}small{color:#9ca3af}textarea{width:100%;min-height:8rem;
font:inherit;padding:.6rem;box-sizing:border-box}form.story{display:block}form.story label{margin-bottom:1rem}
"""


def e(value):
    return html.escape(str(value), quote=True)


def safe_run(name):
    if not RUN_NAME.fullmatch(name):
        return None
    path = RESULTS / name
    if path.is_symlink() or not path.is_dir():
        return None
    return path


def safe_story(name):
    if not STORY_NAME.fullmatch(name):
        return None
    path = RESULTS / name
    if path.is_symlink() or not path.is_file():
        return None
    return path


def recent_german_stories():
    if not RESULTS.is_dir():
        return []
    return sorted(
        (p.name for p in RESULTS.iterdir() if safe_story(p.name) is not None),
        reverse=True,
    )[:30]


def recent_runs():
    if not RESULTS.is_dir():
        return []
    return sorted(
        (p.name for p in RESULTS.iterdir() if safe_run(p.name) is not None),
        reverse=True,
    )[:30]


def read_log(path):
    if not path.is_file() or path.is_symlink():
        return ""
    # Read only the end of large logs, without loading the complete file into memory.
    with path.open("rb") as source:
        source.seek(0, os.SEEK_END)
        source.seek(max(0, source.tell() - 16000))
        return source.read().decode("utf-8", errors="replace")


def read_stories(path):
    if not path.is_file() or path.is_symlink():
        return []
    stories = []
    with path.open(encoding="utf-8") as source:
        for line in source:
            if len(stories) >= 100:
                break
            try:
                row = json.loads(line)
                if isinstance(row, dict) and isinstance(row.get("text"), str):
                    stories.append((row.get("seed", "?"), row["text"]))
            except json.JSONDecodeError:
                continue
    return stories


class WebUI(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        super().__init__(address, Handler)
        self.process = None
        self.process_log = None
        self.process_story = None
        self.guard = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type="text/html; charset=utf-8", extra=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path not in ("/", "/ncm"):
            self.respond(404, "Not found", "text/plain; charset=utf-8")
            return
        if url.path == "/":
            self.german_page(url)
        else:
            self.ncm_page(url)

    def job_state(self):
        with self.server.guard:
            process = self.server.process
            return (process is not None and process.poll() is None,
                    process.poll() if process is not None else None,
                    self.server.process_log, self.server.process_story)

    def german_page(self, url):
        selected = parse_qs(url.query).get("story", [""])[0]
        story = safe_story(selected) if selected else None
        if selected and story is None:
            self.respond(404, "Geschichte nicht gefunden", "text/plain; charset=utf-8")
            return
        running, result, process_log, process_story = self.job_state()
        running = running and process_log is not None and process_log.name != "webui-job.log"
        # Keep the browser on the individual job until it finishes. On success,
        # show the story immediately instead of only adding a link below the form.
        if not selected and not running and result == 0 and process_story and safe_story(process_story.name):
            story = process_story
        refresh = '<meta http-equiv="refresh" content="5">' if running else ""
        parts = [f'<!doctype html><html lang="de"><meta charset="utf-8">{refresh}'
                 '<meta name="viewport" content="width=device-width, initial-scale=1">'
                 f'<title>Deutsche Geschichten</title><style>{CSS}</style><body>'
                 '<header><h1>Deutsche Geschichten</h1><a href="/ncm">NCM TinyStories (Englisch)</a></header><main>'
                 '<p>Schreibe eine Geschichte mit eigenem Thema. Dafür wird '
                 '<a href="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct">Qwen2.5-1.5B-Instruct</a> '
                 'verwendet; das <a href="https://github.com/HazyResearch/ncm">NCM-Modell</a> '
                 'kann keine Prompts verarbeiten.</p><section><h2>Neue Geschichte</h2>']
        if running:
            parts.append('<p class="notice">Generierung läuft – die Seite aktualisiert sich alle 5 Sekunden.</p>')
        else:
            parts.append('<form class="story" method="post" action="/geschichte">'
                         f'<label>Thema / Anweisung<textarea name="prompt" maxlength="2000" required>{e(DEFAULT_PROMPT)}</textarea></label>'
                         '<label>Maximale neue Tokens <input type="number" name="tokens" min="1" max="2048" value="400" required></label>'
                         '<label>Temperatur <input type="number" name="temperature" min="0.1" max="2" step="0.1" value="0.8" required></label>'
                         '<label>Top-p <input type="number" name="top_p" min="0.05" max="1" step="0.05" value="0.9" required></label>'
                         '<button type="submit">Geschichte generieren</button></form>')
        if result is not None and not running and process_log and process_log.name != "webui-job.log":
            if result:
                parts.append(f'<p class="notice">Generierung fehlgeschlagen (Exit-Code {result}). '
                             'Fehlerdetails stehen im Auftragslog unten.</p>')
            else:
                parts.append('<p>Geschichte erfolgreich generiert.</p>')
        if process_story is not None:
            if safe_story(process_story.name):
                parts.append(f'<p><a href="/?{urlencode({"story": process_story.name})}">Neueste Geschichte lesen</a></p>')
            elif running:
                parts.append('<p>Das Modell lädt oder schreibt noch.</p>')
        if process_log and process_log.name != "webui-job.log" and process_log.is_file():
            parts.append(f'<details{" open" if result else ""}><summary>Auftragslog</summary>'
                         f'<pre>{e(read_log(process_log) or "Noch keine Ausgabe (Modell wird ggf. geladen).")}</pre></details>')
        parts.append('</section><section><h2>Gespeicherte Geschichten</h2><ul>')
        for name in recent_german_stories():
            parts.append(f'<li><a href="/?{urlencode({"story": name})}">{e(name)}</a></li>')
        parts.append('</ul></section>')
        if story:
            parts.append(f'<section><h2>{e(story.name)}</h2><article><p>{e(story.read_text(encoding="utf-8"))}</p></article></section>')
        parts.append('</main></body></html>')
        self.respond(200, "".join(parts))

    def ncm_page(self, url):
        selected = parse_qs(url.query).get("run", [""])[0]
        if len(selected) > 40:
            self.respond(404, "Run not found", "text/plain; charset=utf-8")
            return
        run = safe_run(selected) if selected else None
        if selected and run is None:
            self.respond(404, "Run not found", "text/plain; charset=utf-8")
            return
        running, result, process_log, _ = self.job_state()
        running = running and process_log is not None and process_log.name == "webui-job.log"
        refresh = '<meta http-equiv="refresh" content="5">' if running else ""
        parts = [f'<!doctype html><html lang="en"><meta charset="utf-8">{refresh}'
                 '<meta name="viewport" content="width=device-width, initial-scale=1">'
                 f'<title>NCM TinyStories</title><style>{CSS}</style><body>'
                 '<header><h1>NCM TinyStories</h1><a href="/">Deutsche Geschichten</a></header><main>'
                 '<p>Unconditional English stories generated with '
                 '<a href="https://github.com/HazyResearch/ncm">HazyResearch/NCM</a>. '
                 'No topic prompt is supported by this checkpoint.</p><section><h2>Generate</h2>']
        if running:
            parts.append('<p class="notice">Evaluation running — page refreshes every 5 seconds.</p>')
        else:
            parts.append('<form method="post" action="/run">'
                         '<label>Stories per seed (5 seeds)<input type="number" name="samples" min="1" max="256" value="16" required></label>'
                         '<label>Batch size<input type="number" name="batch" min="1" max="128" value="4" required></label>'
                         '<button type="submit">Start NCM evaluation</button></form>')
        if result is not None and not running and process_log and process_log.name == "webui-job.log":
            parts.append(f'<p>Last web job exited with status {result}.</p>')
        if process_log and process_log.name == "webui-job.log" and process_log.is_file():
            parts.append(f'<details><summary>Web job log</summary><pre>{e(read_log(process_log))}</pre></details>')
        parts.append('</section><section><h2>Saved runs</h2><ul>')
        for name in recent_runs():
            parts.append(f'<li><a href="/ncm?{urlencode({"run": name})}">{e(name)}</a></li>')
        parts.append('</ul></section>')
        if run:
            stories = read_stories(run / "stories.jsonl")
            parts.append(f'<section><h2>{e(run.name)}</h2><p>{len(stories)} stories shown (up to 100).</p>')
            for seed, text in stories:
                parts.append(f'<article><small>Seed {e(seed)}</small><p>{e(text)}</p></article>')
            for filename in ("evaluation.log", "shard_0.log"):
                log = read_log(run / filename)
                if log:
                    parts.append(f'<details><summary>{e(filename)}</summary><pre>{e(log)}</pre></details>')
            parts.append('</section>')
        parts.append('</main></body></html>')
        self.respond(200, "".join(parts))

    def do_POST(self):
        if self.path not in ("/run", "/geschichte"):
            self.respond(404, "Not found", "text/plain; charset=utf-8")
            return
        try:
            if self.headers.get("Origin"):
                origin = urlsplit(self.headers["Origin"])
                if origin.scheme != "http" or origin.netloc != self.headers.get("Host"):
                    raise ValueError("Invalid origin")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise ValueError("Invalid form size")
            form = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True)
            fields = {"samples", "batch"} if self.path == "/run" else {"prompt", "tokens", "temperature", "top_p"}
            if set(form) != fields or any(len(values) != 1 for values in form.values()):
                raise ValueError("Invalid form fields")
            if self.path == "/run":
                samples = int(form["samples"][0])
                batch = int(form["batch"][0])
                if not 1 <= samples <= 256 or not 1 <= batch <= 128:
                    raise ValueError("Values outside allowed range")
            else:
                prompt = form["prompt"][0].strip()
                tokens = int(form["tokens"][0])
                temperature = float(form["temperature"][0])
                top_p = float(form["top_p"][0])
                if not (0 < len(prompt) <= 2000 and 1 <= tokens <= 2048
                        and 0.1 <= temperature <= 2 and 0.05 <= top_p <= 1):
                    raise ValueError("Values outside allowed range")
        except (ValueError, KeyError, UnicodeDecodeError):
            self.respond(400, "Ungültige Eingabe oder Parameter.", "text/plain; charset=utf-8")
            return
        with self.server.guard:
            if self.server.process is not None and self.server.process.poll() is None:
                self.respond(409, "Ein Auftrag läuft bereits.", "text/plain; charset=utf-8")
                return
            RESULTS.mkdir(parents=True, exist_ok=True)
            if self.path == "/run":
                log = RESULTS / "webui-job.log"
                command = [RUNNER]
                env = dict(os.environ, NCM_SAMPLES=str(samples), NCM_BATCH_SIZE=str(batch))
                story_path = None
                redirect = "/ncm"
            else:
                name = f"geschichte-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{secrets.token_hex(4)}.txt"
                story_path = RESULTS / name
                log = RESULTS / f"{name}.log"
                command = ["flock", "-n", "/opt/ncm/ncm-tinystories.lock",
                           PYTHON, GERMAN_SCRIPT, prompt, "--max-new-tokens", str(tokens),
                           "--temperature", str(temperature), "--top-p", str(top_p),
                           "--output", str(story_path)]
                env = dict(os.environ, CUDA_VISIBLE_DEVICES="0", HF_HOME="/opt/ncm/cache")
                redirect = "/"
            with log.open("wb") as output:
                self.server.process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, env=env)
            self.server.process_log = log
            self.server.process_story = story_path
        self.respond(303, "", extra={"Location": redirect})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    with WebUI((args.host, args.port)) as server:
        print(f"Stories WebUI listening on http://{args.host}:{args.port}/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
