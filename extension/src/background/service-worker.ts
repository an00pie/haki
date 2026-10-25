// Deliberately idle: haki does not monitor browsing activity in the background.
chrome.runtime.onInstalled.addListener(() => {
  console.info("haki installed; page inspection starts only from the popup button.");
});
