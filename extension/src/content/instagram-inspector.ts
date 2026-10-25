export type InstagramPost={url:string|null;caption:string|null;timestamp:string|null;likes:number|null;comments_count:number|null;comment_samples:string[];image_urls:string[];is_reel?:boolean;video_url?:string|null;media_type?:string};
export type InstagramProfile={profile_url:string;username:string;display_name:string|null;bio:string|null;website_url:string|null;followers:number|null;following:number|null;post_count:number|null;earliest_post_date:string|null;posts:InstagramPost[];image_urls:string[]};

/** Reads only content currently rendered in the active tab, after a popup click. */
export function extractInstagramProfile():InstagramProfile|null {
  if(!/(^|\.)instagram\.com$/i.test(location.hostname))return null;
  const path=location.pathname.split("/").filter(Boolean);
  const username=(path[0]||"").replace(/^@/,"");
  if(!/^[A-Za-z0-9._]{1,64}$/.test(username)||["p","reel","reels","stories","explore","direct","accounts"].includes(username.toLowerCase()))return null;
  const clean=(s:string|null|undefined,max=1200)=>s?.replace(/\s+/g," ").trim().slice(0,max)||null;
  const parseCount=(raw:string|null|undefined):number|null=>{if(!raw)return null;const m=raw.replace(/,/g,"").match(/([\d.]+)\s*([KMB])?/i);if(!m)return null;const n=Number(m[1])*({K:1e3,M:1e6,B:1e9}[m[2]?.toUpperCase()||"" as "K"]||1);return Number.isFinite(n)?Math.round(n):null};
  const getCount=(kind:string)=>{const node=Array.from(document.querySelectorAll<HTMLElement>("header li, header a, header button, header span")).find(x=>(x.innerText||x.textContent||x.getAttribute("aria-label")||"").toLowerCase().includes(kind.replace("?","").toLowerCase()));const raw=node?.getAttribute("title")||node?.innerText||node?.textContent||node?.getAttribute("aria-label")||"";return parseCount(raw)};
  const og=(key:string)=>document.querySelector<HTMLMetaElement>(`meta[property="${key}"]`)?.content||null;
  const usernameCandidate=clean(document.querySelector("header h1")?.textContent,240)||clean(document.querySelector("header h2")?.textContent,240);
  const display=usernameCandidate?.toLowerCase()===username.toLowerCase()?null:usernameCandidate;
  const bio=clean(document.querySelector<HTMLElement>("header section")?.innerText||document.querySelector<HTMLElement>("header")?.querySelector("[dir=auto]")?.textContent,2000);
  let website:string|null=null;
  for(const a of Array.from(document.querySelectorAll<HTMLAnchorElement>("header a[href]"))){try{let u=new URL(a.href);if(/(^|\.)l\.instagram\.com$/i.test(u.hostname)){const target=u.searchParams.get("u")||u.searchParams.get("url");if(target)u=new URL(target)}if(/^https?:$/.test(u.protocol)&&!/(^|\.)instagram\.com$/i.test(u.hostname)){website=u.href;break}}catch{}}
  const imageSet=new Set<string>();const posts:InstagramPost[]=[];
  const articles=Array.from(document.querySelectorAll<HTMLElement>("article, main article")).slice(0,8);
  for(const article of articles){
    const link=article.querySelector<HTMLAnchorElement>('a[href*="/p/"],a[href*="/reel/"]');let postUrl:string|null=null;try{postUrl=link?new URL(link.href,location.href).href:null}catch{}
    const isReel=Boolean((postUrl&&postUrl.includes("/reel/"))||article.querySelector('[aria-label*="Reel" i],svg[aria-label*="Clip" i],[data-testid*="reel" i]'));
    const videoNode=article.querySelector<HTMLVideoElement>("video");
    const videoSrc=videoNode?.currentSrc||videoNode?.src||null;
    let validVideoUrl:string|null=null;
    try{if(videoSrc&&/^https?:\/\//i.test(videoSrc))validVideoUrl=videoSrc}catch{}
    const img=article.querySelector<HTMLImageElement>("img");const src=img?.currentSrc||img?.src||"";const imgs:string[]=[];
    try{if(src&&new URL(src).protocol.startsWith("http")){imgs.push(src);imageSet.add(src)}}catch{}
    const mediaType=isReel?"reel":(validVideoUrl?"video":(imgs.length>1?"carousel":"image"));
    const caption=clean(article.querySelector('[data-testid="post-comment-root"],h1,h2,[dir="auto"]')?.textContent,1200);
    const time=article.querySelector<HTMLTimeElement>("time");const timestamp=time?.dateTime||clean(time?.textContent,80);
    const metric=(kind:string)=>{const node=Array.from(article.querySelectorAll<HTMLElement>("span,[aria-label],a")).find(el=>(el.innerText||el.textContent||el.getAttribute("aria-label")||"").toLowerCase().includes(kind));return parseCount(node?.innerText||node?.textContent||node?.getAttribute("aria-label"))};const likes=metric("like");const commentsCount=metric("comment");
    const comments=Array.from(article.querySelectorAll<HTMLElement>("ul li")).map(li=>Array.from(li.querySelectorAll<HTMLElement>("span")).filter(span=>!span.closest("a")).map(span=>span.textContent||"").join(" ")).map(x=>clean(x,300)).filter((x):x is string=>!!x&&x.length>1).slice(0,12);
    posts.push({url:postUrl,caption,timestamp,likes,comments_count:commentsCount,comment_samples:comments,image_urls:imgs,is_reel:isReel,video_url:validVideoUrl,media_type:mediaType});
  }
  for(const img of Array.from(document.querySelectorAll<HTMLImageElement>("main img" )).slice(0,60)){const src=img.currentSrc||img.src;try{if(src&&new URL(src).protocol.startsWith("http"))imageSet.add(src)}catch{}}

  const dateCandidates: string[] = [];
  for (const t of Array.from(document.querySelectorAll<HTMLTimeElement>("time"))) {
    const dt = t.dateTime || t.getAttribute("datetime") || clean(t.textContent, 80);
    if (dt) dateCandidates.push(dt);
  }
  for (const p of posts) {
    if (p.timestamp) dateCandidates.push(p.timestamp);
  }
  let earliest_post_date: string | null = null;
  if (dateCandidates.length > 0) {
    const parsed = dateCandidates
      .map(c => ({ raw: c, time: Date.parse(c) }))
      .filter(x => !isNaN(x.time));
    if (parsed.length > 0) {
      parsed.sort((a, b) => a.time - b.time);
      earliest_post_date = parsed[0].raw;
    } else {
      earliest_post_date = dateCandidates[dateCandidates.length - 1];
    }
  }

  return {profile_url:location.href.split("?")[0],username,display_name:display,bio,website_url:website,followers:getCount("followers?"),following:getCount("following"),post_count:getCount("posts?"),earliest_post_date,posts,image_urls:[...imageSet].slice(0,12)};
}
