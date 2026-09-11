from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workflow_wires_ebay_secrets_without_literal_credentials():
    workflow = (ROOT / ".github" / "workflows" / "publish-active-market.yml").read_text(encoding="utf-8")
    assert "scripts/enrich_active_market_ebay.py" in workflow
    assert "EBAY_CLIENT_ID: ${{ secrets.EBAY_CLIENT_ID }}" in workflow
    assert "EBAY_CLIENT_SECRET: ${{ secrets.EBAY_CLIENT_SECRET }}" in workflow
    assert "EBAY_MARKETPLACE_ID: EBAY_AU" in workflow
    assert workflow.index("publish_active_market.py") < workflow.index("enrich_active_market_ebay.py") < workflow.index("publish_exact_comparisons.py")


def test_ebay_enrichment_is_targeted_and_secret_safe():
    script = (ROOT / "scripts" / "enrich_active_market_ebay.py").read_text(encoding="utf-8")
    assert 'query=f"{year} {player}"' in script
    assert "DISABLED_MISSING_CREDENTIALS" in script
    assert "ebay.missing_credentials()" in script
    assert "client_secret" not in script.casefold()
    assert "sold" not in script.casefold()
    assert "fair_value" not in script.casefold()


def test_ebay_enrichment_rebuilds_comparison_feed_after_additions():
    script = (ROOT / "scripts" / "enrich_active_market_ebay.py").read_text(encoding="utf-8")
    assert "build_active_price_comparisons(cards)" in script
    assert 'metrics["exact_matches"]' in script
    assert 'metrics["ebay_added_cards"]' in script
