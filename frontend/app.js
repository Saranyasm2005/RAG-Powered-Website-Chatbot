// Global State
let hasApiKey = false;
let pollingInterval = null;

// DOM Elements
const openSettingsBtn = document.getElementById('open-settings-btn');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const cancelSettingsBtn = document.getElementById('cancel-settings-btn');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const settingsModal = document.getElementById('settings-modal');
const groqKeyInput = document.getElementById('groq-key-input');
const toggleKeyVisibility = document.getElementById('toggle-key-visibility');

const crawlUrlInput = document.getElementById('crawl-url');
const maxPagesInput = document.getElementById('max-pages');
const crawlDepthSelect = document.getElementById('crawl-depth');
const startCrawlBtn = document.getElementById('start-crawl-btn');

const crawlingProgressCard = document.getElementById('crawling-progress-card');
const crawlStatusBadge = document.getElementById('crawl-status-badge');
const crawlMessage = document.getElementById('crawl-message');
const crawlProgressBar = document.getElementById('crawl-progress-bar');
const pagesCountSpan = document.getElementById('pages-count');
const queueCountSpan = document.getElementById('queue-count');

const dbDocCount = document.getElementById('db-doc-count');
const dbChunkCount = document.getElementById('db-chunk-count');
const sourcesList = document.getElementById('sources-list');
const clearIndexBtn = document.getElementById('clear-index-btn');

const apiStatus = document.getElementById('api-status');
const apiStatusText = document.getElementById('api-status-text');

const chatThread = document.getElementById('chat-thread');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const assistantSubtitle = document.getElementById('assistant-subtitle');

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    checkApiKeyStatus();
    loadSources();
    checkActiveCrawlTask();
    setupEventListeners();
});

// Setup Events
function setupEventListeners() {
    // Settings modal
    openSettingsBtn.addEventListener('click', openSettings);
    closeSettingsBtn.addEventListener('click', closeSettings);
    cancelSettingsBtn.addEventListener('click', closeSettings);
    saveSettingsBtn.addEventListener('click', saveSettings);
    toggleKeyVisibility.addEventListener('click', toggleKeyField);
    
    // Ingestion controls
    startCrawlBtn.addEventListener('click', startCrawl);
    clearIndexBtn.addEventListener('click', clearIndex);
    
    // Chat UI
    chatForm.addEventListener('submit', handleChatSubmit);
    chatInput.addEventListener('keydown', handleChatKeyDown);
}

// Check if Groq API key exists
async function checkApiKeyStatus() {
    try {
        const res = await fetch('/api/settings');
        const data = await res.json();
        
        hasApiKey = data.has_key;
        updateApiStatusUI(data);
    } catch (err) {
        console.error('Error checking API status:', err);
    }
}

function updateApiStatusUI(data) {
    const dot = apiStatus.querySelector('.dot');
    
    // Enable crawling controls always (since embeddings are local!)
    crawlUrlInput.removeAttribute('disabled');
    maxPagesInput.removeAttribute('disabled');
    crawlDepthSelect.removeAttribute('disabled');
    startCrawlBtn.removeAttribute('disabled');

    if (hasApiKey) {
        dot.className = 'dot green';
        apiStatusText.textContent = `Groq API Active (${data.masked_key})`;
        updateChatInputState();
    } else {
        dot.className = 'dot red';
        apiStatusText.textContent = 'Groq API Key Required';
        
        // Disable chat input
        chatInput.setAttribute('disabled', 'true');
        sendBtn.setAttribute('disabled', 'true');
        chatInput.placeholder = "Please configure your Groq API Key to chat.";
        assistantSubtitle.textContent = "Configure API Key to start";
    }
}

function updateChatInputState() {
    const chunkCount = parseInt(dbChunkCount.textContent || '0');
    if (hasApiKey && chunkCount > 0) {
        chatInput.removeAttribute('disabled');
        sendBtn.removeAttribute('disabled');
        chatInput.placeholder = "Ask something about the indexed website...";
        assistantSubtitle.textContent = "Grounding answers in your crawled pages";
    } else {
        chatInput.setAttribute('disabled', 'true');
        sendBtn.setAttribute('disabled', 'true');
        chatInput.placeholder = hasApiKey 
            ? "Please crawl a website first to activate chat." 
            : "Please configure your Groq API Key to begin.";
        assistantSubtitle.textContent = hasApiKey 
            ? "Crawl a website to start chat" 
            : "Configure API Key to start";
    }
}

