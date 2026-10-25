from types import SimpleNamespace
from app.services.instagram_assessment import comment_metrics, engagement_metrics, deduplicate_results, compare_profile_site_identity
from app.services.risk_engine import assess

def test_repeated_comment_detection_requires_a_minimum_sample():
    insufficient=comment_metrics([{"comment_samples":["nice","nice"]}])
    sufficient=comment_metrics([{"comment_samples":["nice","nice","nice","nice","nice","nice"]}])
    assert insufficient["sample_size"]==2
    assert sufficient["repeated_ratio"]==1.0
    assert engagement_metrics({"posts":[{"comment_samples":["nice","nice"]}]})["observations"]==[]
    near=comment_metrics([{"comment_samples":["Amazing product","Amazing products!"]}])
    assert near["repeated_ratio"]==1.0

def test_engagement_heuristic_is_capped_and_only_scores_with_linked_evidence():
    finding=SimpleNamespace(status="observed",evidence_id="metrics",category="engagement_anomaly",risk_weight=100,id="f1")
    assert assess([finding])["risk_indicator"]==10
    finding.evidence_id=None
    assert assess([finding])["risk_indicator"]==0

def test_public_search_results_deduplicate_repeated_urls():
    rows=[{"url":"https://reports.example/post/1/","title":"A"},{"url":"https://reports.example/post/1#copy","title":"Syndicated"}]
    assert len(deduplicate_results(rows))==1

def test_deduplication_preserves_all_matched_identifiers():
    rows=[{"url":"https://reports.example/post","title":"Lead","matched_identifier":"shopname"},
          {"url":"https://reports.example/post#copy","title":"Syndicated","matched_identifier":"shop.example"}]
    result=deduplicate_results(rows)
    assert len(result)==1
    assert result[0]["matched_identifiers"]==["shopname","shop.example"]

def test_syndicated_search_snippets_are_deduplicated_across_urls():
    rows=[{"url":"https://a.example/report","title":"Customer complaints about Bright Shop","snippet":"Several customers report delayed orders and refunds from Bright Shop after paying online."},
          {"url":"https://b.example/copied","title":"Customer complaints about Bright Shop","snippet":"Several customers report delayed orders and refunds from Bright Shop after paying online."}]
    assert len(deduplicate_results(rows))==1

def test_profile_website_identity_comparison_is_explicitly_weak():
    profile={"username":"brightcraft","display_name":"Bright Craft"}
    mismatch=compare_profile_site_identity(profile,"Other Brand","Welcome to our store")
    overlap=compare_profile_site_identity(profile,"Bright Craft | handmade","Bright Craft goods")
    assert mismatch["status"]=="possible_difference"
    assert "Legitimate sellers" in mismatch["note"]
    assert overlap["status"]=="name_overlap"
