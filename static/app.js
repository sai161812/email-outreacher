// Simple Toast system
function showToast(message, isError = false) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<span class="status-dot ${isError ? 'danger' : 'success'}"></span> ${message}`;
    container.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 4000);
}

// Button loading wrapper
async function withLoading(btn, asyncFn) {
    if (btn.disabled) return;
    const originalHtml = btn.innerHTML;
    const originalWidth = btn.offsetWidth;
    
    btn.disabled = true;
    if (originalWidth > 0) {
        btn.style.minWidth = `${originalWidth}px`;
    }
    btn.innerHTML = `<span class="spinner"></span>` + btn.innerHTML;
    
    try {
        await asyncFn();
    } finally {
        if (document.body.contains(btn)) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
            btn.style.minWidth = '';
        }
    }
}

// Navigation
document.querySelectorAll('#sidebar-nav .nav-item').forEach(nav => {
    nav.addEventListener('click', (e) => {
        document.querySelectorAll('#sidebar-nav .nav-item').forEach(n => n.classList.remove('active'));
        e.target.classList.add('active');
        
        const viewId = e.target.dataset.view;
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById('view-' + viewId).classList.add('active');
        
        loadDataForView(viewId);
    });
});

async function apiCall(url, method = 'GET', body = null) {
    try {
        const options = { method, headers: {} };
        if (body) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }
        const res = await fetch(url, options);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'API Error');
        return data;
    } catch (err) {
        showToast(err.message, true);
        throw err;
    }
}

// View Loaders
function loadDataForView(viewId) {
    if (viewId === 'dashboard') loadDashboard();
    else if (viewId === 'contacts') loadContacts();
    else if (viewId === 'review') loadReviewQueue();
    else if (viewId === 'tracking') loadTracking();
}

async function loadDashboard() {
    const data = await apiCall('/api/stats');
    const summary = data.summary;
    const kpiRow = document.getElementById('kpi-container');
    kpiRow.innerHTML = '';
    const metrics = [
        { label: 'PENDING REVIEW', val: summary.pending_review || 0 },
        { label: 'APPROVED', val: summary.approved || 0 },
        { label: 'SENT', val: summary.sent || 0 },
        { label: 'REPLIED', val: summary.replied || 0 },
    ];
    metrics.forEach(m => {
        kpiRow.innerHTML += `
            <div class="kpi-card">
                <div class="kpi-label">${m.label}</div>
                <div class="kpi-value mono-num">${m.val}</div>
            </div>
        `;
    });
    
    const tbody = document.querySelector('#table-variant-stats tbody');
    tbody.innerHTML = '';
    data.stats.by_variant.forEach(v => {
        tbody.innerHTML += `
            <tr>
                <td>${v.variant}</td>
                <td class="col-num">${v.sent}</td>
                <td class="col-num">${v.replied}</td>
                <td class="col-num">${v.interviews}</td>
                <td class="col-num">${v.reply_rate}</td>
            </tr>
        `;
    });
}

async function loadContacts() {
    const contacts = await apiCall('/api/contacts');
    const tbody = document.querySelector('#table-contacts tbody');
    tbody.innerHTML = '';
    contacts.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${c.company_name}</td>
            <td>${c.name || 'N/A'}</td>
            <td class="mono-num">${c.email}</td>
            <td><button class="secondary btn-compose" data-cid="${c.company_id}" data-ctid="${c.id}">Draft Email</button></td>
        `;
        tbody.appendChild(tr);
    });
    
    document.querySelectorAll('.btn-compose').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const cid = e.target.dataset.cid;
            const ctid = e.target.dataset.ctid;
            withLoading(e.currentTarget, async () => {
                await apiCall('/api/compose', 'POST', { company_id: parseInt(cid), contact_id: parseInt(ctid) });
                showToast('Draft created successfully');
            });
        });
    });
}

