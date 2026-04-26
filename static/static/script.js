// ========== Gmail Verifier - Frontend Script ==========

let statusInterval = null;
let currentTab = 'live';
let autoRefresh = true;

// DOM Elements
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const progressBar = document.getElementById('progressBar');
const resultsList = document.getElementById('resultsList');

// Format time (seconds to MM:SS)
function formatTime(seconds) {
    if (!seconds || seconds < 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Format number with commas
function formatNumber(num) {
    return num ? num.toLocaleString() : '0';
}

// Update status from API
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        // Update stats
        document.getElementById('processed').textContent = formatNumber(data.processed);
        document.getElementById('live').textContent = formatNumber(data.live);
        document.getElementById('disabled').textContent = formatNumber(data.new_disabled);
        document.getElementById('invalid').textContent = formatNumber(data.invalid);
        document.getElementById('error').textContent = formatNumber(data.error);
        document.getElementById('speed').textContent = data.speed || 0;
        document.getElementById('elapsed').textContent = formatTime(data.elapsed);
        
        // Update progress
        const progress = data.total > 0 ? (data.processed / data.total) * 100 : 0;
        progressBar.style.width = `${progress}%`;
        progressBar.textContent = `${Math.round(progress)}%`;
        
        // Update file info
        if (data.files_processed && data.total_files) {
            const fileInfo = document.getElementById('fileInfo');
            if (fileInfo) {
                fileInfo.textContent = `${data.files_processed} / ${data.total_files} ملفات`;
            }
        }
        
        // Update batch info
        if (data.current_batch && data.total_batches) {
            const batchInfo = document.getElementById('batchInfo');
            if (batchInfo) {
                batchInfo.textContent = `دفعة ${data.current_batch} / ${data.total_batches}`;
            }
        }
        
        // Update button states
        startBtn.disabled = data.is_running;
        stopBtn.disabled = !data.is_running;
        
        // Update status badge
        const statusBadge = document.getElementById('statusBadge');
        if (statusBadge) {
            if (data.is_running) {
                statusBadge.textContent = '🟢 جاري الفحص...';
                statusBadge.className = 'status-badge status-running';
            } else {
                statusBadge.textContent = data.processed === data.total && data.total > 0 ? '✅ اكتمل' : '⏹ متوقف';
                statusBadge.className = 'status-badge status-stopped';
            }
        }
        
        // Auto-stop interval when complete
        if (!data.is_running && data.processed === data.total && data.total > 0) {
            if (statusInterval) {
                clearInterval(statusInterval);
                statusInterval = null;
            }
            addLog('✅ اكتمل الفحص بنجاح!', 'success');
        }
        
    } catch (error) {
        console.error('Error fetching status:', error);
        addLog('⚠️ خطأ في الاتصال بالخادم', 'error');
    }
}

// Load results for current tab
async function loadResults() {
    try {
        const response = await fetch('/api/results');
        const data = await response.json();
        
        let results = [];
        let title = '';
        
        switch(currentTab) {
            case 'live':
                results = data.live || [];
                title = '✅ الحسابات النشطة';
                break;
            case 'disabled':
                results = data.new_disabled || [];
                title = '🔒 الحسابات المعطلة';
                break;
            case 'invalid':
                results = data.invalid || [];
                title = '❌ الحسابات غير الموجودة';
                break;
            default:
                results = [];
        }
        
        if (results.length === 0) {
            resultsList.innerHTML = `<div class="empty-state">
                <i>📭</i>
                <div>لا توجد نتائج في هذا التصنيف بعد</div>
                <small>ابدأ الفحص لظهور النتائج</small>
            </div>`;
            return;
        }
        
        resultsList.innerHTML = results.map(email => 
            `<div class="result-item" data-tooltip="انقر لنسخ" onclick="copyToClipboard('${email}')">
                📧 ${email}
            </div>`
        ).join('');
        
    } catch (error) {
        console.error('Error loading results:', error);
        resultsList.innerHTML = `<div class="empty-state">
            <i>⚠️</i>
            <div>خطأ في تحميل النتائج</div>
        </div>`;
    }
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        addLog(`📋 تم نسخ: ${text}`, 'success');
        // Visual feedback
        const tooltip = document.createElement('div');
        tooltip.textContent = '✅ تم النسخ';
        tooltip.style.position = 'fixed';
        tooltip.style.bottom = '20px';
        tooltip.style.right = '20px';
        tooltip.style.background = '#48bb78';
        tooltip.style.color = 'white';
        tooltip.style.padding = '10px 20px';
        tooltip.style.borderRadius = '10px';
        tooltip.style.zIndex = '9999';
        document.body.appendChild(tooltip);
        setTimeout(() => tooltip.remove(), 2000);
    });
}

