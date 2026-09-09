/**
 * Continuity Guardian — Director's Room dashboard logic.
 * Talks to the real backend (api/main.py) via js/api.js.
 *
 * Run the backend first:
 *   uvicorn api.main:app --reload
 * then open this page (or serve /frontend with `python3 -m http.server`).
 */

let scenes = [];
let activeSceneId = null;

async function init() {
  bindUploadHandlers();
  bindPostprodHandlers();
  await refreshScenes();
}

function showBanner(message, type = "info") {
  const banner = document.getElementById("statusBanner");
  banner.textContent = message;
  banner.hidden = false;
  banner.className = `status-banner status-banner--${type}`;
}

function hideBanner() {
  document.getElementById("statusBanner").hidden = true;
}

/* ---------- Loading scenes from the real API ---------- */

async function refreshScenes() {
  try {
    showBanner("Loading scenes…", "loading");
    scenes = await Api.listScenes();
    hideBanner();
  } catch (err) {
    scenes = [];
    showBanner(
      `Can't reach the backend at http://localhost:8000 — is uvicorn running? (${err.message})`,
      "error"
    );
  }

  renderSceneList();

  if (scenes.length === 0) {
    document.getElementById("sceneListEmpty").hidden = false;
    return;
  }
  document.getElementById("sceneListEmpty").hidden = true;

  if (!activeSceneId || !scenes.find((s) => s.scene_id === activeSceneId)) {
    activeSceneId = scenes[0].scene_id;
  }
  function setTakeVideo(videoId, videoUrl, posterUrl) {
  const video = document.getElementById(videoId);

  if (!video) return;

  if (!videoUrl) {
    video.removeAttribute("src");
    video.hidden =
     true;
    return;
  }

  video.src = `${API_ORIGIN}${videoUrl}`;

  if (posterUrl) {
    video.poster = `${API_ORIGIN}${posterUrl}`;
  }

  video.hidden = false;
  video.load();
}
  renderActiveScene();
  renderMetrics();
}

/* ---------- Script upload ---------- */

function bindUploadHandlers() {
  document.getElementById("scriptUploadInput").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      showBanner(`Parsing "${file.name}" with the Script Agent…`, "loading");
      const result = await Api.uploadScript(file);
      document.getElementById("projectName").textContent = file.name.replace(/\.pdf$/i, "");
      showBanner(`Parsed ${result.scenes_created} scenes from the script.`, "info");
      setTimeout(hideBanner, 3000);
      await refreshScenes();
    } catch (err) {
      showBanner(`Script parsing failed: ${err.message}`, "error");
    }
    e.target.value = "";
  });

  document.querySelectorAll(".take-upload-input").forEach((input) => {
    input.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file || !activeSceneId) return;
      try {
        showBanner(`Uploading take and running Continuity Agent…`, "loading");
        await Api.uploadTake(activeSceneId, file);
        hideBanner();
        await refreshScenes();
      } catch (err) {
        showBanner(`Take upload failed: ${err.message}`, "error");
      }
      e.target.value = "";
    });
  });
}

/* ---------- Scene list (left rail) ---------- */

function riskClass(score) {
  if (score >= 6) return "risk-dot--high";
  if (score >= 3) return "risk-dot--mid";
  return "risk-dot--low";
}

function sceneRisk(scene) {
  const scores = scene.takes.map((t) => t.risk_score || 0);
  return scores.length ? Math.max(...scores) : 0;
}

function renderSceneList() {
  const list = document.getElementById("sceneListItems");
  document.getElementById("sceneCount").textContent = scenes.length;

  list.innerHTML = "";
  scenes.forEach((scene) => {
    const li = document.createElement("li");
    li.className = "scene-item" + (scene.scene_id === activeSceneId ? " active" : "");
    li.setAttribute("role", "button");
    li.setAttribute("tabindex", "0");
    li.innerHTML = `
      <span class="risk-dot ${riskClass(sceneRisk(scene))}"></span>
      <span class="scene-item-id">${scene.scene_id}</span>
      <span class="scene-item-name">${scene.location || ""}</span>
    `;
    li.addEventListener("click", () => {
      activeSceneId = scene.scene_id;
      renderSceneList();
      renderActiveScene();
    });
    list.appendChild(li);
  });
}

