#!/usr/bin/env python3

import argparse
import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

LIBRARY_PATTERNS = {
    "darwin": {
        "avutil": re.compile(r"^libavutil(?:\.\d+)*\.dylib$", re.IGNORECASE),
        "avcodec": re.compile(r"^libavcodec(?:\.\d+)*\.dylib$", re.IGNORECASE),
        "avformat": re.compile(r"^libavformat(?:\.\d+)*\.dylib$", re.IGNORECASE),
    },
    "linux": {
        "avutil": re.compile(r"^libavutil\.so(?:\.\d+)*$", re.IGNORECASE),
        "avcodec": re.compile(r"^libavcodec\.so(?:\.\d+)*$", re.IGNORECASE),
        "avformat": re.compile(r"^libavformat\.so(?:\.\d+)*$", re.IGNORECASE),
    },
    "win32": {
        "avutil": re.compile(r"^avutil-\d+\.dll$", re.IGNORECASE),
        "avcodec": re.compile(r"^avcodec-\d+\.dll$", re.IGNORECASE),
        "avformat": re.compile(r"^avformat-\d+\.dll$", re.IGNORECASE),
    },
}


def platform_key() -> str:
    if sys.platform.startswith("win"):
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


PLATFORM_KEY = platform_key()
PATH_SEPARATOR = ";" if PLATFORM_KEY == "win32" else ":"


def runtime_lib_dir() -> Path:
    return Path(sys.base_prefix) / ("Lib" if PLATFORM_KEY == "win32" else "lib")


def normalize_path(value: str | None) -> str:
    return str(value or "").replace("\\", "/").rstrip("/").lower()


def resolved_binary(name: str) -> str | None:
    env_name = f"{name.upper()}_PATH"
    return os.environ.get(env_name) or shutil.which(name)


def ffmpeg_prefix(ffmpeg_path: str | None) -> Path | None:
    if not ffmpeg_path:
        return None
    binary = Path(ffmpeg_path).resolve()
    if PLATFORM_KEY == "win32":
        return binary.parent.parent.parent
    if binary.parent.name == "bin":
        return binary.parent.parent
    return binary.parent.parent


def shared_lib_dir(prefix: Path | None) -> Path | None:
    if prefix is None:
        return None
    if PLATFORM_KEY == "win32":
        return prefix / "Library" / "bin"
    return prefix / "lib"


def choose_library(lib_dir: Path | None, pattern: re.Pattern[str]) -> Path | None:
    if lib_dir is None or not lib_dir.exists():
        return None
    matches = [
        entry
        for entry in lib_dir.iterdir()
        if entry.is_file() or entry.is_symlink()
        if pattern.match(entry.name)
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda entry: (len(entry.name), entry.name), reverse=True)[0]


def runtime_entry_state(runtime_dir: Path, name: str | None) -> dict:
    if not name:
        return {
            "path": None,
            "exists": False,
            "is_symlink": False,
            "symlink_target": None,
        }
    target = runtime_dir / name
    state = {
        "path": str(target),
        "exists": target.exists(),
        "is_symlink": target.is_symlink(),
        "symlink_target": None,
    }
    if target.is_symlink():
        state["symlink_target"] = os.readlink(target)
    return state


def load_by_name(name: str | None) -> dict:
    if not name:
        return {"name": None, "load_by_name": False, "error": "library name not found"}
    try:
        ctypes.CDLL(name)
        return {"name": name, "load_by_name": True}
    except OSError as exc:
        return {"name": name, "load_by_name": False, "error": str(exc)}


def run_command(command: list[str]) -> dict:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def split_path(value: str | None) -> list[str]:
    return [entry for entry in str(value or "").split(PATH_SEPARATOR) if entry]


