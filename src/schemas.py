"""Pydantic schemas for LLM intent routing and tool execution.

Provides schema validation at the boundary between model output and application logic.
Enforces literal action types and parameter typing to eliminate hallucinated actions or malformed payloads.
"""

import json
import logging
import re
from typing import Any, Dict, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

ActionType = Literal[
    "summary",
    "preprocessing",
    "correlation_heatmap",
    "model_evaluation",
    "code_execution",
    "plot_custom",
    "histogram_column",
    "boxplot_column",
    "columns",
    "preview",
    "describe",
    "data_quality",
]


class PlotCustomParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: Literal["line", "bar", "scatter"] = "line"
    x: Optional[str] = None
    y: Optional[str] = None
    agg: Literal["sum", "mean", "median"] = "sum"

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.lower().strip()
            if clean in ("line", "bar", "scatter"):
                return clean
        return "line"

    @field_validator("agg", mode="before")
    @classmethod
    def normalize_agg(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.lower().strip()
            if clean in ("sum", "mean", "median"):
                return clean
        return "sum"


class ColumnParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    column: str


class ModelEvaluationParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    target_col: Optional[str] = None


class CodeExecutionParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str


class PreviewParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    limit: Optional[int] = Field(default=5, ge=1, le=100)


class IntentPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: ActionType
    params: Optional[Dict[str, Any]] = None

    def normalized(self) -> Union[dict, str]:
        """Convert validated model into either a string (for simple actions) or dict with validated params."""
        if not self.params:
            return self.action

        # Validate params based on specific action type
        if self.action == "plot_custom":
            p = PlotCustomParams(**self.params).model_dump(exclude_none=True)
            return {"action": self.action, "params": p}
        elif self.action in ("histogram_column", "boxplot_column"):
            p = ColumnParams(**self.params).model_dump(exclude_none=True)
            return {"action": self.action, "params": p}
        elif self.action == "model_evaluation":
            p = ModelEvaluationParams(**self.params).model_dump(exclude_none=True)
            return {"action": self.action, "params": p}
        elif self.action == "code_execution":
            p = CodeExecutionParams(**self.params).model_dump(exclude_none=True)
            return {"action": self.action, "params": p}
        elif self.action == "preview":
            p = PreviewParams(**self.params).model_dump(exclude_none=True)
            return {"action": self.action, "params": p}

        return {"action": self.action, "params": self.params}


def extract_json_candidate(text: str) -> Optional[dict]:
    """Extract and parse candidate JSON from arbitrary text (handles code fences and conversational preamble)."""
    if not text or not isinstance(text, str):
        return None

    cleaned = text.strip()
    if "<think>" in cleaned:
        cleaned = cleaned.split("</think>")[-1].strip()

    # If wrapped in markdown code fence ```json ... ```
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except Exception:
            pass

    # Look for the outermost JSON object bounds
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate_str = cleaned[start_idx : end_idx + 1]
        try:
            return json.loads(candidate_str)
        except Exception:
            pass

    try:
        return json.loads(cleaned)
    except Exception:
        return None


def validate_action_payload(data: Any) -> Optional[Union[dict, str]]:
    """Validate raw parsed dictionary against IntentPayload schema."""
    if not isinstance(data, dict):
        return None

    try:
        payload = IntentPayload.model_validate(data)
        return payload.normalized()
    except ValidationError as exc:
        logger.debug("Intent schema validation failed: %s", exc)
        return None
    except Exception as exc:
        logger.debug("Unexpected validation error: %s", exc)
        return None
