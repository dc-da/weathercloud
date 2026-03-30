/* ==========================================================================
   Recovery Storico — /recovery
   ========================================================================== */

(() => {
    "use strict";

    const statusBadge = (status) => {
        const map = {
            pending:     "bg-secondary",
            detecting:   "bg-info",
            in_progress: "bg-warning",
            paused:      "bg-primary",
            completed:   "bg-success",
            no_data:     "bg-danger",
            error:       "bg-danger",
            running:     "bg-warning",
            success:     "bg-success",
            budget_exhausted: "bg-primary",
        };
        const cls = map[status] || "bg-secondary";
        return `<span class="badge ${cls}">${status}</span>`;
    };

    const pct = (done, total) => {
        if (!total || total === 0) return "0%";
        return Math.round((done / total) * 100) + "%";
    };

    const progressBar = (done, total) => {
        const p = total > 0 ? Math.round((done / total) * 100) : 0;
        return `
            <div class="d-flex align-items-center gap-2">
                <div class="progress flex-grow-1" style="height:16px; min-width:80px">
                    <div class="progress-bar progress-bar-striped" style="width:${p}%">${p}%</div>
                </div>
                <small style="color:var(--ws-text-muted); white-space:nowrap">${done || 0}/${total || 0}</small>
            </div>`;
    };

    const shortDate = (v) => {
        if (!v) return "--";
        return String(v).slice(0, 10);
    };

    const shortTime = (v) => {
        if (!v) return "--";
        return String(v).slice(0, 19).replace("T", " ");
    };

    const fetchStatus = async () => {
        try {
            const resp = await fetch("/api/recovery/status");
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            renderQueue(data.queue || []);
            renderLog(data.recent_runs || []);
        } catch (err) {
            console.error("Recovery status fetch error:", err);
        }
    };

    const renderQueue = (queue) => {
        const tbody = document.getElementById("queueBody");
        if (!tbody) return;

        if (!queue.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center" style="color:var(--ws-text-muted)">Nessuna stazione in coda</td></tr>';
            return;
        }

        tbody.innerHTML = queue.map((e) => `
            <tr>
                <td><strong>${e.station_id}</strong></td>
                <td>${statusBadge(e.status)}</td>
                <td>${shortDate(e.detected_start)}</td>
                <td>${shortDate(e.current_date)}</td>
                <td>${shortDate(e.end_date)}</td>
                <td>${progressBar(e.days_done, e.days_total)}</td>
                <td>${e.api_calls_used || 0}</td>
                <td>${shortTime(e.last_run_at)}</td>
            </tr>
        `).join("");
    };

    const renderLog = (logs) => {
        const tbody = document.getElementById("logBody");
        if (!tbody) return;

        if (!logs.length) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center" style="color:var(--ws-text-muted)">Nessuna esecuzione registrata</td></tr>';
            return;
        }

        tbody.innerHTML = logs.map((l) => `
            <tr>
                <td>${shortDate(l.run_date)}</td>
                <td>${statusBadge(l.status)}</td>
                <td>${shortTime(l.started_at)}</td>
                <td>${shortTime(l.completed_at)}</td>
                <td>${l.stations_processed || 0}</td>
                <td>${l.api_calls_used || 0}</td>
                <td>${l.days_recovered || 0}</td>
                <td>${l.days_skipped || 0}</td>
                <td>${l.new_stations_found || 0}</td>
                <td>${l.error_message
                    ? '<span style="color:var(--ws-danger)" class="small">' + l.error_message + '</span>'
                    : ''}</td>
            </tr>
        `).join("");
    };

    const runNow = async () => {
        const btn = document.getElementById("btnRunNow");
        if (btn) btn.disabled = true;
        try {
            const resp = await fetch("/api/recovery/run-now", { method: "POST" });
            const data = await resp.json();
            if (!resp.ok) {
                alert(data.error || "Errore nell'avvio del recovery");
            }
        } catch (err) {
            alert("Errore di connessione");
        }
        if (btn) setTimeout(() => { btn.disabled = false; }, 5000);
    };

    document.addEventListener("DOMContentLoaded", () => {
        fetchStatus();
        document.getElementById("btnRefresh")?.addEventListener("click", fetchStatus);
        document.getElementById("btnRunNow")?.addEventListener("click", runNow);

        // Auto-refresh every 30s
        setInterval(fetchStatus, 30000);
    });
})();
