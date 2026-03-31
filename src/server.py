#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import secrets
import socket
from dataclasses import dataclass
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

DEFAULT_PLANS = ["", ""]
SUMMARY_PROMPTS = [
    ">> 👍 有什么进步？",
    ">> 😮‍💨 有什么不足？",
    ">> 💪 明天计划做什么？",
]
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLAN_LINE_PATTERN = re.compile(r"^- \[(?P<done>[ xX])\]\s*(?P<text>.+?)\s*$")
ROOT_DIR = Path(__file__).resolve().parent.parent
PAGE_TEMPLATE_PATH = ROOT_DIR / "fixtures" / "page.html"
FORBIDDEN_TEMPLATE_PATH = ROOT_DIR / "fixtures" / "forbidden.html"


class ValidationError(ValueError):
    """Raised when submitted payload does not satisfy business rules."""


@dataclass(frozen=True)
class PlanItem:
    text: str
    done: bool


@dataclass(frozen=True)
class DailyEntry:
    date_text: str
    exercise: str
    plans: list[PlanItem]
    prompts: list[str]


@lru_cache(maxsize=1)
def _load_page_template() -> str:
    return PAGE_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _load_forbidden_template() -> str:
    return FORBIDDEN_TEMPLATE_PATH.read_text(encoding="utf-8")


def _render_plan_rows() -> str:
    return "\n".join(
        f'''
        <div class="plan-row">
          <input class="plan-done" type="checkbox" aria-label="done-{i}">
          <input class="plan-text" type="text" value="{html.escape(item)}" required>
          <button type="button" class="plan-del" aria-label="删除计划">删除</button>
        </div>
        '''
        for i, item in enumerate(DEFAULT_PLANS)
    )


def _render_prompt_fields() -> str:
    return "\n".join(
        f'''<label class="field-label">{html.escape(prompt)}\n<textarea class="auto-grow" name="prompt_{idx}" rows="3" required></textarea></label>'''
        for idx, prompt in enumerate(SUMMARY_PROMPTS)
    )


def render_page() -> str:
    return (
        _load_page_template()
        .replace("__TODAY__", dt.date.today().isoformat())
        .replace("__PLAN_ROWS__", _render_plan_rows())
        .replace("__PROMPTS_HTML__", _render_prompt_fields())
    )


def render_forbidden_page() -> str:
    return _load_forbidden_template()


def build_markdown(entry: DailyEntry) -> str:
    plan_lines = "\n".join(
        f"- [{'x' if item.done else ' '}] {item.text}" for item in entry.plans
    )
    return (
        "### 每日复盘总结\n\n"
        f">  📅 日期：{entry.date_text}\n\n\n"
        "#### 🎯 今日计划完成情况\n\n"
        f"{plan_lines}\n\n\n"
        "#### 🏃 运动\n\n"
        f"{entry.exercise}\n\n"
        "#### 🤔 总结\n\n"
        f"##### {SUMMARY_PROMPTS[0]}\n\n"
        f"{entry.prompts[0]}\n\n"
        f"##### {SUMMARY_PROMPTS[1]}\n\n"
        f"{entry.prompts[1]}\n\n"
        f"##### {SUMMARY_PROMPTS[2]}\n\n"
        f"{entry.prompts[2]}\n"
    )


def find_open_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 200):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex((host, port)) != 0:
                return port
    raise RuntimeError("No free port found")


def _normalize_plans(plans: Any) -> list[PlanItem]:
    if not isinstance(plans, list) or len(plans) == 0:
        raise ValidationError("请填写至少一个计划")

    normalized_plans: list[PlanItem] = []
    for item in plans:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        done = bool(item.get("done", False))
        if text:
            normalized_plans.append(PlanItem(text=text, done=done))

    if not normalized_plans:
        raise ValidationError("计划内容不能为空")

    return normalized_plans


def _normalize_prompts(prompts: Any) -> list[str]:
    if not isinstance(prompts, list) or len(prompts) != 3:
        raise ValidationError("总结字段数量不匹配")

    normalized_prompts = [str(item).strip() for item in prompts]
    if any(not item for item in normalized_prompts):
        raise ValidationError("请填写所有总结字段")

    return normalized_prompts


def parse_daily_entry(payload: dict[str, Any]) -> DailyEntry:
    date_text = str(payload.get("date", "")).strip()
    exercise = str(payload.get("exercise", "")).strip()

    if not DATE_PATTERN.match(date_text):
        raise ValidationError("日期格式必须是 yyyy-mm-dd")

    try:
        dt.date.fromisoformat(date_text)
    except ValueError as exc:
        raise ValidationError("日期无效") from exc

    if not exercise:
        raise ValidationError("请填写运动内容")

    plans = _normalize_plans(payload.get("plans", []))
    prompts = _normalize_prompts(payload.get("prompts", []))

    return DailyEntry(
        date_text=date_text,
        exercise=exercise,
        plans=plans,
        prompts=prompts,
    )


def save_entry(entry: DailyEntry, warehouse_dir: Path) -> Path:
    year, month, _ = entry.date_text.split("-")
    output_dir = warehouse_dir / year / month
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{entry.date_text}.md"
    output_file.write_text(build_markdown(entry), encoding="utf-8")
    return output_file