async function loadReviewQueue() {
    const drafts = await apiCall('/api/review');
    const container = document.getElementById('review-container');
    container.innerHTML = '';
    
    if (drafts.length === 0) {
        container.innerHTML = '<div style="color: var(--text-secondary);">No drafts pending review.</div>';
        return;
    }
    
    drafts.forEach(d => {
        const isWarning = d.qc_warnings ? 'has-warning' : '';
        const warningHtml = d.qc_warnings ? `<div class="qc-warning-text">QC FLAG: ${d.qc_warnings}</div>` : '';
        
        const card = document.createElement('div');
        card.className = `review-card ${isWarning}`;
        card.innerHTML = `
            <div class="review-card-header">
                <div>
                    <div class="review-card-meta">PENDING REVIEW • ${d.company_name}</div>
                    <div class="review-card-title">${d.contact_email}</div>
                    ${warningHtml}
                </div>
            </div>
            <div class="input-group">
                <div class="input-label">Subject</div>
                <input type="text" class="inp-subject" value="${d.subject || ''}">
            </div>
            <div class="input-group">
                <div class="input-label">Hook</div>
                <input type="text" class="inp-hook" value="${d.hook || ''}">
            </div>
            <div class="input-group">
                <div class="input-label">Body</div>
                <textarea class="inp-body">${d.body || ''}</textarea>
            </div>
            <div class="button-group">
                <button class="primary btn-approve" data-id="${d.id}">Approve</button>
                <button class="secondary btn-save" data-id="${d.id}">Save Edits</button>
                <button class="destructive btn-reject" data-id="${d.id}">Reject</button>
            </div>
        `;
        container.appendChild(card);
    });
    
    // Bind actions
    document.querySelectorAll('.btn-approve').forEach(b => b.addEventListener('click', (e) => {
        withLoading(e.currentTarget, async () => {
            const id = e.currentTarget.dataset.id;
            await apiCall(`/api/review/${id}`, 'POST', { action: 'approve' });
            showToast('Draft approved');
            loadReviewQueue();
        });
    }));
    document.querySelectorAll('.btn-reject').forEach(b => b.addEventListener('click', (e) => {
        withLoading(e.currentTarget, async () => {
            const id = e.currentTarget.dataset.id;
            await apiCall(`/api/review/${id}`, 'POST', { action: 'reject' });
            showToast('Draft rejected', true);
            loadReviewQueue();
        });
    }));
    document.querySelectorAll('.btn-save').forEach(b => b.addEventListener('click', (e) => {
        withLoading(e.currentTarget, async () => {
            const btn = e.currentTarget;
            const id = btn.dataset.id;
            const card = btn.closest('.review-card');
            const subject = card.querySelector('.inp-subject').value;
            const hook = card.querySelector('.inp-hook').value;
            const body = card.querySelector('.inp-body').value;
            await apiCall(`/api/review/${id}`, 'POST', { action: 'edit', subject, hook, body });
            showToast('Edits saved');
        });
    }));
}

