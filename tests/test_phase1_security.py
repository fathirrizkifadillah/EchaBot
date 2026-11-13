import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from api import create_app
from src.code_executor import execute_code


class Phase1SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)

    def setUp(self):
        self.sample_df = pd.DataFrame({
            "store": [1, 1, 2, 2],
            "dept": [1, 2, 1, 2],
            "weekly_sales": [100.0, 200.0, 150.0, 250.0],
            "is_holiday": [False, True, False, False]
        })

    def test_sandbox_blocks_read_pickle(self):
        code = 'result = pd.read_pickle("malicious.pkl")'
        res = execute_code(code, self.sample_df)
        self.assertFalse(res["ok"])
        self.assertTrue(any(word in res["message"].lower() for word in ["ditolak", "tidak diperbolehkan", "error"]))

    def test_sandbox_blocks_read_csv_network(self):
        code = 'result = pd.read_csv("http://169.254.169.254/latest/meta-data/")'
        res = execute_code(code, self.sample_df)
        self.assertFalse(res["ok"])

    def test_sandbox_blocks_dunder_escape(self):
        code = 'result = ().__class__.__base__.__subclasses__()'
        res = execute_code(code, self.sample_df)
        self.assertFalse(res["ok"])

    def test_sandbox_blocks_getattr(self):
        code = 'result = getattr(df, "__class__")'
        res = execute_code(code, self.sample_df)
        self.assertFalse(res["ok"])

    def test_sandbox_blocks_to_pickle(self):
        code = 'df.to_pickle("test.pkl")'
        res = execute_code(code, self.sample_df)
        self.assertFalse(res["ok"])

    def test_sandbox_blocks_to_csv(self):
        code = 'df.to_csv("test.csv")'
        res = execute_code(code, self.sample_df)
        self.assertFalse(res["ok"])

    def test_sandbox_blocks_pd_eval(self):
        code = 'result = pd.eval("1 + 1")'
        res = execute_code(code, self.sample_df)
        self.assertFalse(res["ok"])

    def test_sandbox_allows_normal_analytics(self):
        code = 'result = df.groupby("store")["weekly_sales"].sum()'
        res = execute_code(code, self.sample_df)
        self.assertTrue(res["ok"], res.get("message"))
        self.assertIn(res["type"], ("series", "dataframe"))
        self.assertEqual(len(res["rows"]), 2)

    @patch("api.routes.chat.get_intent_stream")
    def test_chat_stream_buffers_json_action(self, mock_stream):
        """When LLM returns a JSON action, raw JSON tokens should not leak to the UI."""
        mock_stream.return_value = iter(['{"action":', ' "summary"}'])
        with self.app.test_client() as client:
            csrf_res = client.get("/api/csrf")
            token = csrf_res.get_json()["csrf_token"]
            
            # Load sample dataset first
            client.post("/use-sample", headers={"X-CSRF-Token": token})

            response = client.post(
                "/chat/stream",
                headers={"X-CSRF-Token": token},
                json={"message": "ringkasan dataset"},
            )
            self.assertEqual(response.status_code, 200)
            data_str = response.get_data(as_text=True)

            # Ensure raw JSON tokens were NOT emitted as event: token
            self.assertNotIn('event: token\ndata: {"text": "{\\"action\\":"}', data_str)
            # Ensure status event was emitted instead
            self.assertIn('event: status', data_str)
            # Ensure done event occurred
            self.assertIn('event: done', data_str)

    @patch("api.routes.chat.get_intent_stream")
    def test_chat_stream_allows_plain_text(self, mock_stream):
        """When LLM returns plain text conversation, it streams normally."""
        mock_stream.return_value = iter(["Halo, ", "ada ", "yang ", "bisa ", "dibantu?"])
        with self.app.test_client() as client:
            csrf_res = client.get("/api/csrf")
            token = csrf_res.get_json()["csrf_token"]
            response = client.post(
                "/chat/stream",
                headers={"X-CSRF-Token": token},
                json={"message": "hai"},
            )
            self.assertEqual(response.status_code, 200)
            data_str = response.get_data(as_text=True)
            self.assertIn('event: token', data_str)
            self.assertIn("Halo, ", data_str)
