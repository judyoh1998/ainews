/* ═══════════════════════════════════════════════
   NEKO NEWS — Frontend Application
   Wired to FastAPI backend at /api/*
   ═══════════════════════════════════════════════ */

// ── State ──
let token = localStorage.getItem('nk_token');
let currentUser = null;
let stories = [];
let quiz = [];
let cadence = 'daily';
let digestStatus = '';

// ── API helper ──
async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch('/api' + path, { ...opts, headers });
  if (res.status === 401) {
    doLogout();
    throw new Error('Session expired');
  }
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

// ── Auth ──
function showLogin() {
  document.getElementById('loginBox').style.display = 'block';
  document.getElementById('registerBox').style.display = 'none';
}
function showRegister() {
  document.getElementById('loginBox').style.display = 'none';
  document.getElementById('registerBox').style.display = 'block';
}

async function doLogin() {
  const errEl = document.getElementById('loginError');
  errEl.style.display = 'none';
  try {
    const data = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: document.getElementById('loginEmail').value,
        password: document.getElementById('loginPass').value,
      }),
    });
    token = data.token;
    currentUser = data.user;
    localStorage.setItem('nk_token', token);
    enterApp();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
  }
}

async function doRegister() {
  const errEl = document.getElementById('registerError');
  errEl.style.display = 'none';
  try {
    const data = await api('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        username: document.getElementById('regUsername').value,
        email: document.getElementById('regEmail').value,
        password: document.getElementById('regPass').value,
      }),
    });
    token = data.token;
    currentUser = data.user;
    localStorage.setItem('nk_token', token);
    enterApp();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
  }
}

function doLogout() {
  token = null;
  currentUser = null;
  localStorage.removeItem('nk_token');
  document.getElementById('authScreen').style.display = 'flex';
  document.getElementById('nkRoot').style.display = 'none';
}

// ── App entry ──
async function enterApp() {
  document.getElementById('authScreen').style.display = 'none';
  document.getElementById('nkRoot').style.display = 'block';

  // Show username
  if (currentUser) {
    document.getElementById('headerUser').textContent = currentUser.username;
  }

  // Load data in parallel
  try {
    const [digestData, quizData, cadenceData] = await Promise.all([
      api('/digest'),
      api('/quiz'),
      api('/preferences/cadence'),
    ]);

    stories = digestData.stories || [];
    digestStatus = digestData.status;
    quiz = quizData.questions || [];
    cadence = cadenceData.value || 'daily';

    buildGrid();
    buildQuiz();
    loadSources();
    loadCatalog();
    updateCadenceUI();
    initCats();
  } catch (e) {
    console.error('Failed to load app data:', e);
  }
}

// ── Difficulty config ──
const LABELS = ['easy', 'med', 'hard'];
const BADGE_TXT = ['EZ', 'MED', 'PRO'];
const BADGE_STYLES = [
  'background:linear-gradient(135deg,#fce7f3,#fbcfe8);color:#be185d;',
  'background:linear-gradient(135deg,#f472b6,#ec4899);color:#fff;',
  'background:linear-gradient(135deg,#9d174d,#831843);color:#fce7f3;',
];
const TEXT_COLORS = ['#be185d', '#ec4899', '#831843'];

