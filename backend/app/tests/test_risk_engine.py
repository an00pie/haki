from types import SimpleNamespace
from app.services.risk_engine import assess

def test_dead_site_or_unverified_signal_never_causes_high_risk():
    result=assess([SimpleNamespace(status="unverified",evidence_id=None,category="store_inaccessible",risk_weight=100,id="x")])
    assert result["risk_indicator"] == 0

def test_correlated_sources_are_deduplicated_per_family():
    fs=[SimpleNamespace(status="corroborated",evidence_id=f"e{i}",category="corroborated_non_delivery",risk_weight=30,id=f"f{i}") for i in range(3)]
    assert assess(fs)["risk_indicator"] == 30

def test_user_extracted_page_metadata_does_not_add_risk_without_corroboration():
    extracted = SimpleNamespace(status="observed", evidence_id="page-metadata", category="page_metadata", risk_weight=100, id="page")
    assert assess([extracted])["risk_indicator"] == 0
