/**
 * Enterprise Business Assistant — Executive Multi-Theme Frontend
 * Designed for non-technical business users with friendly terminology,
 * instant Light/Dark theme switching, interactive charts, and guide popovers.
 */

// Application State
const state = {
  conversationId: localStorage.getItem('mcp_conversation_id') || generateUUID(),
  theme: localStorage.getItem('mcp_theme') || 'dark',
  messages: [],
  activeChartInstances: {},
  isAnalyzing: false,
};

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const welcomeHero = document.getElementById('welcome-hero');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const clearChatBtn = document.getElementById('clear-chat-btn');
const historyList = document.getElementById('history-list');
const themeToggleBtn = document.getElementById('theme-toggle-btn');
const themeIconSun = document.getElementById('theme-icon-sun');
const themeIconMoon = document.getElementById('theme-icon-moon');
const helpBtn = document.getElementById('help-btn');
const guideModal = document.getElementById('guide-modal');
const modalCloseBtn = document.getElementById('modal-close-btn');
const modalGotItBtn = document.getElementById('modal-got-it-btn');

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initEventListeners();
  checkSystemHealth();
  renderSessionHistory();
});

// Theme Management (Light / Dark)
function initTheme() {
  applyTheme(state.theme);
}

function applyTheme(newTheme) {
  state.theme = newTheme;
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('mcp_theme', newTheme);

  if (newTheme === 'light') {
    themeIconSun.style.display = 'none';
    themeIconMoon.style.display = 'block';
    themeToggleBtn.setAttribute('title', 'Switch to Dark Theme');
  } else {
    themeIconSun.style.display = 'block';
    themeIconMoon.style.display = 'none';
    themeToggleBtn.setAttribute('title', 'Switch to Light Theme');
  }

  // Update chart visual styles dynamically
  updateAllChartsTheme();
}

function toggleTheme() {
  const nextTheme = state.theme === 'dark' ? 'light' : 'dark';
  applyTheme(nextTheme);
}

function updateAllChartsTheme() {
  const isLight = state.theme === 'light';
  const tickColor = isLight ? '#475569' : '#94a3b8';
  const gridColor = isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.05)';
  const tooltipBg = isLight ? '#ffffff' : '#0f172a';
  const tooltipTitle = isLight ? '#0f172a' : '#f8fafc';
  const tooltipBody = isLight ? '#4f46e5' : '#38bdf8';
  const tooltipBorder = isLight ? '#e2e8f0' : 'rgba(255, 255, 255, 0.1)';

  Object.values(state.activeChartInstances).forEach((chart) => {
    if (chart && chart.options) {
      if (chart.options.scales) {
        if (chart.options.scales.x) {
          chart.options.scales.x.ticks.color = tickColor;
          chart.options.scales.x.grid.color = gridColor;
        }
        if (chart.options.scales.y) {
          chart.options.scales.y.ticks.color = tickColor;
          chart.options.scales.y.grid.color = gridColor;
        }
      }
      if (chart.options.plugins && chart.options.plugins.tooltip) {
        chart.options.plugins.tooltip.backgroundColor = tooltipBg;
        chart.options.plugins.tooltip.titleColor = tooltipTitle;
        chart.options.plugins.tooltip.bodyColor = tooltipBody;
        chart.options.plugins.tooltip.borderColor = tooltipBorder;
      }
      chart.update();
    }
  });
}

function initEventListeners() {
  // Theme Toggle Button
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', toggleTheme);
  }

  // Guide Modal
  if (helpBtn) {
    helpBtn.addEventListener('click', () => (guideModal.style.display = 'flex'));
  }
  if (modalCloseBtn) {
    modalCloseBtn.addEventListener('click', () => (guideModal.style.display = 'none'));
  }
  if (modalGotItBtn) {
    modalGotItBtn.addEventListener('click', () => (guideModal.style.display = 'none'));
  }
  if (guideModal) {
    guideModal.addEventListener('click', (e) => {
      if (e.target === guideModal) guideModal.style.display = 'none';
    });
  }

  // Multiline Textarea auto-growth & key handling
  userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 180) + 'px';
    sendBtn.disabled = !userInput.value.trim() || state.isAnalyzing;
  });

  userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) {
        submitQuery(userInput.value.trim());
      }
    }
  });

  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!sendBtn.disabled) {
      submitQuery(userInput.value.trim());
    }
  });

  // Action Buttons
  newChatBtn.addEventListener('click', startNewSession);
  clearChatBtn.addEventListener('click', clearCurrentMessages);

  // Suggestion Chips
  document.querySelectorAll('.chip, .hero-card').forEach((el) => {
    el.addEventListener('click', () => {
      const prompt = el.getAttribute('data-prompt');
      if (prompt) {
        userInput.value = prompt;
        userInput.style.height = 'auto';
        userInput.style.height = userInput.scrollHeight + 'px';
        sendBtn.disabled = false;
        submitQuery(prompt);
      }
    });
  });
}