// Add log message
function addLog(message, type = 'info') {
    const logContainer = document.getElementById('logContainer');
    if (!logContainer) return;
    
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString('ar-EG');
    logEntry.innerHTML = `<span class="log-time">[${time}]</span> ${message}`;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
    
    // Keep only last 100 logs
    while (logContainer.children.length > 100) {
        logContainer.removeChild(logContainer.firstChild);
    }
}

// Start verification
async function startVerification() {
    try {
        addLog('🚀 بدء عملية فحص حسابات Gmail...', 'info');
        
        const response = await fetch('/api/start', { method: 'POST' });
        const data = await response.json();
        
        if (data.error) {
            addLog(`❌ ${data.error}`, 'error');
            return;
        }
        
        addLog('✅ تم بدء الفحص بنجاح', 'success');
        
        // Start auto-refresh
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(() => {
            updateStatus();
            if (autoRefresh) loadResults();
        }, 1000);
        
    } catch (error) {
        addLog(`❌ خطأ: ${error.message}`, 'error');
    }
}

// Stop verification
async function stopVerification() {
    try {
        addLog('⏹ جاري إيقاف الفحص...', 'info');
        
        const response = await fetch('/api/stop', { method: 'POST' });
        const data = await response.json();
        
        if (data.status === 'stopped') {
            addLog('✅ تم إيقاف الفحص', 'success');
        }
        
    } catch (error) {
        addLog(`❌ خطأ: ${error.message}`, 'error');
    }
}

// Download results
async function downloadResults(category) {
    try {
        window.open(`/api/download/${category}`, '_blank');
        addLog(`📥 جاري تحميل نتائج ${category}...`, 'info');
    } catch (error) {
        addLog(`❌ خطأ في التحميل: ${error.message}`, 'error');
    }
}

// Clear logs
function clearLogs() {
    const logContainer = document.getElementById('logContainer');
    if (logContainer) {
        logContainer.innerHTML = '';
        addLog('✨ تم مسح السجل', 'info');
    }
}

// Toggle auto-refresh
function toggleAutoRefresh() {
    autoRefresh = !autoRefresh;
    const btn = document.getElementById('autoRefreshBtn');
    if (btn) {
        btn.textContent = autoRefresh ? '🔄 تحديث تلقائي: ON' : '🔄 تحديث تلقائي: OFF';
        btn.style.opacity = autoRefresh ? '1' : '0.6';
    }
    addLog(autoRefresh ? '🔄 تم تفعيل التحديث التلقائي' : '⏸ تم إيقاف التحديث التلقائي', 'info');
}

// Export all results
async function exportAllResults() {
    try {
        const response = await fetch('/api/results');
        const data = await response.json();
        
        const allResults = {
            live: data.live || [],
            new_disabled: data.new_disabled || [],
            invalid: data.invalid || [],
            timestamp: new Date().toISOString()
        };
        
        const blob = new Blob([JSON.stringify(allResults, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `gmail_verifier_results_${new Date().toISOString().slice(0,19)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        addLog('📦 تم تصدير جميع النتائج', 'success');
    } catch (error) {
        addLog(`❌ خطأ في التصدير: ${error.message}`, 'error');
    }
}

// Initialize event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentTab = tab.dataset.tab;
            loadResults();
        });
    });
    
    // Button listeners
    if (startBtn) startBtn.addEventListener('click', startVerification);
    if (stopBtn) stopBtn.addEventListener('click', stopVerification);
    
    const clearLogsBtn = document.getElementById('clearLogsBtn');
    if (clearLogsBtn) clearLogsBtn.addEventListener('click', clearLogs);
    
    const autoRefreshBtn = document.getElementById('autoRefreshBtn');
    if (autoRefreshBtn) autoRefreshBtn.addEventListener('click', toggleAutoRefresh);
    
    const exportBtn = document.getElementById('exportBtn');
    if (exportBtn) exportBtn.addEventListener('click', exportAllResults);
    
    // Download buttons
    const downloadLive = document.getElementById('downloadLive');
    const downloadDisabled = document.getElementById('downloadDisabled');
    const downloadInvalid = document.getElementById('downloadInvalid');
    
    if (downloadLive) downloadLive.addEventListener('click', () => downloadResults('live'));
    if (downloadDisabled) downloadDisabled.addEventListener('click', () => downloadResults('new_disabled'));
    if (downloadInvalid) downloadInvalid.addEventListener('click', () => downloadResults('invalid'));
    
    // Initial load
    updateStatus();
    loadResults();
    
    // Start auto-refresh
    statusInterval = setInterval(() => {
        updateStatus();
        if (autoRefresh) loadResults();
    }, 1000);
    
    addLog('✨ النظام جاهز. استخدم الأزرار للبدء', 'info');
});
