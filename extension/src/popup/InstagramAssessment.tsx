import {useEffect, useState} from "react";
import {
  ArrowLeft,
  ArrowRight,
  Download,
  ExternalLink,
  Image as ImageIcon,
  LoaderCircle,
  LockKeyhole,
  ScanSearch,
  Shield,
  TriangleAlert,
  Video as VideoIcon,
} from "lucide-react";
import {API, request, type CaseDetail, type Finding, type InstagramProfile} from "../lib/types";
import {extractInstagramProfile} from "../content/instagram-inspector";
import {readVideo, removeVideo, storeVideo} from "../lib/video-storage";
import VideoUpload from "./VideoUpload";
import ProductPhotoUpload from "./ProductPhotoUpload";

type View = "idle" | "preview" | "running" | "resume" | "results" | "error";

type Saved = {
  view: View;
  profile: InstagramProfile | null;
  detail: CaseDetail | null;
  caseId: string;
  requestId: string;
  checkImages: boolean;
  checkComplaints: boolean;
  checkLinkedSite: boolean;
  message: string;
  explanation: {
    observations: string[];
    uncertainties: string[];
    next_checks: string[];
    evidence_ids: string[];
  } | null;
  productName: string;
  productPageUrl: string;
  videoName: string;
  videoSize: number;
  videoDuration: number | null;
  photoName: string;
  photoSize: number;
};

const PREFIX = "haki.instagram.session.v1.";

const INITIAL: Saved = {
  view: "idle",
  profile: null,
  detail: null,
  caseId: "",
  requestId: "",
  checkImages: false,
  checkComplaints: false,
  checkLinkedSite: true,
  message: "",
  explanation: null,
  productName: "",
  productPageUrl: "",
  videoName: "",
  videoSize: 0,
  videoDuration: null,
  photoName: "",
  photoSize: 0,
};

