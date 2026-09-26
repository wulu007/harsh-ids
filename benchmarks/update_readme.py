"""Automatically run benchmarks and update the README.md table.

Usage:
    uv run --group bench python benchmarks/update_readme.py
"""

import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path

README_PATH = Path(__file__).resolve().parent.parent / "README.md"
START_TAG = "<!-- BENCHMARK-START -->"
END_TAG = "<!-- BENCHMARK-END -->"

SCENARIOS = [
    {
        "name": "Encode (3 nums)",
        "py_key": "test_python_encode_small",
        "rs_key": "test_rust_encode_small",
    },
    {
        "name": "Decode (short id)",
        "py_key": "test_python_decode_small",
        "rs_key": "test_rust_decode_small",
    },
    {
        "name": "Encode (100 nums)",
        "py_key": "test_python_encode_large",
        "rs_key": "test_rust_encode_large",
    },
    {
        "name": "Decode (long payload)",
        "py_key": "test_python_decode_large",
        "rs_key": "test_rust_decode_large",
    },
]


def run_benchmark() -> dict:
    """Run pytest-benchmark and return parsed JSON results."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        print("[*] Running benchmarks via pytest-benchmark...")
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "benchmarks/test_compare.py",
            "--benchmark-only",
            f"--benchmark-json={tmp_path}",
            "-q",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout)
            print(res.stderr, file=sys.stderr)
            raise RuntimeError(f"pytest exited with code {res.returncode}")

        with open(tmp_path, "r", encoding="utf-8") as f:
            return json.load(f)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def format_ops(ops: float) -> str:
    """Format operations per second."""
    if ops >= 1_000_000:
        return f"{ops / 1_000_000:.2f} Mops/s"
    if ops >= 1_000:
        return f"{ops / 1_000:.1f} Kops/s"
    return f"{ops:.0f} ops/s"


def format_time(seconds: float) -> str:
    """Format time in microseconds or milliseconds."""
    us = seconds * 1e6
    if us >= 1000:
        return f"{us / 1000:.2f} ms"
    if us >= 10:
        return f"{us:.1f} µs"
    return f"{us:.2f} µs"


def os_label() -> str:
    """Human-readable OS name for the footnote.

    platform.release() (and win32_ver()[0]) report "10" on Windows 11 as
    well, so the build number is the only reliable way to tell them apart.
    """
    if platform.system() == "Windows":
        return "Windows 11" if sys.getwindowsversion().build >= 22000 else "Windows 10"
    return f"{platform.system()} {platform.release()}"


def build_markdown_table(data: dict) -> str:
    """Build the formatted markdown benchmark section."""
    stats_map = {b["name"]: b["stats"] for b in data["benchmarks"]}

    lines = [
        START_TAG,
        "| Operation (Scenario) | Pure Python (`hashids`) | Rust (`harsh-ids`) | Throughput (`harsh-ids`) | **Speedup** |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for item in SCENARIOS:
        py_stat = stats_map[item["py_key"]]
        rs_stat = stats_map[item["rs_key"]]

        py_mean = py_stat["mean"]
        rs_mean = rs_stat["mean"]
        speedup = py_mean / rs_mean if rs_mean > 0 else 1.0
        rs_ops = rs_stat["ops"]

        py_time_str = format_time(py_mean)
        rs_time_str = format_time(rs_mean)
        ops_str = format_ops(rs_ops)

        lines.append(
            f"| **{item['name']}** | {py_time_str} | **{rs_time_str}** | **{ops_str}** | 🚀 **~{speedup:.1f}x** |"
        )

    # Footnote with environment info
    py_ver = sys.version.split()[0]
    os_info = os_label()
    lines.append("")
    lines.append(
        f"> *Environment: Tested on {os_info} with Python {py_ver} using `pytest-benchmark`.*"
    )
    lines.append(END_TAG)

    return "\n".join(lines)


def update_readme(new_content: str) -> None:
    """Replace content between START_TAG and END_TAG in README.md."""
    if not README_PATH.exists():
        raise FileNotFoundError(f"{README_PATH} not found")

    text = README_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"{re.escape(START_TAG)}.*?{re.escape(END_TAG)}",
        re.DOTALL,
    )

    if pattern.search(text):
        updated = pattern.sub(new_content, text)
    else:
        # If tags not found, insert under the Benchmarks section
        target = "## Benchmarks\n"
        if target in text:
            updated = text.replace(target, f"{target}\n{new_content}\n")
        else:
            updated = text + f"\n\n{new_content}\n"

    README_PATH.write_text(updated, encoding="utf-8")
    print(f"[+] Successfully updated {README_PATH}")


def main() -> None:
    data = run_benchmark()
    table_md = build_markdown_table(data)
    update_readme(table_md)


if __name__ == "__main__":
    main()
