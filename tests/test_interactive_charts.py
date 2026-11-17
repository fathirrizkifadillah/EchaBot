import unittest
import pandas as pd
import numpy as np

from src import tools


class InteractiveChartTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            "category": ["A", "B", "A", "B", "C"],
            "sales": [100.0, 200.0, 150.0, 250.0, 300.0],
            "profit": [20.0, 45.0, 30.0, 60.0, 70.0],
            "age": [25, 30, 35, 40, 45],
        })

    def test_plot_custom_returns_structured_chart_data(self):
        """plot_custom should return a chart config with records for Recharts alongside image."""
        res = tools.plot_custom(self.df, kind="bar", x="category", y="sales", agg="sum")
        self.assertIn("chart", res)
        self.assertIn("image", res)
        chart = res["chart"]
        self.assertEqual(chart["type"], "bar")
        self.assertEqual(chart["xKey"], "name")
        self.assertEqual(chart["yKey"], "value")
        self.assertIsInstance(chart["data"], list)
        self.assertGreater(len(chart["data"]), 0)

    def test_scatter_plot_returns_structured_chart_data(self):
        """plot_custom with kind=scatter returns x/y coordinate data for Recharts."""
        res = tools.plot_custom(self.df, kind="scatter", x="sales", y="profit")
        self.assertIn("chart", res)
        chart = res["chart"]
        self.assertEqual(chart["type"], "scatter")
        self.assertEqual(chart["xKey"], "x")
        self.assertEqual(chart["yKey"], "y")
        self.assertIsInstance(chart["data"], list)
        self.assertEqual(len(chart["data"]), 5)

    def test_histogram_column_returns_binned_chart_data(self):
        """histogram_column returns bin names and counts for interactive Recharts bar chart."""
        res = tools.histogram_column(self.df, "sales")
        self.assertIn("chart", res)
        chart = res["chart"]
        self.assertEqual(chart["type"], "bar")
        self.assertIsInstance(chart["data"], list)
        self.assertGreater(len(chart["data"]), 0)
        self.assertIn("count", chart["data"][0])
