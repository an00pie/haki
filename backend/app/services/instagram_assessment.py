"""Conservative, deterministic checks for explicitly submitted public Instagram samples."""
from __future__ import annotations
import re
from difflib import SequenceMatcher
from collections import Counter
from urllib.parse import quote
import httpx
from app.config import settings
from app.security.url_guard import validate_public_url, validate_redirect, UnsafeURL

GENERIC_COMMENTS={"nice pic","nice post","great post","beautiful","love it","wow","amazing","good","nice","🔥","😍","❤️"}
NAME_STOPWORDS={"the","and","for","shop","store","official","online","com","www"}

def compare_profile_site_identity(profile:dict,site_title:str|None,site_text:str|None)->dict:
    display=(profile.get("display_name") or profile.get("username") or "").casefold()
    tokens={x for x in re.findall(r"[a-z0-9]{3,}",display) if x not in NAME_STOPWORDS}
    if not tokens or not site_title:
        return {"status":"insufficient","overlap":[],"note":"A visible profile name or website title was unavailable."}
    website=(site_title+" "+(site_text or "")[:1200]).casefold()
    overlap=sorted(token for token in tokens if token in set(re.findall(r"[a-z0-9]{3,}",website)))
    if overlap:
        return {"status":"name_overlap","overlap":overlap,"note":"Some profile-name terms also appear on the linked page; this does not verify ownership."}
    return {"status":"possible_difference","overlap":[],"note":"No profile-name terms appeared in the sampled linked-page title/text. Legitimate sellers may use different personal, brand, and domain names."}

def comment_metrics(posts: list[dict]) -> dict:
    comments=[re.sub(r"[^\w]+"," ",c.casefold()).strip() for p in posts for c in p.get("comment_samples",[]) if isinstance(c,str) and c.strip()]
    comments=[c for c in comments if c]
    counts=Counter(comments)
    repeated=sum(n for n in counts.values() if n>1)
    duplicate_indexes=set()
    for i,current in enumerate(comments):
        for j in range(i):
            if SequenceMatcher(None,current,comments[j]).ratio()>=0.92:
                duplicate_indexes.update((i,j))
    repeated=max(repeated,len(duplicate_indexes))
    generic=sum(1 for c in comments if c in GENERIC_COMMENTS)
    return {"sample_size":len(comments),"repeated_ratio":round(repeated/len(comments),3) if comments else None,
            "generic_ratio":round(generic/len(comments),3) if comments else None,
            "unique_comments":len(counts)}

