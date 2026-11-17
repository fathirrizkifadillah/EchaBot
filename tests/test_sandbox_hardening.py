import os
import unittest
from pathlib import Path
import pandas as pd

from src.code_executor import execute_code, get_sandboxed_env, validate_code


class SandboxHardeningTests(unittest.TestCase):
    def setUp(self):
        self.sample_df = pd.DataFrame({
            "a": [1, 2, 3],
            "b": [10.0, 20.0, 30.0],
        })

    def test_sandboxed_env_strips_application_secrets(self):
        """Ensure no secrets from parent process leak into subprocess environment."""
        os.environ["GROQ_API_KEY"] = "super_secret_groq_key"
        os.environ["DATABASE_URL"] = "postgres://admin:secretpass@localhost:5432/db"
        os.environ["SECRET_KEY"] = "super_secret_session_key"

        clean_env = get_sandboxed_env()

        self.assertNotIn("GROQ_API_KEY", clean_env)
        self.assertNotIn("DATABASE_URL", clean_env)
        self.assertNotIn("SECRET_KEY", clean_env)
        # Standard system variables should be preserved so Python can run
        self.assertTrue("PATH" in clean_env or "Path" in clean_env)

    def test_code_length_limit(self):
        """Code exceeding 10,000 chars should be rejected immediately."""
        huge_code = "# comment\n" * 1500
        res = execute_code(huge_code, self.sample_df)
        self.assertFalse(res["ok"])
        self.assertIn("terlalu panjang", res["message"].lower())

    def test_blocks_dunder_string_constants(self):
        """String literals containing dunder attributes must be rejected by AST."""
        tricky_code = 's = "__class__"'
        res = execute_code(tricky_code, self.sample_df)
        self.assertFalse(res["ok"])
        self.assertTrue(any(k in res["message"].lower() for k in ["ditolak", "tidak diperbolehkan"]))

    def test_blocks_dangerous_functions_and_modules(self):
        """Direct or indirect references to forbidden modules are blocked."""
        bad_codes = [
            'result = __import__("os")',
            'result = eval("1+1")',
            'result = exec("x=1")',
            'result = open("/etc/passwd")',
        ]
        for c in bad_codes:
            res = execute_code(c, self.sample_df)
            self.assertFalse(res["ok"], f"Should have blocked: {c}")

    def test_safe_analytics_still_works(self):
        """Legitimate pandas operations still succeed with sanitized environment."""
        code = 'result = df["b"].mean()'
        res = execute_code(code, self.sample_df)
        self.assertTrue(res["ok"], res.get("message"))
        self.assertEqual(res["type"], "scalar")
        self.assertIn("20", res["message"])
