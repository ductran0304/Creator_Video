// H2Dev Pipeline Web UI Logic

document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    const navLinks = document.querySelectorAll('.nav-links li');
    const views = document.querySelectorAll('.view');

    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            const targetView = link.dataset.view;
            
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            views.forEach(v => v.classList.remove('active'));
            document.getElementById(`view-${targetView}`).classList.add('active');

            // Load data when view changes
            if (targetView === 'projects') loadProjects();
            if (targetView === 'settings') loadConfig();
        });
    });

    // Pipeline Logic
    const form = document.getElementById('pipeline-form');
    const startBtn = document.getElementById('start-btn');
    const btnText = startBtn.querySelector('.btn-text');
    const spinner = startBtn.querySelector('.spinner');
    const consoleOutput = document.getElementById('console-output');
    const statusBanner = document.getElementById('status-banner');
    const stageList = document.getElementById('stage-list');
    
    let eventSource = null;
    let isRunning = false;
    let stagesData = [];

    // Initialize Tracker UI
    function renderStages(stages) {
        stageList.innerHTML = stages.map(s => `
            <li class="stage-item" id="stage-${s.id}">
                <div class="stage-icon">${s.icon}</div>
                <div class="stage-info">
                    <div class="stage-name">${s.name}</div>
                    <div class="stage-status" id="stage-status-${s.id}">Pending</div>
                </div>
            </li>
        `).join('');
    }

    function updateTracker(state) {
        if (state.status === 'idle') {
            statusBanner.className = 'status-banner';
            statusBanner.textContent = 'Ready';
            resetStages();
            return;
        }

        statusBanner.className = `status-banner ${state.status}`;
        if (state.status === 'running') {
            statusBanner.textContent = `Running: ${state.stage_name || 'Initializing...'}`;
        } else if (state.status === 'completed') {
            statusBanner.textContent = `Completed successfully in ${state.elapsed_seconds || 0}s`;
        } else if (state.status === 'error') {
            statusBanner.textContent = `Error: Pipeline stopped`;
        }

        // Update stage items
        const currentStageId = state.stage;
        stagesData.forEach(s => {
            const el = document.getElementById(`stage-${s.id}`);
            const statusEl = document.getElementById(`stage-status-${s.id}`);
            
            if (!el) return;
            
            el.classList.remove('active', 'done');
            
            if (state.status === 'completed') {
                el.classList.add('done');
                statusEl.textContent = 'Completed';
            } else if (s.id < currentStageId) {
                el.classList.add('done');
                statusEl.textContent = 'Completed';
            } else if (s.id === currentStageId && state.status === 'running') {
                el.classList.add('active');
                statusEl.textContent = 'In Progress...';
            } else {
                statusEl.textContent = 'Pending';
            }
        });
    }

    function resetStages() {
        stagesData.forEach(s => {
            const el = document.getElementById(`stage-${s.id}`);
            const statusEl = document.getElementById(`stage-status-${s.id}`);
            if(el) el.classList.remove('active', 'done');
            if(statusEl) statusEl.textContent = 'Pending';
        });
    }

    function appendLog(message, isSystem = false) {
        const div = document.createElement('div');
        div.className = 'log-line';
        if (isSystem) div.classList.add('system');
        
        // Simple coloring based on text content
        const lower = message.toLowerCase();
        if (lower.includes('[error]') || lower.includes('failed')) div.classList.add('error');
        else if (lower.includes('[✓]') || lower.includes('[+]') || lower.includes('hoàn tất')) div.classList.add('success');
        else if (lower.includes('[warning]') || lower.includes('[⚠]')) div.classList.add('warning');
        else if (message.startsWith('===')) div.classList.add('highlight');
        
        div.textContent = message;
        consoleOutput.appendChild(div);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }

    document.getElementById('clear-log').addEventListener('click', () => {
        consoleOutput.innerHTML = '';
    });

    // Check initial status
    fetch('/api/pipeline/status')
        .then(r => r.json())
        .then(data => {
            stagesData = data.stages;
            renderStages(stagesData);
            if (data.status === 'running') {
                setUIState(true);
                connectSSE();
            } else {
                updateTracker(data);
            }
        });

    function setUIState(running) {
        isRunning = running;
        startBtn.disabled = running;
        if (running) {
            btnText.textContent = 'Pipeline Running...';
            spinner.classList.remove('hidden');
        } else {
            btnText.textContent = 'Start Pipeline';
            spinner.classList.add('hidden');
        }
    }

    function connectSSE() {
        if (eventSource) eventSource.close();
        
        eventSource = new EventSource('/api/pipeline/stream');
        
        eventSource.onmessage = (e) => {
            const data = JSON.parse(e.data);
            
            if (data.type === 'log') {
                appendLog(data.message);
                // Fetch full status occasionally to update tracker accurately
                fetch('/api/pipeline/status').then(r=>r.json()).then(updateTracker);
            } else if (data.type === 'heartbeat') {
                // Ignore
            } else if (data.type === 'done') {
                eventSource.close();
                setUIState(false);
                fetch('/api/pipeline/status').then(r=>r.json()).then(updateTracker);
                
                if (data.status === 'completed') {
                    appendLog("✨ Pipeline finished successfully!", true);
                } else if (data.status === 'error') {
                    appendLog("❌ Pipeline encountered an error.", true);
                }
            }
        };
        
        eventSource.onerror = () => {
            eventSource.close();
            setUIState(false);
        };
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (isRunning) return;

        const topic = document.getElementById('topic').value;
        const language = document.getElementById('language').value;
        
        consoleOutput.innerHTML = '';
        appendLog(`Starting pipeline for: "${topic}"...`, true);
        
        try {
            const res = await fetch('/api/pipeline/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic, language })
            });
            
            const data = await res.json();
            if (res.ok) {
                setUIState(true);
                connectSSE();
                // Immediately fetch status to update tracker
                setTimeout(() => {
                    fetch('/api/pipeline/status').then(r=>r.json()).then(updateTracker);
                }, 500);
            } else {
                appendLog(`Error: ${data.error}`, true);
            }
        } catch (err) {
            appendLog(`Failed to start: ${err.message}`, true);
        }
    });

    // --- Projects Logic ---
    const gallery = document.getElementById('projects-gallery');
    
    async function loadProjects() {
        gallery.innerHTML = '<div class="loading-text">Loading projects...</div>';
        try {
            const res = await fetch('/api/projects');
            const projects = await res.json();
            
            if (projects.length === 0) {
                gallery.innerHTML = '<div class="no-data">No projects found.</div>';
                return;
            }
            
            gallery.innerHTML = projects.map(p => {
                const date = new Date(p.created_at * 1000).toLocaleString();
                const thumb = p.has_thumbnail ? `<img src="${p.thumbnail_url}" alt="Thumbnail">` : `<div class="no-thumb">No Thumbnail</div>`;
                
                let actions = '';
                if (p.has_video) {
                    actions += `<a href="/media/${p.name}/outputs/${p.video_file}" target="_blank" class="primary">Watch Video</a>`;
                }
                if (p.has_seo) {
                    actions += `<a href="/media/${p.name}/outputs/youtube_metadata.txt" target="_blank">Metadata</a>`;
                }
                
                return `
                    <div class="card project-card">
                        <div class="project-thumb">${thumb}</div>
                        <div class="project-info">
                            <div class="project-title" title="${p.display_name}">${p.display_name}</div>
                            <div class="project-date">${date}</div>
                            <div class="project-actions">${actions || '<span class="text-muted">Processing...</span>'}</div>
                        </div>
                    </div>
                `;
            }).join('');
        } catch (err) {
            gallery.innerHTML = `<div class="error">Error loading projects: ${err.message}</div>`;
        }
    }

    // --- Config Logic ---
    const configForm = document.getElementById('config-form');
    const saveConfigBtn = document.getElementById('save-config-btn');
    const configMsg = document.getElementById('config-msg');
    
    let currentConfig = {};

    async function loadConfig() {
        try {
            const res = await fetch('/api/config');
            currentConfig = await res.json();
            renderConfigForm();
        } catch (err) {
            configForm.innerHTML = `<div class="error">Error loading config: ${err.message}</div>`;
        }
    }

    function renderConfigForm() {
        // Group configuration keys
        const groups = {
            "API & Models": ['gemini_api_key', 'use_web2api', 'web2api_url', 'web2api_key', 'web2api_model_script', 'web2api_model_seo'],
            "Voice & Audio": ['language', 'voice_name', 'use_omnivoice', 'bg_music_volume', 'sfx_volume', 'sfx_enabled'],
            "Pipeline Rules": ['script_word_count_min', 'script_word_count_max', 'min_evidence_count', 'delay_min', 'delay_max', 'max_wait_image']
        };

        let html = '';
        for (const [groupName, keys] of Object.entries(groups)) {
            html += `<div class="config-group"><h3>${groupName}</h3><div class="config-grid">`;
            
            keys.forEach(key => {
                const val = currentConfig[key] !== undefined ? currentConfig[key] : '';
                
                if (typeof val === 'boolean' || key === 'use_web2api' || key === 'use_omnivoice' || key === 'sfx_enabled') {
                    const isChecked = Boolean(val);
                    html += `
                        <div class="form-group checkbox-group">
                            <input type="checkbox" id="cfg_${key}" name="${key}" ${isChecked ? 'checked' : ''}>
                            <label for="cfg_${key}">${key}</label>
                        </div>
                    `;
                } else if (typeof val === 'number') {
                    html += `
                        <div class="form-group">
                            <label for="cfg_${key}">${key}</label>
                            <input type="number" step="any" id="cfg_${key}" name="${key}" value="${val}">
                        </div>
                    `;
                } else {
                    html += `
                        <div class="form-group">
                            <label for="cfg_${key}">${key}</label>
                            <input type="text" id="cfg_${key}" name="${key}" value="${val}">
                        </div>
                    `;
                }
            });
            
            html += `</div></div>`;
        }
        
        configForm.innerHTML = html;
    }

    saveConfigBtn.addEventListener('click', async () => {
        const formData = new FormData(configForm);
        const newConfig = { ...currentConfig };
        
        // Setup checkboxes which aren't included in FormData if unchecked
        configForm.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            newConfig[cb.name] = cb.checked;
        });

        // Parse numbers and strings
        configForm.querySelectorAll('input[type="number"], input[type="text"]').forEach(input => {
            if (input.type === 'number') {
                newConfig[input.name] = parseFloat(input.value) || 0;
            } else {
                newConfig[input.name] = input.value;
            }
        });

        try {
            saveConfigBtn.disabled = true;
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newConfig)
            });
            
            if (res.ok) {
                showMsg('Configuration saved successfully!', 'success');
                currentConfig = newConfig; // update local
            } else {
                const data = await res.json();
                showMsg(`Error: ${data.error}`, 'error');
            }
        } catch (err) {
            showMsg(`Error: ${err.message}`, 'error');
        } finally {
            saveConfigBtn.disabled = false;
        }
    });

    function showMsg(text, type) {
        configMsg.textContent = text;
        configMsg.className = `msg show ${type}`;
        setTimeout(() => {
            configMsg.classList.remove('show');
        }, 3000);
    }
});
