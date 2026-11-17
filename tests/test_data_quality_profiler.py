import unittest
import pandas as pd
import numpy as np

from api import create_app
from src import tools
from src.router import route_intent


class DataQualityProfilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)

    def setUp(self):
        # Create a test dataset with known data quality issues:
        # - Column 'val': 1 missing, 1 extreme outlier (1000)
        # - Column 'cat': normal categories
        # - 1 duplicate row
        self.df = pd.DataFrame({
            "id": [1, 2, 3, 4, 4],
            "val": [10.0, 12.0, np.nan, 14.0, 14.0],
            "cat": ["A", "B", "A", "B", "B"],
        })
        # Add an extreme outlier row
        self.df_with_outlier = pd.DataFrame({
            "salary": [3000, 3200, 3100, 3050, 3150, 3300, 3000, 3250, 3100, 150000],
            "dept": ["IT", "IT", "HR", "HR", "IT", "HR", "IT", "HR", "IT", "EXEC"],
        })

    def test_data_quality_audit_structure(self):
        """Audit should return structured summary table and detailed per-column rows."""
        result = tools.data_quality_audit(self.df)
        self.assertIn("message", result)
        self.assertIn("table", result)
        self.assertIn("rows", result)
        self.assertEqual(len(result["rows"]), 3)  # id, val, cat

        # Check completeness and health score in table
        table_keys = list(result["table"].keys())
        self.assertTrue(any("kesehatan" in k.lower() or "health" in k.lower() for k in table_keys))
        self.assertTrue(any("kelengkapan" in k.lower() or "completeness" in k.lower() for k in table_keys))

    def test_outlier_and_skewness_detection(self):
        """Audit should detect numeric outliers via IQR and calculate skewness."""
        result = tools.data_quality_audit(self.df_with_outlier)
        rows_by_col = {r["column"]: r for r in result["rows"]}
        
        salary_profile = rows_by_col["salary"]
        self.assertGreater(salary_profile["outlier_count_iqr"], 0)
        self.assertNotEqual(salary_profile["skewness"], "-")

    def test_router_detects_data_quality_intent(self):
        """Router should recognize data quality and audit keywords."""
        phrases = [
            "cek kualitas data",
            "audit data",
            "data quality",
            "cek outlier dan missing value",
            "bagaimana kualitas dataset ini?",
            "cek kesehatan data",
        ]
        for p in phrases:
            action = route_intent(p)
            self.assertEqual(action, "data_quality", f"Failed for phrase: '{p}'")

    def test_chat_endpoint_answers_data_quality(self):
        """End-to-end test verifying chat endpoint executes data_quality action."""
        with self.app.test_client() as client:
            csrf_res = client.get("/api/csrf")
            token = csrf_res.get_json()["csrf_token"]

            # Load sample dataset
            client.post("/use-sample", headers={"X-CSRF-Token": token})

            # Ask for data quality
            res = client.post(
                "/chat",
                headers={"X-CSRF-Token": token},
                json={"message": "cek kualitas dataset"},
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertIn("message", data)
            self.assertIn("table", data)
            self.assertIn("rows", data)
