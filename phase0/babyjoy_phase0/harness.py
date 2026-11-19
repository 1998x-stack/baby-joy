"""Local Phase 0 harness. Never sends private inputs to a remote service.

The upstream model environments and checkpoints are supplied by the operator,
not downloaded or executed by this package.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
import wave

MODEL_IDS = ("echomimic_v3_flash", "infinitetalk", "wan22_s2v")
CASE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PROMPT = "A baby looking at the camera, gently smiling and speaking, subtle natural facial motions, no exaggerated mouth movement."


class GateError(ValueError):
    """Preflight failure that must prevent GPU execution."""


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        result = json.load(file)
    if not isinstance(result, dict):
        raise GateError("Expected JSON object")
    return result


def private_file(private_root: Path, relative: str, suffixes: tuple[str, ...]) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise GateError("Private asset must have a relative path")
    if ".." in Path(relative).parts:
        raise GateError("Private asset may not traverse above private root")
    root = private_root.resolve(strict=True)
    try:
        candidate = (root / relative).resolve(strict=True)
    except (OSError, FileNotFoundError) as exc:
        raise GateError("Private asset is missing") from exc
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise GateError("Private asset is missing or escapes private root")
    if candidate.suffix.lower() not in suffixes:
        raise GateError("Unexpected private asset file type")
    return candidate


def read_cases(private_root: Path, jsonl: Path) -> list[dict]:
    root = private_root.resolve(strict=True)
    manifest = jsonl.resolve(strict=True)
    if not manifest.is_relative_to(root):
        raise GateError("Case manifest must be inside private root")
    cases: list[dict] = []
    identifiers: set[str] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GateError("Invalid case JSONL") from exc
        if not isinstance(case, dict) or not CASE_ID.fullmatch(str(case.get("case_id", ""))):
            raise GateError("Case requires safe case_id")
        if case["case_id"] in identifiers:
            raise GateError("Duplicate case_id")
        identifiers.add(case["case_id"])
        if not isinstance(case.get("consent_reference"), str) or not case["consent_reference"].strip():
            raise GateError("Consent reference is required for each private image")
        if case.get("consent_scope") != "BENCHMARK_RESEARCH":
            raise GateError("Case has not declared a benchmark-specific consent scope")
        if case.get("consent_active") is not True:
            raise GateError("Consent status must be explicitly active")
        image = private_file(root, case.get("image", ""), (".jpg", ".jpeg", ".png", ".webp"))
        audio = private_file(root, case.get("audio", ""), (".wav",))
        if image.stat().st_size > 8 * 1024 * 1024 or image.stat().st_size == 0:
            raise GateError("Image exceeds benchmark size limit or is empty")
        try:
            with wave.open(str(audio), "rb") as wav:
                if wav.getnframes() == 0 or wav.getframerate() <= 0:
                    raise GateError("Empty WAV input")
                seconds = wav.getnframes() / wav.getframerate()
        except (wave.Error, EOFError) as exc:
            raise GateError("Audio must be a readable PCM WAV") from exc
        if not 0.4 <= seconds <= 12.0:
            raise GateError("WAV duration outside supported 0.4 to 12.0 seconds")
        if not isinstance(case.get("seed", 43), int) or isinstance(case.get("seed", 43), bool):
            raise GateError("Seed must be an integer")
        cases.append({
            "case_id": case["case_id"],
            "image_path": str(image),
            "audio_path": str(audio),
            "audio_seconds": seconds,
            "seed": case.get("seed", 43),
        })
    if not cases:
        raise GateError("No authorized test cases in private manifest")
    return cases


def sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as file:
        for data in iter(lambda: file.read(4 * 1024 * 1024), b""):
            sha.update(data)
    return sha.hexdigest()


def check_approval(config: dict, model_id: str) -> dict:
    approval_path = Path(config.get("approval_file", "")).expanduser()
    if not approval_path.is_file():
        raise GateError("Model approval file missing (default: NOT APPROVED)")
    approval = load_json(approval_path)
    if (approval.get("model_id") != model_id
            or approval.get("decision") not in ("RESEARCH_APPROVED", "COMMERCIAL_APPROVED")
            or not approval.get("reviewer")
            or not approval.get("review_date")
            or not isinstance(approval.get("evidence_urls"), list)
            or not approval["evidence_urls"]):
        raise GateError("Model license review is incomplete or not approved")
    return approval


def check_weights(config: dict) -> list[dict]:
    entries = config.get("weights")
    if not isinstance(entries, list) or not entries:
        raise GateError("Explicit weight hashes required; do not trust a moving checkpoint name")
    verified: list[dict] = []
    for item in entries:
        if not isinstance(item, dict) or not SHA256.fullmatch(str(item.get("sha256", ""))):
            raise GateError("Each weight needs a 64-character SHA256")
        path = Path(item.get("path", ""))
        if not path.is_file() or not path.resolve().is_file():
            raise GateError("Weight file missing")
        actual = sha256_file(path)
        if actual != item["sha256"]:
            raise GateError("Checkpoint hash mismatch")
        verified.append({"filename": path.name, "sha256": actual})
    return verified


def check_gpu() -> str:
    if not shutil.which("nvidia-smi"):
        raise GateError("No nvidia-smi available: real GPU inference NOT RUN")
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
        text=True, capture_output=True, timeout=20, check=False
    )
    if result.returncode or not result.stdout.strip():
        raise GateError("NVIDIA GPU unavailable: real GPU inference NOT RUN")
    return result.stdout.strip()


def checked_model_path(config: dict, key: str, directory: bool = True) -> Path:
    raw = config.get(key)
    if not isinstance(raw, str) or not raw:
        raise GateError("Model config missing " + key)
    path = Path(raw).expanduser().resolve()
    if directory and not path.is_dir():
        raise GateError("Missing model directory " + key)
    if not directory and not path.is_file():
        raise GateError("Missing model file " + key)
    return path


def build_command(model_id: str, config: dict, case: dict, destination: Path) -> tuple[list[str], Path, Path]:
    """Build direct argv for official upstream entrypoints. No shell expansion."""
    if model_id not in MODEL_IDS:
        raise GateError("Unsupported model")
    repo_dir = checked_model_path(config, "repo_dir")
    entry = {
        "echomimic_v3_flash": "infer_flash.py",
        "infinitetalk": "generate_infinitetalk.py",
        "wan22_s2v": "generate.py",
    }[model_id]
    script = repo_dir / entry
    if not script.is_file():
        raise GateError("Upstream entrypoint missing")
    dest = destination.resolve()
    dest.mkdir(parents=True, exist_ok=False)
    os.chmod(dest, 0o700)
    result_file = dest / "result.mp4"
    args = [sys.executable, str(script)]
    if model_id == "echomimic_v3_flash":
        # Upstream truncates audio using min(audio_frames, video_length);
        # the 81-frame example is ~3.24 seconds at 25 FPS, not an 8-second example.
        fps = 25
        video_length = math.ceil(case["audio_seconds"] * fps / 4) * 4 + 1
        args += [
            "--image_path", case["image_path"], "--audio_path", case["audio_path"],
            "--prompt", PROMPT,
            "--config_path", str(checked_model_path(config, "config_path", False)),
            "--model_name", str(checked_model_path(config, "base_model_dir")),
            "--transformer_path", str(checked_model_path(config, "transformer_path", False)),
            "--wav2vec_model_dir", str(checked_model_path(config, "audio_encoder_dir")),
            "--save_path", str(dest), "--video_length", str(video_length),
            "--fps", str(fps), "--num_inference_steps", "8",
            "--seed", str(case["seed"]),
        ]
        expected = dest / (Path(case["image_path"]).stem + "_output.mp4")
    elif model_id == "infinitetalk":
        input_config = dest / "input.json"
        input_config.write_text(json.dumps({
            "prompt": PROMPT, "cond_video": case["image_path"],
            "cond_audio": {"person1": case["audio_path"]},
        }, ensure_ascii=False), encoding="utf-8")
        os.chmod(input_config, 0o600)
        args += [
            "--ckpt_dir", str(checked_model_path(config, "base_model_dir")),
            "--wav2vec_dir", str(checked_model_path(config, "audio_encoder_dir")),
            "--infinitetalk_dir", str(checked_model_path(config, "transformer_path", False)),
            "--input_json", str(input_config), "--size", "infinitetalk-480",
            "--sample_steps", "40", "--mode", "clip",
            "--save_file", str(dest / "result"),
        ]
        expected = result_file
    else:
        args += [
            "--task", "s2v-14B", "--size", "1024*704",
            "--ckpt_dir", str(checked_model_path(config, "base_model_dir")),
            "--offload_model", "True", "--convert_model_dtype",
            "--prompt", PROMPT, "--image", case["image_path"],
            "--audio", case["audio_path"], "--save_file", str(result_file),
        ]
        expected = result_file
    return args, repo_dir, expected


def probe_video(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size < 1024:
        raise GateError("Upstream did not write a nonempty MP4 output")
    if not shutil.which("ffprobe"):
        raise GateError("ffprobe required for independent video verification")
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-show_entries", "stream=codec_type,codec_name,width,height",
        "-of", "json", str(path),
    ], text=True, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise GateError("ffprobe failed to decode generated output")
    info = json.loads(result.stdout)
    duration = float(info.get("format", {}).get("duration", "0"))
    types = {x.get("codec_type") for x in info.get("streams", [])}
    if duration <= 0 or "video" not in types or "audio" not in types:
        raise GateError("MP4 must include decodable audio and video streams")
    return {"duration_seconds": duration, "streams": sorted(types)}


def execute_run(model_id: str, config: dict, case: dict, output_root: Path, timeout: int = 1800) -> dict:
    """Fails closed without license review, checkpoint hashes and real GPU."""
    if model_id not in MODEL_IDS:
        raise GateError("Unknown model")
    revision = config.get("model_revision")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise GateError("Pin the full 40-hex upstream Git commit as model_revision")
    approval = check_approval(config, model_id)
    verified_weights = check_weights(config)
    gpu = check_gpu()
    if timeout < 30 or timeout > 14400:
        raise GateError("Timeout outside allowable 30..14400 seconds")
    output_root.mkdir(parents=True, exist_ok=True)
    os.chmod(output_root, 0o700)
    run_id = str(uuid.uuid4())
    destination = output_root / run_id
    args, cwd, expected = build_command(model_id, config, case, destination)
    record = {
        "schema_version": 1, "run_id": run_id, "case_id": case["case_id"],
        "model_id": model_id, "model_revision": config.get("model_revision", "UNPINNED"),
        "research_approval": approval["decision"],
        "weights_verified": verified_weights, "gpu": gpu,
        "audio_seconds": round(case["audio_seconds"], 4),
        "seed": case["seed"], "status": "RUNNING",
        "verification": "NOT_RUN",
    }
    record_path = destination / "record.json"
    def save():
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(record_path, 0o600)
    save()
    started = time.monotonic()
    try:
        with (destination / "upstream.log").open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=15)
                raise GateError("Upstream model timed out")
        if rc != 0:
            raise GateError("Upstream exited nonzero; inspect private upstream.log")
        if model_id == "infinitetalk" and not expected.is_file():
            matches = list(destination.glob("result*.mp4"))
            if len(matches) == 1:
                expected = matches[0]
        media = probe_video(expected)
        difference = abs(media["duration_seconds"] - case["audio_seconds"])
        if difference > 0.30:
            raise GateError("Audio/video duration drift > 0.30s; possible truncation")
        record.update({"status": "COMPLETED", "verification": "PASS",
                       "media": media, "elapsed_seconds": round(time.monotonic() - started, 3)})
    except Exception as exc:
        record.update({"status": "FAILED", "verification": "FAIL",
                       "error_code": type(exc).__name__,
                       "error": str(exc)[:180],
                       "elapsed_seconds": round(time.monotonic() - started, 3)})
        save()
        raise
    save()
    return record


def report(output_root: Path) -> dict:
    if not output_root.exists():
        return {"status": "NOT_RUN", "runs": 0, "completed": 0, "failed": 0}
    records = []
    for file in output_root.glob("*/record.json"):
        try:
            records.append(load_json(file))
        except (ValueError, OSError, json.JSONDecodeError):
            continue
    completed = [r for r in records if r.get("status") == "COMPLETED"]
    return {
        "status": "OBSERVED" if records else "NOT_RUN",
        "runs": len(records),
        "completed": len(completed),
        "failed": sum(r.get("status") == "FAILED" for r in records),
        "unfinished": sum(r.get("status") == "RUNNING" for r in records),
        "model_ids": sorted({r.get("model_id", "unknown") for r in records}),
        "success_rate": (len(completed) / len(records)) if records else None,
        "latencies_seconds": sorted(r["elapsed_seconds"] for r in completed if "elapsed_seconds" in r),
        "note": "This reports basic run success, not infant identity, QC, consent or commercial readiness.",
    }
