#!/usr/bin/env python3
"""Send a PDF to Gemini Interactions API and save its Markdown output."""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv
except ImportError:  # The script can still use exported environment variables.
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FAULT_PROMPT = """
请阅读附件 PDF，只提取与故障、报警、异常、错误代码、诊断、维修和恢复有关的内容，生成一份可直接保存为 Markdown 的故障排查手册。

这不是普通 OCR 或摘要任务。请理解 PDF 中的正文、表格、流程图、结构图和截图，只保留与故障处理有关的信息。

必须保留：
- 故障代码、报警名称和原始术语
- 故障现象、触发条件和指示信息
- PDF 明确说明的可能原因
- 检查步骤、处理措施和恢复验证
- 安全警告、禁止操作和前置条件
- 与故障有关的表格、流程图、结构图和截图

处理规则：
1. 不得猜测、补写或改造 PDF 中没有出现的参数、原因或维修步骤。
2. 参数、单位、型号、错误代码和操作顺序必须保持原样。
3. 无法确认的内容写“待确认”，不要使用常识补全。
4. 同一故障在多处出现时可以合并，但必须保留所有来源页码。
5. 只输出 Markdown 正文，不要输出 JSON、解释文字、处理过程或外层代码围栏。
6. 如果没有故障相关内容，只输出“未发现明确的故障、报警、错误代码或维修处理内容”。

请按实际内容使用以下结构，缺少的章节不要虚构：

# 故障排查手册
## 故障索引
| 故障代码 | 故障名称 | 典型现象 | 来源页码 |
|---|---|---|---|
## 故障代码：<代码>
### 故障名称
### 故障现象
### 可能原因
### 检查步骤
### 处理措施
### 恢复验证
### 安全限制
### 相关图片或图表
### 来源

图片规则：
- 识别故障相关的流程图、结构图、截图、表格和照片。
- 提取图片中清晰可见的标签、数值、方向和步骤关系。
- 每个图片说明前输出：
  <!-- source_page: <页码>; asset_id: img-p<页码>-<序号>; type: <类型> -->
- 图片使用：![图片标题](assets/img-p<页码>-<序号>.png)
- 图片说明只描述可确认的信息，不得推测未标注的含义。
- 每条故障内容和图片说明都要标注 PDF 来源页码。
""".strip()

FULL_PROMPT = """
请阅读附件 PDF，并将其重构为一份准确、完整、结构清晰的 Markdown 技术说明书。

请理解正文、章节关系、表格、流程图、结构图、截图和警告信息，而不是只做 OCR 或摘要。保留原文事实、型号、参数、单位、限制条件、警告和操作顺序。不得根据常识补充 PDF 中没有出现的内容；无法确认的内容标记为“待确认”。

只输出 Markdown 正文，不要输出 JSON、解释文字、处理过程或外层代码围栏。每个主要章节、图片说明和关键结论都要保留 PDF 来源页码。

按实际内容组织为：文档概述、安全注意事项、设备组成、技术规格、安装与准备、操作说明、维护与保养、故障排查、附录。PDF 中不存在的章节不要虚构。

对每张有实际信息的图片输出图片类型、页码、唯一 asset_id、标题、可见标签、关键数值和准确说明，并使用：
<!-- source_page: <页码>; asset_id: img-p<页码>-<序号>; type: <类型> -->
![图片标题](assets/img-p<页码>-<序号>.png)
""".strip()


class ScriptError(RuntimeError):
    """A user-facing configuration, transport, or response error."""


class ApiRequestError(ScriptError):
    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float
    max_file_bytes: int
    retries: int


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ScriptError(f"{name} must be an integer") from exc


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ScriptError(f"{name} must be a number") from exc