/* ---------- Active scene: takes + flags ---------- */

function renderActiveScene() {
  const scene = scenes.find((s) => s.scene_id === activeSceneId);
  if (!scene) return;

  document.getElementById("activeSceneTitle").textContent =
    `${scene.scene_id} — ${scene.location || "Untitled"}`;

  // Always compare the two MOST RECENT takes, not the first two —
  // this stays correct even after 3+ takes get uploaded to one scene.
  const takeA = scene.takes[scene.takes.length - 2] || scene.takes[0];
  const takeB = scene.takes[scene.takes.length - 1];
 const videoA = document.getElementById("takeFrameVideoA");
const videoB = document.getElementById("takeFrameVideoB");

if (videoA) {
  if (takeA && takeA.video_url) {
    videoA.src = takeA.video_url.startsWith("http")
      ? takeA.video_url
      : `${API_ORIGIN}${takeA.video_url}`;

    videoA.hidden = false;
    videoA.load();
  } else {
    videoA.removeAttribute("src");
    videoA.hidden = true;
  }
}

if (videoB) {
  if (takeB && takeB.video_url) {
    videoB.src = takeB.video_url.startsWith("http")
      ? takeB.video_url
      : `${API_ORIGIN}${takeB.video_url}`;

    videoB.hidden = false;
    videoB.load();
  } else {
    videoB.removeAttribute("src");
    videoB.hidden = true;
  }
}
  document.getElementById("takeAId").textContent = takeA ? takeA.take_id : "—";
  document.getElementById("takeBId").textContent = takeB ? takeB.take_id : "—";

  const frameB = document.getElementById("takeFrameB");
  const marker = document.getElementById("flagMarker");
  const flags = takeB ? takeB.continuity_flags || [] : [];

  frameB.classList.toggle("take-frame--flagged", flags.length > 0);
  marker.hidden = flags.length === 0;

  // Real frame grabs from the backend — plain "human view" for take A,
  // and the "AI view" evidence frame (grabbed at the flagged timestamp)
  // for take B whenever a flag exists, else its own plain grab.
  setTakeVideo(
  "takeFrameVideoA",
  takeA && takeA.video_url,
  takeA && takeA.thumbnail_url
);

setTakeVideo(
  "takeFrameVideoB",
  takeB && takeB.video_url,
  takeB && (takeB.evidence_thumbnail_url || takeB.thumbnail_url)
);
}
function setTakeVideo(videoId, videoUrl, posterUrl) {
  const video = document.getElementById(videoId);

  if (!video) return;

  if (!videoUrl) {
    video.removeAttribute("src");
    video.hidden = true;
    return;
  }

  let url = String(videoUrl);

  // Convert old Windows paths stored in db.json
  // into a browser URL.
  if (/^[A-Za-z]:[\\/]/.test(url)) {
    const filename = url.split(/[\\/]/).pop();
    url = `${API_ORIGIN}/uploads/takes/${encodeURIComponent(filename)}`;
  } else if (url.startsWith("/")) {
    url = `${API_ORIGIN}${url}`;
  }

  console.log("Loading video:", url);

  video.src = url;

  if (posterUrl) {
    video.poster = `${API_ORIGIN}${posterUrl}`;
  }

  video.hidden = false;

  video.onerror = () => {
    console.error("VIDEO LOAD ERROR:", video.src);
  };

  video.onloadeddata = () => {
    console.log("VIDEO LOADED:", video.src);
  };

  video.load();
}

function setTakeFrameImage(imgId, relativeUrl) {
  const img = document.getElementById(imgId);
  if (relativeUrl) {
    img.src = `${API_ORIGIN}${relativeUrl}`;
    img.hidden = false;
  } else {
    img.removeAttribute("src");
    img.hidden = true;
  }
}

function renderNotificationDraft(takeB) {
  const panel = document.getElementById("notificationDraft");
  const draft = takeB && takeB.notification_draft;
  if (!draft) {
    panel.hidden = true;
    return;
  }
  document.getElementById("notificationDraftText").textContent = draft;
  panel.hidden = false;
}