def collect_state() -> dict:
    ffmpeg_path = resolved_binary("ffmpeg")
    ffprobe_path = resolved_binary("ffprobe")
    prefix = ffmpeg_prefix(ffmpeg_path)
    lib_dir = shared_lib_dir(prefix)
    runtime_dir = runtime_lib_dir()
    libraries = []

    for component, pattern in LIBRARY_PATTERNS[PLATFORM_KEY].items():
        shared_path = choose_library(lib_dir, pattern)
        runtime_state = runtime_entry_state(runtime_dir, shared_path.name if shared_path else None)
        load_state = load_by_name(shared_path.name if shared_path else None)
        libraries.append({
            "component": component,
            "name": shared_path.name if shared_path else None,
            "shared_path": str(shared_path) if shared_path else None,
            "shared_exists": bool(shared_path and shared_path.exists()),
            "runtime_path": runtime_state["path"],
            "runtime_exists": runtime_state["exists"],
            "runtime_is_symlink": runtime_state["is_symlink"],
            "runtime_symlink_target": runtime_state["symlink_target"],
            "load_by_name": load_state["load_by_name"],
            "load_error": load_state.get("error"),
        })

    ffmpeg_version = run_command(["ffmpeg", "-hide_banner", "-version"])
    ffprobe_version = run_command(["ffprobe", "-hide_banner", "-version"])
    encoder_output = run_command(["ffmpeg", "-hide_banner", "-encoders"])

    return {
        "platform": platform.platform(),
        "platform_key": PLATFORM_KEY,
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "runtime_lib_dir": str(runtime_dir),
        "ffmpeg_path_env": os.environ.get("FFMPEG_PATH"),
        "ffprobe_path_env": os.environ.get("FFPROBE_PATH"),
        "which_ffmpeg": shutil.which("ffmpeg"),
        "which_ffprobe": shutil.which("ffprobe"),
        "ffmpeg_prefix": str(prefix) if prefix else None,
        "shared_lib_dir": str(lib_dir) if lib_dir else None,
        "path_entries": split_path(os.environ.get("PATH"))[:8],
        "ld_library_path_entries": split_path(os.environ.get("LD_LIBRARY_PATH"))[:8],
        "libraries": libraries,
        "ffmpeg_version": first_line(ffmpeg_version["stdout"] or ffmpeg_version["stderr"]),
        "ffprobe_version": first_line(ffprobe_version["stdout"] or ffprobe_version["stderr"]),
        "has_libmp3lame": "libmp3lame" in ((encoder_output["stdout"] or "") + (encoder_output["stderr"] or "")),
    }


def resolved_binaries_match(state: dict) -> bool:
    ffmpeg_ok = normalize_path(state["ffmpeg_path_env"]) == normalize_path(state["which_ffmpeg"])
    ffprobe_ok = normalize_path(state["ffprobe_path_env"]) == normalize_path(state["which_ffprobe"])
    return ffmpeg_ok and ffprobe_ok


def libraries_ready(state: dict) -> bool:
    if not resolved_binaries_match(state):
        return False
    if not state["ffmpeg_version"] or not state["ffprobe_version"] or not state["has_libmp3lame"]:
        return False
    if not all(item["shared_exists"] and item["load_by_name"] for item in state["libraries"]):
        return False
    if PLATFORM_KEY == "darwin":
        return all(item["runtime_exists"] for item in state["libraries"])
    return True


def print_state(state: dict) -> None:
    print(f"platform: {state['platform']}")
    print(f"python: {state['python']}")
    print(f"executable: {state['executable']}")
    print(f"base_prefix: {state['base_prefix']}")
    print(f"runtime_lib_dir: {state['runtime_lib_dir']}")
    print(f"ffmpeg_path_env: {state['ffmpeg_path_env']}")
    print(f"ffprobe_path_env: {state['ffprobe_path_env']}")
    print(f"which_ffmpeg: {state['which_ffmpeg']}")
    print(f"which_ffprobe: {state['which_ffprobe']}")
    print(f"ffmpeg_prefix: {state['ffmpeg_prefix']}")
    print(f"shared_lib_dir: {state['shared_lib_dir']}")
    print("")
    print("path_entries:")
    for entry in state["path_entries"]:
        print(f"  - {entry}")
    if state["ld_library_path_entries"]:
        print("")
        print("ld_library_path_entries:")
        for entry in state["ld_library_path_entries"]:
            print(f"  - {entry}")
    print("")
    print("libraries:")
    for item in state["libraries"]:
        runtime_suffix = ""
        if item["runtime_is_symlink"] and item["runtime_symlink_target"]:
            runtime_suffix = f" -> {item['runtime_symlink_target']}"
        print(
            f"  - {item['component']}: name={item['name']} shared_exists={item['shared_exists']} "
            f"runtime_exists={item['runtime_exists']} runtime_symlink={item['runtime_is_symlink']}{runtime_suffix}"
        )
    print("")
    print("load_by_name:")
    for item in state["libraries"]:
        if item["load_by_name"]:
            print(f"  - {item['name']}: ok")
        else:
            print(f"  - {item['name']}: failed: {item['load_error']}")
    print("")
    print(f"ffmpeg_version: {state['ffmpeg_version']}")
    print(f"ffprobe_version: {state['ffprobe_version']}")
    print(f"has_libmp3lame: {state['has_libmp3lame']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--require", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    deadline = time.time() + args.timeout
    state = collect_state()

    while args.wait and not libraries_ready(state) and time.time() < deadline:
        time.sleep(args.interval)
        state = collect_state()

    if args.json:
        print(json.dumps(state, indent=2))
    else:
        print_state(state)

    if args.require and not libraries_ready(state):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
