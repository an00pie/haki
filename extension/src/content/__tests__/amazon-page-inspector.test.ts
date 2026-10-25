// @vitest-environment jsdom
// @vitest-environment-options {"url":"https://www.amazon.in/"}
import {afterEach,describe,expect,it} from "vitest";
import {extractCurrentPage} from "../page-inspector";

afterEach(()=>{document.head.innerHTML="";document.body.innerHTML="";document.title="";window.history.replaceState({},"","/")});

describe("Amazon listing extraction",()=>{
  it("uses product-specific selectors and ignores page overlays",()=>{
    window.history.replaceState({},"","/phone/dp/B0H297XH3K/");
    document.title="REDMI Turbo 5 : Amazon.in";
    document.head.innerHTML='<meta itemprop="name" content="Product summary Keyboard shortcut shift + alt + D">';
    document.body.innerHTML='<h1 id="productTitle">REDMI Turbo 5</h1><div id="corePriceDisplay_desktop_feature_div"><span class="a-offscreen">₹40,999</span></div><div id="merchant-info">Ships from Amazon. Sold by DawntTech.</div>';
    const result=extractCurrentPage();
    expect(result.product_name).toBe("REDMI Turbo 5");
    expect(result.price_text).toBe("₹40,999");
    expect(result.seller_text).toBe("Ships from Amazon. Sold by DawntTech.");
  });
  it("does not mistake browse-page banner content for listing data",()=>{
    window.history.replaceState({},"","/s?k=phones");
    document.title="Online Shopping site in India";
    document.head.innerHTML='<meta property="og:title" content="Today deals">';
    document.body.innerHTML='<div class="price">₹999</div><h1>Deals</h1>';
    const result=extractCurrentPage();
    expect(result.product_name).toBeNull();
    expect(result.price_text).toBeNull();
    expect(result.seller_text).toBeNull();
  });
  it("extracts deal pricing with .priceToPay wrapper",()=>{
    window.history.replaceState({},"","/phone/dp/B0H297XH3K/");
    document.title="REDMI Turbo 5 : Amazon.in";
    document.body.innerHTML='<h1 id="productTitle">REDMI Turbo 5</h1><div id="corePriceDisplay_desktop_feature_div"><div class="priceToPay"><span class="a-offscreen">₹40,999</span></div></div>';
    const result=extractCurrentPage();
    expect(result.price_text).toBe("₹40,999");
  });
});
