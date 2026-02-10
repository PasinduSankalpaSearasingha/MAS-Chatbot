document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('url-input');
    const addBtn = document.getElementById('add-btn');
    const urlList = document.getElementById('url-list');
    const startBtn = document.getElementById('start-btn');
    const clearBtn = document.getElementById('clear-btn');
    const statusCard = document.getElementById('status-card');
    const statusBadge = document.getElementById('status-badge');
    const logBox = document.getElementById('log-box');

    let urls = [];
    let isPolling = false;

    // --- UI Helpers ---

    function renderUrls() {
        urlList.innerHTML = '';
        urls.forEach((url, index) => {
            const li = document.createElement('li');
            li.className = 'url-item';
            li.innerHTML = `
                <span>${url}</span>
                <button class="remove-btn" onclick="removeUrl(${index})">Remove</button>
            `;
            urlList.appendChild(li);
        });
        startBtn.disabled = urls.length === 0;
    }

    window.removeUrl = (index) => {
        urls.splice(index, 1);
        renderUrls();
    };

    function addUrl() {
        const url = urlInput.value.trim();
        if (url && (url.startsWith('http://') || url.startsWith('https://'))) {
            urls.push(url);
            urlInput.value = '';
            renderUrls();
        } else if (url) {
            alert('Please enter a valid URL starting with http:// or https://');
        }
    }

    // --- API Calls ---

    async function startScraping() {
        if (urls.length === 0) return;

        try {
            const response = await fetch('/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to start scraping');
            }

            statusCard.style.display = 'block';
            startBtn.disabled = true;
            statusBadge.textContent = 'Running';
            statusBadge.className = 'badge running';

            // Clear previous logs
            logBox.innerHTML = '';

            if (!isPolling) {
                pollStatus();
            }
        } catch (error) {
            alert('Error: ' + error.message);
        }
    }

    async function pollStatus() {
        isPolling = true;
        try {
            const response = await fetch('/api/status');
            const data = await response.json();

            // Update logs
            logBox.innerHTML = data.logs.join('\n');
            logBox.scrollTop = logBox.scrollHeight;

            if (data.is_running) {
                setTimeout(pollStatus, 2000);
            } else {
                statusBadge.textContent = 'Idle';
                statusBadge.className = 'badge idle';
                startBtn.disabled = urls.length === 0;
                isPolling = false;
            }
        } catch (error) {
            console.error('Polling error:', error);
            setTimeout(pollStatus, 5000); // Retry later
        }
    }

    // --- Event Listeners ---

    addBtn.addEventListener('click', addUrl);
    urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') addUrl();
    });

    clearBtn.addEventListener('click', () => {
        urls = [];
        renderUrls();
    });

    startBtn.addEventListener('click', startScraping);

    // Check initial status
    pollStatus();
});
