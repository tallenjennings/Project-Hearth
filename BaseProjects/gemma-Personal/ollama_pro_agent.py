#!/usr/bin/env python3
"""
Professional host-driven Ollama agent with a desktop GUI.

Features:
- Uses Ollama's /api/chat endpoint directly.
- Enforces a JSON-only tool protocol.
- Supports a configurable set of host-executed tools.
- Includes a Tkinter desktop GUI with chat history, tool log, workspace
  controls, and approval prompts for risky tools.
- Still supports CLI and REPL modes for convenience.

Only the host application executes tools.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import operator
import os
import platform
import queue
import re
import shutil
import socket
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b")
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MAX_TURNS = 10
REQUEST_TIMEOUT_S = 90
TEXT_TOOL_LIMIT = 8000
HTTP_TEXT_LIMIT = 5000
FILE_FIND_LIMIT = 200

SAFE_EXPR_PATTERN = re.compile(r"^[0-9+\-*/%().\s]+$")

WEATHER_CODE_DESCRIPTIONS: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow fall",
    73: "moderate snow fall",
    75: "heavy snow fall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

ALLOWED_BIN_OPS: dict[type[ast.AST], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

ALLOWED_UNARY_OPS: dict[type[ast.AST], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


@dataclass(slots=True)
class ParsedResponse:
    kind: str
    raw_text: str
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    content: str | None = None


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    arguments_schema: dict[str, Any]
    category: str
    risky: bool = False
    enabled_by_default: bool = True


@dataclass(slots=True)
class AgentConfig:
    model: str = DEFAULT_MODEL
    host: str = DEFAULT_HOST
    workspace_root: Path = field(default_factory=lambda: Path.cwd())
    max_turns: int = DEFAULT_MAX_TURNS
    debug: bool = False
    auto_approve_risky: bool = False
    enabled_tools: set[str] = field(default_factory=set)


class ToolContext:
    def __init__(
        self,
        config: AgentConfig,
        request_approval: Callable[[str, dict[str, Any]], bool] | None = None,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.request_approval = request_approval
        self.log = log

    def add_log(self, message: str) -> None:
        if self.log is not None:
            self.log(message)

    def resolve_workspace_path(self, raw_path: str, must_exist: bool = False) -> Path:
        path_text = raw_path.strip()
        if not path_text:
            raise ValueError("path must be a non-empty string")

        candidate = Path(path_text)
        if not candidate.is_absolute():
            candidate = (self.config.workspace_root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        workspace = self.config.workspace_root.resolve()
        try:
            candidate.relative_to(workspace)
        except ValueError as exc:
            raise ValueError(
                f'path "{candidate}" is outside the workspace root "{workspace}"'
            ) from exc

        if must_exist and not candidate.exists():
            raise ValueError(f'path "{candidate}" does not exist')
        return candidate


class ProfessionalOllamaAgent:
    def __init__(self) -> None:
        self.tools = self._build_tool_specs()

    def _build_tool_specs(self) -> dict[str, ToolSpec]:
        return {
            "get_current_time": ToolSpec(
                name="get_current_time",
                description="Get the current time in a timezone using an IANA timezone name.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "timezone": {"type": "string", "default": "UTC"}
                    },
                },
                category="utility",
            ),
            "get_weather": ToolSpec(
                name="get_weather",
                description="Get current weather for a city using Open-Meteo.",
                arguments_schema={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
                category="internet",
            ),
            "internet_search": ToolSpec(
                name="internet_search",
                description="Run a lightweight web search and return a concise summary.",
                arguments_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                category="internet",
            ),
            "http_get": ToolSpec(
                name="http_get",
                description="Fetch text content from a URL and return a truncated plain-text response.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "max_chars": {"type": "integer", "default": 3000},
                    },
                    "required": ["url"],
                },
                category="internet",
                risky=True,
            ),
            "calculator": ToolSpec(
                name="calculator",
                description="Safely evaluate arithmetic expressions.",
                arguments_schema={
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"],
                },
                category="utility",
            ),
            "system_info": ToolSpec(
                name="system_info",
                description="Return basic system information about the local machine and Python runtime.",
                arguments_schema={"type": "object", "properties": {}},
                category="system",
            ),
            "list_directory": ToolSpec(
                name="list_directory",
                description="List files and folders inside the workspace.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "default": "."},
                        "limit": {"type": "integer", "default": 100},
                    },
                },
                category="files",
            ),
            "find_files": ToolSpec(
                name="find_files",
                description="Find files in the workspace using a glob-style pattern.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "default": "."},
                        "pattern": {"type": "string"},
                        "recursive": {"type": "boolean", "default": True},
                    },
                    "required": ["pattern"],
                },
                category="files",
            ),
            "read_text_file": ToolSpec(
                name="read_text_file",
                description="Read a text file from the workspace.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "max_chars": {"type": "integer", "default": 5000},
                    },
                    "required": ["path"],
                },
                category="files",
            ),
            "write_text_file": ToolSpec(
                name="write_text_file",
                description="Write text to a file in the workspace. Creates parent folders if needed.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "append": {"type": "boolean", "default": False},
                    },
                    "required": ["path", "content"],
                },
                category="files",
                risky=True,
            ),
            "hash_file": ToolSpec(
                name="hash_file",
                description="Calculate a file hash in the workspace.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "algorithm": {"type": "string", "default": "sha256"},
                    },
                    "required": ["path"],
                },
                category="files",
            ),
            "powershell_access": ToolSpec(
                name="powershell_access",
                description="Run a PowerShell command on the local machine and return stdout/stderr.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "timeout_s": {"type": "integer", "default": 20},
                    },
                    "required": ["command"],
                },
                category="system",
                risky=True,
                enabled_by_default=False,
            ),
            "echo": ToolSpec(
                name="echo",
                description="Return the exact text supplied.",
                arguments_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                category="utility",
            ),
        }

    def default_enabled_tools(self) -> set[str]:
        return {
            name
            for name, spec in self.tools.items()
            if spec.enabled_by_default
        }

    def build_system_prompt(self, enabled_tools: set[str]) -> str:
        tool_lines: list[str] = []
        for name in sorted(enabled_tools):
            spec = self.tools[name]
            risky_text = " Requires host approval in some configurations." if spec.risky else ""
            tool_lines.append(
                f"- {spec.name}: {spec.description} Arguments schema: "
                f"{json.dumps(spec.arguments_schema, ensure_ascii=True)}.{risky_text}"
            )

        tools_block = "\n".join(tool_lines) if tool_lines else "- No tools are enabled."
        return (
            "You are a careful assistant operating inside a host-driven tool loop.\n\n"
            "Available tools:\n"
            f"{tools_block}\n\n"
            "Critical rules:\n"
            "- Respond with EXACTLY one JSON object and no extra text.\n"
            "- Your response must be exactly one of these shapes:\n"
            "  {\"type\":\"tool_call\",\"tool\":\"tool_name\",\"arguments\":{...}}\n"
            "  {\"type\":\"final\",\"content\":\"...\"}\n"
            "- Never invent tool results.\n"
            "- If you need external information, file content, system state, or computation from a tool, emit a tool_call JSON object.\n"
            "- If a tool returns an ERROR, adjust your plan and either try another appropriate tool or explain the limitation in a final response.\n"
            "- After receiving a tool result, either emit another tool_call or emit final.\n"
            "- Prefer concise, direct answers grounded in the actual tool results.\n"
        )

    def call_ollama(
        self,
        messages: list[dict[str, str]],
        model: str,
        host: str,
        timeout_s: int = REQUEST_TIMEOUT_S,
    ) -> str:
        url = f"{host.rstrip('/')}/api/chat"
        payload = {"model": model, "messages": messages, "stream": False}
        try:
            response = requests.post(url, json=payload, timeout=timeout_s)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Invalid JSON response from Ollama: {response.text}") from exc

        message = data.get("message")
        if not isinstance(message, dict):
            raise RuntimeError(f"Unexpected Ollama response format: {data}")

        content = message.get("content", "")
        if not isinstance(content, str):
            raise RuntimeError(f"Unexpected message content type: {type(content)}")
        return content.strip()

    @staticmethod
    def extract_first_json_object(text: str) -> str | None:
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None

    def parse_model_response(self, raw_text: str) -> ParsedResponse:
        parsed_obj: Any | None = None
        text = raw_text.strip()

        try:
            parsed_obj = json.loads(text)
        except json.JSONDecodeError:
            candidate = self.extract_first_json_object(text)
            if candidate is not None:
                try:
                    parsed_obj = json.loads(candidate)
                except json.JSONDecodeError:
                    parsed_obj = None

        if isinstance(parsed_obj, dict):
            msg_type = parsed_obj.get("type")
            if msg_type == "tool_call":
                tool = parsed_obj.get("tool")
                arguments = parsed_obj.get("arguments", {})
                if isinstance(tool, str) and isinstance(arguments, dict):
                    return ParsedResponse(
                        kind="tool_call",
                        raw_text=raw_text,
                        tool=tool,
                        arguments=arguments,
                    )
            elif msg_type == "final":
                content = parsed_obj.get("content")
                if isinstance(content, str):
                    return ParsedResponse(kind="final", raw_text=raw_text, content=content)

        return ParsedResponse(kind="final", raw_text=raw_text, content=text or raw_text)

    def run(
        self,
        user_input: str,
        conversation_history: list[dict[str, str]],
        config: AgentConfig,
        request_approval: Callable[[str, dict[str, Any]], bool] | None = None,
        log: Callable[[str], None] | None = None,
    ) -> tuple[str, list[dict[str, str]]]:
        enabled_tools = config.enabled_tools or self.default_enabled_tools()
        config.enabled_tools = set(enabled_tools)
        context = ToolContext(config=config, request_approval=request_approval, log=log)
        system_prompt = self.build_system_prompt(config.enabled_tools)

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_input})

        last_raw = ""
        context.add_log(f"Model: {config.model}")
        context.add_log(f"Enabled tools: {', '.join(sorted(config.enabled_tools))}")

        for turn in range(1, config.max_turns + 1):
            if config.debug:
                context.add_log(f"[debug] turn {turn}")
            try:
                raw = self.call_ollama(messages=messages, model=config.model, host=config.host)
            except Exception as exc:
                return f"Agent error: {exc}", conversation_history

            last_raw = raw
            if config.debug:
                context.add_log(f"[debug] raw model output: {raw}")

            parsed = self.parse_model_response(raw)
            if parsed.kind == "final":
                final_text = parsed.content if parsed.content is not None else raw
                updated_history = conversation_history + [
                    {"role": "user", "content": user_input},
                    {"role": "assistant", "content": final_text},
                ]
                return final_text, updated_history

            tool_name = parsed.tool or ""
            arguments = parsed.arguments or {}
            context.add_log(f"Tool requested: {tool_name} {json.dumps(arguments, ensure_ascii=True)}")
            tool_result = self.execute_tool(tool_name, arguments, context)
            context.add_log(f"Tool result: {tool_result}")

            messages.append({"role": "assistant", "content": raw})
            tool_payload = {
                "tool": tool_name,
                "arguments": arguments,
                "result": tool_result,
            }
            messages.append({"role": "user", "content": f"TOOL_RESULT: {json.dumps(tool_payload)}"})

        fallback = last_raw.strip() if last_raw.strip() else "Agent stopped without producing a final answer."
        updated_history = conversation_history + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": fallback},
        ]
        return fallback, updated_history

    def execute_tool(self, tool: str, arguments: dict[str, Any], context: ToolContext) -> str:
        if tool not in self.tools:
            return f'ERROR: unknown tool "{tool}"'
        if tool not in context.config.enabled_tools:
            return f'ERROR: tool "{tool}" is disabled in the current session'

        spec = self.tools[tool]
        if spec.risky and not context.config.auto_approve_risky:
            if context.request_approval is None:
                return f'ERROR: tool "{tool}" requires approval and no approval handler is available'
            approved = context.request_approval(tool, arguments)
            if not approved:
                return f'ERROR: execution of tool "{tool}" was not approved'

        try:
            if tool == "get_current_time":
                timezone = arguments.get("timezone", "UTC")
                if not isinstance(timezone, str):
                    return 'ERROR: "timezone" must be a string'
                return self.tool_get_current_time(timezone)

            if tool == "get_weather":
                city = arguments.get("city")
                if not isinstance(city, str):
                    return 'ERROR: "city" is required and must be a string'
                return self.tool_get_weather(city)

            if tool == "internet_search":
                query = arguments.get("query")
                if not isinstance(query, str):
                    return 'ERROR: "query" is required and must be a string'
                return self.tool_internet_search(query)

            if tool == "http_get":
                url = arguments.get("url")
                max_chars = arguments.get("max_chars", 3000)
                if not isinstance(url, str):
                    return 'ERROR: "url" is required and must be a string'
                if not isinstance(max_chars, int):
                    return 'ERROR: "max_chars" must be an integer'
                return self.tool_http_get(url, max_chars)

            if tool == "calculator":
                expression = arguments.get("expression")
                if not isinstance(expression, str):
                    return 'ERROR: "expression" is required and must be a string'
                return self.tool_calculator(expression)

            if tool == "system_info":
                return self.tool_system_info(context)

            if tool == "list_directory":
                raw_path = arguments.get("path", ".")
                limit = arguments.get("limit", 100)
                if not isinstance(raw_path, str):
                    return 'ERROR: "path" must be a string'
                if not isinstance(limit, int):
                    return 'ERROR: "limit" must be an integer'
                return self.tool_list_directory(raw_path, limit, context)

            if tool == "find_files":
                directory = arguments.get("directory", ".")
                pattern = arguments.get("pattern")
                recursive = arguments.get("recursive", True)
                if not isinstance(directory, str):
                    return 'ERROR: "directory" must be a string'
                if not isinstance(pattern, str):
                    return 'ERROR: "pattern" is required and must be a string'
                if not isinstance(recursive, bool):
                    return 'ERROR: "recursive" must be a boolean'
                return self.tool_find_files(directory, pattern, recursive, context)

            if tool == "read_text_file":
                raw_path = arguments.get("path")
                max_chars = arguments.get("max_chars", 5000)
                if not isinstance(raw_path, str):
                    return 'ERROR: "path" is required and must be a string'
                if not isinstance(max_chars, int):
                    return 'ERROR: "max_chars" must be an integer'
                return self.tool_read_text_file(raw_path, max_chars, context)

            if tool == "write_text_file":
                raw_path = arguments.get("path")
                content = arguments.get("content")
                append = arguments.get("append", False)
                if not isinstance(raw_path, str):
                    return 'ERROR: "path" is required and must be a string'
                if not isinstance(content, str):
                    return 'ERROR: "content" is required and must be a string'
                if not isinstance(append, bool):
                    return 'ERROR: "append" must be a boolean'
                return self.tool_write_text_file(raw_path, content, append, context)

            if tool == "hash_file":
                raw_path = arguments.get("path")
                algorithm = arguments.get("algorithm", "sha256")
                if not isinstance(raw_path, str):
                    return 'ERROR: "path" is required and must be a string'
                if not isinstance(algorithm, str):
                    return 'ERROR: "algorithm" must be a string'
                return self.tool_hash_file(raw_path, algorithm, context)

            if tool == "powershell_access":
                command = arguments.get("command")
                timeout_s = arguments.get("timeout_s", 20)
                if not isinstance(command, str):
                    return 'ERROR: "command" is required and must be a string'
                if not isinstance(timeout_s, int):
                    return 'ERROR: "timeout_s" must be an integer'
                return self.tool_powershell_access(command, timeout_s)

            if tool == "echo":
                text = arguments.get("text")
                if not isinstance(text, str):
                    return 'ERROR: "text" is required and must be a string'
                return text

            return f'ERROR: unknown tool "{tool}"'
        except Exception as exc:
            return f"ERROR: tool execution failed ({exc})"

    @staticmethod
    def tool_get_current_time(timezone: str = "UTC") -> str:
        tz = timezone or "UTC"
        try:
            now = datetime.now(ZoneInfo(tz))
        except ZoneInfoNotFoundError:
            return f'ERROR: invalid timezone "{tz}"'
        return now.isoformat()

    @staticmethod
    def tool_get_weather(city: str) -> str:
        city_name = city.strip()
        if not city_name:
            return 'ERROR: "city" is required and must be a non-empty string'

        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        forecast_url = "https://api.open-meteo.com/v1/forecast"

        try:
            geocode_resp = requests.get(
                geocode_url,
                params={"name": city_name, "count": 1, "language": "en", "format": "json"},
                timeout=20,
            )
            geocode_resp.raise_for_status()
            geocode_data = geocode_resp.json()
        except requests.RequestException as exc:
            return f"ERROR: weather geocoding request failed ({exc})"
        except ValueError:
            return "ERROR: weather geocoding returned invalid JSON"

        results = geocode_data.get("results")
        if not isinstance(results, list) or not results:
            return f'ERROR: city "{city_name}" not found'

        location = results[0]
        name = location.get("name")
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        country = location.get("country")

        if not isinstance(name, str) or not isinstance(latitude, (int, float)) or not isinstance(
            longitude, (int, float)
        ):
            return "ERROR: geocoding response missing required location fields"

        try:
            weather_resp = requests.get(
                forecast_url,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,wind_speed_10m,weather_code",
                },
                timeout=20,
            )
            weather_resp.raise_for_status()
            weather_data = weather_resp.json()
        except requests.RequestException as exc:
            return f"ERROR: weather forecast request failed ({exc})"
        except ValueError:
            return "ERROR: weather forecast returned invalid JSON"

        current = weather_data.get("current")
        if not isinstance(current, dict):
            return "ERROR: weather forecast missing current conditions"

        temperature = current.get("temperature_2m")
        wind_speed = current.get("wind_speed_10m")
        weather_code = current.get("weather_code")

        if not isinstance(temperature, (int, float)) or not isinstance(wind_speed, (int, float)):
            return "ERROR: weather forecast missing temperature or wind speed"

        description = (
            WEATHER_CODE_DESCRIPTIONS.get(weather_code, f"code {weather_code}")
            if isinstance(weather_code, int)
            else "unknown conditions"
        )
        location_label = f"{name}, {country}" if isinstance(country, str) and country else name
        return (
            f"Current weather in {location_label}: "
            f"{float(temperature):.1f} C, "
            f"wind {float(wind_speed):.1f} km/h, "
            f"{description}."
        )

    @staticmethod
    def tool_internet_search(query: str) -> str:
        text = query.strip()
        if not text:
            return 'ERROR: "query" is required and must be a non-empty string'

        url = "https://api.duckduckgo.com/"
        try:
            response = requests.get(
                url,
                params={"q": text, "format": "json", "no_html": 1, "no_redirect": 1},
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            return f"ERROR: internet search request failed ({exc})"
        except ValueError:
            return "ERROR: internet search returned invalid JSON"

        lines: list[str] = []
        abstract = data.get("AbstractText")
        abstract_url = data.get("AbstractURL")
        if isinstance(abstract, str) and abstract.strip():
            if isinstance(abstract_url, str) and abstract_url.strip():
                lines.append(f"Answer: {abstract.strip()} (Source: {abstract_url.strip()})")
            else:
                lines.append(f"Answer: {abstract.strip()}")

        related = data.get("RelatedTopics")
        if isinstance(related, list):
            for topic in related:
                if len(lines) >= 5:
                    break
                candidates: list[dict[str, Any]] = []
                if isinstance(topic, dict) and isinstance(topic.get("Topics"), list):
                    candidates = [item for item in topic["Topics"] if isinstance(item, dict)]
                elif isinstance(topic, dict):
                    candidates = [topic]
                for item in candidates:
                    if len(lines) >= 5:
                        break
                    topic_text = item.get("Text")
                    first_url = item.get("FirstURL")
                    if isinstance(topic_text, str) and topic_text.strip():
                        suffix = f" ({first_url.strip()})" if isinstance(first_url, str) and first_url.strip() else ""
                        lines.append(f"- {topic_text.strip()}{suffix}")

        if not lines:
            return f'ERROR: no search results found for "{text}"'
        return "Internet search results:\n" + "\n".join(lines[:5])

    @staticmethod
    def tool_http_get(url: str, max_chars: int) -> str:
        address = url.strip()
        if not address:
            return 'ERROR: "url" is required and must be a non-empty string'
        if not address.startswith(("http://", "https://")):
            return 'ERROR: "url" must start with http:// or https://'
        max_chars = max(200, min(max_chars, HTTP_TEXT_LIMIT))
        try:
            response = requests.get(address, timeout=20, headers={"User-Agent": "OllamaProAgent/1.0"})
            response.raise_for_status()
        except requests.RequestException as exc:
            return f"ERROR: HTTP GET request failed ({exc})"

        content_type = response.headers.get("Content-Type", "")
        text = response.text[:max_chars]
        if not text.strip():
            text = "<empty response body>"
        return f"URL: {address}\nContent-Type: {content_type}\nBody:\n{text}"

    @staticmethod
    def tool_calculator(expression: str) -> str:
        expr = expression.strip()
        if not expr:
            return "ERROR: expression is required"
        if not SAFE_EXPR_PATTERN.fullmatch(expr):
            return "ERROR: expression contains invalid characters"

        try:
            node = ast.parse(expr, mode="eval")
        except SyntaxError:
            return "ERROR: invalid arithmetic expression"

        def eval_node(current: ast.AST) -> float:
            if isinstance(current, ast.Expression):
                return eval_node(current.body)
            if isinstance(current, ast.Constant) and isinstance(current.value, (int, float)):
                return float(current.value)
            if isinstance(current, ast.BinOp):
                op_type = type(current.op)
                operation = ALLOWED_BIN_OPS.get(op_type)
                if operation is None:
                    raise ValueError("unsupported binary operator")
                return operation(eval_node(current.left), eval_node(current.right))
            if isinstance(current, ast.UnaryOp):
                op_type = type(current.op)
                operation = ALLOWED_UNARY_OPS.get(op_type)
                if operation is None:
                    raise ValueError("unsupported unary operator")
                return operation(eval_node(current.operand))
            raise ValueError(f"unsupported syntax: {type(current).__name__}")

        try:
            value = eval_node(node)
        except ZeroDivisionError:
            return "ERROR: division by zero"
        except ValueError as exc:
            return f"ERROR: {exc}"
        except OverflowError:
            return "ERROR: numeric overflow"
        except Exception as exc:
            return f"ERROR: calculation failed ({exc})"

        if float(value).is_integer():
            return str(int(value))
        return str(value)

    @staticmethod
    def tool_system_info(context: ToolContext) -> str:
        workspace = str(context.config.workspace_root.resolve())
        return (
            f"System: {platform.system()} {platform.release()}\n"
            f"Version: {platform.version()}\n"
            f"Machine: {platform.machine()}\n"
            f"Hostname: {socket.gethostname()}\n"
            f"Python: {platform.python_version()}\n"
            f"Current working directory: {os.getcwd()}\n"
            f"Workspace root: {workspace}"
        )

    @staticmethod
    def tool_list_directory(raw_path: str, limit: int, context: ToolContext) -> str:
        target = context.resolve_workspace_path(raw_path or ".", must_exist=True)
        if not target.is_dir():
            return f'ERROR: path "{target}" is not a directory'

        limit = max(1, min(limit, FILE_FIND_LIMIT))
        entries = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        lines = [f"Directory listing for {target}:"]
        for item in entries[:limit]:
            kind = "DIR" if item.is_dir() else "FILE"
            size = "-" if item.is_dir() else str(item.stat().st_size)
            lines.append(f"[{kind}] {item.name} (size={size})")
        if len(entries) > limit:
            lines.append(f"... {len(entries) - limit} more entries not shown")
        return "\n".join(lines)

    @staticmethod
    def tool_find_files(directory: str, pattern: str, recursive: bool, context: ToolContext) -> str:
        base = context.resolve_workspace_path(directory or ".", must_exist=True)
        if not base.is_dir():
            return f'ERROR: path "{base}" is not a directory'
        matcher = fnmatch.fnmatch
        matches: list[Path] = []
        iterator = base.rglob("*") if recursive else base.glob("*")
        for path in iterator:
            if matcher(path.name, pattern):
                matches.append(path)
                if len(matches) >= FILE_FIND_LIMIT:
                    break
        if not matches:
            return f"No files matching pattern '{pattern}' were found in {base}."
        lines = [f"Matches for '{pattern}' in {base}:"]
        for path in matches:
            lines.append(str(path.relative_to(context.config.workspace_root.resolve())))
        if len(matches) >= FILE_FIND_LIMIT:
            lines.append("Results truncated at limit.")
        return "\n".join(lines)

    @staticmethod
    def tool_read_text_file(raw_path: str, max_chars: int, context: ToolContext) -> str:
        target = context.resolve_workspace_path(raw_path, must_exist=True)
        if not target.is_file():
            return f'ERROR: path "{target}" is not a file'
        limit = max(200, min(max_chars, TEXT_TOOL_LIMIT))
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return f"ERROR: failed to read file ({exc})"
        except Exception as exc:
            return f"ERROR: failed to read file ({exc})"
        if len(content) > limit:
            content = content[:limit] + "\n...<truncated>"
        return f"File: {target}\n\n{content}"

    @staticmethod
    def tool_write_text_file(raw_path: str, content: str, append: bool, context: ToolContext) -> str:
        target = context.resolve_workspace_path(raw_path, must_exist=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        try:
            with target.open(mode, encoding="utf-8") as handle:
                handle.write(content)
        except Exception as exc:
            return f"ERROR: failed to write file ({exc})"
        action = "appended to" if append else "wrote"
        return f"Successfully {action} {target} ({len(content)} characters)."

    @staticmethod
    def tool_hash_file(raw_path: str, algorithm: str, context: ToolContext) -> str:
        import hashlib

        target = context.resolve_workspace_path(raw_path, must_exist=True)
        if not target.is_file():
            return f'ERROR: path "{target}" is not a file'
        name = algorithm.lower().strip() or "sha256"
        try:
            hasher = hashlib.new(name)
        except ValueError:
            return f'ERROR: unsupported hash algorithm "{algorithm}"'

        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                hasher.update(chunk)
        return f"{name}({target}) = {hasher.hexdigest()}"

    @staticmethod
    def tool_powershell_access(command: str, timeout_s: int) -> str:
        cmd = command.strip()
        if not cmd:
            return 'ERROR: "command" is required and must be a non-empty string'
        effective_timeout = max(1, min(timeout_s, 120))
        powershell_bin = shutil.which("pwsh") or shutil.which("powershell") or shutil.which("powershell.exe")
        if not powershell_bin:
            return "ERROR: PowerShell executable not found (expected pwsh, powershell, or powershell.exe)"
        try:
            completed = subprocess.run(
                [powershell_bin, "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"ERROR: PowerShell command timed out after {effective_timeout} seconds"
        except Exception as exc:
            return f"ERROR: failed to execute PowerShell command ({exc})"

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        parts: list[str] = [f"exit_code: {completed.returncode}"]
        parts.append(f"stdout:\n{stdout}" if stdout else "stdout:\n<empty>")
        if stderr:
            parts.append(f"stderr:\n{stderr}")
        result = "\n\n".join(parts)
        if len(result) > 5000:
            result = result[:5000] + "\n...<truncated>"
        return result


class AgentGui:
    def __init__(self, root: tk.Tk, agent: ProfessionalOllamaAgent) -> None:
        self.root = root
        self.agent = agent
        self.history: list[dict[str, str]] = []
        self.running = False
        self.tool_log_queue: queue.Queue[str] = queue.Queue()
        self.tool_vars: dict[str, tk.BooleanVar] = {}

        self.root.title("Ollama Pro Agent")
        self.root.geometry("1280x860")
        self.root.minsize(1050, 700)

        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.workspace_var = tk.StringVar(value=str(Path.cwd()))
        self.max_turns_var = tk.IntVar(value=DEFAULT_MAX_TURNS)
        self.debug_var = tk.BooleanVar(value=False)
        self.auto_approve_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")

        self._build_widgets()
        self._poll_log_queue()

    def _build_widgets(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        paned = ttk.Panedwindow(outer, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, padding=(0, 0, 10, 0))
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=4)

        self._build_left_panel(left)
        self._build_right_panel(right)

        status = ttk.Label(self.root, textvariable=self.status_var, anchor=tk.W, relief=tk.SUNKEN)
        status.pack(fill=tk.X, side=tk.BOTTOM)

        self.root.bind("<Control-Return>", lambda _event: self.send_message())

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        connection = ttk.LabelFrame(parent, text="Connection", padding=10)
        connection.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(connection, text="Model").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(connection, textvariable=self.model_var, width=28).grid(row=1, column=0, sticky=tk.EW, pady=(0, 8))

        ttk.Label(connection, text="Ollama host").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(connection, textvariable=self.host_var, width=28).grid(row=3, column=0, sticky=tk.EW, pady=(0, 8))

        ttk.Label(connection, text="Workspace root").grid(row=4, column=0, sticky=tk.W)
        workspace_row = ttk.Frame(connection)
        workspace_row.grid(row=5, column=0, sticky=tk.EW)
        workspace_row.columnconfigure(0, weight=1)
        ttk.Entry(workspace_row, textvariable=self.workspace_var, width=28).grid(row=0, column=0, sticky=tk.EW)
        ttk.Button(workspace_row, text="Browse", command=self.choose_workspace).grid(row=0, column=1, padx=(6, 0))

        ttk.Label(connection, text="Max turns").grid(row=6, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Spinbox(connection, from_=1, to=20, textvariable=self.max_turns_var, width=8).grid(row=7, column=0, sticky=tk.W)

        ttk.Checkbutton(connection, text="Debug logging", variable=self.debug_var).grid(row=8, column=0, sticky=tk.W, pady=(10, 0))
        ttk.Checkbutton(
            connection,
            text="Auto-approve risky tools",
            variable=self.auto_approve_var,
        ).grid(row=9, column=0, sticky=tk.W, pady=(4, 0))
        connection.columnconfigure(0, weight=1)

        tools_frame = ttk.LabelFrame(parent, text="Tools", padding=10)
        tools_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        canvas = tk.Canvas(tools_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tools_frame, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        categories = sorted({spec.category for spec in self.agent.tools.values()})
        row = 0
        for category in categories:
            ttk.Label(inner, text=category.title(), font=("Segoe UI", 10, "bold")).grid(
                row=row, column=0, sticky=tk.W, pady=(8 if row else 0, 4)
            )
            row += 1
            for name, spec in sorted(self.agent.tools.items()):
                if spec.category != category:
                    continue
                default_value = spec.enabled_by_default
                var = tk.BooleanVar(value=default_value)
                self.tool_vars[name] = var
                label = name + ("  [approval]" if spec.risky else "")
                ttk.Checkbutton(inner, text=label, variable=var).grid(row=row, column=0, sticky=tk.W)
                ttk.Label(inner, text=spec.description, wraplength=270, foreground="#555555").grid(
                    row=row + 1, column=0, sticky=tk.W, padx=(20, 0), pady=(0, 6)
                )
                row += 2

        controls = ttk.Frame(parent)
        controls.pack(fill=tk.X)
        ttk.Button(controls, text="Select all safe tools", command=self.enable_safe_tools).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(controls, text="Enable all tools", command=self.enable_all_tools).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(controls, text="Clear chat", command=self.clear_chat).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(controls, text="Export chat", command=self.export_chat).pack(fill=tk.X)

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        transcript_frame = ttk.LabelFrame(parent, text="Conversation", padding=8)
        transcript_frame.pack(fill=tk.BOTH, expand=True)

        self.transcript = ScrolledText(transcript_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 11))
        self.transcript.pack(fill=tk.BOTH, expand=True)
        self.transcript.tag_configure("user", foreground="#1b4d91")
        self.transcript.tag_configure("assistant", foreground="#1f6f43")
        self.transcript.tag_configure("system", foreground="#555555")

        lower = ttk.Panedwindow(parent, orient=tk.VERTICAL)
        lower.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        tools_log_frame = ttk.LabelFrame(lower, text="Tool log", padding=8)
        compose_frame = ttk.LabelFrame(lower, text="Message", padding=8)
        lower.add(tools_log_frame, weight=2)
        lower.add(compose_frame, weight=1)

        self.tool_log = ScrolledText(tools_log_frame, wrap=tk.WORD, state=tk.DISABLED, height=12, font=("Consolas", 10))
        self.tool_log.pack(fill=tk.BOTH, expand=True)

        self.input_box = ScrolledText(compose_frame, wrap=tk.WORD, height=8, font=("Consolas", 11))
        self.input_box.pack(fill=tk.BOTH, expand=True)

        actions = ttk.Frame(compose_frame)
        actions.pack(fill=tk.X, pady=(8, 0))
        self.send_button = ttk.Button(actions, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.RIGHT)
        ttk.Label(actions, text="Ctrl+Enter to send").pack(side=tk.LEFT)

        self.append_transcript(
            "system",
            "Ollama Pro Agent is ready. Configure the model, workspace, and tools on the left, then send a message.",
        )

    def append_transcript(self, role: str, text: str) -> None:
        self.transcript.configure(state=tk.NORMAL)
        label = role.capitalize()
        self.transcript.insert(tk.END, f"{label}:\n", (role,))
        self.transcript.insert(tk.END, text.strip() + "\n\n")
        self.transcript.configure(state=tk.DISABLED)
        self.transcript.see(tk.END)

    def append_tool_log(self, text: str) -> None:
        self.tool_log.configure(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.tool_log.insert(tk.END, f"[{timestamp}] {text}\n")
        self.tool_log.configure(state=tk.DISABLED)
        self.tool_log.see(tk.END)

    def _poll_log_queue(self) -> None:
        while True:
            try:
                message = self.tool_log_queue.get_nowait()
            except queue.Empty:
                break
            self.append_tool_log(message)
        self.root.after(150, self._poll_log_queue)

    def log_from_worker(self, text: str) -> None:
        self.tool_log_queue.put(text)

    def choose_workspace(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.workspace_var.get() or str(Path.cwd()))
        if selected:
            self.workspace_var.set(selected)

    def enable_safe_tools(self) -> None:
        for name, spec in self.agent.tools.items():
            self.tool_vars[name].set(not spec.risky)

    def enable_all_tools(self) -> None:
        for var in self.tool_vars.values():
            var.set(True)

    def clear_chat(self) -> None:
        if self.running:
            messagebox.showinfo("Busy", "Wait for the current run to finish before clearing the chat.")
            return
        self.history.clear()
        self.transcript.configure(state=tk.NORMAL)
        self.transcript.delete("1.0", tk.END)
        self.transcript.configure(state=tk.DISABLED)
        self.tool_log.configure(state=tk.NORMAL)
        self.tool_log.delete("1.0", tk.END)
        self.tool_log.configure(state=tk.DISABLED)
        self.append_transcript(
            "system",
            "Chat cleared. The agent will start from a fresh conversation on the next message.",
        )
        self.status_var.set("Chat cleared")

    def export_chat(self) -> None:
        if not self.history:
            messagebox.showinfo("No chat", "There is no conversation history to export yet.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        lines: list[str] = ["# Ollama Pro Agent Chat Export", ""]
        for message in self.history:
            role = message["role"].capitalize()
            lines.append(f"## {role}")
            lines.append(message["content"])
            lines.append("")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self.status_var.set(f"Exported chat to {path}")

    def get_enabled_tools(self) -> set[str]:
        return {name for name, var in self.tool_vars.items() if var.get()}

    def request_approval(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        decision: dict[str, bool] = {"approved": False}
        event = threading.Event()

        def ask() -> None:
            message = (
                f"Approve execution of '{tool_name}'?\n\n"
                f"Arguments:\n{json.dumps(arguments, indent=2, ensure_ascii=False)}"
            )
            decision["approved"] = messagebox.askyesno("Approve tool", message, parent=self.root)
            event.set()

        self.root.after(0, ask)
        event.wait()
        return decision["approved"]

    def send_message(self) -> None:
        if self.running:
            messagebox.showinfo("Busy", "The agent is already working on a request.")
            return

        user_text = self.input_box.get("1.0", tk.END).strip()
        if not user_text:
            return

        workspace = Path(self.workspace_var.get() or ".")
        if not workspace.exists() or not workspace.is_dir():
            messagebox.showerror("Invalid workspace", "Please select a valid workspace directory.")
            return

        enabled_tools = self.get_enabled_tools()
        if not enabled_tools:
            if not messagebox.askyesno(
                "No tools enabled",
                "No tools are enabled for this session. Continue anyway?",
                parent=self.root,
            ):
                return

        self.input_box.delete("1.0", tk.END)
        self.append_transcript("user", user_text)
        self.running = True
        self.send_button.configure(state=tk.DISABLED)
        self.status_var.set("Running...")

        config = AgentConfig(
            model=self.model_var.get().strip() or DEFAULT_MODEL,
            host=self.host_var.get().strip() or DEFAULT_HOST,
            workspace_root=workspace,
            max_turns=max(1, min(int(self.max_turns_var.get()), 20)),
            debug=self.debug_var.get(),
            auto_approve_risky=self.auto_approve_var.get(),
            enabled_tools=enabled_tools,
        )

        worker = threading.Thread(
            target=self._run_agent_worker,
            args=(user_text, config),
            daemon=True,
        )
        worker.start()

    def _run_agent_worker(self, user_text: str, config: AgentConfig) -> None:
        try:
            answer, updated_history = self.agent.run(
                user_input=user_text,
                conversation_history=self.history,
                config=config,
                request_approval=self.request_approval,
                log=self.log_from_worker,
            )
        except Exception as exc:
            answer = f"Agent error: {exc}"
            updated_history = self.history

        def finish() -> None:
            self.history = updated_history
            self.append_transcript("assistant", answer)
            self.send_button.configure(state=tk.NORMAL)
            self.running = False
            self.status_var.set("Ready")

        self.root.after(0, finish)


def build_cli_config(args: argparse.Namespace, agent: ProfessionalOllamaAgent) -> AgentConfig:
    workspace = Path(args.workspace or ".").resolve()
    enabled_tools = agent.default_enabled_tools()
    if args.enable_powershell:
        enabled_tools.add("powershell_access")
    return AgentConfig(
        model=args.model,
        host=args.host,
        workspace_root=workspace,
        max_turns=args.max_turns,
        debug=args.debug,
        auto_approve_risky=args.auto_approve_risky,
        enabled_tools=enabled_tools,
    )


def run_cli(args: argparse.Namespace, agent: ProfessionalOllamaAgent) -> None:
    config = build_cli_config(args, agent)
    history: list[dict[str, str]] = []

    def cli_log(message: str) -> None:
        print(f"[tool] {message}")

    def cli_request_approval(tool_name: str, arguments: dict[str, Any]) -> bool:
        print(f"Approval required for tool '{tool_name}'")
        print(json.dumps(arguments, indent=2, ensure_ascii=False))
        response = input("Approve? [y/N]: ").strip().lower()
        return response in {"y", "yes"}

    if args.prompt:
        answer, _history = agent.run(
            user_input=args.prompt,
            conversation_history=history,
            config=config,
            request_approval=cli_request_approval,
            log=cli_log if args.debug else None,
        )
        print(answer)
        return

    print("Interactive mode. Type 'exit' or 'quit' to leave.")
    while True:
        try:
            prompt = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        answer, history = agent.run(
            user_input=prompt,
            conversation_history=history,
            config=config,
            request_approval=cli_request_approval,
            log=cli_log if args.debug else None,
        )
        print(answer)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Professional host-driven Ollama agent with GUI and CLI.")
    parser.add_argument("prompt", nargs="?", help="Optional one-shot prompt. When omitted, GUI launches unless --cli is set.")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode instead of launching the GUI.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Ollama host URL (default: {DEFAULT_HOST})")
    parser.add_argument("--workspace", default=str(Path.cwd()), help="Workspace root for file tools")
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS, help="Maximum tool loop turns per request")
    parser.add_argument("--debug", action="store_true", help="Enable tool and raw model logging")
    parser.add_argument(
        "--auto-approve-risky",
        action="store_true",
        help="Automatically approve risky tools such as PowerShell and file writing",
    )
    parser.add_argument(
        "--enable-powershell",
        action="store_true",
        help="Enable the PowerShell tool in CLI mode",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    agent = ProfessionalOllamaAgent()

    if args.cli or args.prompt:
        run_cli(args, agent)
        return

    root = tk.Tk()
    app = AgentGui(root, agent)
    _ = app
    root.mainloop()


if __name__ == "__main__":
    main()