export default function InstagramAssessment() {
  const [s, setS] = useState<Saved>(INITIAL);
  const [key, setKey] = useState("");
  const [online, setOnline] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [video, setVideo] = useState<File | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [mediaTab, setMediaTab] = useState<"photo" | "video">("photo");

  async function update(patch: Partial<Saved>) {
    const stored = key ? ((await chrome.storage.local.get(key))[key] as Partial<Saved> | undefined) : undefined;
    const next = {...INITIAL, ...s, ...stored, ...patch};
    setS(next);
    if (key) await chrome.storage.local.set({[key]: next});
  }

  useEffect(() => {
    void (async () => {
      request("/health").then(() => setOnline(true)).catch(() => setOnline(false));
      const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
      const current = tab?.url ? new URL(tab.url).origin + new URL(tab.url).pathname : "";
      const k = PREFIX + String(tab?.id ?? "current") + ":" + encodeURIComponent(current);
      setKey(k);
      const saved = (await chrome.storage.local.get(k))[k] as Saved | undefined;
      if (saved) {
        setS({...INITIAL, ...saved});
        if (saved.videoName) {
          try {
            setVideo(await readVideo(k));
          } catch {
            /* Browser storage may be unavailable */
          }
        }
        if (saved.caseId) {
          try {
            const d = await request<CaseDetail>("/cases/" + saved.caseId);
            setS(x => ({...x, detail: d, view: saved.view === "running" ? "resume" : saved.view}));
          } catch {
            /* Keep local state */
          }
        }
      }
      setHydrated(true);
    })();
  }, []);

  async function selectVideo(file: File | null) {
    setVideo(file);
    if (!key) return;
    if (file) {
      await storeVideo(key, file);
      const duration = await videoDuration(file);
      await update({videoName: file.name, videoSize: file.size, videoDuration: duration});
    } else {
      await removeVideo(key);
      await update({videoName: "", videoSize: 0, videoDuration: null});
    }
  }

  function videoDuration(file: File): Promise<number | null> {
    return new Promise(resolve => {
      const element = document.createElement("video");
      const url = URL.createObjectURL(file);
      element.preload = "metadata";
      element.onloadedmetadata = () => {
        const value = Number.isFinite(element.duration) ? Math.round(element.duration) : null;
        URL.revokeObjectURL(url);
        resolve(value);
      };
      element.onerror = () => {
        URL.revokeObjectURL(url);
        resolve(null);
      };
      element.src = url;
    });
  }

  async function selectPhoto(file: File | null) {
    setPhoto(file);
    if (file) {
      await update({photoName: file.name, photoSize: file.size});
    } else {
      await update({photoName: "", photoSize: 0});
    }
  }

  async function verifyPhoto() {
    if (!s.caseId || !photo) return;
    const form = new FormData();
    form.append("file", photo, photo.name);
    form.append("reference_text", [s.productName, s.productPageUrl].filter(Boolean).join(" | "));
    setBusy(true);
    await update({message: "Analyzing product photo and running local vision models…"});
    try {
      await request(`/cases/${s.caseId}/product-image/verify`, {method: "POST", body: form});
      const detail = await request<CaseDetail>(`/cases/${s.caseId}`);
      await update({view: "results", detail, message: ""});
    } catch (e) {
      await update({message: e instanceof Error ? e.message : "Photo verification failed"});
    } finally {
      setBusy(false);
    }
  }

  async function verifyVideo() {
    if (!s.caseId) return;
    const source = video || (await readVideo(key));
    if (!source) {
      await update({message: "The saved video is unavailable. Choose it again to continue."});
      return;
    }
    const form = new FormData();
    form.append("file", source, source.name);
    form.append("reference_text", [s.productName, s.productPageUrl].filter(Boolean).join(" | "));
    setBusy(true);
    await update({message: "Sampling video frames and analyzing locally…"});
    try {
      if (s.detail?.stage2) await request(`/cases/${s.caseId}/video`, {method: "DELETE"});
      await request(`/cases/${s.caseId}/video/verify`, {method: "POST", body: form});
      const detail = await request<CaseDetail>(`/cases/${s.caseId}`);
      await update({view: "results", detail, message: ""});
    } catch (e) {
      await update({message: e instanceof Error ? e.message : "Video assessment failed"});
    } finally {
      setBusy(false);
    }
  }

  async function deleteVideo() {
    if (!s.caseId) return;
    setBusy(true);
    try {
      await request(`/cases/${s.caseId}/video`, {method: "DELETE"});
      try {
        await removeVideo(key);
      } catch {
        /* Backend deleted */
      }
      setVideo(null);
      const detail = await request<CaseDetail>(`/cases/${s.caseId}`);
      await update({detail, videoName: "", videoSize: 0, videoDuration: null, message: "Video deleted from case."});
    } catch (e) {
      await update({message: e instanceof Error ? e.message : "Could not delete video evidence"});
    } finally {
      setBusy(false);
    }
  }

  async function deleteCase() {
    if (!s.caseId || !window.confirm("Delete this case and all derived evidence from this device?")) return;
    setBusy(true);
    try {
      await request(`/cases/${s.caseId}`, {method: "DELETE"});
      try {
        await removeVideo(key);
      } catch {
        /* Ignore */
      }
      await chrome.storage.local.remove(key);
      setVideo(null);
      setPhoto(null);
      setS(INITIAL);
    } catch (e) {
      await update({message: e instanceof Error ? e.message : "Could not delete case"});
    } finally {
      setBusy(false);
    }
  }

  async function preview() {
    setBusy(true);
    try {
      const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
      if (tab?.id == null) throw Error("No active tab.");
      const [r] = await chrome.scripting.executeScript({target: {tabId: tab.id}, func: extractInstagramProfile});
      if (!r?.result) throw Error("Open a public Instagram seller profile, then click again.");
      await update({view: "preview", profile: r.result as InstagramProfile, detail: null, caseId: "", requestId: "", message: ""});
    } catch (e) {
      await update({view: "error", message: e instanceof Error ? e.message : "Could not read profile"});
    } finally {
      setBusy(false);
    }
  }

  async function run() {
    if (!s.profile) return;
    const id = s.requestId || crypto.randomUUID();
    await update({view: "running", requestId: id, message: "Saving the profile sample locally…"});
    setBusy(true);
    try {
      const payload = {
        ...s.profile,
        product_name: s.productName || null,
        product_page_url: s.productPageUrl || null,
        client_request_id: id,
      };
      const created = await request<{case_id: string}>("/instagram/inspect", {method: "POST", body: JSON.stringify(payload)});
      await update({caseId: created.case_id, message: "Evaluating profile authenticity metrics…"});
      await request("/cases/" + created.case_id + "/investigations", {
        method: "POST",
        body: JSON.stringify({
          check_linked_site: s.checkLinkedSite,
          check_public_complaints: s.checkComplaints,
          check_images: s.checkImages,
        }),
      });
      const detail = await request<CaseDetail>("/cases/" + created.case_id);
      await update({view: "results", detail, caseId: created.case_id, requestId: "", profile: null, message: ""});
    } catch (e) {
      await update({view: "error", message: e instanceof Error ? e.message : "Assessment failed"});
    } finally {
      setBusy(false);
    }
  }

  async function explain() {
    if (!s.caseId) return;
    setBusy(true);
    await update({message: "Consulting local Gemma model for observations…"});
    try {
      const value = await request<Saved["explanation"]>("/cases/" + s.caseId + "/explain", {method: "POST"});
      await update({explanation: value, message: ""});
    } catch (e) {
      await update({message: e instanceof Error ? e.message : "Local Gemma is unavailable"});
    } finally {
      setBusy(false);
    }
  }

  async function report() {
    if (!s.caseId) return;
    try {
      const r = await request<{download_url: string}>("/cases/" + s.caseId + "/report", {method: "POST"});
      await chrome.tabs.create({url: API.replace("/api/v1", "") + r.download_url});
    } catch (e) {
      await update({message: e instanceof Error ? e.message : "Could not create report"});
    }
  }

  const p = s.profile;
  const d = s.detail;
  const score = d?.risk.risk_indicator || 0;
  const threshold = d?.stage1?.threshold ?? 40;
  const crossedThreshold = Boolean(d && (score >= threshold || d.stage1?.decision.recommend_media || d.stage1?.decision.recommend_video));

  return (
    <main className="popup">
      <header className="top">
        <div className="brand">
          <span className="brand-icon">h</span>
          <span>haki</span>
          <span className="local-tag"><LockKeyhole size={10} /> LOCAL</span>
        </div>
        <button className="icon-btn" title="Backend status"><span className={"dot " + (online ? "ready" : "offline")} /></button>
      </header>

      {s.view === "idle" && (
        <>
          <section className="intro">
            <div className="kicker">INSTAGRAM SELLER AUTHENTICITY</div>
            <h1>Review the seller<br />before you pay.</h1>
            <p>haki evaluates profile creation timeline, follower ratio, bio site link, and unverified seller signals.</p>
          </section>
          <div className="video-reference">
            <label>Seller or product name<input value={s.productName} onChange={e => void update({productName: e.target.value})} placeholder="Optional product description" /></label>
            <label>Product page / post URL<input value={s.productPageUrl} onChange={e => void update({productPageUrl: e.target.value})} placeholder="https://instagram.com/p/…" /></label>
          </div>
          <button className="primary" disabled={!online || !hydrated || busy} onClick={preview}>
            {busy ? <LoaderCircle size={15} /> : <ScanSearch size={15} />} Inspect Instagram Seller <ArrowRight size={15} />
          </button>
          {!online && <div className="warn"><TriangleAlert size={15} /> Start the local haki API first.</div>}
          <footer><Shield size={13} /> Reads only visible active profile tab. No passwords, cookies, or tracking.</footer>
        </>
      )}

      {s.view === "preview" && p && (
        <>
          <button className="back" onClick={() => void update({view: "idle"})}><ArrowLeft size={14} /> Back</button>
          <section className="intro">
            <div className="kicker">PREVIEW PROFILE SAMPLE</div>
            <h1>@{p.username}</h1>
            <p>Review extracted signals before starting the local authenticity check.</p>
          </section>
          <section className="page-facts">
            <div className="section-head">AUTHENTICITY METRICS <span>UNVERIFIED SAMPLE</span></div>
            <div className="fact-row"><span>Display name</span><strong>{p.display_name || "Unavailable"}</strong></div>
            <div className="fact-row"><span>Followers / following</span><strong>{p.followers?.toLocaleString() ?? "—"} followers / {p.following?.toLocaleString() ?? "—"} following</strong></div>
            <div className="fact-row"><span>Earliest visible post</span><strong>{p.earliest_post_date || "Not visible in grid sample"}</strong></div>
            <div className="fact-row"><span>Bio website</span><strong>{p.website_url ? new URL(p.website_url).hostname : "No external link (DM transactions only)"}</strong></div>
            <div className="fact-row"><span>Bio</span><strong>{p.bio || "No bio text"}</strong></div>
          </section>
          <section className="findings">
            <div className="section-head">SAMPLED POSTS <span>{p.posts.length}</span></div>
            {p.posts.map((post, i) => (
              <article className="finding" key={i}>
                <strong>{post.caption || "Caption unavailable"}</strong>
                <small>{post.timestamp || "Time unavailable"} · {post.likes ?? "—"} likes · {post.comments_count ?? "—"} comments</small>
                <p>{post.comment_samples.slice(0, 3).join(" · ") || "No visible comment sample"}</p>
              </article>
            ))}
          </section>
          <label className="image-option">
            <input type="checkbox" checked={s.checkLinkedSite} onChange={e => void update({checkLinkedSite: e.target.checked})} />
            <span>
              <strong>Check linked bio storefront and domain age</strong>
              <small>Looks up bio domain registration (RDAP) and archive records (Wayback).</small>
            </span>
          </label>
          <label className="image-option">
            <input type="checkbox" checked={s.checkComplaints} onChange={e => void update({checkComplaints: e.target.checked})} />
            <span>
              <strong>Search public complaints and scam leads</strong>
              <small>Optional Brave search check for public buyer fraud reports.</small>
            </span>
          </label>
          <label className="image-option">
            <input type="checkbox" checked={s.checkImages} onChange={e => void update({checkImages: e.target.checked})} />
            <span>
              <strong>Compare visible post images for stock reuse</strong>
              <small>Perceptual dHash check against case evidence.</small>
            </span>
          </label>
          <button className="primary" disabled={!online || !hydrated || busy} onClick={run}>
            <ScanSearch size={15} /> Run Authenticity Assessment <ArrowRight size={15} />
          </button>
        </>
      )}

      {(s.view === "running" || s.view === "resume") && (
        <div className="progress">
          <div className="spinner"><LoaderCircle size={24} /></div>
          <div className="kicker">LOCAL INVESTIGATION</div>
          <h2>{s.view === "resume" ? "Resume assessment" : "Analyzing profile authenticity"}</h2>
          <p>{s.message || "Running local heuristics and checks…"}</p>
          <button className="primary" disabled={!online || !hydrated || busy || !p} onClick={run}>
            Resume assessment <ArrowRight size={15} />
          </button>
          <div className="persist-hint">Closing the popup keeps your progress and options.</div>
        </div>
      )}

      {s.view === "results" && d && (
        <>
          <button className="back" onClick={() => void update({view: "idle", profile: null, detail: null, caseId: "", requestId: "", message: ""})}>
            <ArrowLeft size={14} /> New check
          </button>

          <div className="result-heading">
            <div>
              <div className="kicker">PROVISIONAL RISK INDICATOR</div>
              <h2>{score}<small>/100</small></h2>
              <p>{d.risk.risk_level.toUpperCase()} indicator · unverified heuristics</p>
            </div>
            <div className="risk-ring" style={{"--score": String(score) + "%"} as React.CSSProperties}>
              <Shield size={20} />
            </div>
          </div>

          {/* Threshold alert recommendation banner */}
          {crossedThreshold ? (
            <div className="recommend-alert">
              <div className="recommend-alert-header">
                <TriangleAlert size={16} />
                <strong>Unverified Seller Signals Detected ({score}/100 &ge; {threshold})</strong>
              </div>
              <p>
                This Instagram seller crossed the caution threshold. High-risk signals were detected (such as new account maturity, follower engagement discrepancies, or lack of direct storefront buyer protection).
              </p>
              <div className="recommend-alert-action">
                👉 <strong>Action Required:</strong> We strongly suggest uploading product pictures or videos shown on their profile or sent in DMs to verify for stock duplicates or digital manipulation before sending payment.
              </div>
            </div>
          ) : (
            <section className="stage-decision">
              <div className="section-head">SELLER AUTHENTICITY <span>STAGE 1 COMPLETE</span></div>
              <p>{d.stage1?.decision.message || "Current checks did not cross the verification recommendation threshold. Product media verification remains available voluntarily."}</p>
            </section>
          )}

          {/* Key Instagram Factors */}
          <section className="page-facts">
            <div className="section-head">ASSESSMENT BREAKDOWN <span>{d.stage1?.score ?? score}/100</span></div>
            <div className="fact-row"><span>Seller handle</span><strong>@{d.case.seller_handle || p?.username || "unspecified"}</strong></div>
            <div className="fact-row"><span>Evidence strength</span><strong>{d.risk.evidence_strength}</strong></div>
            {(d.stage1?.score_factors || []).map((f, i) => (
              <div className="fact-row" key={i}>
                <span>{f.category.replace("instagram_", "").replace(/_/g, " ")}</span>
                <strong>+{f.points} risk points</strong>
              </div>
            ))}
          </section>

          {/* Automated Media Discovery Section */}
          {d.discovered_media && d.discovered_media.candidates && d.discovered_media.candidates.length > 0 && (
            <section className="stage-decision">
              <div className="section-head">
                AUTOMATED MEDIA DISCOVERY
                <span>{d.discovered_media.candidates.length} CANDIDATE(S)</span>
              </div>
              <small className="stage-observation">
                Ranked relevant profile media matching &ldquo;{d.discovered_media.product_query || "seller catalog"}&rdquo;.
              </small>
              {d.discovered_media.candidates.map((cand, idx) => (
                <div key={idx} className="finding" style={{marginTop: "6px", paddingTop: "6px"}}>
                  <div className="finding-top">
                    <span className="status-dot" />
                    <strong>[{cand.media_type.toUpperCase()}] {cand.caption ? cand.caption.slice(0, 60) + "…" : "Post"}</strong>
                    <span className="unverified">Relevance {cand.relevance_score}</span>
                  </div>
                  <p style={{margin: "4px 0", fontSize: "9px"}}>
                    Retrieval: <b>{cand.retrieval_status}</b> ({cand.retrieval_method})
                  </p>
                  {cand.retrieval_reason && (
                    <div className="warn-badge" style={{marginTop: "4px"}}>
                      <TriangleAlert size={13} /> {cand.retrieval_reason}
                    </div>
                  )}
                  {cand.visual_observations && cand.visual_observations.map((obs, i) => (
                    <small key={i} className="stage-observation">• {obs}</small>
                  ))}
                  {cand.similar_matches && cand.similar_matches.map((m, i) => (
                    <small key={"sm" + i} className="stage-observation" style={{color: "#b45309"}}>
                      ⚠️ Matches case image {m.filename} (distance {m.hamming_distance})
                    </small>
                  ))}
                </div>
              ))}
            </section>
          )}

          {/* Media Verification Upload Section */}
          <div className="upload-box">
            <div className="upload-title">
              <strong>STAGE 2: PRODUCT MEDIA VERIFICATION</strong>
              <span>Verify actual item authenticity using product photos or unboxing videos.</span>
            </div>

            <div className="media-tabs">
              <button
                type="button"
                className={`media-tab ${mediaTab === "photo" ? "active" : ""}`}
                onClick={() => setMediaTab("photo")}
              >
                <ImageIcon size={13} /> Product Picture
              </button>
              <button
                type="button"
                className={`media-tab ${mediaTab === "video" ? "active" : ""}`}
                onClick={() => setMediaTab("video")}
              >
                <VideoIcon size={13} /> Product Video
              </button>
            </div>

            {mediaTab === "photo" ? (
              <>
                <ProductPhotoUpload
                  file={photo}
                  onSelect={f => void selectPhoto(f)}
                  name={s.photoName}
                  size={s.photoSize}
                  disabled={busy}
                />
                <button
                  className="primary photo-action"
                  disabled={busy || !photo}
                  onClick={() => void verifyPhoto()}
                >
                  {busy ? <LoaderCircle size={15} /> : <ScanSearch size={15} />}
                  {crossedThreshold ? "Recommended: Verify Product Photo" : "Verify Product Photo"}
                  <ArrowRight size={15} />
                </button>
              </>
            ) : (
              <>
                <VideoUpload
                  file={video}
                  onSelect={f => void selectVideo(f)}
                  name={s.videoName}
                  size={s.videoSize}
                  duration={s.videoDuration}
                  disabled={!hydrated || busy}
                />
                {!d.stage2 && (
                  <button
                    className="primary video-action"
                    disabled={busy || (!video && !s.videoName)}
                    onClick={() => void verifyVideo()}
                  >
                    {busy ? <LoaderCircle size={15} /> : <ScanSearch size={15} />}
                    {crossedThreshold ? "Recommended: Verify Product Video" : "Verify Product Video"}
                    <ArrowRight size={15} />
                  </button>
                )}
              </>
            )}
          </div>

          {/* Photo assessment output if available */}
          {d.stage2_photo && (
            <section className="stage-decision">
              <div className="section-head">PRODUCT PICTURE ASSESSMENT <span>{d.stage2_photo.visual_analysis.status}</span></div>
              {d.stage2_photo.similar_case_images.length > 0 ? (
                <div className="warn-badge">
                  <TriangleAlert size={14} /> Potential Reused Stock Imagery: Closely matches case image '{d.stage2_photo.similar_case_images[0].filename}' (Hamming distance {d.stage2_photo.similar_case_images[0].hamming_distance}).
                </div>
              ) : (
                <p>No exact image duplicates detected among current case media.</p>
              )}
              {d.stage2_photo.visual_analysis.observations.map((obs, i) => (
                <small className="stage-observation" key={"po" + i}>Gemma vision: {obs}</small>
              ))}
              {d.stage2_photo.visual_analysis.possible_manipulation_indicators.map((ind, i) => (
                <small className="stage-observation" key={"pm" + i}>Manipulation signal: {ind}</small>
              ))}
            </section>
          )}

          {/* Video assessment output if available */}
          {d.stage2 && (
            <section className="stage-decision">
              <div className="section-head">PRODUCT VIDEO ASSESSMENT <span>{d.stage2.visual_analysis.status}</span></div>
              <p>{d.stage2.metadata.duration_seconds}s · {d.stage2.metadata.width}&times;{d.stage2.metadata.height} · {d.stage2.sampled_frame_count} unique frames. OCR: {d.stage2.ocr.status}; speech transcription: {d.stage2.transcription.status}.</p>
              <small className="stage-observation">Score change: {d.stage2.risk_score_change}. {d.stage2.risk_score_change_explanation}</small>
              {d.stage2.visual_analysis.observations.map((x, i) => (
                <small className="stage-observation" key={i}>Gemma vision: {x}</small>
              ))}
              {d.stage2.visual_analysis.possible_manipulation_indicators.map((x, i) => (
                <small className="stage-observation" key={"m" + i}>Manipulation indicator: {x}</small>
              ))}
              <button className="remove-video" onClick={() => void deleteVideo()}>Delete video and derived frames</button>
            </section>
          )}

          {/* Findings & Checks */}
          {d.findings && (
            <section className="findings">
              <div className="section-head">FINDINGS & SIGNALS <span>{d.findings.length}</span></div>
              {d.findings.map((f: Finding) => (
                <article className="finding" key={f.id}>
                  <div className="finding-top">
                    <span className="status-dot" />
                    {f.category.replace(/_/g, " ")}
                    <span className="unverified">{f.status}</span>
                  </div>
                  <p>{f.claim}</p>
                  {f.source_url && (
                    <a href={f.source_url} target="_blank" rel="noreferrer">
                      Open source <ExternalLink size={11} />
                    </a>
                  )}
                </article>
              ))}
            </section>
          )}

          {/* Local Gemma Summarizer */}
          <button className="ai-button" onClick={explain} disabled={busy}>
            {busy ? <LoaderCircle size={14} className="spin-icon" /> : <ScanSearch size={14} />}
            Ask local Gemma to summarize case
          </button>

          {s.explanation && (
            <section className="ai-result">
              <div className="section-head">LOCAL GEMMA INTERPRETATION <span>PROVISIONAL</span></div>
              <strong>Observations</strong>
              <ul>
                {s.explanation.observations.map((x, i) => <li key={"o" + i}>{x}</li>)}
              </ul>
              <strong>Uncertainties</strong>
              <ul>
                {s.explanation.uncertainties.map((x, i) => <li key={"u" + i}>{x}</li>)}
              </ul>
              {s.explanation.next_checks.length > 0 && (
                <>
                  <strong>Recommended Next Checks</strong>
                  <ul>
                    {s.explanation.next_checks.map((x, i) => <li key={"n" + i}>{x}</li>)}
                  </ul>
                </>
              )}
            </section>
          )}

          <button className="primary" onClick={report}>
            <Download size={15} /> Export PDF Report <ArrowRight size={15} />
          </button>
          <button className="remove-video case-delete" onClick={() => void deleteCase()}>
            Delete case and saved evidence
          </button>
          {s.message && <div className="ai-error">{s.message}</div>}
        </>
      )}

      {s.view === "error" && (
        <div className="error-view">
          <div className="error-mark"><TriangleAlert /></div>
          <h2>Assessment could not finish</h2>
          <p>{s.message}</p>
          <button className="primary" onClick={() => (s.profile ? void run() : void update({view: "idle", message: ""}))}>
            Retry or return <ArrowRight size={15} />
          </button>
        </div>
      )}
    </main>
  );
}
