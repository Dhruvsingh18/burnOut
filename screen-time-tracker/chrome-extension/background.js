// Burnout Tracker — Chrome Extension Background Worker
// Sends all open tabs to the backend every 60 seconds.

const BACKEND = "https://burnout-n9p9.onrender.com";

// Set up an alarm that fires every minute
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("sendTabs", { periodInMinutes: 1 });
  console.log("Burnout Tracker extension installed. Sending tabs every minute.");
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === "sendTabs") {
    await sendTabs();
  }
});

// Also send immediately when extension loads
sendTabs();

async function sendTabs() {
  try {
    // Get all open tabs across all windows
    const tabs = await chrome.tabs.query({});

    const payload = tabs
      .filter(tab => tab.url && !tab.url.startsWith("chrome://") && !tab.url.startsWith("chrome-extension://"))
      .map(tab => ({
        url:    tab.url,
        title:  tab.title || "",
        active: tab.active,
      }));

    if (payload.length === 0) return;

    const response = await fetch(`${BACKEND}/api/chrome-tabs`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ tabs: payload }),
    });

    if (response.ok) {
      console.log(`Burnout Tracker: sent ${payload.length} tabs`);
    }
  } catch (err) {
    // Backend unreachable — silently retry next minute
    console.warn("Burnout Tracker: could not reach backend", err.message);
  }
}
