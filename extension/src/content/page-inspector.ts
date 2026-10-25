export type ExtractedPage={url:string;title:string;product_name:string|null;price_text:string|null;seller_text:string|null;image_urls:string[]};

/** Runs only in response to the popup's explicit Inspect click. */
export function extractCurrentPage():ExtractedPage {
  const clean=(value:string|null|undefined,max=500)=>value?.replace(/\s+/g," ").trim().slice(0,max)||null;
  const meta=(...selectors:string[])=>{for(const selector of selectors){const el=document.querySelector<HTMLMetaElement>(selector);if(el?.content)return clean(el.content)}return null};
  const title=clean(document.title,500)||"";
  const host=location.hostname.toLowerCase();
  const amazon=/(^|\.)amazon\.(com|in|co\.uk|ca|de|fr|it|es|co\.jp|com\.au|com\.br|com\.mx)$/.test(host);
  const amazonProductPage=/\/(?:dp|gp\/product|gp\/aw\/d)\/[A-Z0-9]{10}(?:\/|$)/i.test(location.pathname);
  const broadAmazonPage=amazon&&!amazonProductPage;
  const amazonProductTitle=amazonProductPage?clean(document.querySelector("#productTitle")?.textContent,500):null;
  const product=broadAmazonPage?null:(amazonProductTitle||meta('meta[property="og:title"]','meta[name="twitter:title"]','meta[itemprop="name"]')||clean(document.querySelector("h1")?.textContent,500));
  // Broad class-name searches on storefronts often pick promotional banners, not item prices.
  const amazonPrice=amazonProductPage?clean(document.querySelector('#corePriceDisplay_desktop_feature_div .priceToPay .a-offscreen, #corePriceDisplay_desktop_feature_div .a-offscreen, #corePrice_feature_div .priceToPay .a-offscreen, #corePrice_feature_div .a-offscreen, #apex_desktop .priceToPay .a-offscreen, #apex_desktop .a-price .a-offscreen, #corePrice_desktop .a-offscreen, .priceToPay .a-offscreen, .reinventPricePriceToPayMargin .a-offscreen, #priceblock_dealprice, #priceblock_ourprice, #price_inside_buybox, #newAccordionRow .a-price .a-offscreen, #tp_price_block_total_price_ww .a-offscreen, .a-price.aok-align-center .a-offscreen, span.a-price[data-a-color="price"] .a-offscreen, #corePriceDisplay_desktop_feature_div span.a-price-whole')?.textContent,160):null;
  const price=broadAmazonPage?null:(amazonPrice||meta('meta[property="product:price:amount"]','meta[itemprop="price"]','meta[property="og:price:amount"]')||clean(document.querySelector('[itemprop="price"]')?.textContent,160));
  const amazonSeller=amazonProductPage?clean(document.querySelector('#sellerProfileTriggerId, #merchant-info, #tabular-buybox .tabular-buybox-text')?.textContent,300):null;
  const seller=broadAmazonPage?null:(amazonSeller||meta('meta[property="product:brand"]','meta[itemprop="brand"]')||clean(document.querySelector('[itemprop="brand"]')?.textContent,300));
  const images=new Set<string>();
  const addImage=(raw:string)=>{try{const url=new URL(raw,location.href);if(url.protocol==="http:"||url.protocol==="https:")images.add(url.href)}catch{}};
  for(const selector of ['meta[property="og:image"]','meta[name="twitter:image"]','meta[itemprop="image"]']){const v=document.querySelector<HTMLMetaElement>(selector)?.content;if(v)addImage(v)}
  for(const img of Array.from(document.images).slice(0,80)){const raw=img.currentSrc||img.src;if(raw&&img.naturalWidth>=160&&img.naturalHeight>=120)addImage(raw)}
  return {url:location.href,title,product_name:product,price_text:price,seller_text:seller,image_urls:[...images].slice(0,8)};
}