function renderFlags(flags) {
  const list = document.getElementById("flagsList");

  if (flags.length === 0) {
    list.innerHTML = `<li class="flags-empty">No continuity flags — upload a second take to run the check.</li>`;
    return;
  }

  list.innerHTML = "";
  flags.forEach((flag) => {
    const li = document.createElement("li");
    li.className = "flag-item";
    li.dataset.type = (flag.type || "").toLowerCase();
    const t = Math.round(flag.timestamp_sec || 0);
    const mins = Math.floor(t / 60);
    const secs = String(t % 60).padStart(2, "0");
    li.innerHTML = `
      <span class="flag-item-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/><path d="M12 8v5M12 16h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
      </span>
      <span class="flag-item-body">
        <span class="flag-item-meta">
          <span class="flag-item-time">${mins}:${secs}</span>
          <span class="flag-item-type">${flag.type}</span>
        </span>
        <span class="flag-item-desc">${flag.description}</span>
      </span>
    `;
    list.appendChild(li);
  });
}

/* ---------- Forced-check lock — real call to the backend ---------- */

function renderLockControl(scene) {
  const label = document.getElementById("lockStatusLabel");
  const btn = document.getElementById("lockBtn");

  if (scene.lock_status === "locked") {
    label.textContent = "Locked";
    label.style.color = "var(--teal)";
    btn.textContent = "Locked";
    btn.disabled = true;
    btn.classList.remove("ready");
    btn.onclick = null;
    return;
  }

  const latestTake = scene.takes[scene.takes.length - 1];
  const flags = latestTake ? latestTake.continuity_flags || [] : [];
  const hasTwoTakes = scene.takes.length >= 2;
  const canLock = hasTwoTakes && flags.length === 0;

  if (!hasTwoTakes) {
    label.textContent = "Upload 2 takes to check";
    label.style.color = "var(--muted)";
  } else if (canLock) {
    label.textContent = "Checks passed";
    label.style.color = "var(--teal)";
  } else {
    label.textContent = `Blocked — ${flags.length} open flag${flags.length > 1 ? "s" : ""}`;
    label.style.color = "var(--red)";
  }

  btn.disabled = !canLock;
  btn.classList.toggle("ready", canLock);
  btn.textContent = "Lock Scene";

  btn.onclick = async () => {
    if (btn.disabled) return;
    try {
      await Api.lockScene(scene.scene_id);
      await refreshScenes();
    } catch (err) {
      showBanner(`Lock rejected by orchestrator: ${err.message}`, "error");
    }
  };
}

/* ---------- Top metrics + agent rail (from real /dashboard/summary) ---------- */

async function renderMetrics() {
  try {
    const summary = await Api.dashboardSummary();
    document.getElementById("riskScoreValue").textContent =
      Math.max(0, ...summary.risk_by_day);
    document.getElementById("costAvoidedValue").textContent =
      "$" + summary.cost_avoided_usd.toLocaleString("en-US");
    document.getElementById("flagsTodayValue").textContent = summary.flags_today;
    document.getElementById("scenesLockedValue").textContent =
      `${summary.scenes_locked} / ${summary.scenes_total}`;
    drawRiskTrend(summary.risk_by_day);
  } catch (err) {
    // dashboard metrics are non-critical — fail quietly if backend hiccups
  }

  renderAgentRail();
}

