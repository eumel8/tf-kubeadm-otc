#!/usr/bin/env python3
"""Generate a prompt-controlled German story on the existing NCM GPU ECS."""

import argparse
import curses
from datetime import datetime, timezone
from pathlib import Path
import queue
import sys
import textwrap
import threading

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
RESULTS = Path("/opt/ncm/results")
DEFAULT_PROMPT = "Eine Geschichte über wildgewordene Roboter, die eine Stadt auf den Kopf stellen."


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "prompt",
        nargs="?",
        default=DEFAULT_PROMPT,
        help="Thema oder konkrete Anweisung für die deutsche Geschichte",
    )
    parser.add_argument("--max-new-tokens", type=int, default=400, help="Maximale Länge der Antwort in Tokens (Standard: 400)")
    parser.add_argument("--temperature", type=float, default=0.8, help="Kreativität, größer = zufälliger (Standard: 0.8)")
    parser.add_argument("--top-p", type=float, default=0.9, help="Nucleus-Sampling (Standard: 0.9)")
    parser.add_argument("--seed", type=int, default=None, help="Zufalls-Seed für wiederholbare Versuche")
    parser.add_argument("--output", type=Path, help="Ausgabedatei; Standard: /opt/ncm/results/geschichte-<Zeit>.txt")
    parser.add_argument("--tui", action="store_true", help="Interaktive Terminaloberfläche starten")
    args = parser.parse_args()
    if args.max_new_tokens < 1:
        parser.error("--max-new-tokens muss mindestens 1 sein")
    if args.temperature <= 0:
        parser.error("--temperature muss größer als 0 sein")
    if not 0 < args.top_p <= 1:
        parser.error("--top-p muss zwischen 0 (exklusiv) und 1 liegen")
    if args.tui and args.output:
        parser.error("--output ist im TUI-Modus nicht verfügbar; jeder Lauf erhält eine eigene Datei")
    return args


def load_model():
    # Keep imports after argparse so --help works without installed GPU packages.
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise SystemExit("CUDA nicht verfügbar. Auf der ECS nvidia-smi prüfen.")

    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        revision=REVISION,
        torch_dtype=torch.float16,
    ).to("cuda").eval()
    return tokenizer, model


