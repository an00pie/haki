// @vitest-environment jsdom
// @vitest-environment-options {"url":"https://www.instagram.com/"}
import {afterEach,describe,expect,it} from "vitest";
import {extractInstagramProfile} from "../instagram-inspector";

afterEach(()=>{document.head.innerHTML="";document.body.innerHTML="";window.history.replaceState({},"","/");});

describe("Instagram public profile extraction",()=>{
  it("extracts bounded visible fields and validates links",()=>{
    window.history.replaceState({},"","/smallshop/");
    document.body.innerHTML='<header><h1>Small Shop</h1><section>Handmade goods</section><a href="https://small.example">Website</a><ul><li>1,234 followers</li><li>80 following</li><li>12 posts</li></ul></header><main><article><a href="/p/ABC/"><img src="https://cdn.example/item.jpg"></a><div dir="auto">Blue bag</div><time datetime="2026-10-01">Oct 1</time><span>25 likes</span><span>2 comments</span><ul><li><span>lovely work</span></li></ul></article></main>';
    const value=extractInstagramProfile();
    expect(value?.username).toBe("smallshop");
    expect(value?.followers).toBe(1234);
    expect(value?.website_url).toBe("https://small.example/");
    expect(value?.earliest_post_date).toBe("2026-10-01");
    expect(value?.posts[0]).toMatchObject({likes:25,comments_count:2,caption:"Blue bag",timestamp:"2026-10-01"});
  });
  it("returns unavailable values safely when layout is missing",()=>{
    window.history.replaceState({},"","/minimal/");
    const value=extractInstagramProfile();
    expect(value).toMatchObject({username:"minimal",followers:null,following:null,post_count:null,posts:[],website_url:null});
  });
  it("refuses non-profile routes and non-Instagram pages",()=>{
    window.history.replaceState({},"","/p/abc/");
    expect(extractInstagramProfile()).toBeNull();
  });
  it("detects reels and extracts video stream URLs when rendered in DOM",()=>{
    window.history.replaceState({},"","/videoshop/");
    document.body.innerHTML='<header><h1>Video Shop</h1><ul><li>500 followers</li><li>50 following</li><li>5 posts</li></ul></header><main><article><a href="/reel/XYZ123/"><span aria-label="Reel">Reel</span></a><video src="https://cdn.example/reel.mp4"></video><div dir="auto">Demonstration of leather bag</div><time datetime="2026-10-15">Oct 15</time></article></main>';
    const value=extractInstagramProfile();
    expect(value?.username).toBe("videoshop");
    expect(value?.posts[0]).toMatchObject({is_reel:true,media_type:"reel",video_url:"https://cdn.example/reel.mp4",caption:"Demonstration of leather bag"});
  });
});
