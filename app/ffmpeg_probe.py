#!/usr/bin/env python3

import argparse
import ctypes
import json
import os
import platform
import sys
import time
from pathlib import Path

LIBRARIES = [
    "libavutil.60.dylib",
    "libavcodec.62.dylib",
    "libavformat.62.dylib",
]


def runtime_lib_dir() -> Path:
    return Path(sys.base_prefix) / "lib"


def dylib_state(lib_dir: Path, name: str) -> dict:
    target = lib_dir / name
    info = {
        "name": name,
        "path": str(target),
        "exists": target.exists(),
        "is_symlink": target.is_symlink(),
        "symlink_target": None,
    }
    if target.is_symlink():
        info["symlink_target"] = os.readlink(target)
    return info


def load_by_name(name: str) -> dict:
    try:
        ctypes.CDLL(name)
        return {"name": name, "load_by_name": True}
    except OSError as exc:
        return {"name": name, "load_by_name": False, "error": str(exc)}


def collect_state() -> dict:
    lib_dir = runtime_lib_dir()
    libs = [dylib_state(lib_dir, name) for name in LIBRARIES]
    loads = [load_by_name(name) for name in LIBRARIES]
    return {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "runtime_lib_dir": str(lib_dir),
        "libraries": libs,
        "loads": loads,
    }


def libraries_ready(state: dict) -> bool:
    return all(item["exists"] for item in state["libraries"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--require", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if sys.platform != "darwin":
        print("This probe is macOS-specific.")
        return 0

    deadline = time.time() + args.timeout
    state = collect_state()

    while args.wait and not libraries_ready(state) and time.time() < deadline:
        time.sleep(args.interval)
        state = collect_state()

    if args.json:
        print(json.dumps(state, indent=2))
    else:
        print(f"python: {state['python']}")
        print(f"executable: {state['executable']}")
        print(f"base_prefix: {state['base_prefix']}")
        print(f"runtime_lib_dir: {state['runtime_lib_dir']}")
        print("")
        print("libraries:")
        for item in state["libraries"]:
            suffix = ""
            if item["is_symlink"] and item["symlink_target"]:
                suffix = f" -> {item['symlink_target']}"
            print(f"  - {item['name']}: exists={item['exists']} symlink={item['is_symlink']}{suffix}")
        print("")
        print("load_by_name:")
        for item in state["loads"]:
            if item["load_by_name"]:
                print(f"  - {item['name']}: ok")
            else:
                print(f"  - {item['name']}: failed: {item['error']}")

    if args.require and not libraries_ready(state):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