// ── Build Feed Grid ──
function buildGrid() {
  const grid = document.getElementById('grid');
  grid.innerHTML = '';

  if (!stories.length) {
    grid.innerHTML = `
      <div class="nk-empty" style="grid-column:1/-1;">
        <div class="nk-empty-icon">🐱</div>
        <div class="nk-empty-text">
          No stories yet!<br>
          Go to SOURCES tab, paste a newsletter,<br>
          and hit GENERATE DIGEST.
        </div>
      </div>`;
    return;
  }

  stories.forEach((s, i) => {
    const texts = [s.easy, s.medium, s.pro];
    const tag = s.tag || s.category || '';
    const card = document.createElement('div');
    card.className = 'nk-card';
    card.innerHTML = `
      <div class="nk-slider-col">
        <span class="nk-slider-label" id="lbl${i}">easy</span>
        <input type="range" class="nk-vslider" min="0" max="2" step="1" value="0"
               id="sl${i}" oninput="onSlide(${i},this.value)">
        <span class="nk-diff-badge" id="badge${i}" style="${BADGE_STYLES[0]}">EZ</span>
      </div>
      <div class="nk-body">
        <span class="nk-tag">${tag}</span>
        ${digestStatus === 'seed' ? '<span class="nk-seed-badge">DEMO</span>' : ''}
        <div class="nk-headline">${s.headline}</div>
        <div class="nk-text" id="txt${i}">${texts[0]}</div>
      </div>`;
    // Store texts on the element for slider access
    card.dataset.texts = JSON.stringify(texts);
    grid.appendChild(card);
  });
}

function onSlide(i, val) {
  const v = parseInt(val);
  const card = document.querySelectorAll('.nk-card')[i];
  const texts = JSON.parse(card.dataset.texts);
  document.getElementById('txt' + i).textContent = texts[v];
  document.getElementById('lbl' + i).textContent = LABELS[v];
  document.getElementById('badge' + i).textContent = BADGE_TXT[v];
  document.getElementById('badge' + i).style.cssText = BADGE_STYLES[v];
  document.getElementById('txt' + i).style.color = TEXT_COLORS[v];
  spawnSparkles(document.getElementById('badge' + i));
}

// ── Build Quiz ──
function buildQuiz() {
  const wrap = document.getElementById('quiz');
  wrap.innerHTML = '';

  if (!quiz.length) {
    wrap.innerHTML = `
      <div class="nk-empty">
        <div class="nk-empty-icon">📝</div>
        <div class="nk-empty-text">No quiz available yet.</div>
      </div>`;
    return;
  }

  wrap.innerHTML = `<div class="nk-score" id="qscore" data-c="0" data-t="0">✦ TODAY'S QUIZ — ${quiz.length} QUESTIONS ✦</div>`;
  quiz.forEach((q, qi) => {
    const card = document.createElement('div');
    card.className = 'nk-quiz-card';
    card.innerHTML = `<div class="nk-quiz-q">${q.question}</div>` +
      q.options.map((o, oi) =>
        `<button class="nk-opt" onclick="pickOpt(this,${qi},${oi},${q.correct_index})">${o}</button>`
      ).join('');
    wrap.appendChild(card);
  });
  const retry = document.createElement('div');
  retry.style = 'text-align:center;margin-top:4px;';
  retry.innerHTML = `<button class="nk-cadence-btn on" onclick="buildQuiz()">RETRY ↺</button>`;
  wrap.appendChild(retry);
}

function pickOpt(btn, qi, oi, ans) {
  const card = btn.closest('.nk-quiz-card');
  if (card.dataset.done) return;
  card.dataset.done = '1';
  card.querySelectorAll('.nk-opt')[ans].classList.add('ok');
  if (oi !== ans) btn.classList.add('no');
  const el = document.getElementById('qscore');
  let c = parseInt(el.dataset.c || 0), t = parseInt(el.dataset.t || 0);
  t++; if (oi === ans) c++;
  el.dataset.c = c; el.dataset.t = t;
  el.textContent = `✦ SCORE: ${c} / ${t} ✦`;
  spawnSparkles(btn);
}

// ── Sources ──
async function loadSources() {
  try {
    const srcs = await api('/sources');
    const chips = document.getElementById('srcChips');
    chips.innerHTML = '';
    if (!srcs.length) {
      chips.innerHTML = '<div style="font-size:7px;color:#9d174d;">No sources yet. Browse the catalog above to subscribe!</div>';
      return;
    }
    srcs.forEach(s => {
      const c = document.createElement('div');
      c.className = 'nk-chip ' + (s.active ? 'active' : 'inactive');
      const typeIcon = s.source_type === 'rss' ? '\u{1F4E1} ' : '';
      c.textContent = typeIcon + s.name;
      c.onclick = () => toggleSource(s.id, !s.active, c);
      chips.appendChild(c);
    });
  } catch (e) {
    console.error('Failed to load sources:', e);
  }
}

