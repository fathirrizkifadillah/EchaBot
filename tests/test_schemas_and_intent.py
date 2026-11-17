import unittest
from src.llm import parse_intent
from src.schemas import IntentPayload, validate_action_payload


class SchemasAndIntentTests(unittest.TestCase):
    def test_parse_simple_action_string(self):
        """Simple action without params returns action name."""
        text = '{"action": "summary"}'
        result = parse_intent(text)
        self.assertEqual(result, "summary")

    def test_parse_action_with_valid_params(self):
        """Action with params returns dictionary containing validated params."""
        text = '{"action": "plot_custom", "params": {"kind": "bar", "x": "category", "y": "sales", "agg": "mean"}}'
        result = parse_intent(text)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["action"], "plot_custom")
        self.assertEqual(result["params"]["kind"], "bar")
        self.assertEqual(result["params"]["agg"], "mean")

    def test_parse_markdown_fenced_json(self):
        """Extracts JSON wrapped in markdown code fences and conversational preamble."""
        text = (
            "Tentu, ini hasil request kamu:\n"
            "```json\n"
            '{\n  "action": "histogram_column",\n  "params": {"column": "weekly_sales"}\n}\n'
            "```"
        )
        result = parse_intent(text)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["action"], "histogram_column")
        self.assertEqual(result["params"]["column"], "weekly_sales")

    def test_reject_hallucinated_action(self):
        """Actions not in the allowed schema must be rejected gracefully."""
        text = '{"action": "drop_database", "params": {"target": "all"}}'
        result = parse_intent(text)
        self.assertIsNone(result)

    def test_plain_text_conversation_returns_none(self):
        """Normal conversational text returns None so chat can stream text directly."""
        text = "Halo! Aku EchaBot. Upload dataset kamu dulu untuk mulai analisis ya."
        result = parse_intent(text)
        self.assertIsNone(result)

    def test_pydantic_schema_validation_direct(self):
        """Direct Pydantic schema validation for IntentPayload."""
        valid_payload = {"action": "describe"}
        validated = validate_action_payload(valid_payload)
        self.assertIsNotNone(validated)
        self.assertEqual(validated, "describe")