def list_recorded_dates(warehouse_dir: Path) -> list[str]:
    if not warehouse_dir.exists():
        return []

    dates: set[str] = set()
    for md_file in warehouse_dir.rglob("*.md"):
        date_text = md_file.stem
        if DATE_PATTERN.match(date_text):
            dates.add(date_text)
    return sorted(dates)


def _extract_section(
    markdown: str, start_marker: str, end_marker: str | None = None
) -> str:
    start = markdown.find(start_marker)
    if start < 0:
        raise ValidationError("记录内容格式不支持自动回填")
    content_start = start + len(start_marker)

    if end_marker is None:
        return markdown[content_start:].strip()

    end = markdown.find(end_marker, content_start)
    if end < 0:
        raise ValidationError("记录内容格式不支持自动回填")
    return markdown[content_start:end].strip()


def _entry_file_path(date_text: str, warehouse_dir: Path) -> Path:
    year, month, _ = date_text.split("-")
    return warehouse_dir / year / month / f"{date_text}.md"


def load_entry(date_text: str, warehouse_dir: Path) -> DailyEntry:
    entry_file = _entry_file_path(date_text, warehouse_dir)
    if not entry_file.exists():
        raise FileNotFoundError(date_text)

    markdown = entry_file.read_text(encoding="utf-8")
    plan_section = _extract_section(markdown, "#### 🎯 今日计划完成情况", "#### 🏃 运动")
    exercise = _extract_section(markdown, "#### 🏃 运动", "#### 🤔 总结").strip()
    summary_section = _extract_section(markdown, "#### 🤔 总结", None)

    plans: list[PlanItem] = []
    for raw_line in plan_section.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        matched = PLAN_LINE_PATTERN.match(line)
        if not matched:
            continue
        plans.append(
            PlanItem(
                text=matched.group("text").strip(),
                done=matched.group("done").lower() == "x",
            )
        )

    prompts: list[str] = []
    for idx, prompt_title in enumerate(SUMMARY_PROMPTS):
        marker = f"##### {prompt_title}"
        next_marker = (
            f"##### {SUMMARY_PROMPTS[idx + 1]}"
            if idx + 1 < len(SUMMARY_PROMPTS)
            else None
        )
        prompt_text = _extract_section(summary_section, marker, next_marker).strip()
        prompts.append(prompt_text)

    if not plans:
        plans = [PlanItem(text="", done=False)]

    return DailyEntry(
        date_text=date_text,
        exercise=exercise,
        plans=plans,
        prompts=prompts,
    )


class DailyHandler(BaseHTTPRequestHandler):
    warehouse_dir: Path = Path("warehouse")
    access_token: str = ""

    def _json_response(self, code: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _html_response(self, code: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json_body(self) -> Any:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            parsed = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # Keep behavior aligned with existing invalid-body response.
            raise ValidationError("无效请求体") from exc
        return parsed

    def _is_token_valid(self) -> bool:
        query = parse_qs(urlparse(self.path).query)
        provided_token = query.get("token", [""])[0]
        return provided_token == self.access_token

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path

        if route == "/api/dates":
            if not self._is_token_valid():
                self._json_response(403, {"error": "missing or invalid token"})
                return
            self._json_response(200, {"dates": list_recorded_dates(self.warehouse_dir)})
            return

        if route == "/api/entry":
            if not self._is_token_valid():
                self._json_response(403, {"error": "missing or invalid token"})
                return
            date_text = parse_qs(parsed.query).get("date", [""])[0].strip()
            if not DATE_PATTERN.match(date_text):
                self._json_response(400, {"error": "日期格式必须是 yyyy-mm-dd"})
                return
            try:
                dt.date.fromisoformat(date_text)
            except ValueError:
                self._json_response(400, {"error": "日期无效"})
                return
            try:
                entry = load_entry(date_text, self.warehouse_dir)
            except FileNotFoundError:
                self._json_response(404, {"error": "该日期没有记录"})
                return
            except ValidationError as exc:
                self._json_response(422, {"error": str(exc)})
                return

            self._json_response(
                200,
                {
                    "entry": {
                        "date": entry.date_text,
                        "exercise": entry.exercise,
                        "plans": [
                            {"text": plan.text, "done": plan.done}
                            for plan in entry.plans
                        ],
                        "prompts": entry.prompts,
                    }
                },
            )
            return

        if route != "/":
            self.send_error(404)
            return

        if not self._is_token_valid():
            self._html_response(403, render_forbidden_page())
            return

        self._html_response(200, render_page())

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/submit":
            self.send_error(404)
            return

        if not self._is_token_valid():
            self._json_response(403, {"error": "missing or invalid token"})
            return

        try:
            payload = self._read_json_body()
            entry = parse_daily_entry(payload)
            output_file = save_entry(entry, self.warehouse_dir)
        except ValidationError as exc:
            self._json_response(400, {"error": str(exc)})
            return

        self._json_response(200, {"ok": True, "path": str(output_file)})

    def log_message(self, *_: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily plan recorder")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    DailyHandler.warehouse_dir = ROOT_DIR / "warehouse"
    DailyHandler.access_token = secrets.token_urlsafe(24)

    port = find_open_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), DailyHandler)

    print(
        "Daily recorder is running at: "
        f"http://{args.host}:{port}/?token={DailyHandler.access_token}"
    )
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