function startNewSession() {
  state.conversationId = generateUUID();
  localStorage.setItem('mcp_conversation_id', state.conversationId);
  clearCurrentMessages();
  saveSessionToHistory('New Question');
  renderSessionHistory();
}

function clearCurrentMessages() {
  chatMessages.innerHTML = '';
  chatMessages.appendChild(welcomeHero);
  welcomeHero.style.display = 'block';
  state.messages = [];
  // Destroy existing chart instances
  Object.values(state.activeChartInstances).forEach((chart) => chart.destroy());
  state.activeChartInstances = {};
}

// Submit Natural Language Business Query
async function submitQuery(queryText) {
  if (!queryText || state.isAnalyzing) return;

  state.isAnalyzing = true;
  sendBtn.disabled = true;
  userInput.value = '';
  userInput.style.height = 'auto';

  // Hide welcome hero if visible
  if (welcomeHero && welcomeHero.style.display !== 'none') {
    welcomeHero.style.display = 'none';
  }

  // 1. Render User Message
  appendUserMessage(queryText);
  saveSessionToHistory(queryText.slice(0, 32));

  // 2. Render Loading Indicator
  const loadingElement = appendLoadingIndicator();
  scrollToBottom();

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: queryText,
        conversation_id: state.conversationId,
      }),
    });

    if (!response.ok) {
      throw new Error(`Server responded with status: ${response.status}`);
    }

    const data = await response.json();
    loadingElement.remove();

    // 3. Render Grounded AI Response
    appendAIMessage(data);
  } catch (error) {
    loadingElement.remove();
    appendErrorMessage(
      `We encountered an issue looking up company records: ${error.message}. Please verify the system is online and try again.`
    );
  } finally {
    state.isAnalyzing = false;
    sendBtn.disabled = !userInput.value.trim();
    scrollToBottom();
  }
}

// Render User Message Bubble
function appendUserMessage(text) {
  const row = document.createElement('div');
  row.className = 'message-row user';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = text;

  row.appendChild(bubble);
  chatMessages.appendChild(row);
  scrollToBottom();
}

// Render Loading Dots
function appendLoadingIndicator() {
  const row = document.createElement('div');
  row.className = 'message-row ai';

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar avatar-ai';
  avatar.innerHTML = 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.innerHTML = `
    <div class="loading-indicator">
      <div class="dot"></div>
      <div class="dot"></div>
      <div class="dot"></div>
      <span style="font-size: 0.85rem; color: var(--text-muted); margin-left: 6px;">Looking up verified company data...</span>
    </div>
  `;

  row.appendChild(avatar);
  row.appendChild(bubble);
  chatMessages.appendChild(row);
  return row;
}

// Render AI Response Bubble with Charts, Tables & Sources
function appendAIMessage(payload) {
  const row = document.createElement('div');
  row.className = 'message-row ai';

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar avatar-ai';
  avatar.innerHTML = 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';

  const content = document.createElement('div');
  content.className = 'message-content';

  // Format Markdown Text
  const formattedHtml = parseMarkdown(payload.answer);
  content.innerHTML = formattedHtml;

  // 1. Render Visualization if available
  if (payload.visualization) {
    const visEl = renderVisualization(payload.visualization);
    if (visEl) content.appendChild(visEl);
  }

  // 2. Render Structured Data Table if present and has > 1 row
  if (payload.data && Array.isArray(payload.data) && payload.data.length > 0) {
    const tableContainerId = 'table-' + generateUUID();
    const tableEl = renderDataTable(payload.data, tableContainerId);
    if (tableEl) content.appendChild(tableEl);
  }

  // 3. Render Source Citations & Copy Action
  if (payload.sources && payload.sources.length > 0) {
    const sourcesEl = renderSourcesBar(payload.sources, payload.answer);
    content.appendChild(sourcesEl);
  }

  bubble.appendChild(content);
  row.appendChild(avatar);
  row.appendChild(bubble);
  chatMessages.appendChild(row);
  scrollToBottom();
}

function appendErrorMessage(errorText) {
  const row = document.createElement('div');
  row.className = 'message-row ai';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.style.borderColor = 'rgba(239, 68, 68, 0.4)';
  bubble.style.backgroundColor = 'rgba(239, 68, 68, 0.08)';

  bubble.innerHTML = `
    <div style="color: #ef4444; font-weight: 500;">
      ⚠️ ${escapeHtml(errorText)}
    </div>
  `;

  row.appendChild(bubble);
  chatMessages.appendChild(row);
  scrollToBottom();
}

