"""
Response Formatter for Phase 7 Output Layer.
Transforms Phase 5 / pipeline objects into standardized JSON, Pretty JSON, and Markdown formats.
"""
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Union

from phase_5.models import Phase5Response
from phase_7.contracts import (
    MetaContract,
    QuerySummaryContract,
    RestaurantOutputContract,
    StandardErrorResponse,
    StandardSuccessResponse,
)
from phase_7.validator import ContractValidator


class ResponseFormatter:
    """
    Handles serialization and presentation formatting for the recommendation system output.
    """

    @classmethod
    def from_phase5_response(
        cls,
        phase5_resp: Union[Phase5Response, Dict[str, Any]],
        execution_time_ms: Optional[int] = None,
        provider_name: Optional[str] = None,
    ) -> StandardSuccessResponse:
        """
        Transforms a Phase 5 response into the standardized Phase 7 contract model.
        """
        if isinstance(phase5_resp, Phase5Response):
            data = phase5_resp.model_dump()
        else:
            data = dict(phase5_resp)

        query_raw = data.get("query_summary", {})
        query_summary = QuerySummaryContract(
            location=ContractValidator.sanitize_text(query_raw.get("location", "Bangalore")),
            cuisines=[ContractValidator.sanitize_text(c) for c in query_raw.get("cuisines", [])],
            max_budget=int(query_raw.get("max_budget", 1000)),
            min_rating=float(query_raw.get("min_rating", 3.8)),
            cluster=ContractValidator.sanitize_text(query_raw.get("cluster")) if query_raw.get("cluster") else None,
            vibe_or_notes=ContractValidator.sanitize_text(query_raw.get("vibe_or_notes")) if query_raw.get("vibe_or_notes") else None,
        )

        recommendations: List[RestaurantOutputContract] = []
        for rec in data.get("recommendations", []):
            if isinstance(rec, dict):
                r_dict = rec
            else:
                r_dict = rec.model_dump() if hasattr(rec, "model_dump") else rec.__dict__

            recommendations.append(
                RestaurantOutputContract(
                    restaurant_id=str(r_dict.get("restaurant_id", "")),
                    name=ContractValidator.sanitize_text(r_dict.get("name", "")),
                    location=ContractValidator.sanitize_text(r_dict.get("location", "")),
                    cuisines=[ContractValidator.sanitize_text(c) for c in r_dict.get("cuisines", [])],
                    price_for_two=int(r_dict.get("price_for_two", 0)),
                    rating=float(r_dict["rating"]) if r_dict.get("rating") is not None else None,
                    votes=int(r_dict.get("votes", 0)),
                    popular_dishes=[ContractValidator.sanitize_text(d) for d in r_dict.get("popular_dishes", [])],
                    recommendation_reason=ContractValidator.sanitize_text(r_dict.get("recommendation_reason", "")),
                    url=r_dict.get("url"),
                    match_rank=r_dict.get("match_rank"),
                    location_cluster=r_dict.get("location_cluster"),
                )
            )

        meta_raw = data.get("meta", {})
        latency = (
            execution_time_ms
            if execution_time_ms is not None
            else int(meta_raw.get("execution_time_ms", 100))
        )
        provider = provider_name or data.get("provider_used") or meta_raw.get("provider")

        meta = MetaContract(
            execution_time_ms=max(0, latency),
            timestamp=datetime.now(timezone.utc).isoformat(),
            provider=provider,
            engine_version="1.0.0",
        )

        return StandardSuccessResponse(
            status="success",
            query_summary=query_summary,
            total_candidates_found=int(data.get("total_candidates_found", len(recommendations))),
            recommendations=recommendations,
            was_relaxed=bool(data.get("was_relaxed", False)),
            relaxation_notes=[ContractValidator.sanitize_text(n) for n in data.get("relaxation_notes", [])],
            meta=meta,
        )

    @classmethod
    def format_error(
        cls,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        execution_time_ms: int = 0,
    ) -> StandardErrorResponse:
        """Constructs a standardized error contract response."""
        return StandardErrorResponse(
            status="error",
            error_code=ContractValidator.sanitize_text(error_code),
            message=ContractValidator.sanitize_text(message),
            details=details,
            meta=MetaContract(
                execution_time_ms=max(0, execution_time_ms),
                timestamp=datetime.now(timezone.utc).isoformat(),
            ),
        )

    @classmethod
    def to_json(
        cls,
        response: Union[StandardSuccessResponse, StandardErrorResponse, Dict[str, Any]],
        indent: Optional[int] = None,
    ) -> str:
        """Serializes response model or dict to standard JSON."""
        if hasattr(response, "model_dump"):
            data = response.model_dump()
        else:
            data = response
        return json.dumps(data, indent=indent, ensure_ascii=False)

    @classmethod
    def to_pretty_json(
        cls,
        response: Union[StandardSuccessResponse, StandardErrorResponse, Dict[str, Any]],
    ) -> str:
        """Serializes response to indented, human-readable JSON string."""
        return cls.to_json(response, indent=2)

    @classmethod
    def to_markdown(cls, response: StandardSuccessResponse) -> str:
        """
        Formats a StandardSuccessResponse into a rich GitHub-flavored Markdown report.
        """
        qs = response.query_summary
        cuisines_str = ", ".join(qs.cuisines) if qs.cuisines else "Any"
        rating_str = f"{qs.min_rating}+ ★"

        lines = [
            f"# 🍽️ GourmetAI Recommendation Report - {qs.location}",
            "",
            "### 🔍 Search Criteria",
            f"- **Location**: `{qs.location}` ({qs.cluster or 'Metro Cluster'})",
            f"- **Cuisines**: {cuisines_str}",
            f"- **Max Budget for Two**: ₹{qs.max_budget:,}",
            f"- **Minimum Rating**: {rating_str}",
        ]

        if qs.vibe_or_notes:
            lines.append(f"- **Occasion / Notes**: *\"{qs.vibe_or_notes}\"*")

        if response.was_relaxed and response.relaxation_notes:
            lines.extend([
                "",
                "> [!NOTE]",
                "> **Relaxation Notice**: " + "; ".join(response.relaxation_notes),
            ])

        lines.extend([
            "",
            f"### 🏆 Top Curated Matches ({len(response.recommendations)} of {response.total_candidates_found} candidates)",
            "",
        ])

        for rec in response.recommendations:
            rank_str = f"#{rec.match_rank} " if rec.match_rank else ""
            rating_display = f"★ {rec.rating:.1f}" if rec.rating is not None else "★ New"
            cuisines_joined = ", ".join(rec.cuisines) if rec.cuisines else "Multi-Cuisine"
            dishes_joined = ", ".join(rec.popular_dishes) if rec.popular_dishes else "Chef Specials"

            lines.extend([
                f"#### {rank_str}{rec.name}",
                f"- **Rating**: `{rating_display}` ({rec.votes:,} reviews) | **Cost**: `₹{rec.price_for_two:,} for two`",
                f"- **Address**: {rec.location}",
                f"- **Cuisines**: {cuisines_joined}",
                f"- **Popular Dishes**: {dishes_joined}",
                f"- **AI Curated Rationale**: {rec.recommendation_reason}",
            ])
            if rec.url:
                lines.append(f"- **Zomato URL**: [{rec.name}]({rec.url})")
            lines.append("")

        lines.extend([
            "---",
            f"*Generated in {response.meta.execution_time_ms} ms via {response.meta.provider or 'AI Engine'} &middot; Engine v{response.meta.engine_version}*",
        ])

        return "\n".join(lines)
