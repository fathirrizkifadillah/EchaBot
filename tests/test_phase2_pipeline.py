import io
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src.llm import generate_chat_title, get_intent
from src.loader import load_data
from src.tools import model_evaluation


class Phase2PipelineTests(unittest.TestCase):
    def test_llm_groq_active_models_and_title_fallback(self):
        """Test that Groq models use active 2024/2026 models and title generation has robust fallback."""
        with patch.dict("os.environ", {"GROQ_API_KEY": "dummy_key", "GROQ_MODEL": ""}):
            with patch("groq.Groq") as mock_groq_cls:
                mock_client = MagicMock()
                mock_groq_cls.return_value = mock_client
                mock_choice = MagicMock()
                mock_choice.message.content = "Analisis Penjualan Toko"
                mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

                # 1. Title generation should use active fast model llama-3.1-8b-instant by default
                title = generate_chat_title("Tolong analisis data penjualan toko tahun 2023")
                self.assertEqual(title, "Analisis Penjualan Toko")
                call_args = mock_client.chat.completions.create.call_args[1]
                self.assertEqual(call_args["model"], "llama-3.1-8b-instant")

                # 2. Intent detection should use active model llama-3.3-70b-versatile by default
                mock_choice.message.content = '{"action":"summary"}'
                get_intent("ringkas data")
                call_args = mock_client.chat.completions.create.call_args[1]
                self.assertEqual(call_args["model"], "llama-3.3-70b-versatile")

        # 3. Fallback when LLM call throws exception
        with patch.dict("os.environ", {"GROQ_API_KEY": "dummy_key"}):
            with patch("groq.Groq", side_effect=RuntimeError("Groq API unreachable")):
                title_fallback = generate_chat_title("Analisis penjualan bulanan toko cabang Jakarta")
                self.assertTrue(len(title_fallback) > 0)
                self.assertIn("Analisis penjualan", title_fallback)

    def test_auto_ml_handles_nan_in_features(self):
        """Auto-ML should handle NaN in both numeric and categorical features without raising ValueError."""
        np.random.seed(42)
        n = 40
        df = pd.DataFrame({
            "age": [25.0, np.nan, 30.0, 45.0, np.nan, 35.0, 28.0, 50.0] * 5,
            "income": [5000.0, 6000.0, np.nan, 8000.0, 5500.0, np.nan, 7200.0, 9000.0] * 5,
            "category": ["A", "B", np.nan, "A", "C", "B", np.nan, "C"] * 5,
            "target_num": [100.0 + i * 2 for i in range(n)],
            "target_cat": (["Yes", "No"] * (n // 2))
        })

        # Test regression with NaNs in features
        reg_result = model_evaluation(df, target_col="target_num")
        self.assertIn("rows", reg_result)
        for model_res in reg_result["rows"]:
            self.assertNotIn("Error:", model_res.get("Status", ""), f"Model failed on numeric NaNs: {model_res}")
            self.assertIn("MAE", model_res)

        # Test classification with NaNs in features
        clf_result = model_evaluation(df, target_col="target_cat")
        self.assertIn("rows", clf_result)
        for model_res in clf_result["rows"]:
            self.assertNotIn("Error:", model_res.get("Status", ""), f"Model failed on categorical NaNs: {model_res}")
            self.assertIn("Accuracy", model_res)

    def test_auto_ml_temporal_leakage_prevention(self):
        """When a date/time column is detected, split chronologically so no train row is newer than test rows."""
        n = 50
        dates = pd.date_range("2023-01-01", periods=n, freq="D")
        df = pd.DataFrame({
            "tanggal": dates,
            "feature_x": np.linspace(10, 50, n),
            "weekly_sales": np.sin(np.linspace(0, 10, n)) * 100 + 500
        })

        # Shuffle input to ensure ordering is tested properly
        df_shuffled = df.sample(frac=1.0, random_state=42).reset_index(drop=True)

        res = model_evaluation(df_shuffled, target_col="weekly_sales")
        self.assertIn("rows", res)
        # Result should indicate chronological temporal split was used
        self.assertTrue(
            res.get("temporal_split", False) or "kronologis" in res.get("message", "").lower() or "kronologis" in res.get("warning", "").lower(),
            "Result should indicate chronological temporal split"
        )
        self.assertIn("warning", res)
        self.assertIn("kronologis", res["warning"].lower())
        # Check that no train row is newer than test rows
        split_info = res.get("split_info", {})
        if "train_max_date" in split_info and "test_min_date" in split_info:
            self.assertLessEqual(split_info["train_max_date"], split_info["test_min_date"])

    def test_loader_delimiter_and_cp1252_encoding(self):
        """Loader should auto-detect semicolon delimiter and cp1252/latin-1 encoding."""
        # CSV with semicolon delimiter and Windows-1252 characters
        csv_text = "produk;wilayah;penjualan\nKafe Münster;Jakarta;150000\nCrème Brûlée;Bandung;250000\n"
        encoded_bytes = csv_text.encode("cp1252")

        file_obj = io.BytesIO(encoded_bytes)
        file_obj.name = "data_penjualan.csv"

        df, report = load_data(file_obj)
        self.assertEqual(len(df.columns), 3)
        self.assertListEqual(list(df.columns), ["produk", "wilayah", "penjualan"])
        self.assertEqual(len(df), 2)
        self.assertIn("Münster", df["produk"].iloc[0])

    def test_loader_handles_corrupt_content_gracefully(self):
        """Corrupt or invalid files should raise ValueError with informative message."""
        bad_bytes = b"\x00\x01\x02\x03\x04\xff\xfe\x00"
        file_obj = io.BytesIO(bad_bytes)
        file_obj.name = "corrupt.csv"

        with self.assertRaises(ValueError) as ctx:
            load_data(file_obj)
        self.assertTrue(len(str(ctx.exception)) > 0)