// Interactive Visualization Renderer with Dynamic Theme Support
function renderVisualization(vis) {
  const container = document.createElement('div');
  container.className = 'vis-container';

  if (vis.type === 'kpi') {
    container.innerHTML = `
      <div class="kpi-card">
        <div class="kpi-label">${escapeHtml(vis.title || vis.kpi_label || 'Key Metric')}</div>
        <div class="kpi-value">${escapeHtml(String(vis.kpi_value))}</div>
      </div>
    `;
    return container;
  }

  const canvasId = 'chart-' + generateUUID();
  container.innerHTML = `
    <div class="vis-header">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="20" x2="18" y2="10"></line>
        <line x1="12" y1="20" x2="12" y2="4"></line>
        <line x1="6" y1="20" x2="6" y2="14"></line>
      </svg>
      <span>${escapeHtml(vis.title || 'Data Chart')}</span>
    </div>
    <div class="chart-wrapper">
      <canvas id="${canvasId}"></canvas>
    </div>
  `;

  // Render Chart via Chart.js once element is in DOM
  setTimeout(() => {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const isLight = state.theme === 'light';
    const isLine = vis.type === 'line';

    const bgGradient = ctx.createLinearGradient(0, 0, 0, 240);
    if (isLight) {
      bgGradient.addColorStop(0, 'rgba(79, 70, 229, 0.85)');
      bgGradient.addColorStop(1, 'rgba(2, 132, 199, 0.25)');
    } else {
      bgGradient.addColorStop(0, 'rgba(79, 70, 229, 0.85)');
      bgGradient.addColorStop(1, 'rgba(6, 182, 212, 0.2)');
    }

    const tickColor = isLight ? '#475569' : '#94a3b8';
    const gridColor = isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.05)';
    const tooltipBg = isLight ? '#ffffff' : '#0f172a';
    const tooltipTitle = isLight ? '#0f172a' : '#f8fafc';
    const tooltipBody = isLight ? '#4f46e5' : '#38bdf8';
    const tooltipBorder = isLight ? '#e2e8f0' : 'rgba(255, 255, 255, 0.1)';

    const chartInstance = new Chart(ctx, {
      type: isLine ? 'line' : 'bar',
      data: {
        labels: vis.x || [],
        datasets: [
          {
            label: vis.title || 'Revenue ($)',
            data: vis.y || [],
            backgroundColor: isLine ? (isLight ? 'rgba(79, 70, 229, 0.1)' : 'rgba(79, 70, 229, 0.2)') : bgGradient,
            borderColor: isLight ? '#4f46e5' : '#38bdf8',
            borderWidth: 2,
            tension: 0.35,
            fill: isLine,
            pointBackgroundColor: isLight ? '#4f46e5' : '#38bdf8',
            pointRadius: isLine ? 4 : 0,
            borderRadius: isLine ? 0 : 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: tooltipBg,
            titleColor: tooltipTitle,
            bodyColor: tooltipBody,
            borderColor: tooltipBorder,
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (ctx) => ` Revenue: $${Number(ctx.parsed.y).toLocaleString()}`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: gridColor },
            ticks: { color: tickColor, font: { size: 11, family: 'Inter' } },
          },
          y: {
            grid: { color: gridColor },
            ticks: {
              color: tickColor,
              font: { size: 11, family: 'Inter' },
              callback: (val) => '$' + Number(val).toLocaleString(),
            },
          },
        },
      },
    });

    state.activeChartInstances[canvasId] = chartInstance;
  }, 60);

  return container;
}