function renderAgentRail() {
  const pipeline = [
    { name: "Script Agent", status: scenes.length ? "done" : "idle" },
    { name: "Continuity Agent", status: scenes.some((s) => s.takes.length >= 2) ? "done" : "idle" },
    { name: "Performance Agent", status: "idle" },
    { name: "Budget Agent", status: "idle" },
    { name: "Previz Agent", status: "idle" },
    { name: "Score Agent", status: "idle" },
    { name: "Localization Agent", status: "idle" },
    { name: "Accessibility Agent", status: "idle" },
  ];

  const agentVisuals = {
    "Script Agent": { color: "#4F8EF7", icon: `<path d="M7 3h8l4 4v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M9 12h6M9 16h6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>` },
    "Continuity Agent": { color: "#6C5CE7", icon: `<circle cx="7" cy="7" r="2.5" stroke="currentColor" stroke-width="1.7"/><circle cx="17" cy="7" r="2.5" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="18" r="2.5" stroke="currentColor" stroke-width="1.7"/><path d="M9 8.3 11 16M15 8.3 13 16M9.3 7h5.4" stroke="currentColor" stroke-width="1.5"/>` },
    "Performance Agent": { color: "#4F8EF7", icon: `<path d="M4 19V9M10 19V5M16 19v-7M22 19H2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>` },
    "Budget Agent": { color: "#6C5CE7", icon: `<path d="M12 3v18M8 6.5c0-1.4 1.8-2.5 4-2.5s4 1.1 4 2.5-1.8 2.5-4 2.5-4 1.1-4 2.5 1.8 2.5 4 2.5 4 1.1 4 2.5-1.8 2.5-4 2.5-4-1.1-4-2.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>` },
    "Previz Agent": { color: "#22B573", icon: `<path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><circle cx="12" cy="12" r="2.6" stroke="currentColor" stroke-width="1.7"/>` },
    "Score Agent": { color: "#F0B429", icon: `<path d="m12 3 2.6 5.9L21 9.8l-4.6 4.1L17.7 21 12 17.7 6.3 21l1.3-7.1L3 9.8l6.4-.9L12 3Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>` },
    "Localization Agent": { color: "#F5934A", icon: `<circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.7"/><path d="M3.5 12h17M12 3.5c2.2 2.3 3.4 5.3 3.4 8.5s-1.2 6.2-3.4 8.5c-2.2-2.3-3.4-5.3-3.4-8.5S9.8 5.8 12 3.5Z" stroke="currentColor" stroke-width="1.7"/>` },
    "Accessibility Agent": { color: "#F0568C", icon: `<circle cx="12" cy="5" r="1.8" fill="currentColor"/><path d="M4 9.5 12 8l8 1.5M12 8v6M8 21l4-7 4 7M9 13l-3 2M15 13l3 2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>` },
  };

  const list = document.getElementById("agentList");
  list.innerHTML = "";
  pipeline.forEach((agent) => {
    const li = document.createElement("li");
    li.className = "agent-item";
    li.dataset.status = agent.status;
    const visual = agentVisuals[agent.name] || { color: "#8B87A6", icon: "" };
    li.innerHTML = `
      <span class="agent-item-icon" style="background:${visual.color}" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none">${visual.icon}</svg>
      </span>
      <span class="agent-item-status agent-item-status--${agent.status}"></span>
      <span class="agent-item-name">${agent.name}</span>
      <span class="agent-item-time">${agent.status === "done" ? "ready" : "—"}</span>
    `;
    list.appendChild(li);
  });
}

/* ---------- Risk trend chart ---------- */

