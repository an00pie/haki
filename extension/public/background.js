// haki intentionally does not monitor tabs. Inspection is triggered only from the popup.
chrome.runtime.onInstalled.addListener(() => console.info("haki ready; no background browsing collection."));