// Structured Data Table Renderer (with Toggle for Non-Tech Users)
function renderDataTable(rows, containerId) {
  if (!rows || rows.length === 0) return null;
  const container = document.createElement('div');
  container.className = 'table-container';
  container.id = containerId;

  const table = document.createElement('table');
  table.className = 'data-table';

  const keys = Object.keys(rows[0]).slice(0, 6); // Max 6 columns for clean display

  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  keys.forEach((key) => {
    const th = document.createElement('th');
    th.textContent = formatColumnHeader(key);
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  rows.slice(0, 10).forEach((row) => {
    const tr = document.createElement('tr');
    keys.forEach((key) => {
      const td = document.createElement('td');
      let val = row[key];
      if (typeof val === 'number') {
        val = Number.isInteger(val) ? val.toLocaleString() : '$' + val.toLocaleString(undefined, { minimumFractionDigits: 2 });
      }
      td.textContent = val !== null && val !== undefined ? val : '—';
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.appendChild(table);

  return container;
}

// Friendly non-tech Column Header formatter
function formatColumnHeader(key) {
  const map = {
    region_name: 'Region',
    total_revenue: 'Total Revenue',
    monthly_revenue: 'Monthly Revenue',
    customer_segment: 'Customer Segment',
    customer_name: 'Customer Name',
    product_name: 'Product Name',
    product_category: 'Category',
    order_count: 'Orders',
    customer_count: 'Customers',
    units_sold: 'Units Sold',
    total_spent: 'Total Spent',
    total_completed_orders: 'Completed Orders',
    active_customers: 'Active Customers',
    avg_order_value: 'Average Order Value',
    month: 'Month',
  };
  return map[key] || key.replace(/_/g, ' ');
}

// Friendly Source Citation Badges & Copy Summary Action
function renderSourcesBar(sources, rawAnswer) {
  const bar = document.createElement('div');
  bar.className = 'sources-bar';

  const left = document.createElement('div');
  left.className = 'sources-left';

  const label = document.createElement('span');
  label.className = 'sources-label';
  label.textContent = 'Verified Evidence:';
  left.appendChild(label);

  sources.forEach((src) => {
    const badge = document.createElement('span');
    badge.className = `source-badge ${src.type}`;
    if (src.type === 'mysql') {
      badge.textContent = '📊 Sales Database (Verified)';
    } else {
      const docTitle = src.name || 'Company Policy';
      badge.textContent = `📄 ${docTitle}`;
    }
    left.appendChild(badge);
  });

  bar.appendChild(left);

  // Message Actions (Copy Summary)
  const actions = document.createElement('div');
  actions.className = 'message-actions';

  const copyBtn = document.createElement('button');
  copyBtn.className = 'action-chip-btn';
  copyBtn.innerHTML = '📋 Copy Summary';
  copyBtn.title = 'Copy summary to clipboard';
  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(rawAnswer).then(() => {
      copyBtn.innerHTML = '✓ Copied!';
      setTimeout(() => (copyBtn.innerHTML = '📋 Copy Summary'), 2000);
    });
  });
  actions.appendChild(copyBtn);

  bar.appendChild(actions);

  return bar;
}

// Markdown Parser Helper
function parseMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Bold **text**
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italic *text*
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Bullet lists
  html = html.replace(/^\s*-\s+(.*)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
  // Newlines
  html = html.replace(/\n\n/g, '</p><p>');
  html = html.replace(/\n/g, '<br>');

  return `<p>${html}</p>`;
}

function escapeHtml(string) {
  const entityMap = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };
  return String(string).replace(/[&<>"']/g, (s) => entityMap[s]);
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// System Health Poller
async function checkSystemHealth() {
  try {
    const res = await fetch('/health');
    if (!res.ok) return;
    const data = await res.json();
    const comps = data.components || {};

    const mysqlInd = document.getElementById('mysql-indicator');
    const chromaInd = document.getElementById('chroma-indicator');

    if (mysqlInd && comps.mysql === 'healthy') {
      mysqlInd.classList.add('online');
    }
    if (chromaInd && comps.chromadb === 'healthy') {
      chromaInd.classList.add('online');
    }
  } catch (e) {
    console.debug('Health check offline:', e);
  }
}

// Local Session History Management
function saveSessionToHistory(title) {
  let sessions = JSON.parse(localStorage.getItem('mcp_sessions') || '[]');
  const existing = sessions.find((s) => s.id === state.conversationId);
  if (existing) {
    existing.title = title;
    existing.timestamp = new Date().toISOString();
  } else {
    sessions.unshift({
      id: state.conversationId,
      title: title,
      timestamp: new Date().toISOString(),
    });
  }
  sessions = sessions.slice(0, 10);
  localStorage.setItem('mcp_sessions', JSON.stringify(sessions));
  renderSessionHistory();
}

function renderSessionHistory() {
  if (!historyList) return;
  const sessions = JSON.parse(localStorage.getItem('mcp_sessions') || '[]');
  historyList.innerHTML = '';

  if (sessions.length === 0) {
    historyList.innerHTML = `<span style="font-size:0.75rem; color:var(--text-muted); padding:6px 12px;">No previous questions</span>`;
    return;
  }

  sessions.forEach((s) => {
    const item = document.createElement('div');
    item.className = `history-item ${s.id === state.conversationId ? 'active' : ''}`;
    item.textContent = s.title || 'Question';
    item.title = s.title;
    item.addEventListener('click', () => {
      state.conversationId = s.id;
      localStorage.setItem('mcp_conversation_id', s.id);
      renderSessionHistory();
    });
    historyList.appendChild(item);
  });
}