function drawRiskTrend(data) {
  const canvas = document.getElementById("riskTrendCanvas");
  if (!data || data.length === 0) return;

  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = 140 * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = 140;
  const pad = 20;
  const max = 10;

  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "#E4DFFB";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(pad, h - pad);
  ctx.lineTo(w - pad, h - pad);
  ctx.stroke();

  const stepX = data.length > 1 ? (w - pad * 2) / (data.length - 1) : 0;
  const points = data.map((v, i) => ({
    x: pad + i * stepX,
    y: h - pad - (v / max) * (h - pad * 2),
  }));

  // soft fill under the line
  if (points.length > 1) {
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "rgba(108, 92, 231, 0.18)");
    grad.addColorStop(1, "rgba(108, 92, 231, 0.01)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(points[0].x, h - pad);
    points.forEach((p) => ctx.lineTo(p.x, p.y));
    ctx.lineTo(points[points.length - 1].x, h - pad);
    ctx.closePath();
    ctx.fill();
  }

  ctx.strokeStyle = "#6C5CE7";
  ctx.lineWidth = 2.5;
  ctx.lineJoin = "round";
  ctx.beginPath();
  points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.stroke();

  points.forEach((p, i) => {
    ctx.fillStyle = "#FFFFFF";
    ctx.beginPath();
    ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = data[i] >= 6 ? "#E4536B" : "#6C5CE7";
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.fillStyle = "#8B87A6";
  ctx.font = "600 11px 'Poppins', sans-serif";
  ctx.textAlign = "center";
  points.forEach((p, i) => {
    ctx.fillText(scenes[i] ? scenes[i].scene_id : `#${i + 1}`, p.x, h - 4);
  });
}

/* ---------- Post-production agent buttons ---------- */

function setPostprodOutput(id, html, isError = false) {
  const el = document.getElementById(id);
  el.innerHTML = html;
  el.classList.toggle("postprod-output--error", isError);
  el.classList.remove("postprod-output--empty");
}

async function runAgentButton(btnId, outputId, apiCall, onSuccess) {
  const btn = document.getElementById(btnId);
  if (!activeSceneId) return;
  btn.disabled = true;
  setPostprodOutput(outputId, "Running…");
  try {
    const scene = await apiCall(activeSceneId);
    onSuccess(scene);
  } catch (err) {
    setPostprodOutput(outputId, err.message, true);
  } finally {
    btn.disabled = false;
  }
}

function bindPostprodHandlers() {
  document.getElementById("runBudgetBtn").addEventListener("click", () =>
    runAgentButton("runBudgetBtn", "budgetOutput", Api.runBudget, (scene) => {
      const factors = (scene.budget_factors || []).map((f) => `<li>${f}</li>`).join("");
      setPostprodOutput(
        "budgetOutput",
        `<strong>${scene.budget_complexity_score} / 10</strong><ul>${factors}</ul>`
      );
    })
  );

  document.getElementById("runPerformanceBtn").addEventListener("click", () =>
    runAgentButton("runPerformanceBtn", "performanceOutput", Api.runPerformance, (scene) => {
      const latest = scene.takes[scene.takes.length - 1];
      const perf = latest.performance || {};
      setPostprodOutput(
        "performanceOutput",
        `<strong>Match: ${Math.round((perf.delivery_match_score || 0) * 100)}%</strong><p>${perf.notes || ""}</p>`
      );
    })
  );

  document.getElementById("runPrevizBtn").addEventListener("click", () =>
    runAgentButton("runPrevizBtn", "previzOutput", Api.runPreviz, (scene) => {
      setPostprodOutput("previzOutput", `<img src="${API_ORIGIN}${scene.storyboard_url}" alt="Storyboard" />`);
    })
  );

  document.getElementById("runScoreBtn").addEventListener("click", () =>
    runAgentButton("runScoreBtn", "scoreOutput", Api.runScore, (scene) => {
      setPostprodOutput(
        "scoreOutput",
        `<audio controls src="${API_ORIGIN}${scene.score_track_url}"></audio>`
      );
    })
  );

  document.getElementById("runLocalizationBtn").addEventListener("click", () => {
    const lang = document.getElementById("localizeLangSelect").value;
    runAgentButton(
      "runLocalizationBtn",
      "localizationOutput",
      (sceneId) => Api.runLocalization(sceneId, lang),
      (scene) => {
        const url = scene.dub_tracks[lang];
        setPostprodOutput("localizationOutput", `<audio controls src="${API_ORIGIN}${url}"></audio>`);
      }
    );
  });

  document.getElementById("runAccessibilityBtn").addEventListener("click", () =>
    runAgentButton("runAccessibilityBtn", "accessibilityOutput", Api.runAccessibility, (scene) => {
      const c = scene.captions || {};
      setPostprodOutput(
        "accessibilityOutput",
        `<strong>Captions</strong><p>${(c.en || "").replace(/\n/g, "<br>")}</p>
         <strong>Audio description</strong><p>${c.audio_description || ""}</p>
         <audio controls src="${API_ORIGIN}${c.audio_description_url}"></audio>`
      );
    })
  );
}

window.addEventListener("resize", () => renderMetrics());
document.addEventListener("DOMContentLoaded", init);
