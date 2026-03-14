"""Tests for model pricing, cost computation, and token usage tracking."""

from src.agent.agent import _compute_cost, _build_token_usage, MODELS, DEFAULT_MODEL


class TestComputeCost:
    def test_haiku_basic(self):
        cost = _compute_cost(1000, 500, 0, 0, model_key="haiku")
        expected = 1000 * 1.00 / 1_000_000 + 500 * 5.00 / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_sonnet_basic(self):
        cost = _compute_cost(1000, 500, 0, 0, model_key="sonnet")
        expected = 1000 * 3.00 / 1_000_000 + 500 * 15.00 / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_sonnet_is_3x_haiku(self):
        haiku = _compute_cost(1000, 500, 0, 0, model_key="haiku")
        sonnet = _compute_cost(1000, 500, 0, 0, model_key="sonnet")
        assert abs(sonnet / haiku - 3.0) < 1e-10

    def test_no_cache_savings_default(self):
        """Without cache savings, all input-side tokens charged at input rate."""
        cost = _compute_cost(100, 200, 300, 400, model_key="haiku")
        total_input = 100 + 300 + 400
        expected = total_input * 1.00 / 1_000_000 + 200 * 5.00 / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_with_cache_savings(self):
        """With cache savings, each token type gets its own rate."""
        cost = _compute_cost(
            100, 200, 300, 400,
            model_key="haiku",
            include_cache_savings=True,
        )
        expected = (
            100 * 1.00 / 1_000_000
            + 200 * 5.00 / 1_000_000
            + 300 * 1.25 / 1_000_000
            + 400 * 0.10 / 1_000_000
        )
        assert abs(cost - expected) < 1e-10

    def test_cache_savings_cheaper_than_no_savings(self):
        """Cache-aware cost should always be <= no-savings estimate."""
        no_savings = _compute_cost(100, 200, 300, 400, model_key="haiku")
        with_savings = _compute_cost(
            100, 200, 300, 400,
            model_key="haiku",
            include_cache_savings=True,
        )
        assert with_savings <= no_savings

    def test_batch_discount(self):
        normal = _compute_cost(1000, 500, 0, 0, model_key="haiku")
        batch = _compute_cost(1000, 500, 0, 0, model_key="haiku", is_batch=True)
        assert abs(batch - normal * 0.5) < 1e-10

    def test_zero_tokens(self):
        assert _compute_cost(0, 0, 0, 0) == 0.0

    def test_default_model_is_sonnet(self):
        assert DEFAULT_MODEL == "sonnet"


class TestBuildTokenUsage:
    def test_returns_correct_fields(self):
        usage = _build_token_usage(100, 200, 50, 30, api_calls=2, tool_calls=3)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 200
        assert usage.cache_write_tokens == 50
        assert usage.cache_read_tokens == 30
        assert usage.api_calls == 2
        assert usage.tool_calls == 3
        assert usage.model == "sonnet"
        assert usage.is_batch is False
        assert usage.total_cost_usd > 0

    def test_model_key_stored(self):
        usage = _build_token_usage(100, 200, 0, 0, 1, 0, model_key="sonnet")
        assert usage.model == "sonnet"

    def test_batch_flag(self):
        normal = _build_token_usage(100, 200, 0, 0, 1, 0, model_key="haiku")
        batch = _build_token_usage(100, 200, 0, 0, 1, 0, model_key="haiku", is_batch=True)
        assert batch.is_batch is True
        assert abs(batch.total_cost_usd - normal.total_cost_usd * 0.5) < 1e-10

    def test_cost_matches_compute_cost(self):
        usage = _build_token_usage(500, 300, 100, 50, 1, 0, model_key="haiku")
        expected = _compute_cost(500, 300, 100, 50, model_key="haiku")
        assert abs(usage.total_cost_usd - expected) < 1e-10


class TestModelsRegistry:
    def test_haiku_exists(self):
        assert "haiku" in MODELS
        assert MODELS["haiku"]["id"] == "claude-haiku-4-5"

    def test_sonnet_exists(self):
        assert "sonnet" in MODELS
        assert MODELS["sonnet"]["id"] == "claude-sonnet-4-6"

    def test_all_models_have_required_keys(self):
        required = {"id", "label", "input", "output", "cache_write", "cache_read"}
        for key, model in MODELS.items():
            assert required.issubset(model.keys()), f"Model '{key}' missing keys"
