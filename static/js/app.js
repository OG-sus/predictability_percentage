
        // --- Start of Consolidated Script ---
        document.addEventListener('DOMContentLoaded', () => {

            // --- Global Functions ---
            window.redirectToCheckout = async function(planType = 'pro') {
                try {
                    const response = await fetch('/api/create-checkout-session', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ plan: planType })
                    });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error.message);
                    window.location.href = data.url;
                } catch (error) { alert(`Error: ${error.message}`); }
            }

            window.redirectToPortal = async function() {
                try {
                    const response = await fetch('/api/create-portal-session', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                    });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error?.message);
                    if (data.url) window.location.href = data.url;
                } catch (error) { alert(`Error: ${error.message}`); }
            }

            // --- Unified Auth Modal Functions ---
            const authModal = document.getElementById('auth-modal');
            const loginForm = document.getElementById('login-form');
            const registerForm = document.getElementById('register-form');
            const resetForm = document.getElementById('reset-form');
            const authSuccess = document.getElementById('auth-success');

            window.openAuthModal = function(mode) {
                if (authModal) {
                    authModal.classList.add('visible');
                    switchTab(mode);
                }
            }

            window.closeAuthModal = function() {
                if (authModal) {
                    authModal.classList.remove('visible');
                    // Remove query param if present to clean URL
                    const url = new URL(window.location);
                    if (url.searchParams.has('action')) {
                        url.searchParams.delete('action');
                        window.history.replaceState({}, '', url);
                    }
                }
            }

            window.switchTab = function(mode) {
                document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
                document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));

                if (mode === 'login' || mode === 'register') {
                    const tab = document.getElementById(`tab-${mode}`);
                    const form = document.getElementById(`${mode}-form`);
                    if(tab) tab.classList.add('active');
                    if(form) form.classList.add('active');
                    const authTabs = document.querySelector('.auth-tabs');
                    if(authTabs) authTabs.style.display = 'flex';
                } else if (mode === 'reset') {
                    if(resetForm) resetForm.classList.add('active');
                    const authTabs = document.querySelector('.auth-tabs');
                    if(authTabs) authTabs.style.display = 'none';
                } else if (mode === 'success') {
                    if(authSuccess) authSuccess.classList.add('active');
                    const authTabs = document.querySelector('.auth-tabs');
                    if(authTabs) authTabs.style.display = 'none';
                }
                document.querySelectorAll('.error-msg').forEach(e => e.textContent = '');
            }

            async function handleAuth(event, endpoint) {
                event.preventDefault();
                const form = event.target;
                const formData = new FormData(form);
                const data = Object.fromEntries(formData.entries());
                const errorDiv = document.getElementById(`${endpoint}-error`);

                try {
                    const response = await fetch(`/api/${endpoint}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    const result = await response.json();
                    if (response.ok) {
                        if (endpoint === 'register') {
                            document.getElementById('success-msg').textContent = 'Account created successfully.';
                            document.getElementById('recovery-display').textContent = result.recovery_key;
                            document.getElementById('recovery-section').style.display = 'block';
                            document.getElementById('reset-success-btn').style.display = 'none';
                            switchTab('success');
                        } else if (endpoint === 'reset_password') {
                            document.getElementById('success-msg').textContent = 'Password reset successfully.';
                            document.getElementById('recovery-section').style.display = 'none';
                            document.getElementById('reset-success-btn').style.display = 'block';
                            switchTab('success');
                        } else {
                            window.location.reload();
                        }
                    } else {
                        if(errorDiv) errorDiv.textContent = result.error || 'Authentication failed.';
                    }
                } catch (err) {
                    if(errorDiv) errorDiv.textContent = 'Server error. Please try again.';
                }
            }

            if (authModal) {
                authModal.addEventListener('click', (e) => {
                    if (e.target === authModal) closeAuthModal();
                });
            }
            if(loginForm) loginForm.addEventListener('submit', (e) => handleAuth(e, 'login'));
            if(registerForm) registerForm.addEventListener('submit', (e) => handleAuth(e, 'register'));
            if(resetForm) resetForm.addEventListener('submit', (e) => handleAuth(e, 'reset_password'));

            // --- Main App Logic ---
            let myChart, savedData = [], parsedData = [];
            let currentRawScore = null;
            let user = { id: null, tier: 'Free' };
            let currentK = 1.0;
            let folders = [];
            let currentEditingId = null;
            let calculationMode = 'standard';

            const CHART_COLORS = ['#33C3F0', '#FF5252', '#FFD700', '#69F0AE', '#E040FB', '#FFAB40', '#7700f8', '#20c997', '#e83e8c', '#fd7e14'];
            Chart.defaults.font.size = 11;
            Chart.defaults.maintainAspectRatio = false;

            const calculateBtn = document.getElementById('calculate-btn'),
                  clearFormBtn = document.getElementById('clear-form-btn'),
                  scoresInput = document.getElementById('scores-input'),
                  notesInput = document.getElementById('notes-input'),
                  targetInput = document.getElementById('target-input'),
                  resultArea = document.getElementById('result-area'),
                  errorDiv = document.getElementById('error'),
                  chartCanvas = document.getElementById('scores-chart'),
                  chartWrapper = document.getElementById('chart-wrapper'),
                  savedList = document.getElementById('saved-list'),
                  foldersContainer = document.getElementById('folders-container'),
                  loadBtn = document.getElementById('load-btn'),
                  compareBtn = document.getElementById('compare-btn'),
                  moveBtn = document.getElementById('move-btn'),
                  deleteSelectedBtn = document.getElementById('delete-selected-btn'),
                  fileUpload = document.getElementById('file-upload'),
                  previewArea = document.getElementById('preview-area'),
                  filePreview = document.getElementById('file-preview'),
                  clearPreviewBtn = document.getElementById('clear-preview-btn'),
                  userInfoContainer = document.getElementById('user-info-container'),
                  switchBtns = document.querySelectorAll('.switch-btn'),
                  lockMessage = document.getElementById('lock-message'),
                  newFolderBtn = document.getElementById('new-folder-btn'),
                  confirmationModal = document.getElementById('confirmation-modal'),
                  modalMessage = document.getElementById('modal-message'),
                  modalConfirmBtn = document.getElementById('modal-confirm-btn'),
                  modalCancelBtn = document.getElementById('modal-cancel-btn'),
                  modeStandardBtn = document.getElementById('mode-standard'),
                  modeSlidingBtn = document.getElementById('mode-sliding'),
                  windowSizeContainer = document.getElementById('window-size-container'),
                  windowSizeInput = document.getElementById('window-size-input'),
                  exportBtn = document.getElementById('export-btn'),
                  shareBtn = document.getElementById('share-btn'),
                  criticalAlert = document.getElementById('critical-alert'),
                  deviationDisplay = document.getElementById('deviation-display'),
                  averageDisplay = document.getElementById('average-display'),
                  settingsModal = document.getElementById('settings-modal'),
                  changePasswordBtn = document.getElementById('change-password-btn'),
                  closeSettingsBtn = document.getElementById('close-settings-btn'),
                  settingsFeedback = document.getElementById('settings-feedback'),
                  devSettings = document.getElementById('dev-settings'),
                  apiKeyDisplay = document.getElementById('api-key-display'),
                  generateKeyBtn = document.getElementById('generate-key-btn');

            function updateActionButtons() {
                const checked = document.querySelectorAll('.compare-cb:checked');
                let count = checked.length;
                loadBtn.style.display = count === 1 ? 'inline-block' : 'none';
                compareBtn.style.display = count > 1 ? 'inline-block' : 'none';
                moveBtn.style.display = count > 0 ? 'inline-block' : 'none';
                deleteSelectedBtn.style.display = count > 0 ? 'inline-block' : 'none';
                compareBtn.textContent = `Compare (${count})`;
                deleteSelectedBtn.textContent = `Delete (${count})`;
            }

            let confirmCallback = null;
            function showConfirmationModal(message, onConfirm) {
                modalMessage.textContent = message;
                confirmCallback = onConfirm;
                confirmationModal.classList.add('visible');
            }
            function hideConfirmationModal() {
                confirmationModal.classList.remove('visible');
                confirmCallback = null;
            }
            modalConfirmBtn.addEventListener('click', () => { if (confirmCallback) confirmCallback(); hideConfirmationModal(); });
            modalCancelBtn.addEventListener('click', hideConfirmationModal);

            window.openSettings = () => {
                settingsModal.classList.add('visible');
                document.getElementById('old-password').value = '';
                document.getElementById('new-password').value = '';
                settingsFeedback.textContent = '';
            };
            closeSettingsBtn.addEventListener('click', () => settingsModal.classList.remove('visible'));

            changePasswordBtn.addEventListener('click', async () => {
                const oldPass = document.getElementById('old-password').value;
                const newPass = document.getElementById('new-password').value;
                if(!oldPass || !newPass) {
                    settingsFeedback.textContent = 'Both fields required.';
                    settingsFeedback.style.color = '#dc3545';
                    return;
                }
                try {
                    const response = await fetch('/api/change_password', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({old_password: oldPass, new_password: newPass})
                    });
                    const data = await response.json();
                    if(response.ok) {
                        settingsFeedback.textContent = 'Password updated!';
                        settingsFeedback.style.color = '#198754';
                        setTimeout(() => settingsModal.classList.remove('visible'), 1500);
                    } else {
                        settingsFeedback.textContent = data.error || 'Failed.';
                        settingsFeedback.style.color = '#dc3545';
                    }
                } catch(e) {
                    settingsFeedback.textContent = 'Server error.';
                    settingsFeedback.style.color = '#dc3545';
                }
            });

            async function checkSession() {
                try {
                    const response = await fetch('/api/session_status', { credentials: 'include' });
                    const data = await response.json();
                    if (data.logged_in) {
                        user.tier = data.tier;
                        updateUIForAuthState(true, data.tier, data.username, data.stripe_customer_id);
                    } else {
                        updateUIForAuthState(false);
                        // Check for URL params to open auth modal
                        const urlParams = new URLSearchParams(window.location.search);
                        const action = urlParams.get('action');
                        if (action === 'login' || action === 'register') {
                            openAuthModal(action);
                        }
                    }
                } catch (e) { updateUIForAuthState(false); }
            }

            function updateUIForAuthState(isLoggedIn, tier = 'Free', username = 'N/A', stripeCustomerId = null) {
                document.getElementById('app-section').classList.remove('blurred');
                
                // Always show Sliding Window button now
                modeSlidingBtn.style.display = 'block';

                if (isLoggedIn) {
                    let links = `Logged in as <b>${username}</b> (${tier})`;
                    // CHANGED: Redirect to Pricing Section instead of direct checkout
                    if (tier === 'Free') links += ` | <a href="/#pricing" style="cursor:pointer; color:var(--primary-color)">Upgrade</a>`;
                    links += ` | <a href="/u/${encodeURIComponent(username)}" style="cursor:pointer; color:var(--primary-color)">Portfolio</a>`;
                    links += ` | <a href="/gallery" style="cursor:pointer; color:var(--primary-color)">Gallery</a>`;
                    links += ` | <a onclick="openSettings()" style="cursor:pointer; color:var(--primary-color)">Settings</a>`;
                    if (stripeCustomerId) links += ` | <a onclick="redirectToPortal()" style="cursor:pointer; color:var(--primary-color)">Billing</a>`;
                    links += ` | <a id="logout-btn" style="cursor:pointer; color:var(--primary-color)">Log Out</a>`;
                    userInfoContainer.innerHTML = links;
                    document.getElementById('logout-btn').addEventListener('click', async () => {
                        await fetch('/api/logout', { method: 'POST', credentials: 'include' });
                        window.location.href = '/';
                    });
                    updateSwitchState();
                    loadFoldersAndAnalyses();
                    if (tier === 'API_Business' || tier === 'API_Basic') {
                        devSettings.style.display = 'block';
                        fetch('/api/get_key', { credentials: 'include' })
                            .then(res => res.json())
                            .then(data => {
                                if(data.api_key) apiKeyDisplay.value = data.api_key;
                            });
                    } else {
                        devSettings.style.display = 'none';
                    }
                } else {
                    userInfoContainer.innerHTML = `<a onclick="openAuthModal('login')" style="cursor:pointer; color:var(--primary-color); font-weight:bold;">Login / Register</a>`;
                    devSettings.style.display = 'none';
                }
            }

            modeStandardBtn.addEventListener('click', () => {
                calculationMode = 'standard';
                modeStandardBtn.classList.add('active');
                modeSlidingBtn.classList.remove('active');
                windowSizeContainer.style.display = 'none';
                calculateBtn.textContent = 'Calculate Score';
                calculateBtn.disabled = false;
                calculateBtn.style.opacity = '1';
                calculateBtn.style.cursor = 'pointer';
            });

            modeSlidingBtn.addEventListener('click', () => {
                calculationMode = 'sliding';
                modeSlidingBtn.classList.add('active');
                modeStandardBtn.classList.remove('active');
                windowSizeContainer.style.display = 'block';
                
                if (user.tier === 'Free' || user.tier === 'Pro') {
                    calculateBtn.textContent = 'Upgrade to Business to Calculate';
                    calculateBtn.disabled = true;
                    calculateBtn.style.opacity = '0.5';
                    calculateBtn.style.cursor = 'not-allowed';
                } else {
                    calculateBtn.textContent = 'Calculate Sliding Window';
                    calculateBtn.disabled = false;
                    calculateBtn.style.opacity = '1';
                    calculateBtn.style.cursor = 'pointer';
                }
            });

            switchBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    if (btn.classList.contains('disabled')) {
                        lockMessage.style.display = 'block'; return;
                    }
                    switchBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    currentK = parseFloat(btn.dataset.k);
                    lockMessage.style.display = 'none';
                });
            });

            function updateSwitchState(kValue = null) {
                if (user.tier !== 'Free') {
                    switchBtns.forEach(btn => btn.classList.remove('disabled'));
                    lockMessage.style.display = 'none';
                }
                if (kValue !== null) {
                    currentK = kValue;
                    switchBtns.forEach(btn => {
                        if (parseFloat(btn.dataset.k) === kValue) btn.classList.add('active');
                        else btn.classList.remove('active');
                    });
                }
            }

            calculateBtn.addEventListener('click', async () => {
                if (calculationMode === 'sliding' && (user.tier === 'Free' || user.tier === 'Pro')) {
                    alert("Sliding Window analysis requires a Business Plan.");
                    return;
                }

                const scores = scoresInput.value.split(/[\s,]+/).filter(s => s.trim() !== '').map(Number).filter(n => !isNaN(n));
                
                const originalText = calculateBtn.textContent;
                calculateBtn.textContent = 'Calculating...';
                calculateBtn.disabled = true;
                calculateBtn.style.opacity = '0.7';
                calculateBtn.style.cursor = 'wait';

                try {
                    await calculateAndDisplay(scores);
                } finally {
                    calculateBtn.textContent = originalText;
                    calculateBtn.disabled = false;
                    calculateBtn.style.opacity = '1';
                    calculateBtn.style.cursor = 'pointer';
                    // Re-apply lock if necessary
                    if (calculationMode === 'sliding' && (user.tier === 'Free' || user.tier === 'Pro')) {
                        calculateBtn.textContent = 'Upgrade to Business to Calculate';
                        calculateBtn.disabled = true;
                        calculateBtn.style.opacity = '0.5';
                        calculateBtn.style.cursor = 'not-allowed';
                    }
                }
            });

            clearFormBtn.addEventListener('click', () => {
                scoresInput.value = '';
                notesInput.value = '';
                targetInput.value = '';
                document.getElementById('dataset-name').value = '';
                currentEditingId = null;
                document.getElementById('save-btn').style.display = 'inline-block';
                document.getElementById('update-btn').style.display = 'none';
                clearResults();
            });

            async function calculateAndDisplay(scores) {
                if (!scores || scores.length < 2) { showError('Need at least 2 numbers.'); return; }
                clearResults();
                try {
                    let data;
                    if (calculationMode === 'standard') {
                        const targetVal = targetInput.value ? parseFloat(targetInput.value) : null;
                        const response = await fetch('/api/predictability_score', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ scores: scores, k: currentK, target_value: targetVal }),
                        });
                        data = await response.json();
                        if (!response.ok) throw new Error(data.error || 'API Error');
                        currentRawScore = data.predictability_score;
                        let deviation = null;
                        if (data.target_deviation !== undefined) {
                            deviation = data.target_deviation;
                            deviationDisplay.textContent = `Deviation: ${deviation > 0 ? '+' : ''}${deviation.toFixed(2)}%`;
                            deviationDisplay.style.display = 'block';
                            if (currentRawScore < 95 && Math.abs(deviation) > 2) {
                                criticalAlert.style.display = 'block';
                            }
                        }
                        displaySingleResult({ name: 'Input Data', predictability_score: currentRawScore, scores: scores });
                    } else {
                        const windowSize = parseInt(windowSizeInput.value);
                        const targetVal = targetInput.value ? parseFloat(targetInput.value) : null;
                        const response = await fetch('/api/sliding_window', {
                            method: 'POST', headers: { 'Content-Type': 'application/json', 'Credentials': 'include' },
                            body: JSON.stringify({ scores: scores, k: currentK, window_size: windowSize, target_value: targetVal }),
                        });
                        data = await response.json();
                        if (!response.ok) throw new Error(data.error || 'API Error');
                        resultArea.style.display = 'block';
                        renderSlidingChart(data.sliding_window_results);
                    }
                } catch (err) { showError(err.message); }
            }

            function displaySingleResult(result) {
                resultArea.style.display = 'block';
                document.getElementById('comparison-list').style.display = 'none';
                document.getElementById('display-score').style.display = 'block';
                document.getElementById('display-score').textContent = result.predictability_score.toFixed(2) + '%';
                const cleanScores = sanitizeScores(result.scores);
                const avg = cleanScores.reduce((a,b)=>a+b,0) / cleanScores.length;
                averageDisplay.textContent = `(Avg: ${avg.toFixed(2)})`;
                averageDisplay.style.display = 'block';
                renderSingleLineChart({ name: document.getElementById('dataset-name').value || result.name || 'Scores', scores: cleanScores });
            }

            function displayComparisonResults(results) {
                resultArea.style.display = 'block';
                document.getElementById('display-score').style.display = 'none';
                averageDisplay.style.display = 'none';
                const comparisonList = document.getElementById('comparison-list');
                comparisonList.innerHTML = '';
                comparisonList.style.display = 'flex';
                results.forEach((res, i) => {
                    const color = CHART_COLORS[i % CHART_COLORS.length];
                    const div = document.createElement('div');
                    div.style.color = color;
                    div.style.fontWeight = 'bold';
                    div.style.fontSize = '2em';
                    div.textContent = `${parseFloat(res.predictability_score).toFixed(2)}%`;
                    comparisonList.appendChild(div);
                });
                renderMultiLineChart(results);
            }

            function renderSlidingChart(results) {
                if (myChart) myChart.destroy();
                const labels = results.map(r => `Window ${r.index + 1}`);
                const dataPoints = results.map(r => r.score);
                const rawData = results.map(r => r.data);
                const datasetName = document.getElementById('dataset-name').value || 'Predictability';
                myChart = new Chart(chartCanvas.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: `${datasetName} (Window: ${windowSizeInput.value}, k=${currentK})`,
                            data: dataPoints,
                            pointRadius: 5,
                            pointHoverRadius: 7,
                            tension: 0.1,
                            fill: false,
                            raw_data_points: rawData,
                            segment: {
                                borderColor: ctx => {
                                    const dev = Math.abs(results[ctx.p1DataIndex].deviation);
                                    if (dev > 2) return '#dc3545';
                                    if (dev > 1) return '#ffc107';
                                    return '#6610f2';
                                }
                            }
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: { y: { beginAtZero: false } },
                        onClick: (e, activeEls) => {
                            if (activeEls.length > 0) {
                                const index = activeEls[0].index;
                                const score = dataPoints[index];
                                const points = rawData[index];
                                const content = `<p><strong>Window:</strong> ${index + 1}</p><p><strong>Score:</strong> ${score.toFixed(2)}%</p><p><strong>Data Points:</strong></p><p>${points.join(', ')}</p>`;
                                document.getElementById('drilldown-content').innerHTML = content;
                                document.getElementById('drilldown-modal').classList.add('visible');
                            }
                        }
                    }
                });
                // Show avg of all window scores — labelled "Avg:" so viewer knows it's not a single FSR score
                const avgScore = dataPoints.reduce((a, b) => a + b, 0) / dataPoints.length;
                const scoreEl = document.getElementById('display-score');
                scoreEl.style.display = 'block';
                scoreEl.textContent = `Avg: ${avgScore.toFixed(2)}%`;
            }

            function sanitizeScores(scores) {
                if (!scores) return [];
                let cleanScores = [];
                if (typeof scores === 'string') {
                    try {
                        cleanScores = JSON.parse(scores);
                    } catch (e) {
                        cleanScores = scores.split(/[\s,]+/).filter(s => s.trim() !== '');
                    }
                } else if (Array.isArray(scores)) {
                    cleanScores = scores;
                }
                return cleanScores.map(Number).filter(n => !isNaN(n));
            }

            function renderSingleLineChart(dataset) {
                if (myChart) myChart.destroy();
                const cleanScores = sanitizeScores(dataset.scores);
                const labels = Array.from({length: cleanScores.length}, (_, i) => i + 1);
                const avg = cleanScores.reduce((a,b)=>a+b,0)/cleanScores.length;
                
                const datasets = [
                    { label: dataset.name, data: cleanScores, borderColor: CHART_COLORS[0], tension: 0.1, fill: false },
                    { label: 'Average', data: Array(cleanScores.length).fill(avg), borderColor: CHART_COLORS[1], borderDash: [5, 5], pointRadius: 0, borderWidth: 2 }
                ];

                // Add Target Line if target exists
                const targetVal = document.getElementById('target-input').value;
                if (targetVal) {
                    const targetNum = parseFloat(targetVal);
                    datasets.push({
                        label: 'Target',
                        data: Array(cleanScores.length).fill(targetNum),
                        borderColor: '#fd7e14', // Orange/Red
                        borderDash: [10, 5],
                        pointRadius: 0,
                        borderWidth: 2,
                        fill: false
                    });
                }

                myChart = new Chart(chartCanvas.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: datasets
                    },
                    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } }, scales: { y: { beginAtZero: false } } }
                });
            }

            function renderMultiLineChart(datasets) {
                if (myChart) myChart.destroy();
                let maxLen = 0;
                const finalDatasets = [];
                datasets.forEach((ds, i) => {
                    const cleanScores = sanitizeScores(ds.scores);
                    console.log(`Processing dataset ${i}: ${ds.name}`, cleanScores);
                    if (cleanScores.length > maxLen) maxLen = cleanScores.length;
                    const color = CHART_COLORS[i % CHART_COLORS.length];
                    const avg = cleanScores.reduce((a, b) => a + b, 0) / cleanScores.length;
                    finalDatasets.push({ label: ds.name, data: cleanScores, borderColor: color, fill: false, tension: 0.1, spanGaps: true });
                    finalDatasets.push({ label: `_hidden_${ds.name}_avg`, data: Array(cleanScores.length).fill(avg), borderColor: color, borderDash: [5, 5], pointRadius: 0, borderWidth: 2, fill: false, spanGaps: true });
                });
                const labels = Array.from({length: maxLen}, (_, i) => i + 1);
                myChart = new Chart(chartCanvas.getContext('2d'), {
                    type: 'line',
                    data: { labels: labels, datasets: finalDatasets },
                    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true, labels: { filter: (item) => !item.text.includes('_hidden_'), font: { size: 14 } } } }, scales: { y: { beginAtZero: false } } }
                });
            }

            function showError(msg) { errorDiv.textContent = msg; errorDiv.style.display = 'block'; }

            function clearResults() {
                resultArea.style.display = 'none';
                errorDiv.style.display = 'none';
                criticalAlert.style.display = 'none';
                deviationDisplay.style.display = 'none';
                averageDisplay.style.display = 'none';
                document.getElementById('comparison-list').style.display = 'none';
                document.getElementById('display-score').style.display = 'block';
                document.getElementById('display-score').textContent = '--';
                if (myChart) { myChart.destroy(); myChart = null; }
            }

            async function loadFoldersAndAnalyses(openFolderId = null) {
                try {
                    const t = new Date().getTime();
                    const [fRes, aRes] = await Promise.all([
                        fetch(`/api/folders?t=${t}`, { credentials: 'include' }),
                        fetch(`/api/analyses?t=${t}`, { credentials: 'include' })
                    ]);
                    const fData = await fRes.json();
                    const aData = await aRes.json();
                    folders = fData.folders || [];
                    savedData = aData.saved_analyses || [];
                    renderDashboard(openFolderId);
                    populateFolderSelect();
                } catch (e) { console.error(e); }
            }

            function renderDashboard(openFolderId) {
                foldersContainer.innerHTML = '';
                savedList.innerHTML = '';
                const grouped = {};
                folders.forEach(f => grouped[f.id] = []);
                const uncategorized = [];
                savedData.forEach(item => {
                    if (item.folder_id && grouped[item.folder_id]) grouped[item.folder_id].push(item);
                    else uncategorized.push(item);
                });
                folders.forEach(f => {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'folder-wrapper';
                    const card = document.createElement('div');
                    card.className = 'folder-card';
                    card.innerHTML = `<button class="folder-delete-btn" onclick="deleteFolder(${f.id})">✕</button><div class="folder-icon">📁</div><div class="folder-name">${f.name}</div><div class="folder-count">${grouped[f.id].length}</div>`;
                    card.onclick = (e) => {
                        if(e.target.classList.contains('folder-delete-btn')) return;
                        wrapper.querySelector('.folder-content-list').classList.toggle('open');
                    };
                    wrapper.appendChild(card);
                    const list = document.createElement('ul');
                    list.className = 'folder-content-list';
                    if (openFolderId == f.id) list.classList.add('open');
                    grouped[f.id].forEach(item => list.appendChild(createItemHTML(item)));
                    wrapper.appendChild(list);
                    foldersContainer.appendChild(wrapper);
                });
                if (uncategorized.length > 0) {
                    const h = document.createElement('h3');
                    h.textContent = 'Uncategorized';
                    h.style.fontSize = '1em';
                    h.style.marginTop = '15px';
                    savedList.appendChild(h);
                    uncategorized.forEach(item => savedList.appendChild(createItemHTML(item)));
                }
                updateActionButtons();
            }

            function createItemHTML(item) {
                const li = document.createElement('li');
                const kInfo = item.k ? `(k=${item.k})` : '';
                const noteInfo = item.notes ? `<span class="item-notes">- ${item.notes}</span>` : '';
                const shareLinkBtn = user.tier !== 'Free'
                    ? `<button class="share-link-btn" data-id="${item.id}" title="Copy shareable link">🔗</button>`
                    : '';
                li.innerHTML = `<div class="item-info"><input type="checkbox" class="compare-cb" data-id="${item.id}"><span class="item-details">${item.name} ${kInfo} - ${parseFloat(item.predictability_score).toFixed(2)}% ${noteInfo}</span></div><div class="actions">${shareLinkBtn}<button class="del-btn" data-id="${item.id}" data-fid="${item.folder_id}">🗑️</button></div>`;
                const linkBtn = li.querySelector('.share-link-btn');
                if (linkBtn) {
                    linkBtn.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        const id = linkBtn.dataset.id;
                        try {
                            const res = await fetch(`/api/analyses/${id}/share`, { method: 'POST', credentials: 'include' });
                            const data = await res.json();
                            if (data.share_url) {
                                await navigator.clipboard.writeText(data.share_url);
                                linkBtn.textContent = '✅';
                                setTimeout(() => { linkBtn.textContent = '🔗'; }, 2000);
                            } else {
                                alert(data.error || 'Could not generate link.');
                            }
                        } catch (err) {
                            alert('Failed to copy link. Try again.');
                        }
                    });
                }
                return li;
            }

            function populateFolderSelect() {
                const sel = document.getElementById('folder-select');
                sel.innerHTML = '<option value="">Uncategorized</option>';
                folders.forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.id; opt.textContent = f.name;
                    sel.appendChild(opt);
                });
            }

            moveBtn.addEventListener('click', async () => {
                const checked = document.querySelectorAll('.compare-cb:checked');
                if (checked.length === 0) return;
                let folderOptions = "Enter Folder ID:\n0: Uncategorized\n";
                folders.forEach(f => folderOptions += `${f.id}: ${f.name}\n`);
                const targetId = prompt(folderOptions);
                if (targetId === null) return;
                const fid = targetId === '0' ? "" : parseInt(targetId);
                if (isNaN(fid) && targetId !== "") { alert("Invalid ID"); return; }
                for (const cb of checked) {
                    const id = cb.dataset.id;
                    await fetch(`/api/analysis/${id}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, credentials: 'include', body: JSON.stringify({ folder_id: fid }) });
                }
                await loadFoldersAndAnalyses();
            });

            loadBtn.addEventListener('click', () => {
                const checked = document.querySelectorAll('.compare-cb:checked');
                if (checked.length !== 1) return;
                const id = parseInt(checked[0].dataset.id);
                fetch(`/api/analysis/${id}`, { credentials: 'include' })
                    .then(res => res.json())
                    .then(item => {
                        if(item && !item.error) {
                            scoresInput.value = item.scores.join(', ');
                            notesInput.value = item.notes || '';
                            document.getElementById('dataset-name').value = item.name;
                            if(document.getElementById('folder-select')) document.getElementById('folder-select').value = item.folder_id || "";
                            currentEditingId = id;
                            updateSwitchState(item.k);
                            calculateAndDisplay(item.scores);
                            document.getElementById('save-btn').style.display = 'none';
                            document.getElementById('update-btn').style.display = 'inline-block';
                        } else {
                            showError(item.error || "Failed to load analysis.");
                        }
                    });
            });

            compareBtn.addEventListener('click', async () => {
                const checked = document.querySelectorAll('.compare-cb:checked');
                if (checked.length < 2) return;
                const promises = Array.from(checked).map(cb => fetch(`/api/analysis/${parseInt(cb.dataset.id)}`, { credentials: 'include' }).then(res => res.json()));
                try {
                    const items = await Promise.all(promises);
                    const validItems = items.filter(item => item && !item.error);
                    if (validItems.length < checked.length) showError("Could not load all selected analyses.");
                    if (validItems.length > 1) displayComparisonResults(validItems);
                } catch (e) {
                    console.error("Error fetching comparison data:", e);
                    showError("Failed to load comparison data.");
                }
            });

            document.getElementById('save-btn').addEventListener('click', async () => {
                const name = document.getElementById('dataset-name').value.trim();
                const saveFeedback = document.getElementById('save-feedback');
                if (!name) return alert('Name required');
                const fid = document.getElementById('folder-select').value;
                const notes = notesInput.value.trim();
                const scores = scoresInput.value.split(/[\s,]+/).filter(s => s.trim() !== '').map(Number).filter(n => !isNaN(n));
                if (scores.length < 2) return alert('At least 2 scores are required.');
                let scoreToSave = currentRawScore;
                if (calculationMode === 'sliding') {
                    const response = await fetch('/api/predictability_score', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scores: scores, k: currentK }) });
                    const data = await response.json();
                    scoreToSave = data.predictability_score;
                }
                if (scoreToSave === null) return alert('Could not calculate a base score to save.');
                try {
                    const response = await fetch('/api/analyses', { method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'include', body: JSON.stringify({ name, scores, predictability_score: scoreToSave, folder_id: fid || "", k: currentK, notes: notes }) });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || 'Failed to save analysis');
                    saveFeedback.textContent = 'Saved successfully!';
                    saveFeedback.style.color = '#198754';
                    setTimeout(() => saveFeedback.textContent = '', 3000);
                    document.getElementById('dataset-name').value = '';
                    notesInput.value = '';
                    await loadFoldersAndAnalyses(fid || null);
                } catch (err) {
                    console.error('Save Error:', err);
                    saveFeedback.textContent = 'Error: ' + err.message;
                    saveFeedback.style.color = '#dc3545';
                }
            });

            document.getElementById('update-btn').addEventListener('click', async () => {
                const name = document.getElementById('dataset-name').value.trim();
                const saveFeedback = document.getElementById('save-feedback');
                const fid = document.getElementById('folder-select').value;
                const notes = notesInput.value.trim();
                const scores = scoresInput.value.split(/[\s,]+/).filter(s => s.trim() !== '').map(Number).filter(n => !isNaN(n));
                if (scores.length < 2) return alert('At least 2 scores are required.');
                let scoreToSave = currentRawScore;
                if (calculationMode === 'sliding') {
                     const response = await fetch('/api/predictability_score', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scores: scores, k: currentK }) });
                    const data = await response.json();
                    scoreToSave = data.predictability_score;
                }
                try {
                    const response = await fetch(`/api/analysis/${currentEditingId}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, credentials: 'include', body: JSON.stringify({ name, scores, predictability_score: scoreToSave, folder_id: fid || "", k: currentK, notes: notes }) });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || 'Failed to update analysis');
                    saveFeedback.textContent = 'Updated successfully!';
                    saveFeedback.style.color = '#198754';
                    setTimeout(() => saveFeedback.textContent = '', 3000);
                    document.getElementById('dataset-name').value = '';
                    notesInput.value = '';
                    currentEditingId = null;
                    document.getElementById('save-btn').style.display = 'inline-block';
                    document.getElementById('update-btn').style.display = 'none';
                    await loadFoldersAndAnalyses(fid || null);
                } catch (err) {
                    console.error('Update Error:', err);
                    saveFeedback.textContent = 'Error: ' + err.message;
                    saveFeedback.style.color = '#dc3545';
                }
            });

            newFolderBtn.addEventListener('click', async () => {
                const name = prompt("Folder Name:");
                if(name) {
                    await fetch('/api/folders', { method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'include', body: JSON.stringify({name}) });
                    await loadFoldersAndAnalyses();
                }
            });

            const handleListClick = (e) => {
                if (e.target.classList.contains('del-btn')) {
                    const id = e.target.dataset.id;
                    const fid = e.target.dataset.fid;
                    showConfirmationModal("Delete this analysis?", async () => {
                        await fetch(`/api/analysis/${id}`, { method: 'DELETE', credentials: 'include' });
                        await loadFoldersAndAnalyses(fid);
                    });
                } else if (e.target.classList.contains('compare-cb')) {
                    setTimeout(updateActionButtons, 0);
                }
            };
            savedList.addEventListener('click', handleListClick);
            foldersContainer.addEventListener('click', handleListClick);
            savedList.addEventListener('change', (e) => { if (e.target.classList.contains('compare-cb')) updateActionButtons(); });
            foldersContainer.addEventListener('change', (e) => { if (e.target.classList.contains('compare-cb')) updateActionButtons(); });

            window.deleteFolder = (id) => {
                showConfirmationModal("Delete folder? Items will move to Uncategorized.", async () => {
                    await fetch(`/api/folder/${id}`, { method: 'DELETE', credentials: 'include' });
                    await loadFoldersAndAnalyses();
                });
            };

            deleteSelectedBtn.addEventListener('click', () => {
                const checked = document.querySelectorAll('.compare-cb:checked');
                showConfirmationModal(`Delete ${checked.length} items?`, async () => {
                    for(const cb of checked) {
                        await fetch(`/api/analysis/${cb.dataset.id}`, { method: 'DELETE', credentials: 'include' });
                    }
                    await loadFoldersAndAnalyses();
                });
            });

            exportBtn.addEventListener('click', () => {
                const scores = scoresInput.value.split(/[\s,]+/).filter(s => s.trim() !== '').map(Number).filter(n => !isNaN(n));
                if (scores.length < 2) return alert('Need data to export.');
                const name = document.getElementById('dataset-name').value || 'Analysis';
                const score = document.getElementById('display-score').textContent;
                const notes = notesInput.value;
                let csvContent = "data:text/csv;charset=utf-8,";
                csvContent += "Name,Predictability Score,K-Factor,Notes\n";
                csvContent += `"${name}","${score}","${currentK}","${notes.replace(/"/g, '""')}"\n\n`;
                csvContent += "Data Points\n";
                csvContent += scores.join("\n");
                const encodedUri = encodeURI(csvContent);
                const link = document.createElement("a");
                link.setAttribute("href", encodedUri);
                link.setAttribute("download", `${name}_Predictability.csv`);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            });

            shareBtn.addEventListener('click', () => {
                if (user.tier === 'Free') {
                    alert('⭐ Sharing is a Pro feature. Upgrade to download white-background charts for your posts.');
                    return;
                }
                if (!myChart) return alert("No chart to share!");
                const canvas = document.getElementById('scores-chart');
                const newCanvas = document.createElement('canvas');
                newCanvas.width = canvas.width;
                newCanvas.height = canvas.height;
                const ctx = newCanvas.getContext('2d');
                ctx.fillStyle = '#ffffff';
                ctx.fillRect(0, 0, newCanvas.width, newCanvas.height);
                ctx.drawImage(canvas, 0, 0);
                ctx.font = 'bold 16px Arial';
                ctx.fillStyle = '#007bff';
                ctx.textAlign = 'right';
                ctx.fillText('predictability-api.com', newCanvas.width - 15, newCanvas.height - 15);
                let scoreText = document.getElementById('display-score').textContent;
                const comparisonList = document.getElementById('comparison-list');
                if (comparisonList.style.display === 'flex') {
                    const comparisonDivs = document.querySelectorAll('#comparison-list div');
                    if (comparisonDivs.length > 0) {
                        let yPos = 40;
                        ctx.font = 'bold 24px Arial';
                        ctx.textAlign = 'left';
                        comparisonDivs.forEach(div => {
                            ctx.fillStyle = div.style.color;
                            ctx.fillText(div.textContent, 20, yPos);
                            yPos += 30;
                        });
                    }
                } else {
                    const title = document.getElementById('dataset-name').value || 'Analysis';
                    const notes = notesInput ? notesInput.value.trim() : '';
                    ctx.font = 'bold 28px Arial';
                    ctx.fillStyle = '#333';
                    ctx.textAlign = 'left';
                    ctx.fillText(title, 20, 40);
                    ctx.font = 'bold 36px Arial';
                    // Sliding window shows "Avg: X.XX%" — skip redundant "Score:" prefix
                    ctx.fillText(calculationMode === 'sliding' ? scoreText : `Score: ${scoreText}`, 20, 80);
                    if (notes) {
                        ctx.font = '16px Arial';
                        ctx.fillStyle = '#555';
                        ctx.fillText(notes.length > 80 ? notes.slice(0, 77) + '…' : notes, 20, 116);
                    }
                }
                const link = document.createElement('a');
                link.download = 'Predictability_Score.png';
                link.href = newCanvas.toDataURL('image/png');
                link.click();
            });

            fileUpload.addEventListener('change', (event) => {
                if (user.tier === 'Free') {
                    alert('⭐ CSV & file upload is a Pro feature. Upgrade to import your data directly.');
                    event.target.value = '';
                    return;
                }
                const file = event.target.files[0];
                if (!file) return;
                clearResults();
                if (file.name.endsWith('.txt')) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        const scores = e.target.result.split(/[\s,]+/).filter(s => s.trim() !== '').map(Number).filter(n => !isNaN(n));
                        if (scores.length > 0) {
                            scoresInput.value = scores.join(', ');
                            calculateAndDisplay(scores);
                        } else {
                            showError('The .txt file is empty or has no numbers.');
                        }
                    };
                    reader.readAsText(file);
                    return;
                }
                Papa.parse(file, {
                    header: true, skipEmptyLines: true, dynamicTyping: true,
                    complete: (results) => {
                        if (results.data && results.data.length > 0) {
                            parsedData = results.data;
                            displayPreview(results.meta.fields, parsedData.slice(0, 3));
                        } else {
                            showError('CSV file appears to be empty or could not be parsed.');
                        }
                    },
                    error: (err) => showError(`A fatal error occurred while parsing the CSV file: ${err.message}`)
                });
            });

            function displayPreview(headers, dataRows) {
                let table = '<table><thead><tr>';
                headers.forEach(header => { table += `<th data-header="${header}" style="cursor:pointer; background:#e9ecef; padding:5px; border:1px solid #dee2e6;">${header}</th>`; });
                table += '</tr></thead><tbody>';
                dataRows.forEach(row => {
                    table += '<tr>';
                    headers.forEach(header => { table += `<td style="padding:5px; border:1px solid #dee2e-6;">${row[header] || ''}</td>`; });
                    table += '</tr>';
                });
                table += '</tbody></table>';
                filePreview.innerHTML = table;
                previewArea.style.display = 'block';
            }

            filePreview.addEventListener('click', (event) => {
                if (event.target.tagName === 'TH') {
                    const header = event.target.dataset.header;
                    const scores = parsedData.map(row => parseFloat(row[header])).filter(n => !isNaN(n));
                    if (scores.length === 0) { showError(`Column '${header}' has no numbers.`); return; }
                    scoresInput.value = scores.join(', ');
                    calculateAndDisplay(scores);
                }
            });

            clearPreviewBtn.addEventListener('click', () => {
                previewArea.style.display = 'none';
                filePreview.innerHTML = '';
                parsedData = [];
                fileUpload.value = '';
            });

            function populateWithExampleData() {
                const exampleName = "Simulated Bridge Sensor Data (Vibration Frequency)";
                const exampleScores = [50.1, 50.2, 49.9, 50.0, 49.8, 50.1, 50.3, 50.2, 49.9, 50.0, 50.1, 50.4, 50.5, 50.7, 51.2, 51.5, 51.9, 52.5];
                document.getElementById('dataset-name').value = exampleName;
                scoresInput.value = exampleScores.join(', ');
                // Do NOT calculate automatically
            }

            generateKeyBtn.addEventListener('click', async () => {
                try {
                    const response = await fetch('/api/generate_key', { method: 'POST', credentials: 'include' });
                    const data = await response.json();
                    if(response.ok) {
                        apiKeyDisplay.value = data.api_key;
                        alert('New API Key Generated!');
                    } else {
                        alert(data.error || 'Failed to generate key.');
                    }
                } catch(e) { alert('Server error.'); }
            });

            // --- Initial Load ---
            checkSession();
            populateWithExampleData();

        });
        // --- End of Consolidated Script ---
