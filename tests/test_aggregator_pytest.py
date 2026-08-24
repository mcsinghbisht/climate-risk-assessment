"""
Pytest test suite for RiskAggregator (Task 17)

Run with: pytest tests/test_aggregator_pytest.py -v
"""

import pytest

from src.risk_scoring.aggregator import RiskAggregator


@pytest.fixture
def aggregator():
    return RiskAggregator()


class TestAggregateScores:
    """Tests matching the exact examples from docs/task-breakdown.md."""

    def test_60_40_averages_to_50_medium(self, aggregator):
        result = aggregator.aggregate_scores(wildfire_score=60, flood_score=40)
        assert result["overall_score"] == 50.0
        assert result["risk_level"] == "medium"

    def test_85_90_triggers_single_hazard_override(self, aggregator):
        """
        Both scores are already high, and flood=90 alone crosses the
        critical_single_hazard_threshold (85), so the override raises
        overall_score from the plain weighted average (87.5) up to the
        dominant score (90).
        """
        result = aggregator.aggregate_scores(wildfire_score=85, flood_score=90)
        assert result["overall_score"] == 90.0
        assert result["risk_level"] == "critical"
        assert result["breakdown"]["single_hazard_override"] is True
        assert result["breakdown"]["dominant_score"] == 90

    def test_zero_zero_is_low(self, aggregator):
        result = aggregator.aggregate_scores(0, 0)
        assert result["overall_score"] == 0.0
        assert result["risk_level"] == "low"

    def test_100_100_is_critical(self, aggregator):
        result = aggregator.aggregate_scores(100, 100)
        assert result["overall_score"] == 100.0
        assert result["risk_level"] == "critical"

    def test_result_has_breakdown(self, aggregator):
        result = aggregator.aggregate_scores(60, 40)
        assert "breakdown" in result
        assert result["breakdown"]["wildfire_score"] == 60
        assert result["breakdown"]["flood_score"] == 40

    def test_breakdown_contributions_sum_to_overall(self, aggregator):
        result = aggregator.aggregate_scores(60, 40)
        contributions = (
            result["breakdown"]["wildfire_contribution"] + result["breakdown"]["flood_contribution"]
        )
        assert contributions == result["overall_score"]

    def test_extreme_single_hazard_triggers_critical_override(self, aggregator):
        """
        A maximal wildfire score (100) with flood=0 must not be diluted to
        'medium' by a plain 50/50 average - the single-hazard override
        raises overall_score to the dominant score (100) and forces
        risk_level to 'critical', regardless of the other hazard being calm.
        """
        result = aggregator.aggregate_scores(wildfire_score=100, flood_score=0)
        assert result["overall_score"] == 100.0
        assert result["risk_level"] == "critical"
        assert result["breakdown"]["single_hazard_override"] is True
        assert result["breakdown"]["dominant_score"] == 100

    def test_just_below_threshold_does_not_trigger_override(self, aggregator):
        result = aggregator.aggregate_scores(wildfire_score=84, flood_score=0)
        assert result["breakdown"]["single_hazard_override"] is False
        assert result["breakdown"]["dominant_score"] is None
        assert result["overall_score"] == 42.0  # plain weighted average, no override
        assert result["risk_level"] == "medium"

    def test_exactly_at_threshold_triggers_override(self, aggregator):
        result = aggregator.aggregate_scores(wildfire_score=85, flood_score=0)
        assert result["breakdown"]["single_hazard_override"] is True
        assert result["overall_score"] == 85.0
        assert result["risk_level"] == "critical"

    def test_override_uses_higher_of_weighted_average_and_dominant_score(self, aggregator):
        """If the weighted average is already higher than the dominant score
        (possible with asymmetric weights), the override must not lower it."""
        result = aggregator.aggregate_scores(wildfire_score=90, flood_score=90)
        assert result["overall_score"] == 90.0  # average and dominant are equal here
        assert result["risk_level"] == "critical"


class TestClassifyRiskLevel:
    """Boundary tests for the four risk_levels thresholds."""

    def test_low_boundary(self, aggregator):
        assert aggregator.classify_risk_level(0) == "low"
        assert aggregator.classify_risk_level(25) == "low"

    def test_medium_boundary(self, aggregator):
        assert aggregator.classify_risk_level(26) == "medium"
        assert aggregator.classify_risk_level(50) == "medium"

    def test_high_boundary(self, aggregator):
        assert aggregator.classify_risk_level(51) == "high"
        assert aggregator.classify_risk_level(75) == "high"

    def test_critical_boundary(self, aggregator):
        assert aggregator.classify_risk_level(76) == "critical"
        assert aggregator.classify_risk_level(100) == "critical"


class TestBuildOverallAssessment:
    """Tests for the storage/LLM-context convenience method."""

    def test_combines_both_scorer_outputs(self, aggregator):
        property_data = {"property_id": 42}
        wildfire_result = {"score": 60, "factors": {"a": 1}, "explanation": "wildfire explanation"}
        flood_result = {"score": 40, "factors": {"b": 2}, "explanation": "flood explanation"}

        assessment = aggregator.build_overall_assessment(property_data, wildfire_result, flood_result)

        assert assessment["property_id"] == 42
        assert assessment["wildfire_risk_score"] == 60
        assert assessment["flood_risk_score"] == 40
        assert assessment["overall_risk_score"] == 50.0
        assert assessment["risk_level"] == "medium"
        assert assessment["wildfire_factors"] == {"a": 1}
        assert assessment["flood_factors"] == {"b": 2}
        assert assessment["wildfire_explanation"] == "wildfire explanation"
        assert assessment["flood_explanation"] == "flood explanation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
