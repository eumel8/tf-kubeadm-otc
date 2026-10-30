"""Exercise the browser endpoints without a GPU or external network access."""

import importlib.util
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SPEC = importlib.util.spec_from_file_location(
    "ncm_webui", Path(__file__).resolve().parents[1] / "files/ncm-webui.py"
)
webui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(webui)


class WebUITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.results = Path(self.tmp.name)
        self.results_patch = patch.object(webui, "RESULTS", self.results)
        self.results_patch.start()
        self.addCleanup(self.results_patch.stop)
        self.server = webui.WebUI(("127.0.0.1", 0))
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def post(self, data, path="/run", **headers):
        return Request(self.base + path, data=data.encode(), headers=headers, method="POST")

    def post_no_redirect(self, path, data):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request("POST", path, data, {"Content-Type": "application/x-www-form-urlencoded"})
        response = conn.getresponse()
        status, location = response.status, response.getheader("Location")
        response.read()
        conn.close()
        return status, location

    def test_german_story_is_default(self):
        with urlopen(self.base + "/") as response:
            page = response.read().decode()
            self.assertIn('action="/geschichte"', page)
            self.assertIn("wildgewordene Roboter", page)
            self.assertIn('href="/ncm"', page)

        form = urlencode({"prompt": "Eine Geschichte über <Roboter> & Hunde", "tokens": 300,
                          "temperature": 0.8, "top_p": 0.9})

        class FakeProcess:
            def poll(self):
                return None

        with patch.object(webui.subprocess, "Popen", return_value=FakeProcess()) as popen:
            self.assertEqual(self.post_no_redirect("/geschichte", form), (303, "/"))
            command = popen.call_args.args[0]
            self.assertEqual(command[:5], ["flock", "-n", "/opt/ncm/ncm-tinystories.lock",
                                           webui.PYTHON, webui.GERMAN_SCRIPT])
            self.assertEqual(command[5], "Eine Geschichte über <Roboter> & Hunde")
            self.assertEqual(command[6:10], ["--max-new-tokens", "300", "--temperature", "0.8"])
            self.assertEqual(command[10:12], ["--top-p", "0.9"])
            self.assertEqual(command[12], "--output")
            self.assertEqual(Path(command[13]).parent, self.results)
            self.assertEqual(popen.call_args.kwargs["env"]["HF_HOME"], "/opt/ncm/cache")
            with self.assertRaises(HTTPError) as raised:
                urlopen(self.post("samples=4&batch=2"))
            self.assertEqual(raised.exception.code, 409)

            path = Path(command[13])
            path.write_text("<script>hallo</script> & Roboter", encoding="utf-8")
            with urlopen(self.base + "/?story=" + path.name) as response:
                page = response.read().decode()
                self.assertIn("&lt;script&gt;hallo&lt;/script&gt; &amp; Roboter", page)
                self.assertNotIn("<script>", page)

        class FinishedProcess:
            def poll(self):
                return 0

        self.server.process = FinishedProcess()
        with urlopen(self.base + "/") as response:
            page = response.read().decode()
            self.assertIn("Geschichte erfolgreich generiert.", page)
            self.assertIn("&lt;script&gt;hallo&lt;/script&gt; &amp; Roboter", page)

        class FailedProcess:
            def poll(self):
                return 1

        path.unlink()
        self.server.process = FailedProcess()
        self.server.process_log.write_text("Model download failed", encoding="utf-8")
        with urlopen(self.base + "/") as response:
            page = response.read().decode()
            self.assertIn("Generierung fehlgeschlagen (Exit-Code 1)", page)
            self.assertIn("Model download failed", page)
            self.assertIn("<details open>", page)

    def test_run_launch_and_existing_results(self):
        name = "20261030T120000-abcdef"
        run = self.results / name
        run.mkdir()
        (run / "stories.jsonl").write_text(json.dumps({"seed": 42, "text": "<script>alert(1)</script>"}) + "\n")
        (run / "evaluation.log").write_text("score 12.34\n")
        with urlopen(self.base + "/ncm?run=" + name) as response:
            page = response.read().decode()
            self.assertIn("&lt;script&gt;", page)
            self.assertNotIn("<script>", page)
            self.assertIn("score 12.34", page)

        class FakeProcess:
            def poll(self):
                return None

        with patch.object(webui.subprocess, "Popen", return_value=FakeProcess()) as popen:
            self.assertEqual(self.post_no_redirect("/run", "samples=3&batch=2"), (303, "/ncm"))
            self.assertEqual(popen.call_args.args[0], [webui.RUNNER])
            self.assertEqual(popen.call_args.kwargs["env"]["NCM_SAMPLES"], "3")
            self.assertEqual(popen.call_args.kwargs["env"]["NCM_BATCH_SIZE"], "2")
            with self.assertRaises(HTTPError) as raised:
                urlopen(self.post("samples=4&batch=2"))
            self.assertEqual(raised.exception.code, 409)

    def test_bad_requests(self):
        for data in ("samples=0&batch=1", "samples=1&batch=129", "samples=oops&batch=1"):
            with self.subTest(data=data), self.assertRaises(HTTPError) as raised:
                urlopen(self.post(data))
            self.assertEqual(raised.exception.code, 400)
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.post("samples=1&batch=1", Origin="http://other.example"))
        self.assertEqual(raised.exception.code, 400)
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.base + "/ncm?run=../../etc")
        self.assertEqual(raised.exception.code, 404)
        for data in (
            urlencode({"prompt": "  ", "tokens": 400, "temperature": 0.8, "top_p": 0.9}),
            urlencode({"prompt": "Roboter", "tokens": 0, "temperature": 0.8, "top_p": 0.9}),
            urlencode({"prompt": "Roboter", "tokens": 400, "temperature": "nan", "top_p": 0.9}),
            urlencode({"prompt": "Roboter", "tokens": 400, "temperature": 0.8, "top_p": 2}),
        ):
            with self.subTest(data=data), self.assertRaises(HTTPError) as raised:
                urlopen(self.post(data, path="/geschichte"))
            self.assertEqual(raised.exception.code, 400)
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.base + "/?story=../../etc/passwd")
        self.assertEqual(raised.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
