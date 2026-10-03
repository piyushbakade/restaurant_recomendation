"""
Contract Validator and Content Sanitizer for Phase 7 Output Layer.
Ensures strict compliance with JSON schemas, business rules, and security guidelines.
"""
import html
import json
import re
from typing import Any, Dict, List, Optional, Set
from pydantic import ValidationError

from phase_7.contracts import (
    StandardErrorResponse,
    StandardSuccessResponse,
)


class ValidationReport:
    """Holds the outcome of contract validation with errors and warnings."""

    def __init__(self, is_valid: bool, errors: Optional[List[str]] = None, warnings: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []

    def __repr__(self) -> str:
        status = "PASSED" if self.is_valid else "FAILED"
        return f"<ValidationReport status={status} errors={len(self.errors)} warnings={len(self.warnings)}>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ContractValidator:
    """
    Validates recommendation output payloads against the standardized Phase 7 contract.
    """

    PLACEHOLDER_PATTERNS = [
        re.compile(r"\{\{.*?\}\}"),
        re.compile(r"\[TODO\]", re.IGNORECASE),
        re.compile(r"lorem ipsum", re.IGNORECASE),
        re.compile(r"^undefined$", re.IGNORECASE),
        re.compile(r"^null$", re.IGNORECASE),
    ]

    @classmethod
    def sanitize_text(cls, text: Optional[str]) -> str:
        """
        Strips dangerous HTML control characters, zero-width spaces, and normalizes whitespace.
        """
        if not text:
            return ""
        # Remove zero-width spaces and non-printable control characters
        cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\u200B-\u200D\uFEFF]", "", str(text))
        # Strip excessive multi-space/tab whitespace
        cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
        # Entity-encode potential HTML injection
        return html.escape(cleaned, quote=False)

    @classmethod
    def validate_success_response(cls, data: Dict[str, Any]) -> ValidationReport:
        """
        Validates a success response payload against the Pydantic schema and domain rules.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Pydantic structural validation
        try:
            model = StandardSuccessResponse.model_validate(data)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"])
                errors.append(f"Schema violation at '{loc}': {err['msg']}")
            return ValidationReport(is_valid=False, errors=errors, warnings=warnings)

        # 2. Domain Rule: Status check
        if model.status != "success":
            errors.append(f"Expected status 'success', got '{model.status}'")

        # 3. Domain Rule: Duplicate restaurant IDs
        seen_ids: Set[str] = set()
        seen_names: Set[str] = set()
        for idx, rec in enumerate(model.recommendations):
            r_id = rec.restaurant_id.strip()
            r_name = rec.name.strip().lower()

            if r_id in seen_ids:
                errors.append(f"Duplicate restaurant_id '{r_id}' at recommendation index {idx}")
            seen_ids.add(r_id)

            if r_name in seen_names:
                warnings.append(f"Possible duplicate venue name '{rec.name}' at recommendation index {idx}")
            seen_names.add(r_name)

            # Check for placeholder text in recommendation_reason
            for pattern in cls.PLACEHOLDER_PATTERNS:
                if pattern.search(rec.recommendation_reason):
                    errors.append(
                        f"Recommendation reason for '{rec.name}' contains placeholder artifact: {pattern.pattern}"
                    )

            # Sanity check on pricing and ratings
            if rec.price_for_two <= 0:
                errors.append(f"Restaurant '{rec.name}' has non-positive price_for_two: {rec.price_for_two}")
            if rec.rating is not None and not (1.0 <= rec.rating <= 5.0):
                errors.append(f"Restaurant '{rec.name}' has rating out of range [1.0, 5.0]: {rec.rating}")

            # Check popular dishes cleanliness
            if not rec.popular_dishes:
                warnings.append(f"Restaurant '{rec.name}' has no popular dishes listed")

        # 4. Total candidate count sanity
        if model.total_candidates_found < len(model.recommendations):
            warnings.append(
                f"total_candidates_found ({model.total_candidates_found}) is less than recommendation count ({len(model.recommendations)})"
            )

        # 5. Latency telemetry sanity
        if model.meta.execution_time_ms < 0:
            errors.append(f"Negative execution_time_ms: {model.meta.execution_time_ms}")
        elif model.meta.execution_time_ms > 15000:
            warnings.append(f"Unusually high execution_time_ms: {model.meta.execution_time_ms} ms")

        is_valid = len(errors) == 0
        return ValidationReport(is_valid=is_valid, errors=errors, warnings=warnings)

    @classmethod
    def validate_error_response(cls, data: Dict[str, Any]) -> ValidationReport:
        """
        Validates an error response payload against StandardErrorResponse schema.
        """
        errors: List[str] = []
        warnings: List[str] = []

        try:
            model = StandardErrorResponse.model_validate(data)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"])
                errors.append(f"Error schema violation at '{loc}': {err['msg']}")
            return ValidationReport(is_valid=False, errors=errors, warnings=warnings)

        if model.status != "error":
            errors.append(f"Expected status 'error', got '{model.status}'")

        if not model.error_code or not model.error_code.strip():
            errors.append("error_code must be a non-empty string")

        if not model.message or not model.message.strip():
            errors.append("message must be a non-empty string")

        is_valid = len(errors) == 0
        return ValidationReport(is_valid=is_valid, errors=errors, warnings=warnings)

    @classmethod
    def validate_json_string(cls, json_str: str) -> ValidationReport:
        """Parses and validates a raw JSON string."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return ValidationReport(is_valid=False, errors=[f"Invalid JSON syntax: {e.msg} at line {e.lineno}"])

        if not isinstance(data, dict):
            return ValidationReport(is_valid=False, errors=["JSON root must be an object/dict"])

        status = data.get("status")
        if status == "error":
            return cls.validate_error_response(data)
        else:
            return cls.validate_success_response(data)
