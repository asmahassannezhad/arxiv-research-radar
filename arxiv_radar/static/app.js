let state = {top: [], ignored: []};
let activeTab = "top";

const $ = (id) => document.getElementById(id);
const escapeHtml = (s="") => s.replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));

async function api(path, options={}) {
  const response = await fetch(path, {headers:{"Content-Type":"application/json"}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function update(next) {
  state = next;
  $("topCountLabel").textContent = `(${next.top.length})`;
  $("ignoredCountLabel").textContent = `(${next.ignored.length})`;
  const period = next.target_date ? `submitted on ${next.target_date}` : `over ${next.days} days`;
  $("summary").textContent = next.total ? `${next.total} papers scanned ${period} · last run ${new Date(next.last_run).toLocaleString()}` : "Run the radar to collect papers.";
  render();
}

function paperCard(p) {
  const evidence = p.evidence.length ? p.evidence.join(" · ") : "No specific match found";
  const feedback = p.feedback_rating;
  return `<article class="paper" data-paper-id="${p.arxiv_id}">
    <div class="rank">${p.rank}</div>
    <div>
      <h2>${escapeHtml(p.title)}</h2>
      <div class="meta">${escapeHtml(p.authors.join(", "))} · ${escapeHtml(p.primary_category)} · ${p.submitted.slice(0,10)}</div>
      <div class="scoreline"><span class="score">${p.score}/100</span><span class="label">${escapeHtml(p.label)}</span></div>
      <p class="abstract">${escapeHtml(p.abstract)}</p>
      <div class="evidence">${escapeHtml(evidence)}</div>
      <div class="actions">
        <a href="${p.abstract_url}" target="_blank" rel="noreferrer">arXiv</a>
        <a href="${p.pdf_url}" target="_blank" rel="noreferrer">PDF</a>
        <button class="${feedback==='very_relevant'?'selected strong':''}" onclick="rate('${p.arxiv_id}','very_relevant')">Very relevant</button>
        <button class="${feedback==='useful'?'selected':''}" onclick="rate('${p.arxiv_id}','useful')">Useful</button>
        <button class="${feedback==='save_later'?'selected':''}" onclick="rate('${p.arxiv_id}','save_later')">Save later</button>
        <button class="${feedback==='not_relevant'?'selected':''}" onclick="rate('${p.arxiv_id}','not_relevant')">Not relevant</button>
      </div>
    </div>
  </article>`;
}

function render() {
  const papers = state[activeTab] || [];
  $("paperList").innerHTML = papers.length ? papers.map(paperCard).join("") : `<div class="panel empty">Nothing here yet.</div>`;
}

async function runRadar() {
  const button = $("runButton");
  button.disabled = true;
  $("runStatus").textContent = "Reading arXiv… usually 35–60 seconds";
  try {
    const mode = $("dateMode").value;
    const now = new Date();
    const today = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0,10);
    const targetDate = mode === "today" ? today : mode === "specific" ? $("targetDate").value : null;
    if (mode === "specific" && !targetDate) throw new Error("Choose the day you want to browse.");
    const payload = {days:$("days").value, top_count:$("topCount").value};
    if (targetDate) payload.target_date = targetDate;
    update(await api("/api/run", {method:"POST", body:JSON.stringify(payload)}));
    $("runStatus").textContent = "Radar refreshed";
  } catch (error) { $("runStatus").textContent = error.message; }
  finally { button.disabled = false; }
}

async function rate(arxiv_id, rating) {
  try {
    update(await api("/api/feedback", {method:"POST", body:JSON.stringify({arxiv_id, rating})}));
    $("runStatus").textContent = rating === "not_relevant" ? "Moved outside the cut and preference learned" : rating === "very_relevant" ? "Promoted and preference learned" : "Preference saved";
  }
  catch (error) { alert(error.message); }
}

document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active")); tab.classList.add("active"); activeTab = tab.dataset.tab; render();
}));
$("dateMode").addEventListener("change", () => {
  const specific = $("dateMode").value === "specific";
  $("specificDateLabel").hidden = !specific;
  $("days").closest("label").hidden = $("dateMode").value !== "recent";
});
$("runButton").addEventListener("click", runRadar);
api("/api/status").then(update).catch(error => $("runStatus").textContent = error.message);
