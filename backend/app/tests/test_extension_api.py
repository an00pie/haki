import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.api import routes
from app.services.ollama import Explanation

client=TestClient(app)

def test_extension_page_inspection_keeps_extracted_content_unverified():
    response=client.post("/api/v1/inspect",json={"url":"https://example.invalid/product","title":"Product page","product_name":"Lamp","price_text":"49.00","image_urls":[]})
    assert response.status_code==201
    case_id=response.json()["case_id"]
    details=client.get(f"/api/v1/cases/{case_id}").json()
    assert details["findings"][0]["status"]=="observed"
    assert details["risk"]["risk_indicator"]==0
    assert client.delete(f"/api/v1/cases/{case_id}").status_code==204

def test_local_model_interpretation_is_stored_unverified_and_unscored(monkeypatch):
    response=client.post("/api/v1/inspect",json={"url":"https://example.invalid/product","title":"Product page"})
    case_id=response.json()["case_id"]
    async def fake_explanation(_, __=None):
        return Explanation(observations=["One page title was extracted."],uncertainties=["Seller identity was not verified."],next_checks=["Check independent sources."],evidence_ids=["fabricated-id"])
    monkeypatch.setattr(routes,"explain_untrusted_evidence",fake_explanation)
    result=client.post(f"/api/v1/cases/{case_id}/explain")
    assert result.status_code==200,result.text
    assert result.json()["status"]=="unverified"
    assert result.json()["risk_contribution"]==0
    assert result.json()["evidence_ids"]==[]
    details=client.get(f"/api/v1/cases/{case_id}").json()
    assert any(f["category"]=="model_interpretation" and f["status"]=="unverified" for f in details["findings"])
    assert details["risk"]["risk_indicator"]==0
    assert client.delete(f"/api/v1/cases/{case_id}").status_code==204

def test_retried_popup_inspection_request_does_not_create_duplicate_cases():
    import uuid
    request_id=str(uuid.uuid4())
    payload={"url":"https://example.invalid/product","title":"Product page","client_request_id":request_id}
    first=client.post("/api/v1/inspect",json=payload)
    second=client.post("/api/v1/inspect",json=payload)
    assert first.status_code==201 and second.status_code==201
    assert first.json()["case_id"]==second.json()["case_id"]
    assert second.json()["message"]=="Resumed existing inspection request."
    assert client.delete(f"/api/v1/cases/{first.json()['case_id']}").status_code==204

def test_instagram_sample_is_saved_to_existing_case_and_report():
    import uuid
    payload={"profile_url":"https://www.instagram.com/sample.shop/","username":"sample.shop","display_name":"Sample Shop","followers":120,"posts":[{"caption":"Example item","likes":7,"comments_count":1,"comment_samples":["nice","nice","nice","nice","nice","nice"]}],"client_request_id":str(uuid.uuid4())}
    first=client.post("/api/v1/instagram/inspect",json=payload)
    assert first.status_code==201,first.text
    again=client.post("/api/v1/instagram/inspect",json=payload)
    assert again.json()["case_id"]==first.json()["case_id"]
    case_id=first.json()["case_id"]
    detail=client.get(f"/api/v1/cases/{case_id}").json()
    assert detail["case"]["seller_handle"]=="sample.shop"
    assert any(e["filename"]=="instagram-profile-sample.json" for e in detail["evidence"])
    run=client.post(f"/api/v1/cases/{case_id}/investigations",json={"check_linked_site":False,"check_public_complaints":False,"check_images":False})
    assert run.status_code==202,run.text
    detail=client.get(f"/api/v1/cases/{case_id}").json()
    assert any(f["category"]=="engagement_anomaly" for f in detail["findings"])
    assert detail["risk"]["risk_indicator"]>0
    report=client.post(f"/api/v1/cases/{case_id}/report")
    assert report.status_code==201
    assert client.get(report.json()["download_url"]).status_code==200
    assert client.delete(f"/api/v1/cases/{case_id}").status_code==204

def test_instagram_username_must_match_instagram_profile_url():
    response=client.post("/api/v1/instagram/inspect",json={"profile_url":"https://www.instagram.com/real.shop/","username":"other.shop"})
    assert response.status_code==422

def test_opted_in_instagram_linked_site_records_safe_domain_context(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings,"public_checks_enabled",True)
    async def fake_page(_):
        return {"status":"completed","requested_url":"https://shop.example","url":"https://shop.example/","http_status":200,"https_final":True,"redirect_chain":[],"title":"Sample Shop","text_excerpt":"Sample Shop contact shipping refund return privacy","image_urls":[]}
    async def fake_json(url):
        return {"status":"completed","url":url,"data":{"events":[]}}
    monkeypatch.setattr(routes,"fetch_page",fake_page)
    monkeypatch.setattr(routes,"safe_json_get",fake_json)
    response=client.post("/api/v1/instagram/inspect",json={"profile_url":"https://www.instagram.com/sample.shop/","username":"sample.shop","display_name":"Sample Shop","website_url":"https://shop.example"})
    assert response.status_code==201,response.text
    case_id=response.json()["case_id"]
    run=client.post(f"/api/v1/cases/{case_id}/investigations",json={"check_linked_site":True,"check_public_complaints":False,"check_images":False})
    assert run.status_code==202,run.text
    details=client.get(f"/api/v1/cases/{case_id}").json()
    assert {a["tool_name"] for a in details["audits"]}>={"linked_website_fetch","rdap_domain_registration","wayback_archive_history"}
    assert any(f["category"]=="website_policy_context" for f in details["findings"])
    assert client.delete(f"/api/v1/cases/{case_id}").status_code==204