def profile_authenticity_metrics(profile: dict) -> dict:
    posts = profile.get("posts", [])
    followers = profile.get("followers")
    following = profile.get("following")
    post_count = profile.get("post_count")
    website = profile.get("website_url")
    bio = profile.get("bio") or ""

    maturity_obs = []
    maturity_weight = 0
    credibility_obs = []
    credibility_weight = 0
    website_obs = []
    website_weight = 0

    if followers is not None:
        if followers < 50:
            maturity_obs.append(f"Account has very few followers ({followers}) for a commercial store, indicating minimal public track record.")
            maturity_weight = max(maturity_weight, 12)
        elif followers < 200:
            maturity_obs.append(f"Account has a low follower count ({followers}) with limited public transaction history.")
            maturity_weight = max(maturity_weight, 8)

        if following is not None and following > 0:
            ratio = following / max(1, followers)
            if following > 1000 and ratio >= 5.0:
                credibility_obs.append(f"Follower-to-following ratio is heavily skewed ({following} following vs {followers} followers; {ratio:.1f}:1), typical of automated follow-back spam tactics.")
                credibility_weight = max(credibility_weight, 15)
            elif following > 800 and ratio >= 3.0:
                credibility_obs.append(f"Follower-to-following ratio is skewed ({following} following vs {followers} followers; {ratio:.1f}:1), typical of follow-back mass engagement tactics.")
                credibility_weight = max(credibility_weight, 10)

        if followers >= 2000 and posts:
            likes = [p.get("likes") for p in posts if isinstance(p.get("likes"), int)]
            if len(likes) >= 2:
                avg_likes = sum(likes) / len(likes)
                rate = avg_likes / followers
                if rate < 0.001:
                    credibility_obs.append(f"Severe engagement disconnect: posts average only {avg_likes:.0f} likes across {followers:,} followers (engagement rate <0.1%), strongly indicating inactive or purchased followers.")
                    credibility_weight = max(credibility_weight, 15)
                elif rate < 0.003:
                    credibility_obs.append(f"Low engagement rate ({rate:.2%}) relative to {followers:,} followers.")
                    credibility_weight = max(credibility_weight, 8)

    timestamps = [p.get("timestamp") for p in posts if p.get("timestamp")]
    earliest_date = profile.get("earliest_post_date") or (timestamps[-1] if timestamps else None)
    if earliest_date:
        maturity_obs.append(f"Earliest visible post timestamp: {earliest_date}.")
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(str(earliest_date).replace("Z", "+00:00"))
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            days_old = max(0, (datetime.now(timezone.utc) - dt).days)
            if days_old <= 30:
                maturity_obs.append(f"Account's earliest visible post is very recent ({days_old} day(s) old), indicating a newly created seller profile with minimal public tenure.")
                maturity_weight = max(maturity_weight, 15)
            elif days_old <= 90:
                maturity_obs.append(f"Account's earliest visible post is relatively new ({days_old} days old).")
                maturity_weight = max(maturity_weight, 10)
        except Exception:
            pass

    if post_count is not None and post_count <= 2 and (followers or 0) > 1000:
        maturity_obs.append(f"Account has only {post_count} visible post(s) despite claiming {(followers or 0):,} followers; sparse catalog activity.")
        maturity_weight = max(maturity_weight, 12)

    if not website:
        website_obs.append("No external website or storefront link found in bio. Commercial transactions rely on direct messaging (DM) without standard buyer protection.")
        website_weight = max(website_weight, 15)
    else:
        site_lower = website.casefold()
        if any(shortener in site_lower for shortener in ("bit.ly", "tinyurl.com", "is.gd", "cutt.ly")):
            website_obs.append(f"Bio uses an unverified link shortener ({website}) masking the destination domain.")
            website_weight = max(website_weight, 10)
        elif any(chat in site_lower for chat in ("wa.me", "api.whatsapp.com", "t.me")):
            website_obs.append(f"Bio links directly to a private chat ({website}) rather than an independent storefront with checkout protection.")
            website_weight = max(website_weight, 10)

    bio_lower = bio.casefold()
    if any(phrase in bio_lower for phrase in ("no refund", "no return", "no exchange")):
        website_obs.append("Bio explicitly states 'no refund / no return / no exchange' policy.")
        website_weight = min(15, website_weight + 5)
    if any(phrase in bio_lower for phrase in ("dm to order", "dm for price", "dm to buy")):
        website_obs.append("Bio instructs customers to 'DM to order/price', concealing official commercial pricing.")
        website_weight = min(15, website_weight + 4)

    return {
        "account_maturity": {"observations": maturity_obs, "risk_weight": min(15, maturity_weight)},
        "follower_credibility": {"observations": credibility_obs, "risk_weight": min(15, credibility_weight)},
        "website_link": {"observations": website_obs, "risk_weight": min(15, website_weight)},
    }

def engagement_metrics(profile:dict) -> dict:
    posts=profile.get("posts",[])
    observations=[]; weight=0
    comment=comment_metrics(posts)
    if comment["sample_size"]>=6 and comment["repeated_ratio"] is not None and comment["repeated_ratio"]>=0.4:
        observations.append(f"{comment['repeated_ratio']:.0%} of {comment['sample_size']} sampled visible comments repeat exactly (weak engagement heuristic).")
        weight=max(weight,4)
    if comment["sample_size"]>=8 and comment["generic_ratio"] is not None and comment["generic_ratio"]>=0.6:
        observations.append(f"{comment['generic_ratio']:.0%} of {comment['sample_size']} sampled comments match a short generic phrase list (weak heuristic).")
        weight=max(weight,3)
    metrics=[]
    if profile.get("followers") and profile["followers"]>0:
        for post in posts:
            if isinstance(post.get("likes"),int) and isinstance(post.get("comments_count"),int):
                metrics.append((post["likes"]+post["comments_count"])/profile["followers"])
    if len(metrics)>=3:
        mean=sum(metrics)/len(metrics)
        cv=(sum((x-mean)**2 for x in metrics)/len(metrics))**0.5/mean if mean else 0
        if cv>=1.5:
            observations.append(f"Visible engagement ratios vary substantially across {len(metrics)} sampled posts (coefficient of variation {cv:.2f}); this is contextual, not proof of manipulation.")
            weight=min(10,weight+3)
    return {"comment_metrics":comment,"engagement_ratios":metrics,"observations":observations,"risk_weight":min(10,weight)}

