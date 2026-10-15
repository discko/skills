import base64
import concurrent.futures
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/html-plan/scripts"
sys.path.insert(0, str(SCRIPTS))
import core
import host
import plan
spec = importlib.util.spec_from_file_location("plan_setup", SCRIPTS / "setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="html plan 中文 ")
        self.root = Path(self.temp.name)
        self.path = self.root / "有 空格 # %.html"
        self.spec = json.loads((ROOT / "skills/html-plan/assets/example.json").read_text(encoding="utf-8"))
        plan.build(self.spec, self.path)
        self.original = self.path.read_bytes()
        self.state = core.parse_document(self.original)[0]

    def tearDown(self):
        self.temp.cleanup()

    def message(self, **extra):
        result = {"protocol": core.PROTOCOL, "action": "save", "requestId": "request-1", "fileUrl": self.path.as_uri(),
                  "planId": self.state["planId"], "documentId": self.state["documentId"],
                  "documentRevision": 1, "expectedReviewRevision": 0, "review": core.empty_review()}
        result.update(extra)
        return result

    def test_save_preserves_all_other_bytes_and_text(self):
        review = core.empty_review()
        review["comments"]["review-plan"] = '中文 </script><script>alert(1)</script>\n& \\ " 😊'
        result = core.handle_message(self.message(review=review))
        self.assertEqual(result["reviewRevision"], 1)
        saved = self.path.read_bytes()
        state, begin, end = core.parse_document(saved)
        _, old_begin, old_end = core.parse_document(self.original)
        self.assertEqual(saved[:begin], self.original[:old_begin])
        self.assertEqual(saved[end:], self.original[old_end:])
        self.assertEqual(state["review"], review)
        self.assertNotIn(b"<script>alert", saved)

    def test_conflict_and_idempotent_retry(self):
        message = self.message()
        core.handle_message(message)
        before = self.path.read_bytes()
        self.assertTrue(core.handle_message(message)["replayed"])
        self.assertEqual(before, self.path.read_bytes())
        with self.assertRaises(core.PlanError) as error:
            core.handle_message(self.message(requestId="second-tab"))
        self.assertEqual(error.exception.code, "REVISION_CONFLICT")
        self.assertEqual(self.path.read_bytes(), before)
        changed = self.message()
        changed["review"]["note"] = "different"
        with self.assertRaises(core.PlanError):
            core.handle_message(changed)

    def test_document_mismatch(self):
        with self.assertRaises(core.PlanError) as error:
            core.handle_message(self.message(documentId="different"))
        self.assertEqual(error.exception.code, "DOCUMENT_CHANGED")
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_two_processes_one_winner(self):
        def run(number):
            data = json.dumps(self.message(requestId=f"concurrent-{number}")).encode()
            output = subprocess.run([sys.executable, str(SCRIPTS / "host.py")], input=struct.pack("=I", len(data)) + data,
                                    capture_output=True, check=True).stdout
            return json.loads(output[4:])
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(sum(r["ok"] for r in results), 1)
        self.assertEqual([r["code"] for r in results if not r["ok"]], ["REVISION_CONFLICT"])
        self.assertEqual(core.parse_document(self.path.read_bytes())[0]["reviewRevision"], 1)

    def test_missing_duplicate_and_invalid_markers(self):
        for data in (self.original.replace(core.END, b""), self.original + core.BEGIN,
                     self.original.replace(b"<head>", b"<body>")):
            with self.subTest(data=data[:30]):
                with self.assertRaises(core.PlanError):
                    core.parse_document(data)

    def test_new_version_prefill_and_history(self):
        message = self.message()
        message["review"].update({"decisions": {"save-mode": "先下载副本", "removed-decision": "old"},
                                  "comments": {"review-plan": "请保留", "removed": "已删除条目的意见"},
                                  "seen": ["review-plan"], "struck": ["iterate-plan"]})
        core.handle_message(message)
        next_path = self.root / "v2.html"
        plan.build(self.spec, next_path, self.path)
        new = core.parse_document(next_path.read_bytes())[0]
        self.assertEqual(new["planId"], self.state["planId"])
        self.assertNotEqual(new["documentId"], self.state["documentId"])
        self.assertEqual(new["documentRevision"], 2)
        self.assertEqual(new["reviewRevision"], 0)
        self.assertEqual(new["review"]["seen"], [])
        self.assertEqual(new["review"]["decisions"], {"save-mode": "先下载副本"})
        self.assertEqual(new["review"]["comments"], {"review-plan": "请保留"})
        self.assertIn("removed", new["previousFeedback"][0]["review"]["comments"])

    def test_build_never_overwrites(self):
        with self.assertRaises(FileExistsError):
            plan.build(self.spec, self.path)
        self.assertEqual(self.path.read_bytes(), self.original)

    def feedback(self):
        return {"type": "html-plan-review", "schemaVersion": 1, "title": "标题",
                "planId": self.state["planId"], "documentId": self.state["documentId"],
                "documentRevision": 1, "baseReviewRevision": 0, "review": core.empty_review()}

    def test_clipboard_feedback_prefills_without_writing_original(self):
        payload = self.feedback()
        payload["review"]["comments"]["review-plan"] = '中文 </script>\n" 😊'
        payload["review"]["decisions"]["save-mode"] = "先下载副本"
        payload["review"]["seen"] = ["review-plan"]
        feedback = self.root / "feedback.json"
        feedback.write_text(json.dumps(payload), encoding="utf-8")
        next_path = self.root / "v2.html"
        subprocess.run([sys.executable, str(SCRIPTS / "plan.py"), "build", str(ROOT / "skills/html-plan/assets/example.json"),
                        str(next_path), "--previous", str(self.path), "--feedback", str(feedback)], check=True, capture_output=True)
        state = core.parse_document(next_path.read_bytes())[0]
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(state["review"]["comments"], payload["review"]["comments"])
        self.assertEqual(state["review"]["decisions"], payload["review"]["decisions"])
        self.assertEqual(state["review"]["seen"], [])
        self.assertEqual(state["previousFeedback"][-1]["feedbackSource"], "clipboard")
        self.assertEqual(state["reviewRevision"], 0)

    def test_clipboard_rejects_mismatched_or_invalid_feedback(self):
        feedback = self.root / "feedback.json"
        for changes in ({"type": "other"}, {"schemaVersion": True}, {"planId": "other"}, {"documentId": "other"},
                        {"documentRevision": True}, {"baseReviewRevision": 1}, {"baseReviewRevision": False}, {"review": {}}):
            with self.subTest(changes=changes):
                payload = self.feedback()
                payload.update(changes)
                feedback.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises((ValueError, core.PlanError)):
                    plan.build(self.spec, self.root / "invalid.html", self.path, feedback_path=feedback)
                self.assertFalse((self.root / "invalid.html").exists())
        with self.assertRaises(ValueError):
            plan.build(self.spec, self.root / "invalid.html", feedback_path=feedback)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_source_excerpt_and_fence(self):
        source = self.root / "sample.py"
        source.write_text("a = 1\nb = 2\n", encoding="utf-8")
        exhibit = self.spec["claims"][0]["children"][0]["exhibits"][0]
        exhibit["source"] = {"file": "sample.py", "start": 2, "end": 2}
        self.assertIn("b = 2", plan.render(self.spec, root=self.root))
        exhibit["source"]["file"] = str(ROOT / "README.md")
        with self.assertRaises(ValueError):
            plan.render(self.spec, root=self.root)

    def test_validation_and_path(self):
        for url in ("https://example.com/plan.html", "file://server/share/plan.html"):
            with self.assertRaises(core.PlanError):
                core.path_from_url(url)
        for value in ([], None, {"note": "x"}):
            with self.assertRaises(core.PlanError):
                core.validate_review(value)
        with self.assertRaises(core.PlanError):
            core.handle_message(self.message(expectedReviewRevision=True))

    def test_native_protocol(self):
        data = json.dumps(self.message(), ensure_ascii=False).encode()
        class ShortReads(io.BytesIO):
            def read(self, n=-1):
                return super().read(min(n, 3))
        output = io.BytesIO()
        host.serve(ShortReads(struct.pack("=I", len(data)) + data), output)
        result = output.getvalue()
        self.assertEqual(struct.unpack("=I", result[:4])[0], len(result[4:]))
        self.assertTrue(json.loads(result[4:])["ok"])
        for data in (b"", b"\x00", struct.pack("=I", core.MAX_MESSAGE + 1), struct.pack("=I", 2) + b"{"):
            output = io.BytesIO()
            host.serve(io.BytesIO(data), output)
            self.assertFalse(json.loads(output.getvalue()[4:])["ok"])

    def test_wrong_origin(self):
        output = io.BytesIO()
        host.serve(io.BytesIO(), output, "chrome-extension://other/")
        self.assertEqual(json.loads(output.getvalue()[4:])["code"], "INVALID_ORIGIN")

    def test_atomic_write_failure_retains_original(self):
        from unittest.mock import patch
        with patch("core.os.replace", side_effect=PermissionError("busy")):
            with self.assertRaises(PermissionError):
                core.handle_message(self.message())
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_typed_feedback_roundtrip_migration_and_clipboard(self):
        mixed = json.loads((ROOT / "skills/html-plan/assets/mixed-review.json").read_text(encoding="utf-8"))
        self.path = self.root / "mixed.html"
        plan.build(mixed, self.path)
        self.state = core.parse_document(self.path.read_bytes())[0]
        review = core.empty_review()
        review["decisions"] = {"notify-ready": False, "export-fields": ["编号", "更新时间"], "delivery-mode": "同步下载",
                               "search-project": "中文 </script> &", "search-tags": []}
        review["comments"] = {"search-caller": "核对后调整"}
        before = self.path.read_bytes()
        data = json.dumps(self.message(review=review), ensure_ascii=False).encode()
        output = io.BytesIO()
        host.serve(io.BytesIO(struct.pack("=I", len(data)) + data), output)
        self.assertTrue(json.loads(output.getvalue()[4:])["ok"])
        saved, start, end = core.parse_document(self.path.read_bytes())
        self.assertEqual(saved["review"], review)
        _, old_start, old_end = core.parse_document(before)
        self.assertEqual(self.path.read_bytes()[:start], before[:old_start])
        self.assertEqual(self.path.read_bytes()[end:], before[old_end:])
        migrated = plan.new_state(mixed, saved)
        self.assertEqual(migrated["review"]["decisions"], review["decisions"])
        self.assertEqual(migrated["review"]["comments"], review["comments"])
        mixed["claims"][0]["decisions"][2]["options"] = ["名称", "编号"]
        migrated = plan.new_state(mixed, saved)
        self.assertNotIn("export-fields", migrated["review"]["decisions"])
        self.assertEqual(migrated["previousFeedback"][-1]["review"]["decisions"]["export-fields"], ["编号", "更新时间"])
        payload = self.feedback()
        payload.update(baseReviewRevision=1, review=review)
        path = self.root / "typed-feedback.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        imported = plan.apply_feedback(saved, path)
        self.assertEqual(imported["review"], review)
        self.assertEqual(imported["feedbackSource"], "clipboard")

    def test_typed_validation_rejects_ambiguous_values(self):
        for value in (None, 1, {"x": "y"}, [True], [["nested"]], ["same", "same"]):
            review = core.empty_review()
            review["decisions"]["field"] = value
            with self.subTest(value=value), self.assertRaises(core.PlanError):
                core.validate_review(review)
        for field in ("comments", "edits"):
            review = core.empty_review()
            review[field]["item"] = False
            with self.assertRaises(core.PlanError):
                core.validate_review(review)
        self.assertIn("typed-decisions", core.handle_message({"protocol": core.PROTOCOL, "action": "ping"})["capabilities"])

    def test_layout_and_control_semantics(self):
        from html.parser import HTMLParser
        class Elements(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags = []
            def handle_starttag(self, tag, attrs):
                self.tags.append((tag, dict(attrs)))
        mixed = json.loads((ROOT / "skills/html-plan/assets/mixed-review.json").read_text(encoding="utf-8"))
        # Deliberately reverse defaults; emitted state and input order must agree.
        mixed["claims"][0]["decisions"][2]["default"] = ["编号", "名称"]
        rendered = plan.render(mixed)
        state = core.parse_document(rendered.encode())[0]
        self.assertEqual(state["decisionDefaults"]["export-fields"], ["名称", "编号"])
        parser = Elements()
        parser.feed(rendered)
        claims = {attrs["data-claim"]: (tag, attrs) for tag, attrs in parser.tags if "data-claim" in attrs}
        self.assertEqual(claims["delivery"][0], "section")
        self.assertEqual(claims["delivery-details"][0], "details")
        self.assertNotIn("open", claims["delivery-details"][1])
        self.assertEqual(claims["search-caller"][0], "tr")
        controls = {attrs["data-decision"]: (tag, attrs) for tag, attrs in parser.tags if "data-decision" in attrs}
        self.assertEqual(len(controls), len(plan.validate_spec(mixed)[1]))
        self.assertEqual(controls["delivery-mode"][0], "fieldset")
        self.assertEqual(controls["notify-ready"][1]["type"], "checkbox")
        self.assertEqual(controls["export-fields"][0], "fieldset")
        comments = [attrs["data-comment"] for _, attrs in parser.tags if "data-comment" in attrs]
        self.assertIn("search-caller", comments)
        self.assertNotIn("project-mapping", comments)

    def test_table_and_defaults_validation(self):
        import copy
        mixed = json.loads((ROOT / "skills/html-plan/assets/mixed-review.json").read_text(encoding="utf-8"))
        for mutate in (
            lambda spec: spec.update(layout="unknown"),
            lambda spec: spec["claims"][0]["decisions"][1].update(default="false"),
            lambda spec: spec["claims"][0]["decisions"][2].update(default=["missing"]),
            lambda spec: spec["claims"][1]["table"]["rows"][0].update(id="delivery"),
            lambda spec: spec["claims"][1]["table"]["rows"][0]["cells"].update(unknown="x"),
            lambda spec: spec["claims"][1]["table"]["columns"].append({"key": "status", "label": "duplicate"}),
        ):
            candidate = copy.deepcopy(mixed)
            mutate(candidate)
            with self.assertRaises(ValueError):
                plan.validate_spec(candidate)


class SetupTests(unittest.TestCase):
    def test_install_doctor_update_uninstall(self):
        with tempfile.TemporaryDirectory(prefix="html plan 中文 ") as temp:
            root = Path(temp) / "runtime"
            manifest = Path(temp) / "registration" / (core.HOST_NAME + ".json")
            system = "Windows" if os.name == "nt" else "Darwin"
            result = setup.install(root, manifest, system, register=False)
            self.assertTrue(result["ok"])
            before = (root / "connection-test.html").read_bytes()
            setup.install(root, manifest, system, register=False)
            self.assertEqual(before, (root / "connection-test.html").read_bytes())
            checks = setup.doctor(root, manifest, system, check_registry=False)
            self.assertTrue(checks["ok"], checks)
            self.assertFalse(checks["browserVerified"])
            setup.uninstall(root, manifest, system, register=False)
            self.assertFalse(manifest.exists())
            self.assertTrue((root / "connection-test.html").exists())

    def test_identity_and_launchers(self):
        self.assertEqual(setup.extension_id(), core.EXTENSION_ID)
        shell = setup.launcher_text("Darwin", "/a b/python", "/c d/host.py")
        self.assertIn("exec '/a b/python' '/c d/host.py'", shell)
        batch = setup.launcher_text("Windows", "C:\\a%foo%!\\python.exe", "C:\\空 格\\host.py")
        self.assertIn("a%%foo%%!", batch)
        self.assertIn("DisableDelayedExpansion", batch)


if __name__ == "__main__":
    unittest.main()