async function toggleSource(id, active, el) {
  try {
    await api(`/sources/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ active }),
    });
    el.className = 'nk-chip ' + (active ? 'active' : 'inactive');
  } catch (e) {
    console.error('Failed to toggle source:', e);
  }
}

async function applySourceChanges() {
  const statusEl = document.getElementById('fetchStatus');
  const btn = document.getElementById('applySourcesBtn');
  btn.disabled = true;
  statusEl.className = 'nk-status-msg ok';
  statusEl.textContent = 'Regenerating digest...';
  statusEl.style.display = 'inline-block';
  try {
    const gen = await api('/digest/generate', {
      method: 'POST',
      body: JSON.stringify({ force: true }),
    });
    await pollAndRefreshDigest(gen.digest_id, statusEl, '');
  } catch (e) {
    statusEl.textContent = 'Failed: ' + e.message;
    statusEl.className = 'nk-status-msg err';
  } finally {
    btn.disabled = false;
  }
}

// ── RSS Catalog ──
async function loadCatalog() {
  try {
    const catalog = await api('/sources/catalog');
    const container = document.getElementById('rssCatalog');
    container.innerHTML = '';

    const groups = {};
    catalog.forEach(entry => {
      const cat = entry.category || 'other';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(entry);
    });

    const categoryLabels = {
      news: 'NEWS OUTLETS',
      labs: 'AI LABS',
      community: 'COMMUNITY',
      research: 'RESEARCH',
      twitter: 'TWITTER/X (VIA NITTER)',
    };

    for (const [cat, entries] of Object.entries(groups)) {
      const groupDiv = document.createElement('div');
      const title = document.createElement('div');
      title.className = 'nk-catalog-group-title';
      title.textContent = categoryLabels[cat] || cat.toUpperCase();
      groupDiv.appendChild(title);

      const chipsDiv = document.createElement('div');
      chipsDiv.className = 'nk-catalog-group';

      entries.forEach(entry => {
        const chip = document.createElement('div');
        chip.className = 'nk-catalog-item ' + (entry.subscribed ? 'subscribed' : 'available');
        chip.textContent = (entry.subscribed ? '\u2713 ' : '+ ') + entry.name;
        chip.onclick = () => toggleCatalogSubscription(entry, chip);
        chipsDiv.appendChild(chip);
      });

      groupDiv.appendChild(chipsDiv);
      container.appendChild(groupDiv);
    }
  } catch (e) {
    console.error('Failed to load catalog:', e);
  }
}

async function toggleCatalogSubscription(entry, chip) {
  try {
    if (chip.classList.contains('subscribed')) {
      // Unsubscribe: find and delete this source
      const sources = await api('/sources');
      const match = sources.find(s => s.url === entry.url);
      if (match) {
        await api(`/sources/${match.id}`, { method: 'DELETE' });
      }
      chip.className = 'nk-catalog-item available';
      chip.textContent = '+ ' + entry.name;
    } else {
      // Subscribe
      await api('/sources', {
        method: 'POST',
        body: JSON.stringify({ name: entry.name, url: entry.url, source_type: 'rss' }),
      });
      chip.className = 'nk-catalog-item subscribed';
      chip.textContent = '\u2713 ' + entry.name;
    }
    loadSources();
  } catch (e) {
    if (e.message.includes('Already subscribed')) {
      chip.className = 'nk-catalog-item subscribed';
      chip.textContent = '\u2713 ' + entry.name;
    } else {
      console.error('Subscription toggle failed:', e);
    }
  }
}

// ── Custom RSS ──
async function addCustomRss() {
  const nameEl = document.getElementById('customRssName');
  const urlEl = document.getElementById('customRssUrl');
  const url = urlEl.value.trim();
  if (!url) return;
  const name = nameEl.value.trim() || new URL(url).hostname;

  try {
    await api('/sources', {
      method: 'POST',
      body: JSON.stringify({ name, url, source_type: 'rss' }),
    });
    nameEl.value = '';
    urlEl.value = '';
    loadSources();
    loadCatalog();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Fetch RSS ──
async function doFetchRss() {
  await _fetchRss(false);
}

async function doForceRefetch() {
  if (!confirm('This clears all previously fetched articles and re-downloads everything. Continue?')) return;
  await _fetchRss(true);
}

async function _fetchRss(force) {
  const btn = document.getElementById('fetchBtn');
  const forceBtn = document.getElementById('forceFetchBtn');
  const statusEl = document.getElementById('fetchStatus');
  const errorsEl = document.getElementById('fetchErrors');
  btn.disabled = true;
  forceBtn.disabled = true;
  errorsEl.style.display = 'none';
  statusEl.className = 'nk-status-msg ok';
  statusEl.textContent = force ? 'Force re-fetching all feeds...' : 'Fetching feeds...';
  statusEl.style.display = 'inline-block';

  try {
    const result = await api('/sources/fetch?force=' + force, { method: 'POST' });
    let msg = `${result.total_new} new, ${result.total_skipped} skipped from ${result.sources_fetched} feeds.`;

    // Show per-source errors
    if (result.errors.length > 0) {
      msg += ` (${result.errors.length} failed)`;
      errorsEl.innerHTML = result.errors.map(e => '&bull; ' + e).join('<br>');
      errorsEl.style.display = 'block';
    }

    if (result.total_new > 0) {
      statusEl.textContent = msg + ' Generating digest...';
      try {
        const gen = await api('/digest/generate', {
          method: 'POST',
          body: JSON.stringify({ force: true }),
        });
        await pollAndRefreshDigest(gen.digest_id, statusEl, msg);
      } catch (e) {
        statusEl.textContent = msg + ' Digest generation failed: ' + e.message;
        statusEl.className = 'nk-status-msg err';
      }
    } else {
      statusEl.textContent = msg + ' No new articles — digest unchanged.';
      statusEl.className = 'nk-status-msg ok';
    }
  } catch (e) {
    statusEl.textContent = 'Fetch error: ' + e.message;
    statusEl.className = 'nk-status-msg err';
  } finally {
    btn.disabled = false;
    forceBtn.disabled = false;
  }
}

// ── Cadence ──
function updateCadenceUI() {
  document.querySelectorAll('.nk-cadence-btn').forEach(btn => {
    btn.classList.toggle('on', btn.dataset.val === cadence);
  });
}

async function setCadence(val) {
  try {
    await api('/preferences/cadence', {
      method: 'PUT',
      body: JSON.stringify({ value: val }),
    });
    cadence = val;
    updateCadenceUI();
  } catch (e) {
    console.error('Failed to set cadence:', e);
  }
}

// ── Ingest ──
async function doIngest() {
  const text = document.getElementById('ingestText').value.trim();
  if (!text) return;

  const statusEl = document.getElementById('ingestStatus');
  const btn = document.getElementById('ingestBtn');
  btn.disabled = true;
  statusEl.className = 'nk-status-msg';
  statusEl.style.display = 'none';

  try {
    const contentType = text.trim().startsWith('<') ? 'html' : 'text';
    const data = await api('/ingest', {
      method: 'POST',
      body: JSON.stringify({ content: text, content_type: contentType }),
    });
    statusEl.textContent = `Ingested! Parsed ${data.article_count} articles.`;
    statusEl.className = 'nk-status-msg ok';
    document.getElementById('ingestText').value = '';
  } catch (e) {
    statusEl.textContent = 'Error: ' + e.message;
    statusEl.className = 'nk-status-msg err';
  } finally {
    btn.disabled = false;
  }
}

async function doGenerate() {
  const statusEl = document.getElementById('ingestStatus');
  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  statusEl.className = 'nk-status-msg ok';
  statusEl.textContent = 'Generating digest...';

  try {
    const gen = await api('/digest/generate', {
      method: 'POST',
      body: JSON.stringify({ force: true }),
    });
    await pollAndRefreshDigest(gen.digest_id, statusEl, '');
    switchTab('feed', document.querySelector('.nk-tab'));
  } catch (e) {
    statusEl.textContent = 'Error: ' + e.message;
    statusEl.className = 'nk-status-msg err';
  } finally {
    btn.disabled = false;
  }
}

// ── Poll for digest completion then refresh feed ──
async function pollAndRefreshDigest(digestId, statusEl, msgPrefix) {
  const maxAttempts = 30;  // 30 x 2s = 60s max
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 2000));
    try {
      const status = await api(`/digest/status/${digestId}`);
      if (status.status === 'complete' || status.status === 'partial') {
        // Done — refresh feed and quiz
        const [digestData, quizData] = await Promise.all([
          api('/digest'),
          api('/quiz'),
        ]);
        stories = digestData.stories || [];
        digestStatus = digestData.status;
        quiz = quizData.questions || [];
        buildGrid();
        buildQuiz();
        statusEl.textContent = msgPrefix + ` Digest updated with ${stories.length} stories!`;
        statusEl.className = 'nk-status-msg ok';
        return;
      } else if (status.status === 'failed') {
        statusEl.textContent = msgPrefix + ' Digest generation failed.';
        statusEl.className = 'nk-status-msg err';
        return;
      }
      // Still generating — update dots
      statusEl.textContent = msgPrefix + ' Generating digest' + '.'.repeat((i % 3) + 1);
    } catch (e) {
      // Poll error, keep trying
    }
  }
  statusEl.textContent = msgPrefix + ' Digest is still generating. Refresh the page in a moment.';
}

// ── Tab Switching ──
function switchTab(tab, btn) {
  ['feed', 'quiz', 'src'].forEach(t => {
    document.getElementById(t).style.display = 'none';
  });
  const el = document.getElementById(tab);
  el.style.display = tab === 'quiz' ? 'flex' : 'block';
  document.querySelectorAll('.nk-tab').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
}

// ── Sparkle Burst ──
function spawnSparkles(el) {
  const rootEl = document.getElementById('nkRoot');
  const rr = rootEl.getBoundingClientRect();
  const er = el.getBoundingClientRect();
  for (let k = 0; k < 5; k++) {
    const sp = document.createElement('div');
    sp.className = 'nk-sparkle';
    sp.style.left = (er.left - rr.left + Math.random() * 20 - 10) + 'px';
    sp.style.top = (er.top - rr.top + Math.random() * 10) + 'px';
    sp.style.animationDuration = (0.8 + Math.random() * 0.6) + 's';
    sp.style.animationDelay = (Math.random() * 0.3) + 's';
    sp.innerHTML = `<svg width="6" height="6" viewBox="0 0 6 6"><path d="M3 0L3.5 2.5L6 3L3.5 3.5L3 6L2.5 3.5L0 3L2.5 2.5Z" fill="#ec4899"/></svg>`;
    rootEl.appendChild(sp);
    setTimeout(() => sp.remove(), 1400);
  }
}

/* ═══════════════════════════════════════════════
   PIXEL CAT RENDERER
   ═══════════════════════════════════════════════ */
const PINKS = [
  { body: '#f9a8d4', ol: '#be185d', eye: '#831843', nose: '#fce7f3' },
  { body: '#fce7f3', ol: '#ec4899', eye: '#9d174d', nose: '#fbcfe8' },
  { body: '#f472b6', ol: '#9d174d', eye: '#fdf2f8', nose: '#fce7f3' },
  { body: '#ec4899', ol: '#831843', eye: '#fde68a', nose: '#fce7f3' },
];

let cvs, ctx2, cats = [];

function initCats() {
  cvs = document.getElementById('catCvs');
  ctx2 = cvs.getContext('2d');
  resizeCvs();
  window.addEventListener('resize', resizeCvs);

  cats = PINKS.map((c, i) => ({
    x: 50 + i * 120,
    y: 200 + (i % 2) * 80,
    vx: (0.5 + Math.random() * 0.6) * (i % 2 === 0 ? 1 : -1),
    vy: 0,
    frame: 0,
    ft: 0,
    hop: 40 + i * 30,
    c,
  }));

  animCats();
}

function resizeCvs() {
  if (!cvs) return;
  const r = document.getElementById('nkRoot');
  cvs.width = r.offsetWidth;
  cvs.height = r.offsetHeight;
}

function drawCat(cx, cy, c, frame) {
  const S = 3;
  ctx2.imageSmoothingEnabled = false;
  function px(x, y, col) {
    ctx2.fillStyle = col;
    ctx2.fillRect(cx + x * S, cy + y * S, S, S);
  }
  const eH = frame === 0 ? 0 : -1;

  [[2, 1], [3, 1], [7, 1], [8, 1]].forEach(([x, y]) => {
    px(x, y + eH, c.ol);
    px(x, y + eH + 1, c.body);
  });
  for (let x = 1; x <= 9; x++) px(x, 2, x === 1 || x === 9 ? c.ol : c.body);
  [0, 10].forEach(x => px(x, 3, c.ol));
  for (let x = 1; x <= 9; x++) px(x, 3, c.body);
  [0, 10].forEach(x => px(x, 4, c.ol));
  for (let x = 1; x <= 9; x++) px(x, 4, c.body);
  [2, 3, 7, 8].forEach(x => px(x, 3, c.eye));
  px(5, 4, c.nose);
  [0, 10].forEach(x => px(x, 5, c.ol));
  for (let x = 1; x <= 9; x++) px(x, 5, c.body);
  for (let x = 1; x <= 9; x++) px(x, 6, x === 1 || x === 9 ? c.ol : c.body);
  [1, 9].forEach(x => px(x, 7, c.ol));
  [2, 3, 4, 6, 7, 8].forEach(x => px(x, 7, c.body));
  [1, 2, 4, 6, 8, 9].forEach(x => px(x, 8, c.ol));
  [3, 7].forEach(x => px(x, 8, c.body));
  const tx = frame === 0 ? 11 : 10;
  px(tx, 5, c.ol); px(tx + 1, 4, c.ol); px(tx + 1, 5, c.body); px(tx + 2, 3, c.ol);
}

function animCats() {
  if (!cvs) return;
  const W = cvs.width, H = cvs.height;
  ctx2.clearRect(0, 0, W, H);
  cats.forEach(cat => {
    cat.ft++;
    if (cat.ft > 14) { cat.frame = 1 - cat.frame; cat.ft = 0; }
    cat.hop--;
    if (cat.hop <= 0) { cat.vy = -3.5; cat.hop = 70 + Math.random() * 90; }
    cat.vy += 0.22;
    cat.x += cat.vx;
    cat.y += cat.vy;
    if (cat.y > H - 55) { cat.y = H - 55; cat.vy = 0; }
    if (cat.y < 55) { cat.y = 55; cat.vy = 0; }
    if (cat.x < 8) { cat.x = 8; cat.vx *= -1; }
    if (cat.x > W - 55) { cat.x = W - 55; cat.vx *= -1; }
    drawCat(Math.round(cat.x), Math.round(cat.y), cat.c, cat.frame);
  });
  requestAnimationFrame(animCats);
}

/* ═══════════════════════════════════════════════
   INIT — check for existing token
   ═══════════════════════════════════════════════ */
(async function init() {
  if (token) {
    try {
      const user = await api('/auth/me');
      currentUser = user;
      enterApp();
    } catch (e) {
      // Token expired
      doLogout();
    }
  }
})();