// Load Index Sources
async function loadSources() {
    try {
        const res = await fetch('/api/sources');
        const data = await res.json();
        
        dbDocCount.textContent = data.total_documents;
        dbChunkCount.textContent = data.total_chunks;
        
        // Render source list
        sourcesList.innerHTML = '';
        if (data.sources.length === 0) {
            sourcesList.innerHTML = '<div class="empty-sources">No pages indexed yet.</div>';
        } else {
            data.sources.forEach(src => {
                const item = document.createElement('div');
                item.className = 'source-item';
                item.innerHTML = `
                    <div class="source-title" title="${src.title}">${src.title}</div>
                    <div class="source-meta">
                        <a href="${src.url}" class="source-url" target="_blank" title="${src.url}">${src.url}</a>
                        <span class="source-chunks">${src.chunk_count} chunks</span>
                    </div>
                `;
                sourcesList.appendChild(item);
            });
        }
        updateChatInputState();
    } catch (err) {
        console.error('Error loading index sources:', err);
    }
}

// Settings modal mechanics
function openSettings() {
    settingsModal.classList.remove('hidden');
    groqKeyInput.focus();
}

function closeSettings() {
    settingsModal.classList.add('hidden');
    groqKeyInput.value = '';
}

function toggleKeyField() {
    const isPass = groqKeyInput.type === 'password';
    groqKeyInput.type = isPass ? 'text' : 'password';
    toggleKeyVisibility.querySelector('i').className = isPass 
        ? 'fa-solid fa-eye-slash' 
        : 'fa-solid fa-eye';
}

async function saveSettings() {
    const key = groqKeyInput.value.trim();
    if (!key) {
        alert('Please enter a valid key.');
        return;
    }
    
    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ groq_api_key: key })
        });
        
        const data = await res.json();
        if (res.ok) {
            closeSettings();
            await checkApiKeyStatus();
        } else {
            alert(data.detail || 'Failed to save API key.');
        }
    } catch (err) {
        console.error('Save settings error:', err);
        alert('Failed to connect to backend.');
    }
}

// Web scraper triggers
async function startCrawl() {
    const url = crawlUrlInput.value.trim();
    if (!url) {
        alert('Please enter a website URL.');
        return;
    }
    
    startCrawlBtn.setAttribute('disabled', 'true');
    crawlingProgressCard.classList.remove('hidden');
    
    try {
        const res = await fetch('/api/crawl', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                max_pages: parseInt(maxPagesInput.value),
                depth_limit: parseInt(crawlDepthSelect.value)
            })
        });
        
        const data = await res.json();
        if (res.ok) {
            pollCrawlStatus();
        } else {
            alert(data.detail || 'Crawl request failed.');
            startCrawlBtn.removeAttribute('disabled');
            crawlingProgressCard.classList.add('hidden');
        }
    } catch (err) {
        console.error('Crawl starting error:', err);
        startCrawlBtn.removeAttribute('disabled');
    }
}

// Clear Database Index
async function clearIndex() {
    if (!confirm('Are you sure you want to delete all indexed website content? This action is irreversible.')) {
        return;
    }
    
    try {
        const res = await fetch('/api/sources/clear', { method: 'POST' });
        if (res.ok) {
            appendSystemMessage("Knowledge base database has been cleared.");
            loadSources();
            crawlingProgressCard.classList.add('hidden');
        }
    } catch (err) {
        console.error('Clear database index error:', err);
    }
}

// Poll Active Ingestion task
async function checkActiveCrawlTask() {
    try {
        const res = await fetch('/api/crawl/status');
        const data = await res.json();
        
        if (data.status === 'crawling' || data.status === 'indexing') {
            crawlingProgressCard.classList.remove('hidden');
            startCrawlBtn.setAttribute('disabled', 'true');
            pollCrawlStatus();
        }
    } catch (err) {
        console.error('Active crawl task lookup error:', err);
    }
}

function pollCrawlStatus() {
    if (pollingInterval) clearInterval(pollingInterval);
    
    pollingInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/crawl/status');
            const data = await res.json();
            
            // Render updates
            crawlStatusBadge.textContent = data.status;
            crawlStatusBadge.className = `badge ${data.status}`;
            crawlMessage.textContent = data.current_url || data.message;
            
            const maxVal = parseInt(maxPagesInput.value) || 30;
            let percent = 0;
            
            if (data.status === 'crawling') {
                percent = Math.round((data.pages_crawled / maxVal) * 100);
            } else if (data.status === 'indexing') {
                percent = 95;
            } else if (data.status === 'completed') {
                percent = 100;
            }
            
            crawlProgressBar.style.width = `${percent}%`;
            pagesCountSpan.textContent = data.pages_crawled;
            queueCountSpan.textContent = data.queue_size;
            
            if (data.status === 'completed' || data.status === 'failed') {
                clearInterval(pollingInterval);
                pollingInterval = null;
                startCrawlBtn.removeAttribute('disabled');
                
                // Refresh sources layout
                await loadSources();
                
                if (data.status === 'completed') {
                    appendSystemMessage(`Indexing Finished! <strong>${data.total_chunks} chunks</strong> were generated locally using Sentence Transformers. You can now configure your Groq key and chat about this content.`);
                } else {
                    appendSystemMessage(`Crawl operation stopped. Log details: <span style="color:var(--rose-accent)">${data.message}</span>`);
                }
            }
        } catch (err) {
            console.error('Polling tick error:', err);
            clearInterval(pollingInterval);
        }
    }, 1200);
}