def generate(prompt, max_new_tokens, temperature, top_p, seed, tokenizer, model):
    import torch

    if seed is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    messages = [
        {
            "role": "system",
            "content": (
                "Du schreibst fantasievolle, in sich abgeschlossene Kurzgeschichten "
                "ausschließlich auf Deutsch. Gib nur die Geschichte aus, ohne Vorrede, "
                "Erklärung oder Übersetzung."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    inputs = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True,
        return_dict=True, return_tensors="pt",
    ).to("cuda")
    with torch.inference_mode():
        result = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
            pad_token_id=tokenizer.pad_token_id,
        )
    return tokenizer.decode(result[0, inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()


def save(story, output=None):
    output = output or RESULTS / f"geschichte-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(story + "\n", encoding="utf-8")
    return output


def display_lines(story, width):
    lines = []
    for paragraph in story.splitlines():
        lines.extend(textwrap.wrap(paragraph, width=max(1, width), break_long_words=True) or [""])
    return lines


def put(screen, y, x, text):
    height, width = screen.getmaxyx()
    if 0 <= y < height and 0 <= x < width:
        try:
            screen.addnstr(y, x, str(text), width - x - 1)
        except curses.error:
            pass


def edit_prompt(screen, initial):
    """Edit one scrollable line; Enter saves, Escape cancels."""
    value = list(initial)
    pos = len(value)
    screen.timeout(-1)
    try:
        while True:
            height, width = screen.getmaxyx()
            screen.erase()
            put(screen, 0, 0, "Prompt bearbeiten: Enter speichern | Esc abbrechen")
            if height > 2:
                available = max(1, width - 2)
                start = max(0, pos - available + 1)
                put(screen, 2, 0, "".join(value[start:start + available]))
                try:
                    screen.move(2, min(pos - start, width - 2))
                except curses.error:
                    pass
            screen.refresh()
            key = screen.get_wch()
            if key in ("\n", "\r", curses.KEY_ENTER):
                return "".join(value).strip() or initial
            if key == "\x1b":
                return initial
            if key in (curses.KEY_BACKSPACE, "\b", "\x7f") and pos:
                value.pop(pos - 1)
                pos -= 1
            elif key == curses.KEY_DC and pos < len(value):
                value.pop(pos)
            elif key == curses.KEY_LEFT:
                pos = max(0, pos - 1)
            elif key == curses.KEY_RIGHT:
                pos = min(len(value), pos + 1)
            elif key == curses.KEY_HOME:
                pos = 0
            elif key == curses.KEY_END:
                pos = len(value)
            elif isinstance(key, str) and key.isprintable():
                value.insert(pos, key)
                pos += 1
    finally:
        screen.timeout(150)


def tui(screen, args):
    curses.curs_set(0)
    screen.keypad(True)
    screen.timeout(150)
    prompt = args.prompt
    story = ""
    saved = ""
    status = "Modell laden (beim ersten Mal Download) ..."
    scroll = 0
    tasks = queue.Queue()
    tokenizer = model = None
    busy = True

    def worker(kind, fn):
        try:
            tasks.put((kind, fn(), None))
        except Exception as exc:
            tasks.put((kind, None, str(exc)))

    threading.Thread(target=worker, args=("load", load_model), daemon=True).start()
    while True:
        try:
            kind, value, error = tasks.get_nowait()
            busy = False
            if error:
                status = f"Fehler: {error}"
            elif kind == "load":
                tokenizer, model = value
                status = "Modell bereit. G generiert eine Geschichte."
            else:
                story, saved = value
                scroll = 0
                status = f"Gespeichert: {saved}"
        except queue.Empty:
            pass

        height, width = screen.getmaxyx()
        screen.erase()
        put(screen, 0, 0, "Deutsche Geschichten | Q Ende | E Prompt | G Generieren")
        put(screen, 1, 0, f"Prompt: {prompt}")
        put(screen, 2, 0, f"Tokens: {args.max_new_tokens} (< >) | Temp: {args.temperature:.2f} (- +) | Top-p: {args.top_p:.2f} ([ ])")
        put(screen, 3, 0, "Pfeile/PgUp/PgDn: Text scrollen | Modell: Qwen2.5-1.5B")
        put(screen, 4, 0, status)
        if height > 6:
            put(screen, 5, 0, "─" * max(0, width - 1))
            lines = display_lines(story, width - 1)
            visible = height - 6
            scroll = min(scroll, max(0, len(lines) - visible))
            for y, line in enumerate(lines[scroll:scroll + visible], start=6):
                put(screen, y, 0, line)
        screen.refresh()
        try:
            key = screen.get_wch()
        except curses.error:
            continue
        if key in ("q", "Q") and not busy:
            return
        if key in (curses.KEY_DOWN, curses.KEY_NPAGE):
            scroll += max(1, height - 7) if key == curses.KEY_NPAGE else 1
        elif key in (curses.KEY_UP, curses.KEY_PPAGE):
            scroll = max(0, scroll - (max(1, height - 7) if key == curses.KEY_PPAGE else 1))
        elif busy:
            continue
        elif key in ("e", "E"):
            prompt = edit_prompt(screen, prompt)
        elif key in ("g", "G"):
            if model is None:
                status = "Modell noch nicht bereit."
                continue
            busy = True
            status = "Generiere ... (Q nach Abschluss möglich)"

            def run():
                result = generate(prompt, args.max_new_tokens, args.temperature, args.top_p,
                                  args.seed, tokenizer, model)
                return result, save(result)

            threading.Thread(target=worker, args=("generate", run), daemon=True).start()
        elif key == "+":
            args.temperature = round(min(2.0, args.temperature + 0.1), 2)
        elif key == "-":
            args.temperature = round(max(0.1, args.temperature - 0.1), 2)
        elif key == ">":
            args.max_new_tokens = min(2048, args.max_new_tokens + 100)
        elif key == "<":
            args.max_new_tokens = max(100, args.max_new_tokens - 100)
        elif key == "]":
            args.top_p = round(min(1.0, args.top_p + 0.05), 2)
        elif key == "[":
            args.top_p = round(max(0.05, args.top_p - 0.05), 2)


def main():
    args = arguments()
    if args.tui:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise SystemExit("--tui benötigt ein interaktives Terminal (z. B. ssh -t).")
        curses.wrapper(tui, args)
        return

    tokenizer, model = load_model()
    story = generate(args.prompt, args.max_new_tokens, args.temperature, args.top_p,
                     args.seed, tokenizer, model)
    output = save(story, args.output)
    print(story)
    print(f"\nGespeichert: {output}")


if __name__ == "__main__":
    main()
