// --- DOM Elements ---
const navChat = document.getElementById("nav-chat");
const navInterests = document.getElementById("nav-interests");
const viewChat = document.getElementById("view-chat");
const viewInterests = document.getElementById("view-interests");

const chatHistory = document.getElementById("chat-history");
const askForm = document.getElementById("ask-form");
const questionInput = document.getElementById("question-input");

const btnOpenAdd = document.getElementById("btn-open-add");
const btnCloseModal = document.getElementById("btn-close-modal");
const addModal = document.getElementById("add-modal");
const resourceForm = document.getElementById("resource-form");
const ingestResult = document.getElementById("ingest-result");
const cardsContainer = document.getElementById("cards-container");

// --- View Switching ---
function switchView(view) {
  navChat.classList.remove("active");
  navInterests.classList.remove("active");
  viewChat.classList.add("hidden");
  viewInterests.classList.add("hidden");
  
  viewChat.classList.remove("active");
  viewInterests.classList.remove("active");

  if (view === "chat") {
    navChat.classList.add("active");
    viewChat.classList.add("active");
    viewChat.classList.remove("hidden");
  } else {
    navInterests.classList.add("active");
    viewInterests.classList.add("active");
    viewInterests.classList.remove("hidden");
    fetchInterests(); // Fetch on tab open
  }
}

navChat.addEventListener("click", () => switchView("chat"));
navInterests.addEventListener("click", () => switchView("interests"));

// --- Auto Resize Textarea ---
questionInput.addEventListener("input", function() {
  this.style.height = "auto";
  this.style.height = (this.scrollHeight) + "px";
});

// --- API Helpers ---
async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || "Server Error");
  return data;
}

function endpointFor(type, input) {
  // Hardcoded limit to 5 to simplify UI per requirements (type & url only)
  const limit = 5; 
  if (type === "rss") return ["/api/feeds", { url: input, limit }];
  if (type === "youtube") {
    if (input.includes("youtube.com") || input.includes("youtu.be")) {
      return ["/api/feeds/youtube", { channel_url: input, limit }];
    }
    return ["/api/feeds/youtube", { channel_id: input, limit }];
  }
  return ["/api/feeds/url", { any_url: input, limit }];
}

// --- Chat Logic ---
function appendMessage(role, contentHtml) {
  const msgDiv = document.createElement("div");
  msgDiv.className = `message ${role}-message`;
  
  const avatarText = role === "user" ? "U" : "AI";
  
  msgDiv.innerHTML = `
    <div class="avatar ${role}-avatar">${avatarText}</div>
    <div class="message-content">
      <div class="text">${contentHtml}</div>
    </div>
  `;
  chatHistory.appendChild(msgDiv);
  chatHistory.scrollTop = chatHistory.scrollHeight;
  return msgDiv; // Return so we can modify it if loading
}

askForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  // Render User question
  appendMessage("user", question);
  questionInput.value = "";
  questionInput.style.height = "auto"; // reset height

  // Render Loading AI state
  const loadingMsg = appendMessage("ai", "<em>Thinking...</em>");

  try {
    const response = await postJson("/api/ask", { question, top_k: 4 });
    const data = response.data || response; // depending on backend wrap

    let answerText = data.answer || "I'm sorry, I couldn't find an answer.";
    
    // Construct Accordion if sources are present
    let sourcesHtml = "";
    if (data.sources && data.sources.length > 0) {
      const sourceItems = data.sources.map(s => 
        `<div class="source-item">
          <a href="${s.link || '#'}" target="_blank">${s.title || 'Source'}</a>
          <p>${s.summary || s.excerpt || ''}</p>
        </div>`
      ).join("");
      
      sourcesHtml = `
        <details class="sources-accordion">
          <summary>View Sources & Details</summary>
          <div class="sources-content">
            ${data.langsmith_project_id ? `<p><strong>Project ID:</strong> ${data.langsmith_project_id}</p>` : ''}
            <div style="margin-top:8px;">${sourceItems}</div>
          </div>
        </details>
      `;
    }

    loadingMsg.querySelector('.text').innerHTML = answerText + sourcesHtml;

  } catch (error) {
    loadingMsg.querySelector('.text').innerHTML = `<span style="color: red;">Error: ${error.message}</span>`;
  }
});