async function loadTracking() {
    const due = await apiCall('/api/tracking/due');
    const sent = await apiCall('/api/tracking');
    
    const dueBody = document.querySelector('#table-due tbody');
    dueBody.innerHTML = '';
    due.forEach(d => {
        dueBody.innerHTML += `
            <tr>
                <td>${d.company_name}</td>
                <td class="mono-num">${d.contact_email}</td>
                <td class="mono-num">${d.sent_at}</td>
                <td><button class="secondary btn-followup" data-id="${d.id}">Draft Follow-up</button></td>
            </tr>
        `;
    });
    
    document.querySelectorAll('.btn-followup').forEach(b => b.addEventListener('click', (e) => {
        withLoading(e.currentTarget, async () => {
            const id = e.currentTarget.dataset.id;
            await apiCall(`/api/tracking/${id}/followup`, 'POST', {});
            showToast('Follow-up drafted');
            loadTracking();
        });
    }));
    
    const sentBody = document.querySelector('#table-tracking tbody');
    sentBody.innerHTML = '';
    sent.forEach(s => {
        let dotClass = 'neutral';
        if (['replied','interview_scheduled','interview_completed','offer'].includes(s.status)) dotClass = 'success';
        if (s.status === 'bounced' || s.status === 'no_offer') dotClass = 'danger';
        if (s.status === 'ghosted') dotClass = 'warning';
        
        sentBody.innerHTML += `
            <tr>
                <td>${s.company_name}</td>
                <td class="mono-num">${s.contact_email}</td>
                <td>
                    <div class="dropdown-container">
                        <button class="secondary">
                            <span class="status-dot ${dotClass}"></span> ${s.status}
                        </button>
                        <div class="dropdown-menu">
                            <button class="dropdown-item btn-mark" data-id="${s.id}" data-st="replied"><span class="status-dot success"></span> replied</button>
                            <button class="dropdown-item btn-mark" data-id="${s.id}" data-st="interview_scheduled"><span class="status-dot success"></span> interview_scheduled</button>
                            <button class="dropdown-item btn-mark" data-id="${s.id}" data-st="offer"><span class="status-dot success"></span> offer</button>
                            <button class="dropdown-item btn-mark" data-id="${s.id}" data-st="ghosted"><span class="status-dot warning"></span> ghosted</button>
                            <button class="dropdown-item btn-mark" data-id="${s.id}" data-st="bounced"><span class="status-dot danger"></span> bounced</button>
                        </div>
                    </div>
                </td>
                <td class="mono-num">${s.updated_at}</td>
            </tr>
        `;
    });
    
    document.querySelectorAll('.btn-mark').forEach(b => b.addEventListener('click', (e) => {
        withLoading(e.currentTarget, async () => {
            const id = e.currentTarget.dataset.id;
            const st = e.currentTarget.dataset.st;
            await apiCall(`/api/tracking/${id}/mark`, 'POST', { status: st });
            showToast('Status updated');
            loadTracking();
        });
    }));
}

// Global actions
document.getElementById('btn-send-batch').addEventListener('click', (e) => {
    withLoading(e.currentTarget, async () => {
        const res = await apiCall('/api/send', 'POST', {});
        showToast(`Batch run. Sent ${res.summary.length} emails.`);
        loadDashboard();
    });
});

document.getElementById('btn-check-replies').addEventListener('click', (e) => {
    withLoading(e.currentTarget, async () => {
        const res = await apiCall('/api/check_replies', 'POST', {});
        showToast(`Checked IMAP. Found ${res.matches.length} replies.`);
        loadDashboard();
    });
});

// Modals
document.getElementById('btn-show-add-contact').addEventListener('click', () => {
    document.getElementById('modal-add-contact').classList.remove('hidden');
});
document.getElementById('btn-cancel-add-contact').addEventListener('click', () => {
    document.getElementById('modal-add-contact').classList.add('hidden');
});
document.getElementById('btn-save-contact').addEventListener('click', (e) => {
    withLoading(e.currentTarget, async () => {
        const cid = document.getElementById('add-company-id').value;
        const email = document.getElementById('add-email').value;
        const name = document.getElementById('add-name').value;
        
        await apiCall('/api/contacts', 'POST', { company_id: cid, email, name });
        showToast('Contact added');
        document.getElementById('modal-add-contact').classList.add('hidden');
        loadContacts();
    });
});


document.getElementById('inp-import-csv').addEventListener('change', async (e) => {
    if (!e.target.files.length) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        showToast('Uploading CSV...', false);
        const res = await fetch('/api/contacts/import', { method: 'POST', body: formData });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Upload failed');
        
        const errCount = data.errors ? data.errors.length : 0;
        showToast(`Imported ${data.companies_created} companies, ${data.contacts_created} contacts. ${errCount} errors.`);
        loadContacts();
    } catch (err) {
        showToast(err.message, true);
    }
    e.target.value = '';
});
// Initial load
loadDashboard();

