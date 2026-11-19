#!/usr/bin/env python3
"""Static evidence gate for documentation-only Baby Joy blueprint.

No user photos, model weights, GPU or WeChat credentials required.
"""
from pathlib import Path
import re
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specs" / "openapi.yaml"

def ensure_refs(node, root, parents="root"):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                if not isinstance(value, str) or not value.startswith("#/"):
                    raise ValueError(f"Invalid ref at {parents}: {value!r}")
                target = root
                for part in value[2:].split("/"):
                    part = part.replace("~1", "/").replace("~0", "~")
                    if not isinstance(target, dict) or part not in target:
                        raise ValueError(f"Broken ref at {parents}: {value}")
                    target = target[part]
            else:
                ensure_refs(value, root, f"{parents}.{key}")
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            ensure_refs(value, root, f"{parents}[{idx}]")

def validate_openapi():
    with SPEC.open(encoding="utf-8") as handle:
        d = yaml.safe_load(handle)
    assert isinstance(d, dict)
    assert str(d["openapi"]).startswith("3.1.")
    assert "/v1/auth/wechat" in d["paths"]
    assert "/v1/jobs" in d["paths"]
    assert "/v1/jobs/{job_id}/download" in d["paths"]
    assert "/v1/jobs/{job_id}" in d["paths"]
    assert "/v1/deletions/{deletion_id}" in d["paths"]
    assert "/v1/assets/images" in d["paths"]
    assert d["paths"]["/v1/auth/wechat"]["post"]["security"] == []
    assert "bearerAuth" in d["components"]["securitySchemes"]
    ensure_refs(d, d)
    print(f"PASS OpenAPI YAML + refs ({len(d['paths'])} paths)")

def validate_links():
    broken = []
    files = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    for file in files:
        for link in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
            raw = link.split("#", 1)[0].strip()
            if not raw or raw.startswith(("https://", "http://", "mailto:", "/")):
                continue
            target = (file.parent / raw).resolve()
            if not target.is_relative_to(ROOT) or not target.exists():
                broken.append(f"{file.relative_to(ROOT)} -> {link}")
    if broken:
        raise ValueError("Broken relative links:\n" + "\n".join(broken))
    print(f"PASS Markdown relative links ({len(files)} files)")

def validate_private_files():
    paths = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    forbidden_prefixes = ("data/", "private/", "storage/", "uploads/", "outputs/", "checkpoints/", "weights/")
    for p in paths:
        if p.startswith(forbidden_prefixes) or p.endswith((".safetensors", ".ckpt", ".pth", ".pt")):
            raise ValueError(f"Private/media/weight artifact tracked: {p}")
    print(f"PASS no private media/weights tracked ({len(paths)} indexed files)")

if __name__ == "__main__":
    try:
        validate_openapi()
        validate_links()
        validate_private_files()
    except Exception as exc:
        print("FAIL blueprint validation:", exc, file=sys.stderr)
        raise SystemExit(1)
