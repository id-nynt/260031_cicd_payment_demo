"""Console evidence tests using local child processes; no controller/deployment."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_controller import run_with_console_log


class ConsoleCaptureTests(unittest.TestCase):
    def test_failure_keeps_stdout_stderr_live_and_on_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'controller-console.log'
            display = io.StringIO()
            with contextlib.redirect_stdout(display):
                code = run_with_console_log(
                    [sys.executable, '-u', '-c',
                     "import sys; print('agent decision'); print('worker error', file=sys.stderr); sys.exit(7)"],
                    cwd=directory, env=os.environ.copy(), log_path=log)
            self.assertEqual(code, 7)
            saved = log.read_text(encoding='utf-8')
            self.assertEqual(saved, display.getvalue())
            self.assertIn('agent decision', saved)
            self.assertIn('worker error', saved)

    def test_invalid_output_byte_does_not_lose_later_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'controller-console.log'
            with contextlib.redirect_stdout(io.StringIO()):
                code = run_with_console_log(
                    [sys.executable, '-u', '-c',
                     "import sys; sys.stdout.buffer.write(b'bad byte: \\xff\\nfinal result\\n')"],
                    cwd=directory, env=os.environ.copy(), log_path=log)
            self.assertEqual(code, 0)
            self.assertIn('final result', log.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