// --- Interests / Cards Logic ---
// --- Interests / Cards Logic ---
async function fetchInterests() {
  cardsContainer.innerHTML = "<p>Loading recent content...</p>";
  try {
    const response = await fetch("/api/content?limit=20&offset=0");
    const data = await response.json();
    
    // Robustly hunt down the array, no matter how the backend wraps it
    let items = [];
    if (Array.isArray(data)) {
      items = data;
    } else if (data && Array.isArray(data.items)) {
      items = data.items;
    } else if (data && data.data && Array.isArray(data.data.items)) {
      items = data.data.items;
    } else if (data && Array.isArray(data.data)) {
      items = data.data;
    } else {
      throw new Error("Could not find an array of items in the response payload. Check the console for the raw data structure.");
    }
    
    if (items.length === 0) {
      cardsContainer.innerHTML = "<p>No resources found. Add some!</p>";
      return;
    }

    cardsContainer.innerHTML = "";
    items.forEach(item => {
      const title = item.title || "Untitled";
      const summary = (item.summaries && item.summaries.short) ? item.summaries.short : "No summary available.";
      const sourceType = item.source_name || "Resource";
      
      // Fallback date handling just in case a record is missing it
      const dateStr = item.created_at ? new Date(item.created_at).toLocaleDateString() : "";
      
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div class="card-title">${title}</div>
        <div class="card-summary">${summary}</div>
        <div class="card-meta">${sourceType} ${dateStr ? '• ' + dateStr : ''}</div>
      `;
      cardsContainer.appendChild(card);
    });
  } catch (error) {
    cardsContainer.innerHTML = `<p style="color:red;">Failed to load: ${error.message}</p>`;
    // Log the actual error to the console so we can see what the backend is really sending
    console.error("Fetch Interests Error. Raw response might not match expectations:", error); 
  }
}

// --- Add Resource Modal Logic ---
btnOpenAdd.addEventListener("click", () => {
  addModal.classList.remove("hidden");
  ingestResult.textContent = "";
});

btnCloseModal.addEventListener("click", () => {
  addModal.classList.add("hidden");
});

// Close when clicking outside modal content
addModal.addEventListener("click", (e) => {
  if (e.target === addModal) addModal.classList.add("hidden");
});

resourceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const sourceType = document.getElementById("source-type").value;
  const resourceInput = document.getElementById("resource-input").value.trim();
  
  const [url, payload] = endpointFor(sourceType, resourceInput);

  ingestResult.textContent = "Ingesting resource... Please wait.";
  ingestResult.style.color = "var(--text-muted)";
  
  const submitBtn = document.getElementById("ingest-submit-btn");
  submitBtn.disabled = true;

  try {
    await postJson(url, payload);
    ingestResult.textContent = "Resource added successfully!";
    ingestResult.style.color = "green";
    document.getElementById("resource-input").value = "";
    
    // Refresh the content list seamlessly
    fetchInterests();
    
    // Auto-close after a short delay
    setTimeout(() => { addModal.classList.add("hidden"); }, 1500);
  } catch (error) {
    ingestResult.textContent = `Error: ${error.message}`;
    ingestResult.style.color = "red";
  } finally {
    submitBtn.disabled = false;
  }
});

// Initialize on load
switchView("chat");
// --- Suggestion Logic ---
const suggestionChip = document.getElementById("suggestion-chip");
const btnSuggestYes = document.getElementById("btn-suggest-yes");
const btnSuggestNo = document.getElementById("btn-suggest-no");

// Function to trigger a question programmatically
async function handleAutoPrompt(promptText) {
  // Hide the suggestion UI
  suggestionChip.style.display = "none";
  
  // Reuse our existing logic: append user message then call API
  appendMessage("user", promptText);
  const loadingMsg = appendMessage("ai", "<em>Generating weekly summary...</em>");

  try {
    const response = await postJson("/api/ask", { question: promptText, top_k: 10 });
    const data = response.data || response;
    
    let answerText = data.answer || "I couldn't generate a summary at this time.";
    
    // Construct sources if available (same as our askForm logic)
    let sourcesHtml = "";
    if (data.sources && data.sources.length > 0) {
      const sourceItems = data.sources.map(s => 
        `<div class="source-item">
          <a href="${s.link || '#'}" target="_blank">${s.title || 'Source'}</a>
        </div>`
      ).join("");
      
      sourcesHtml = `
        <details class="sources-accordion">
          <summary>Referenced Resources</summary>
          <div class="sources-content">${sourceItems}</div>
        </details>
      `;
    }

    loadingMsg.querySelector('.text').innerHTML = answerText + sourcesHtml;
  } catch (error) {
    loadingMsg.querySelector('.text').innerHTML = `<span style="color: red;">Error: ${error.message}</span>`;
  }
}

// Event Listeners for Suggestion Buttons
btnSuggestYes.addEventListener("click", () => {
  handleAutoPrompt("Summarise the saved resources for this week.");
});

btnSuggestNo.addEventListener("click", () => {
  // Simply hide the chip
  suggestionChip.style.opacity = "0";
  setTimeout(() => {
    suggestionChip.style.display = "none";
  }, 300);
});