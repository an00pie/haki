// @vitest-environment jsdom
import {afterEach,describe,expect,it} from "vitest";
import {extractCurrentPage} from "../page-inspector";

afterEach(()=>{document.head.innerHTML="";document.body.innerHTML="";document.title="";window.history.replaceState({},"","/")});

describe("click-triggered page extraction",()=>{
  it("extracts common product metadata and labels it only as page content",()=>{
    document.head.innerHTML='<meta property="og:title" content="Handmade lamp"><meta property="product:price:amount" content="49.00"><meta property="og:image" content="/lamp.jpg">';
    document.title="Shop item";
    document.body.innerHTML="<h1>Visible title</h1>";
    const result=extractCurrentPage();
    expect(result.title).toBe("Shop item");
    expect(result.product_name).toBe("Handmade lamp");
    expect(result.price_text).toBe("49.00");
    expect(result.image_urls).toEqual(["http://localhost:3000/lamp.jpg"]);
  });
  it("returns no seller or image claims when the page has no matching fields",()=>{
    document.title="Plain page";
    const result=extractCurrentPage();
    expect(result.seller_text).toBeNull();
    expect(result.image_urls).toEqual([]);
  });
});
