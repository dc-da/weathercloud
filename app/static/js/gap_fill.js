/* ==========================================================================
   Gap-Fill — /station/<id>/gap-fill
   ========================================================================== */

(() => {
    "use strict";

    const wsUrl = (path) => (window.WS_API_PREFIX || "") + path;

    const qualityBadge = (score) => {
        if (score >= 75) return '<span class="badge bg-success">Ottima</span>';
        if (score >= 50) return '<span class="badge bg-primary">Buona</span>';
        if (score >= 25) return '<span class="badge bg-warning">Discreta</span>';
        if (score > 0)  return '<span class="badge bg-danger">Scarsa</span>';
        return '<span class="badge bg-secondary">Inutile</span>';
    };

    const fetchStatus = async () => {
        try {
            const resp = await fetch(wsUrl("/api/gap-fill/status"));
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            renderSummary(data);
            renderStations(data.stations || []);
            renderMissingDays(data.missing_days_sample || [], data.missing_days_count || 0);
        } catch (err) {
            console.error("Gap-fill status error:", err);
        }
    };

    const renderSummary = (data) => {
        const el = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };
        el("missingCount", data.missing_days_count || 0);
        el("filledCount", data.gap_filled_count || 0);
        el("stationCount", (data.stations || []).filter(s => s.score > 0).length);
    };

    const renderStations = (stations) => {
        const tbody = document.getElementById("stationsBody");
        if (!tbody) return;

        if (!stations.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center" style="color:var(--ws-text-muted)">Nessuna stazione gap-fill configurata o coordinate non ancora disponibili</td></tr>';
            return;
        }

        tbody.innerHTML = stations.map(s => `
            <tr${s.score <= 0 ? ' style="opacity:0.5"' : ''}>
                <td><strong>${s.station_id}</strong></td>
                <td>${s.name}</td>
                <td>${s.latitude?.toFixed(3) || '--'}</td>
                <td>${s.longitude?.toFixed(3) || '--'}</td>
                <td>${s.distance_km}</td>
                <td><strong>${s.score}</strong>/100</td>
                <td>${qualityBadge(s.score)}</td>
            </tr>
        `).join("");
    };

    const renderMissingDays = (sample, total) => {
        const el = document.getElementById("missingDaysPreview");
        if (!el) return;

        if (!sample.length) {
            el.innerHTML = '<span style="color:var(--ws-success)">Nessun giorno mancante!</span>';
            return;
        }

        const badges = sample.map(d => `<span class="badge bg-secondary me-1 mb-1">${d}</span>`).join("");
        const more = total > sample.length ? `<span class="badge bg-info">... e altri ${total - sample.length}</span>` : "";
        el.innerHTML = badges + more;
    };

    const runGapFill = async () => {
        const btn = document.getElementById("btnRunGapFill");
        if (btn) btn.disabled = true;

        const resultCard = document.getElementById("resultCard");
        const resultBody = document.getElementById("resultBody");

        try {
            const resp = await fetch(wsUrl("/api/gap-fill/run"), { method: "POST" });
            const data = await resp.json();

            if (resultCard) resultCard.classList.remove("d-none");
            if (resultBody) {
                const statusCls = data.status === "success" ? "alert-success" : "alert-warning";
                resultBody.innerHTML = `
                    <div class="alert ${statusCls} mb-0">
                        <strong>${data.message}</strong>
                        ${data.days_filled ? `<br>Giorni riempiti: <strong>${data.days_filled}</strong>` : ''}
                        ${data.days_unfillable ? `<br>Non riempibili: <strong>${data.days_unfillable}</strong>` : ''}
                        ${data.stations_used ? `<br>Stazioni utilizzate: <strong>${data.stations_used}</strong>` : ''}
                    </div>`;
            }

            // Refresh status after execution
            await fetchStatus();
        } catch (err) {
            console.error("Gap-fill run error:", err);
            if (resultCard) resultCard.classList.remove("d-none");
            if (resultBody) resultBody.innerHTML = '<div class="alert alert-danger mb-0">Errore durante l\'esecuzione</div>';
        }

        if (btn) btn.disabled = false;
    };

    document.addEventListener("DOMContentLoaded", () => {
        fetchStatus();
        document.getElementById("btnRefresh")?.addEventListener("click", fetchStatus);
        document.getElementById("btnRunGapFill")?.addEventListener("click", runGapFill);
    });
})();
