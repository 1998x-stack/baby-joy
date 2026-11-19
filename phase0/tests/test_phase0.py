"""CPU-only safety and contract tests; no real baby photos and no GPU needed."""
import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

from babyjoy_phase0.cli import main
from babyjoy_phase0.evaluation import summarize_ratings, wilson
from babyjoy_phase0.harness import (
    GateError, build_command, check_approval, check_gpu, check_weights,
    check_repo_revision, sample_gpu_used_mib,
    load_json, private_file, probe_video, read_cases, report,
)


class Phase0HarnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "assets").mkdir()
        (self.root / "assets" / "test.png").write_bytes(b"not a real baby image; a unit-test placeholder")
        with wave.open(str(self.root / "assets" / "test.wav"), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\0\0" * 16000)
        self.cases = self.root / "cases.jsonl"
        self.valid = {
            "case_id": "case01", "image": "assets/test.png", "audio": "assets/test.wav",
            "consent_reference": "internal-authorization-reference",
            "consent_scope": "BENCHMARK_RESEARCH", "consent_active": True,
            "seed": 43,
        }
        self.cases.write_text(json.dumps(self.valid) + "\n", encoding="utf-8")
        self.vendor = self.root / "vendor"
        self.vendor.mkdir()
        for script in ("infer_flash.py", "generate_infinitetalk.py", "generate.py"):
            (self.vendor / script).write_text("# unit-test placeholder\n", encoding="utf-8")
        self.base = self.root / "base"
        self.base.mkdir()
        self.encoder = self.root / "encoder"
        self.encoder.mkdir()
        self.checkpoint = self.root / "model.safetensors"
        self.checkpoint.write_bytes(b"tiny fake weights for unit test only")
        self.config_file = self.root / "upstream.yaml"
        self.config_file.write_text("upstream: placeholder\n", encoding="utf-8")
        self.config = {
            "repo_dir": str(self.vendor), "base_model_dir": str(self.base),
            "audio_encoder_dir": str(self.encoder),
            "transformer_path": str(self.checkpoint),
            "config_path": str(self.config_file),
        }

    def test_authorized_manifest_validation(self):
        entries = read_cases(self.root, self.cases)
        self.assertEqual(len(entries), 1)
        self.assertAlmostEqual(entries[0]["audio_seconds"], 1.0)

    def test_missing_consent_rejected(self):
        case = dict(self.valid)
        case.pop("consent_reference")
        self.cases.write_text(json.dumps(case) + "\n", encoding="utf-8")
        with self.assertRaises(GateError):
            read_cases(self.root, self.cases)

    def test_wrong_consent_scope_rejected(self):
        case = dict(self.valid, consent_scope="PUBLIC_POSTING")
        self.cases.write_text(json.dumps(case) + "\n", encoding="utf-8")
        with self.assertRaises(GateError):
            read_cases(self.root, self.cases)

    def test_inactive_consent_rejected(self):
        case = dict(self.valid, consent_active=False)
        self.cases.write_text(json.dumps(case) + "\n", encoding="utf-8")
        with self.assertRaises(GateError):
            read_cases(self.root, self.cases)

    def test_duplicate_case_id_rejected(self):
        self.cases.write_text((json.dumps(self.valid) + "\n") * 2, encoding="utf-8")
        with self.assertRaises(GateError):
            read_cases(self.root, self.cases)

    def test_path_escape_rejected(self):
        with self.assertRaises(GateError):
            private_file(self.root, "../escape.png", (".png",))

    def test_absolute_path_rejected(self):
        with self.assertRaises(GateError):
            private_file(self.root, str(self.root / "assets" / "test.png"), (".png",))

    def test_incorrect_weight_hash_rejected(self):
        self.config["weights"] = [{"path": str(self.checkpoint), "sha256": "0" * 64}]
        with self.assertRaises(GateError):
            check_weights(self.config)

    def test_correct_weight_hash(self):
        sha = hashlib.sha256(self.checkpoint.read_bytes()).hexdigest()
        self.config["weights"] = [{"path": str(self.checkpoint), "sha256": sha}]
        self.assertEqual(len(check_weights(self.config)), 1)

    def test_license_default_denied(self):
        with self.assertRaises(GateError):
            check_approval({}, "echomimic_v3_flash")

    def test_license_pending_denied(self):
        approval_file = self.root / "approval.json"
        approval_file.write_text(json.dumps({
            "model_id": "echomimic_v3_flash", "decision": "PENDING",
            "reviewer": "test", "review_date": "2026-11-19", "evidence_urls": ["https://example.org"],
        }))
        with self.assertRaises(GateError):
            check_approval({"approval_file": str(approval_file)}, "echomimic_v3_flash")

    def test_license_research_approved_for_local_run(self):
        approval_file = self.root / "approval.json"
        approval_file.write_text(json.dumps({
            "model_id": "echomimic_v3_flash", "decision": "RESEARCH_APPROVED",
            "reviewer": "test", "review_date": "2026-11-19", "evidence_urls": ["https://example.org"],
        }))
        self.assertEqual(check_approval({"approval_file": str(approval_file)},
                                        "echomimic_v3_flash")["decision"], "RESEARCH_APPROVED")

    def test_echo_builds_full_audio_length_not_81_frames(self):
        case = read_cases(self.root, self.cases)[0]
        case["audio_seconds"] = 8.0
        args, cwd, expected = build_command(
            "echomimic_v3_flash", self.config, case, self.root / "run-echo")
        frames = int(args[args.index("--video_length") + 1])
        self.assertGreaterEqual(frames, 200)
        self.assertNotIn(";", args)
        self.assertEqual(cwd, self.vendor)
        self.assertEqual(expected.parent, self.root / "run-echo")

    def test_infinitetalk_builds_input_json_locally(self):
        case = read_cases(self.root, self.cases)[0]
        args, cwd, expected = build_command(
            "infinitetalk", self.config, case, self.root / "run-talk")
        model_input = self.root / "run-talk" / "input.json"
        self.assertTrue(model_input.exists())
        self.assertEqual(json.loads(model_input.read_text())["cond_audio"]["person1"],
                         case["audio_path"])
        self.assertIn("--mode", args)
        self.assertEqual(cwd, self.vendor)

    def test_wan_uses_external_audio_and_not_tts(self):
        case = read_cases(self.root, self.cases)[0]
        args, _, output = build_command("wan22_s2v", self.config, case, self.root / "run-wan")
        self.assertIn("--audio", args)
        self.assertNotIn("--enable_tts", args)
        self.assertEqual(output.suffix, ".mp4")

    def test_unpinned_source_blocked(self):
        with self.assertRaises(GateError):
            check_repo_revision(self.vendor, "NOT_A_SHA")

    def test_fake_git_directory_blocked(self):
        with self.assertRaises(GateError):
            check_repo_revision(self.vendor, "f" * 40)

    def test_gpu_sample_not_fabricated_without_utility(self):
        # On CPU CI this will be None; on GPU-backed runners it may be an integer.
        value = sample_gpu_used_mib()
        self.assertTrue(value is None or (type(value) is int and value >= 0))

    def test_empty_run_report_not_run(self):
        self.assertEqual(report(self.root / "nonexistent")["status"], "NOT_RUN")

    def test_empty_human_report_not_run(self):
        self.assertEqual(summarize_ratings(self.root / "nonexistent.jsonl")["status"], "NOT_RUN")

    def test_severe_artifact_is_hard_veto(self):
        records = [
            {"case_id": "case01", "model_id": "echo", "reviewer_id": "r01",
             "identity": 5, "motion": 5, "lip_sync": 5, "continuity": 5, "emotion": 5,
             "severe_artifact": True},
            {"case_id": "case02", "model_id": "echo", "reviewer_id": "r01",
             "identity": 4, "motion": 4, "lip_sync": 4, "continuity": 4, "emotion": 4,
             "severe_artifact": False},
        ]
        fn = self.root / "ratings.jsonl"
        fn.write_text("\n".join(json.dumps(x) for x in records))
        summary = summarize_ratings(fn)
        self.assertEqual(summary["accepted_ratings"], 1)
        self.assertEqual(summary["status"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(summary["severe_artifact_ratings"], 1)

    def test_no_ffprobe_output_is_not_success(self):
        with self.assertRaises(GateError):
            probe_video(self.root / "not-generated.mp4")

    def test_cli_validate_has_no_external_dependencies(self):
        self.assertEqual(main(["validate", "--private-root", str(self.root),
                               "--cases", str(self.cases)]), 0)

    def test_wilson_and_zero_sample(self):
        self.assertIsNone(wilson(0, 0))
        low, high = wilson(9, 10)
        self.assertTrue(0 < low < high < 1)


if __name__ == "__main__":
    unittest.main()
