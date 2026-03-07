const ingestForm = document.getElementById("resource-form");
const askForm = document.getElementById("ask-form");
const refreshBtn = document.getElementById("refresh-content");
const ingestResult = document.getElementById("ingest-result");
const askResult = document.getElementById("ask-result");
const contentResult = document.getElementById("content-result");

function pretty(data) {
  return JSON.stringify(data, null, 2);
}

function endpointFor(type, input, limit) {
  if (type === "rss") {
    return ["/api/feeds", { url: input, limit }];
  }
  if (type === "youtube") {
    if (input.includes("youtube.com") || input.includes("youtu.be")) {
      return ["/api/feeds/youtube", { channel_url: input, limit }];
    }
    return ["/api/feeds/youtube", { channel_id: input, limit }];
  }
  if (type === "twitter") {
    if (input.includes("x.com") || input.includes("twitter.com")) {
      return ["/api/feeds/twitter", { thread_url: input, limit }];
    }
    return ["/api/feeds/twitter", { twitter_handle: input, limit }];
  }
  if (type === "hackernews") {
    return ["/api/feeds/hackernews", { limit }];
  }
  return ["/api/feeds/url", { any_url: input, limit }];
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  return { status: response.status, data };
}

ingestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const sourceType = document.getElementById("source-type").value;
  const resourceInput = document.getElementById("resource-input").value.trim();
  const limit = Number(document.getElementById("limit-input").value || 5);
  const [url, payload] = endpointFor(sourceType, resourceInput, limit);

  ingestResult.textContent = "Ingesting...";
  try {
    const result = await postJson(url, payload);
    ingestResult.textContent = pretty(result);
  } catch (error) {
    ingestResult.textContent = String(error);
  }
});

askForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = document.getElementById("question-input").value.trim();
  const topK = Number(document.getElementById("topk-input").value || 4);
  askResult.textContent = "Thinking...";
  try {
    const result = await postJson("/api/ask", { question, top_k: topK });
    askResult.textContent = pretty(result);
  } catch (error) {
    askResult.textContent = String(error);
  }
});

refreshBtn.addEventListener("click", async () => {
  contentResult.textContent = "Loading...";
  try {
    const response = await fetch("/api/content?limit=10&offset=0");
    const data = await response.json();
    contentResult.textContent = pretty(data);
  } catch (error) {
    contentResult.textContent = String(error);
  }
});