// Chat functions
function appendSystemMessage(htmlText) {
    const msg = document.createElement('div');
    msg.className = 'message system-message';
    msg.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="message-content">
            <p>${htmlText}</p>
        </div>
    `;
    chatThread.appendChild(msg);
    scrollToBottom();
}

function appendUserMessage(text) {
    const msg = document.createElement('div');
    msg.className = 'message user-message';
    msg.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-user"></i></div>
        <div class="message-content">
            <p>${escapeHtml(text)}</p>
        </div>
    `;
    chatThread.appendChild(msg);
    scrollToBottom();
}

function handleChatKeyDown(e) {
    // Submit on Enter without shift key
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.requestSubmit();
    }
}

async function handleChatSubmit(e) {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;
    
    // Add user question
    appendUserMessage(query);
    chatInput.value = '';
    
    // Add temporary chatbot bubble loading
    const loaderId = 'chat-loader-' + Date.now();
    const botMsg = document.createElement('div');
    botMsg.className = 'message bot-message';
    botMsg.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="message-content" id="${loaderId}">
            <p><i class="fa-solid fa-spinner fa-spin"></i> Retrieving sources & querying Groq LLM...</p>
        </div>
    `;
    chatThread.appendChild(botMsg);
    scrollToBottom();
    
    try {
        const res = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query, top_k: 5 })
        });
        
        const data = await res.json();
        const loaderContainer = document.getElementById(loaderId);
        
        if (res.ok) {
            // Render markdown-like response
            let formattedAnswer = parseMarkdown(data.answer);
            loaderContainer.innerHTML = `<p>${formattedAnswer}</p>`;
            
            // Add citation anchors if available
            if (data.sources && data.sources.length > 0) {
                const citeContainer = document.createElement('div');
                citeContainer.className = 'citations-container';
                citeContainer.innerHTML = '<div class="citations-header">Sources Cited</div>';
                
                const linksContainer = document.createElement('div');
                linksContainer.className = 'citation-links';
                
                data.sources.forEach((src, idx) => {
                    const tag = document.createElement('a');
                    tag.className = 'citation-tag';
                    tag.href = src.url;
                    tag.target = '_blank';
                    tag.innerHTML = `<i class="fa-solid fa-link"></i> ${src.title} (${Math.round(src.score * 100)}%)`;
                    linksContainer.appendChild(tag);
                });
                
                citeContainer.appendChild(linksContainer);
                loaderContainer.appendChild(citeContainer);
            }
        } else {
            loaderContainer.innerHTML = `<p style="color:var(--rose-accent)"><i class="fa-solid fa-triangle-exclamation"></i> Error: ${data.detail || 'Failed to complete query.'}</p>`;
        }
        scrollToBottom();
    } catch (err) {
        console.error('Chat routing error:', err);
        const loaderContainer = document.getElementById(loaderId);
        if (loaderContainer) {
            loaderContainer.innerHTML = `<p style="color:var(--rose-accent)"><i class="fa-solid fa-triangle-exclamation"></i> Communication error connecting to server.</p>`;
        }
    }
}

// Simple Helper Utilities
function scrollToBottom() {
    chatThread.scrollTop = chatThread.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.innerText = text;
    return div.innerHTML;
}

// Light markdown converter (supports links, bold, code highlights)
function parseMarkdown(text) {
    let clean = escapeHtml(text);
    
    // Bold matches (**text**)
    clean = clean.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Code blocks (`text`)
    clean = clean.replace(/`(.*?)`/g, '<code>$1</code>');
    
    // Link tags [label](url)
    clean = clean.replace(/\[(.*?)\]\((https?:\/\/.*?)\)/g, '<a href="$2" target="_blank" style="color:var(--cyan-accent); font-weight:500;">$1</a>');
    
    // Convert double newline to paragraphs, single to line breaks
    clean = clean.replace(/\n\n/g, '</p><p>');
    clean = clean.replace(/\n/g, '<br>');
    
    return clean;
}
