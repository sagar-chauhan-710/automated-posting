const form = document.getElementById("post-form");
const messageInput = document.getElementById("message");
const charCount = document.getElementById("char-count");
const submitBtn = document.getElementById("submit-btn");
const resultsList = document.getElementById("results-list");
const resultsSummary = document.getElementById("results-summary");
const toast = document.getElementById("toast");

function platformCheckboxes() {
  return Array.from(document.querySelectorAll('input[name="platforms"]'));
}

function selectedPlatforms() {
  return platformCheckboxes()
    .filter((el) => el.checked)
    .map((el) => el.value);
}

function updateCharCount() {
  charCount.textContent = `${messageInput.value.length} / 200`;
}

function showToast(text, type) {
  toast.hidden = false;
  toast.textContent = text;
  toast.className = `toast ${type}`;
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    toast.hidden = true;
  }, 4000);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderResults(payload) {
  const results = payload.results || [];
  const successCount = results.filter((r) => r.status === "success").length;

  resultsSummary.textContent = payload.success
    ? `Published to ${successCount}/${results.length} platform(s).`
    : `All ${results.length} selected platform(s) failed.`;

  if (!results.length) {
    resultsList.innerHTML = '<div class="empty-state">No results.</div>';
    return;
  }

  resultsList.innerHTML = results
    .map((item) => {
      const ok = item.status === "success";
      const meta = [];
      if (ok && item.date && item.time) meta.push(`${item.date} ${item.time} UTC`);
      if (ok) meta.push(item.public_access ? "Public" : "Not public");
      if (!ok && item.error) meta.push(item.error);

      const link = item.posted_url
        ? `<a class="result-link" href="${escapeHtml(item.posted_url)}" target="_blank" rel="noopener">Open post</a>`
        : "";

      return `
        <article class="result-card ${item.status}">
          <div class="result-top">
            <span class="result-platform">${escapeHtml(item.platform)}</span>
            <span class="badge ${item.status}">${escapeHtml(item.status)}</span>
          </div>
          <p class="result-meta">${escapeHtml(meta.join(" · ") || "-")}</p>
          ${link}
        </article>
      `;
    })
    .join("");
}

function parseError(detail) {
  if (!detail) return "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join(" ");
  return "Request failed";
}

document.getElementById("select-all").addEventListener("click", () => {
  platformCheckboxes().forEach((el) => {
    el.checked = true;
  });
});

document.getElementById("clear-all").addEventListener("click", () => {
  platformCheckboxes().forEach((el) => {
    el.checked = false;
  });
});

messageInput.addEventListener("input", updateCharCount);
updateCharCount();

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const platforms = selectedPlatforms();
  if (!platforms.length) {
    showToast("Select at least one platform", "failed");
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Publishing...";
  resultsSummary.textContent = "Publishing...";

  try {
    const response = await fetch("/posting", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: messageInput.value, platforms }),
    });
    const data = await response.json();

    if (!response.ok) {
      const msg = parseError(data.detail);
      showToast(msg, "failed");
      resultsSummary.textContent = "Validation error";
      resultsList.innerHTML = `<div class="empty-state">${escapeHtml(msg)}</div>`;
      return;
    }

    renderResults(data);
    showToast(
      data.success ? "Publish completed" : "Publish completed with failures",
      data.success ? "success" : "failed"
    );
  } catch (err) {
    showToast("Network error", "failed");
    resultsSummary.textContent = "Network error";
    resultsList.innerHTML = '<div class="empty-state">Could not reach server.</div>';
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Publish";
  }
});