def deduplicate_results(results:list[dict])->list[dict]:
    seen=set();out=[];text_keys=[]
    for item in results:
        url=(item.get("url") or "").split("#",1)[0].rstrip("/").casefold()
        key=url or re.sub(r"\W+"," ",(item.get("title") or "").casefold()).strip()
        if not key:continue
        text_key=re.sub(r"\W+"," ",((item.get("title") or "")+" "+(item.get("snippet") or "")).casefold()).strip()
        existing=next((x for x in out if (x.get("url") or "").split("#",1)[0].rstrip("/").casefold()==url),None) if url else None
        if existing is None and len(text_key.split())>=8:
            existing=next((x for x,previous_text in zip(out,text_keys) if len(previous_text.split())>=8 and SequenceMatcher(None,text_key,previous_text).ratio()>=0.94),None)
        if key in seen or existing is not None:
            if existing is None and url:existing=next((x for x in out if (x.get("url") or "").split("#",1)[0].rstrip("/").casefold()==url),None)
            if existing and item.get("matched_identifier"):
                ids=existing.setdefault("matched_identifiers",[])
                if item["matched_identifier"] not in ids:ids.append(item["matched_identifier"])
            continue
        seen.add(key)
        if item.get("matched_identifier"):item.setdefault("matched_identifiers",[item.pop("matched_identifier")])
        out.append(item);text_keys.append(text_key)
    return out

async def brave_complaint_search(query:str)->dict:
    """Optional Brave web-search adapter. The secret remains backend-side."""
    key=settings.brave_search_api_key
    if not key:return {"status":"unavailable","reason":"BRAVE_SEARCH_API_KEY is not configured","results":[]}
    url="https://api.search.brave.com/res/v1/web/search"
    try:
        validate_public_url(url)
        async with httpx.AsyncClient(timeout=8,trust_env=False,follow_redirects=False) as client:
            response=await client.get(url,params={"q":query[:400],"count":8,"search_lang":"en"},headers={"X-Subscription-Token":key,"Accept":"application/json"})
        if response.status_code!=200:return {"status":"unavailable","reason":f"Search provider returned HTTP {response.status_code}","results":[]}
        data=response.json();rows=[]
        for item in data.get("web",{}).get("results",[])[:8]:
            link=item.get("url")
            if not isinstance(link,str):continue
            try:validate_public_url(link)
            except UnsafeURL:continue
            rows.append({"url":link,"title":str(item.get("title",""))[:300],"snippet":str(item.get("description",""))[:800]})
        return {"status":"completed","results":deduplicate_results(rows)}
    except Exception as exc:return {"status":"unavailable","reason":str(exc)[:240],"results":[]}

async def safe_json_get(url:str)->dict:
    """Fetch one fixed public metadata URL with validation on each redirect."""
    current=url
    try:
        async with httpx.AsyncClient(timeout=7,trust_env=False,follow_redirects=False) as client:
            for _ in range(4):
                validate_public_url(current)
                response=await client.get(current,headers={"User-Agent":"haki/0.3 (user-requested public metadata check)"})
                if response.is_redirect:
                    current=validate_redirect(current,response.headers.get("location",""));continue
                if response.status_code>=400:return {"status":"unavailable","reason":f"HTTP {response.status_code}","url":current}
                return {"status":"completed","url":str(response.url),"data":response.json()}
        return {"status":"unavailable","reason":"Redirect limit exceeded","url":current}
    except Exception as exc:return {"status":"unavailable","reason":str(exc)[:240],"url":current}