def _load_environment() -> None:
    if load_dotenv is None:
        return
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    load_dotenv(override=False)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a PDF to Gemini Interactions API and save Markdown."
    )
    parser.add_argument("pdf", type=Path, help="Path to the PDF file")
    parser.add_argument(
        "--scope",
        choices=("fault", "full"),
        default=None,
        help="Prompt scope; defaults to PDF_LLM_SCOPE or fault",
    )
    parser.add_argument("--prompt-file", type=Path, help="Use a custom UTF-8 prompt file")
    parser.add_argument("--output", type=Path, help="Markdown output path")
    parser.add_argument(
        "--base-url",
        help="Override GEMINI_BASE_URL (defaults to the Gemini v1beta API base URL)",
    )
    parser.add_argument("--model", help="Override GEMINI_MODEL")
    parser.add_argument("--timeout", type=float, help="Request timeout in seconds")
    parser.add_argument("--max-file-mb", type=float, help="Maximum local PDF size in MB")
    parser.add_argument("--retries", type=int, help="Retries for transient errors")
    return parser.parse_args()


def _resolve_config(args: argparse.Namespace) -> Config:
    base_url = args.base_url or _first_env(
        "GEMINI_BASE_URL", "GEMINI_API_BASE", "PDF_LLM_BASE_URL"
    ) or "https://generativelanguage.googleapis.com/v1beta"
    api_key = _first_env("GEMINI_API_KEY", "PDF_LLM_API_KEY")
    model = args.model or _first_env("GEMINI_MODEL", "PDF_LLM_MODEL") or "gemini-3.8-flash"
    timeout = args.timeout if args.timeout is not None else _env_float("PDF_LLM_TIMEOUT_SECONDS", 180.0)
    max_file_mb = (
        args.max_file_mb
        if args.max_file_mb is not None
        else _env_float("PDF_LLM_MAX_FILE_MB", 50.0)
    )
    retries = args.retries if args.retries is not None else _env_int("PDF_LLM_RETRIES", 1)

    if not base_url:
        raise ScriptError(
            "Missing API base URL. Set GEMINI_BASE_URL in .env."
        )
    if not api_key:
        raise ScriptError(
            "Missing API key. Set GEMINI_API_KEY in .env."
        )
    if timeout <= 0 or max_file_mb <= 0 or retries < 0:
        raise ScriptError("Timeout and file limit must be positive; retries cannot be negative")

    return Config(
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        model=model,
        timeout_seconds=timeout,
        max_file_bytes=int(max_file_mb * 1024 * 1024),
        retries=retries,
    )


def _endpoint(base_url: str) -> str:
    if base_url.endswith("/interactions"):
        return base_url
    return f"{base_url}/interactions"


def _build_payload(
    config: Config, pdf_bytes: bytes, prompt: str
) -> Dict[str, Any]:
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    return {
        "model": config.model,
        "input": [
            {
                "type": "document",
                "data": encoded,
                "mime_type": "application/pdf",
            },
            {"type": "text", "text": prompt},
        ],
        "store": False,
    }


def _response_error_message(body: bytes) -> str:
    text = body.decode("utf-8", errors="replace").strip()
    if len(text) > 1000:
        text = text[:1000] + "..."
    return text or "empty error response"


def _ssl_context() -> ssl.SSLContext:
    ca_bundle = _first_env(
        "PDF_LLM_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"
    )
    if ca_bundle:
        ca_path = Path(ca_bundle).expanduser()
        if not ca_path.is_file():
            raise ScriptError(f"CA bundle does not exist: {ca_path}")
        return ssl.create_default_context(cafile=str(ca_path))

    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _post_once(endpoint: str, config: Config, payload: Dict[str, Any]) -> Dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "x-goog-api-key": config.api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=config.timeout_seconds, context=_ssl_context()
        ) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = _response_error_message(exc.read())
        retryable = exc.code == 429 or exc.code >= 500
        raise ApiRequestError(f"API returned HTTP {exc.code}: {detail}", retryable) from exc
    except urllib.error.URLError as exc:
        raise ApiRequestError(f"API request failed: {exc.reason}", retryable=True) from exc
    except TimeoutError as exc:
        raise ApiRequestError("API request timed out", retryable=True) from exc

    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScriptError("API returned a non-JSON response") from exc
    if not isinstance(parsed, dict):
        raise ScriptError("API returned JSON, but the top-level value is not an object")
    return parsed


