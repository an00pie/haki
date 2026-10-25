from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from xml.sax.saxutils import escape
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
from app.config import settings
from app.services.risk_engine import assess, RISK_RULES_VERSION

def create_report(case, findings, audits, version, report_id):
    risk = assess(findings, audits)
    snapshot = json.dumps({"case":case.id,"findings":[{"id":f.id,"evidence_id":f.evidence_id} for f in findings],"audits":[a.id for a in audits],"rules":RISK_RULES_VERSION,"score":risk["risk_indicator"]}, sort_keys=True).encode()
    digest = hashlib.sha256(snapshot).hexdigest()
    path = settings.data_dir / "reports" / f"{report_id}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter, rightMargin=0.7*inch, leftMargin=0.7*inch)
    styles = getSampleStyleSheet(); story=[Paragraph("haki · Investigation report",styles["Title"]),Spacer(1,10)]
    story += [Paragraph(f"Case: {escape(case.title)}",styles["Heading2"]),Paragraph(f"Generated: {datetime.now(timezone.utc).isoformat()}",styles["Normal"]),
      Paragraph(f"Provisional risk indicator: {risk['risk_indicator']}/100 ({risk['risk_level']})",styles["Heading2"]),
      Paragraph("This heuristic is not a calibrated probability or a definitive fraud determination.",styles["Normal"]),
      Paragraph(f"Risk rules version: {escape(RISK_RULES_VERSION)}",styles["Normal"]),
      Paragraph(f"Evidence strength: {risk['evidence_strength']}. Coverage: {risk['coverage']}",styles["Normal"]),Spacer(1,12),Paragraph("Findings",styles["Heading2"])]
    if case.seller_handle and (case.notes or "").startswith("Instagram public profile assessment"):
        story += [Paragraph("Instagram profile assessment",styles["Heading2"]),
                  Paragraph(f"Profile: @{escape(case.seller_handle)}",styles["Normal"]),
                  Paragraph(f"Profile URL: {escape(case.store_url or 'Unavailable')}",styles["Normal"]),
                  Paragraph("Sampled profile fields and engagement metrics are browser-extracted, bounded, and unverified.",styles["Normal"]),Spacer(1,8)]
        profile_evidence=next((e for e in case.evidence if e.filename=="instagram-profile-sample.json"),None)
        if profile_evidence:
            try:
                profile=json.loads(Path(profile_evidence.storage_path).read_text(encoding="utf-8"))
                story += [Paragraph("Visible profile sample",styles["Heading3"]),
                          Paragraph(f"Display name: {escape(str(profile.get('display_name') or 'Unavailable')[:240])}; followers: {profile.get('followers') if profile.get('followers') is not None else 'Unavailable'}; following: {profile.get('following') if profile.get('following') is not None else 'Unavailable'}; listed posts: {profile.get('post_count') if profile.get('post_count') is not None else 'Unavailable'}; sampled: {len(profile.get('posts',[]))}.",styles["BodyText"]),
                          Paragraph(f"Bio excerpt: {escape(str(profile.get('bio') or 'Unavailable')[:800])}",styles["BodyText"]),
                          Paragraph(f"Linked website: {escape(str(profile.get('website_url') or 'Unavailable')[:500])}; captured: {escape(profile_evidence.ingested_at.isoformat() if profile_evidence.ingested_at else 'timestamp unavailable')}",styles["BodyText"])]
                for index,post in enumerate(profile.get("posts",[])[:8],1):
                    story.append(Paragraph(f"Sample post {index}: {escape(str(post.get('caption') or 'Caption unavailable')[:400])}; time: {escape(str(post.get('timestamp') or 'unavailable')[:80])}; likes: {post.get('likes') if post.get('likes') is not None else 'unavailable'}; comments: {post.get('comments_count') if post.get('comments_count') is not None else 'unavailable'}.",styles["BodyText"]))
                story.append(Spacer(1,8))
            except (OSError,ValueError,TypeError):
                story.append(Paragraph("The stored Instagram profile sample could not be rendered; its evidence hash remains in the evidence ledger.",styles["BodyText"]))
    stage1=next((e for e in case.evidence if e.filename=="stage-1-assessment.json"),None)
    if stage1:
        try:
            data=json.loads(Path(stage1.storage_path).read_text(encoding="utf-8"))
            decision=data.get("decision",{})
            story += [Paragraph("Preliminary Seller Assessment",styles["Heading2"]),
                      Paragraph(f"Seller-only score: {data.get('score','unavailable')}/100; evidence strength: {escape(str(data.get('evidence_strength','unknown')))}; threshold used: {data.get('threshold','unavailable')}/100.",styles["BodyText"]),
                      Paragraph(escape(str(decision.get("message","Decision unavailable"))),styles["BodyText"]),
                      Paragraph("Stage 1 score factors: "+escape(", ".join(f"{factor.get('category')} +{factor.get('points')}" for factor in data.get("score_factors",[])) or "No scored factors."),styles["BodyText"]),
                      Paragraph(f"Coverage: {escape(str(data.get('coverage',{})))}; rules version: {escape(str(data.get('risk_rules_version','unknown')))}; recorded: {escape(str(data.get('calculated_at','timestamp unavailable')))}",styles["BodyText"]),
                      Paragraph("Crossing the threshold recommends further verification and does not prove fraud.",styles["Italic"]),Spacer(1,8)]
        except (OSError,ValueError,TypeError):
            story.append(Paragraph("Preliminary Seller Assessment metadata could not be read; its evidence hash remains in the ledger.",styles["BodyText"]))
    video_ev=next((e for e in case.evidence if e.filename=="product-video-analysis.json"),None)
    if video_ev:
        try:
            video=json.loads(Path(video_ev.storage_path).read_text(encoding="utf-8"))
            meta=video.get("metadata",{});visual=video.get("visual_analysis",{})
            story += [Paragraph("Product Video Assessment",styles["Heading2"]),
                      Paragraph(f"Video evidence ID: {escape(str(video.get('video_evidence_id','unavailable')))}; SHA-256: {escape(str(video.get('video_sha256','unavailable')))}; duration: {meta.get('duration_seconds','unavailable')} s; size: {meta.get('width','?')} × {meta.get('height','?')}; codec: {escape(str(meta.get('codec','unavailable')))}; sampled unique frames: {video.get('sampled_frame_count',0)}.",styles["BodyText"]),
                      Paragraph(f"Visual analysis: {escape(str(visual.get('status','unavailable')))}; model: {escape(str(visual.get('model') or 'unavailable'))}; OCR: {escape(str(video.get('ocr',{}).get('status','unavailable')))}; transcription: {escape(str(video.get('transcription',{}).get('status','unavailable')))}.",styles["BodyText"]),
                      Paragraph(f"Risk score change from video evidence: {video.get('risk_score_change',0)} points. {escape(str(video.get('risk_score_change_explanation','No change recorded.')))}",styles["BodyText"]),
                      Paragraph("Sampled timestamps: "+escape(", ".join(str(x.get("timestamp_seconds"))+"s" for x in video.get("frames",[]))),styles["BodyText"])]
            for frame in video.get("frames",[])[:12]:
                story.append(Paragraph(f"Frame at {frame.get('timestamp_seconds')} s — evidence ID: {escape(str(frame.get('evidence_id','unavailable')))}; SHA-256: {escape(str(frame.get('sha256','unavailable')))}.",styles["Italic"]))
            for label,items in (("Visual observations",visual.get("observations",[])),("Possible manipulation indicators",visual.get("possible_manipulation_indicators",[])),("Uncertainties",visual.get("uncertainties",[]))):
                if items:
                    story.append(Paragraph(escape(label),styles["Heading3"]))
                    for item in items: story.append(Paragraph("• "+escape(str(item)[:500]),styles["BodyText"]))
            story += [Paragraph("Video findings are separate from seller-trust scoring and add no automatic risk points. A video does not prove seller ownership, shipment, or delivery of the same item. No obvious artifacts does not establish authenticity.",styles["Italic"]),Spacer(1,8)]
        except (OSError,ValueError,TypeError):
            story.append(Paragraph("Video assessment metadata could not be rendered; stored media evidence remains in the evidence ledger.",styles["BodyText"]))
    else:
        story += [Paragraph("Product Video Assessment",styles["Heading2"]),Paragraph("Not performed. This is a seller-only report; the product has not been video verified.",styles["BodyText"]),Spacer(1,8)]
    discovered_ev=next((e for e in case.evidence if e.filename=="discovered-media-analysis.json"),None)
    if discovered_ev:
        try:
            disc=json.loads(Path(discovered_ev.storage_path).read_text(encoding="utf-8"))
            candidates=disc.get("candidates",[])
            story += [Paragraph("Automated Instagram Media & Reels Analysis",styles["Heading2"]),
                      Paragraph(f"Product query: '{escape(disc.get('product_query') or 'None')}'; candidates ranked: {disc.get('candidates_ranked',0)} of {disc.get('total_posts_sampled',0)} sampled posts.",styles["BodyText"]),
                      Paragraph(escape(disc.get("guidance","")),styles["Italic"])]
            for idx,c in enumerate(candidates,1):
                post_url=escape(str(c.get("post_url") or "URL unavailable"))
                media_type=escape(str(c.get("media_type") or "media").upper())
                score=c.get("relevance_score",0)
                status=escape(str(c.get("retrieval_status","unknown")))
                method=escape(str(c.get("retrieval_method","unknown")))
                caption=escape(str(c.get("caption") or "(no caption)")[:240])
                story.append(Paragraph(f"<b>Candidate {idx} [{media_type}]</b> (relevance: {score}) — {post_url}",styles["Heading3"]))
                story.append(Paragraph(f"Caption: {caption}",styles["BodyText"]))
                story.append(Paragraph(f"Retrieval status: {status} (via {method}). File SHA-256: {escape(str(c.get('file_sha256') or 'N/A'))}.",styles["Italic"]))
                if c.get("retrieval_reason"):
                    story.append(Paragraph(f"Retrieval disclosure: {escape(str(c.get('retrieval_reason'))[:500])}",styles["BodyText"]))
                if c.get("visual_observations"):
                    story.append(Paragraph("Visual consistency observations (unverified):",styles["Italic"]))
                    for obs in c.get("visual_observations",[])[:4]:
                        story.append(Paragraph("• "+escape(str(obs)[:300]),styles["BodyText"]))
                if c.get("ocr_summary"):
                    story.append(Paragraph(f"OCR extracted text: {escape(str(c.get('ocr_summary'))[:300])}",styles["BodyText"]))
                if c.get("similar_matches"):
                    for m in c.get("similar_matches",[]):
                        story.append(Paragraph(f"• Matches case file '{escape(str(m.get('filename')))}' (Hamming distance {m.get('hamming_distance')}).",styles["BodyText"]))
            story.append(Spacer(1,8))
        except (OSError,ValueError,TypeError):
            story.append(Paragraph("Discovered media metadata could not be rendered; stored media evidence remains in the evidence ledger.",styles["BodyText"]))
    evidence_by_id={e.id:e for e in case.evidence}
    for f in findings:
        story.append(Paragraph(f"<b>{escape(f.category)}</b> — {escape(f.claim[:1200])}",styles["BodyText"]))
        created=f.created_at.isoformat() if f.created_at else "timestamp unavailable"
        ev=evidence_by_id.get(f.evidence_id) if f.evidence_id else None
        evidence_ref=(f"Evidence ID: {ev.id}; SHA-256: {ev.sha256}" if ev else "Evidence: not linked; heuristic or unavailable check")
        story.append(Paragraph(f"Status: {escape(f.status)}; evidence strength: {escape(f.evidence_strength)}; collected: {escape(created)}; {escape(evidence_ref)}; source: {escape(f.source_url or 'unverified / user supplied')}",styles["Italic"]))
        story.append(Spacer(1,6))
    if audits:
        story += [Spacer(1,8),Paragraph("Checks performed",styles["Heading2"])]
        for audit in audits:
            when=audit.created_at.isoformat() if audit.created_at else "timestamp unavailable"
            story.append(Paragraph(f"<b>{escape(audit.tool_name)}</b> — {escape(audit.status)}; {escape(when)}; {escape((audit.source_url or 'no external URL')[:500])}",styles["BodyText"]))
            story.append(Paragraph(escape(audit.result_summary[:800]),styles["Italic"]))
    story += [Spacer(1,8),Paragraph("Recommended next steps",styles["Heading2"]),Paragraph("Verify seller identity through an independently obtained channel; preserve original receipts and messages; contact your payment provider promptly if you paid. Review this report before sharing it. haki does not submit complaints or contact sellers.",styles["BodyText"]),Paragraph("Limitations",styles["Heading2"]),Paragraph("Public pages may be blocked or change. Absence of evidence is not evidence of legitimacy. The report contains only findings stored in this case at generation time.",styles["BodyText"])]
    doc.build(story)
    return path, digest, risk