def _post_with_retries(endpoint: str, config: Config, payload: Dict[str, Any]) -> Dict[str, Any]:
    for attempt in range(config.retries + 1):
        try:
            return _post_once(endpoint, config, payload)
        except ApiRequestError as exc:
            if not exc.retryable or attempt >= config.retries:
                raise
            time.sleep(min(2**attempt, 8))
    raise ScriptError("API request failed without a response")


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _extract_markdown(response: Dict[str, Any]) -> str:
    status = response.get("status")
    if status and status != "completed":
        error = response.get("error")
        detail = json.dumps(error, ensure_ascii=False) if error else str(status)
        raise ScriptError(f"Gemini interaction did not complete: {detail}")

    steps = response.get("steps")
    if isinstance(steps, list):
        parts = []
        for step in steps:
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            parts.append(_content_text(step.get("content")))
        text = "".join(parts).strip()
        if text:
            return text

    # Keep support for the SDK convenience response in local fixtures.
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    keys = ", ".join(sorted(response.keys()))
    raise ScriptError(f"Could not find model output text in Gemini response. Top-level keys: {keys}")


def _normalize_markdown(text: str) -> str:
    normalized = text.strip()
    lines = normalized.splitlines()
    if len(lines) >= 2 and lines[0].strip().lower() in {"```", "```md", "```markdown"}:
        if lines[-1].strip() == "```":
            normalized = "\n".join(lines[1:-1]).strip()
    if not normalized:
        raise ScriptError("The API returned empty Markdown")
    return normalized + "\n"


def _prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        try:
            prompt = args.prompt_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ScriptError(f"Could not read prompt file: {args.prompt_file}") from exc
        if not prompt:
            raise ScriptError("The prompt file is empty")
        return prompt
    scope = args.scope or _first_env("PDF_LLM_SCOPE") or "fault"
    return FAULT_PROMPT if scope == "fault" else FULL_PROMPT


def _output_path(args: argparse.Namespace, pdf_path: Path) -> Path:
    if args.output:
        return args.output.expanduser()
    output_dir = Path(os.getenv("PDF_LLM_OUTPUT_DIR", "data/gemini-output"))
    return output_dir / f"{pdf_path.stem}.md"


def main() -> int:
    _load_environment()
    args = _parse_args()
    config = _resolve_config(args)
    pdf_path = args.pdf.expanduser().resolve()

    if not pdf_path.is_file():
        raise ScriptError(f"PDF file does not exist: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ScriptError(f"Expected a .pdf file: {pdf_path}")

    pdf_bytes = pdf_path.read_bytes()
    if not pdf_bytes:
        raise ScriptError("The PDF file is empty")
    if len(pdf_bytes) > config.max_file_bytes:
        limit_mb = config.max_file_bytes / 1024 / 1024
        raise ScriptError(f"PDF exceeds the configured {limit_mb:.1f} MB limit")

    endpoint = _endpoint(config.base_url)
    payload = _build_payload(config, pdf_bytes, _prompt(args))
    print(f"Sending {pdf_path.name} to {endpoint} with model {config.model}...")
    response = _post_with_retries(endpoint, config, payload)
    markdown = _normalize_markdown(_extract_markdown(response))

    output_path = _output_path(args, pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    raw_path = output_path.with_suffix(".response.json")
    raw_path.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Markdown written to: {output_path}")
    print(f"Raw response written to: {raw_path}")
    print(f"Markdown characters: {len(markdown)}")
    if not markdown.lstrip().startswith("#"):
        print("Warning: response does not start with a Markdown heading.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
