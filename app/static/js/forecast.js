/* ==========================================================================
   Previsioni 5 Giorni — /station/<id>/forecast
   ========================================================================== */

(() => {
    "use strict";

    const wsUrl = (path) => (window.WS_API_PREFIX || "") + path;

    // WU icon code → Bootstrap icon + color
    const wxIcon = (code) => {
        if (code == null) return { icon: "bi-question-circle", color: "var(--ws-text-muted)" };
        const map = {
            0:  { icon: "bi-tornado", color: "var(--ws-danger)" },
            1:  { icon: "bi-tropical-storm", color: "var(--ws-danger)" },
            2:  { icon: "bi-tropical-storm", color: "var(--ws-danger)" },
            3:  { icon: "bi-cloud-lightning-rain-fill", color: "var(--ws-warning)" },
            4:  { icon: "bi-cloud-lightning-rain-fill", color: "var(--ws-warning)" },
            5:  { icon: "bi-cloud-sleet-fill", color: "var(--ws-accent)" },
            6:  { icon: "bi-cloud-sleet-fill", color: "var(--ws-accent)" },
            7:  { icon: "bi-cloud-snow-fill", color: "var(--ws-temp-cold)" },
            8:  { icon: "bi-cloud-drizzle-fill", color: "var(--ws-accent)" },
            9:  { icon: "bi-cloud-drizzle-fill", color: "var(--ws-accent)" },
            10: { icon: "bi-cloud-sleet-fill", color: "var(--ws-accent)" },
            11: { icon: "bi-cloud-rain-fill", color: "var(--ws-accent)" },
            12: { icon: "bi-cloud-rain-fill", color: "var(--ws-accent)" },
            13: { icon: "bi-cloud-snow-fill", color: "var(--ws-temp-cold)" },
            14: { icon: "bi-snow2", color: "var(--ws-temp-cold)" },
            15: { icon: "bi-snow", color: "var(--ws-temp-cold)" },
            16: { icon: "bi-cloud-snow-fill", color: "var(--ws-temp-cold)" },
            17: { icon: "bi-cloud-hail-fill", color: "var(--ws-accent)" },
            18: { icon: "bi-cloud-sleet-fill", color: "var(--ws-accent)" },
            19: { icon: "bi-wind", color: "var(--ws-text-secondary)" },
            20: { icon: "bi-cloud-fog-fill", color: "var(--ws-text-muted)" },
            21: { icon: "bi-cloud-haze-fill", color: "var(--ws-text-muted)" },
            22: { icon: "bi-cloud-haze-fill", color: "var(--ws-text-muted)" },
            23: { icon: "bi-wind", color: "var(--ws-text-secondary)" },
            24: { icon: "bi-wind", color: "var(--ws-text-secondary)" },
            25: { icon: "bi-snow2", color: "var(--ws-temp-cold)" },
            26: { icon: "bi-clouds-fill", color: "var(--ws-text-secondary)" },
            27: { icon: "bi-cloud-fill", color: "var(--ws-text-secondary)" },
            28: { icon: "bi-clouds-fill", color: "var(--ws-text-secondary)" },
            29: { icon: "bi-cloud-moon-fill", color: "var(--ws-text-secondary)" },
            30: { icon: "bi-cloud-sun-fill", color: "var(--ws-warning)" },
            31: { icon: "bi-moon-stars-fill", color: "var(--ws-accent)" },
            32: { icon: "bi-sun-fill", color: "var(--ws-warning)" },
            33: { icon: "bi-moon-fill", color: "var(--ws-accent)" },
            34: { icon: "bi-brightness-high-fill", color: "var(--ws-warning)" },
            35: { icon: "bi-cloud-hail-fill", color: "var(--ws-accent)" },
            36: { icon: "bi-thermometer-sun", color: "var(--ws-temp-hot)" },
            37: { icon: "bi-cloud-lightning-fill", color: "var(--ws-warning)" },
            38: { icon: "bi-cloud-lightning-fill", color: "var(--ws-warning)" },
            39: { icon: "bi-cloud-rain-fill", color: "var(--ws-accent)" },
            40: { icon: "bi-cloud-rain-heavy-fill", color: "var(--ws-accent)" },
            41: { icon: "bi-cloud-snow-fill", color: "var(--ws-temp-cold)" },
            42: { icon: "bi-snow", color: "var(--ws-temp-cold)" },
            43: { icon: "bi-cloud-snow-fill", color: "var(--ws-temp-cold)" },
            44: { icon: "bi-cloud-fill", color: "var(--ws-text-secondary)" },
            45: { icon: "bi-cloud-rain-fill", color: "var(--ws-accent)" },
            46: { icon: "bi-cloud-snow-fill", color: "var(--ws-temp-cold)" },
            47: { icon: "bi-cloud-lightning-rain-fill", color: "var(--ws-warning)" },
        };
        return map[code] || { icon: "bi-cloud-fill", color: "var(--ws-text-secondary)" };
    };

    const tempColor = (t) => {
        if (t == null) return "var(--ws-text)";
        if (t < 5) return "var(--ws-temp-cold)";
        if (t < 18) return "var(--ws-temp-mild)";
        if (t < 30) return "var(--ws-temp-warm)";
        return "var(--ws-temp-hot)";
    };

    const precipBadge = (chance, type) => {
        if (chance == null || chance < 10) return "";
        const colors = {
            rain: "var(--ws-accent)",
            snow: "var(--ws-temp-cold)",
            precip: "var(--ws-text-secondary)",
        };
        const icons = { rain: "bi-cloud-rain-fill", snow: "bi-snow2", precip: "bi-droplet" };
        const c = colors[type] || colors.precip;
        const ic = icons[type] || icons.precip;
        return `<span class="badge" style="background:${c}; font-size:0.7rem"><i class="bi ${ic} me-1"></i>${chance}%</span>`;
    };

    const renderDaypartBlock = (part, label) => {
        if (!part || part.temp == null) return `<div class="col-6 text-center" style="opacity:0.3"><small>${label}</small><br>--</div>`;
        const wx = wxIcon(part.iconCode);
        return `
        <div class="col-6">
            <div class="text-center mb-1">
                <small class="fw-semibold" style="color:var(--ws-text-secondary)">${part.name || label}</small>
            </div>
            <div class="text-center mb-2">
                <i class="bi ${wx.icon}" style="font-size:2rem; color:${wx.color}"></i>
            </div>
            <div class="text-center mb-1">
                <span style="font-size:1.5rem; font-weight:700; color:${tempColor(part.temp)}">${part.temp}&deg;</span>
            </div>
            <div class="text-center" style="font-size:0.75rem; color:var(--ws-text-secondary)">
                ${part.wxPhrase || ''}
            </div>
            <div class="mt-2" style="font-size:0.75rem; color:var(--ws-text-secondary); line-height:1.8">
                ${precipBadge(part.precipChance, part.precipType)}
                <span class="ms-1"><i class="bi bi-droplet" style="color:var(--ws-accent)"></i> ${part.humidity ?? '--'}%</span>
                <span class="ms-1"><i class="bi bi-wind" style="color:var(--ws-temp-mild)"></i> ${part.windSpeed ?? '--'} km/h ${part.windDir || ''}</span>
                <span class="ms-1"><i class="bi bi-clouds" style="color:var(--ws-text-muted)"></i> ${part.cloudCover ?? '--'}%</span>
                ${part.uvIndex != null ? `<span class="ms-1"><i class="bi bi-sun-fill" style="color:var(--ws-warning)"></i> UV ${part.uvIndex}</span>` : ''}
            </div>
        </div>`;
    };

    const renderDayCard = (day, idx) => {
        const isToday = idx === 0;
        const borderStyle = isToday ? "border: 2px solid var(--ws-accent)" : "";
        const todayBadge = isToday ? '<span class="badge bg-info ms-2">Oggi</span>' : '';

        return `
        <div class="${isToday ? 'col-12' : 'col-lg-6'}">
            <div class="card h-100" style="${borderStyle}">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${day.dayOfWeek}</strong> <small style="color:var(--ws-text-muted)">${day.validDate}</small>
                        ${todayBadge}
                    </div>
                    <div class="d-flex align-items-center gap-3" style="font-size:0.8rem; color:var(--ws-text-secondary)">
                        <span style="color:var(--ws-temp-hot)"><i class="bi bi-arrow-up"></i> ${day.tempMax ?? '--'}&deg;</span>
                        <span style="color:var(--ws-temp-cold)"><i class="bi bi-arrow-down"></i> ${day.tempMin ?? '--'}&deg;</span>
                        ${day.qpf > 0 ? `<span style="color:var(--ws-accent)"><i class="bi bi-cloud-rain"></i> ${day.qpf} mm</span>` : ''}
                        <span><i class="bi bi-sunrise" style="color:var(--ws-warning)"></i> ${day.sunrise || '--'}</span>
                        <span><i class="bi bi-sunset" style="color:var(--ws-temp-warm)"></i> ${day.sunset || '--'}</span>
                        ${day.moonPhase ? `<span><i class="bi bi-moon-fill" style="color:var(--ws-text-muted)"></i> ${day.moonPhase}</span>` : ''}
                    </div>
                </div>
                <div class="card-body">
                    <div class="mb-2" style="font-size:0.85rem; color:var(--ws-text-secondary); font-style:italic">
                        ${day.narrative || ''}
                    </div>
                    <div class="row g-3">
                        ${renderDaypartBlock(day.day, "Giorno")}
                        ${renderDaypartBlock(day.night, "Notte")}
                    </div>
                </div>
            </div>
        </div>`;
    };

    const loadForecast = async () => {
        const grid = document.getElementById("forecastGrid");
        if (!grid) return;

        try {
            const resp = await fetch(wsUrl("/api/forecast"));
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                grid.innerHTML = `<div class="ws-no-data"><i class="bi bi-exclamation-triangle me-2"></i>${err.error || 'Errore nel caricamento'}</div>`;
                return;
            }
            const days = await resp.json();

            if (!days.length) {
                grid.innerHTML = '<div class="ws-no-data">Nessun dato previsionale disponibile</div>';
                return;
            }

            grid.innerHTML = days.map((d, i) => renderDayCard(d, i)).join("");
        } catch (err) {
            console.error("Forecast load error:", err);
            grid.innerHTML = '<div class="ws-no-data">Errore di connessione</div>';
        }
    };

    document.addEventListener("DOMContentLoaded", () => {
        loadForecast();
        document.getElementById("btnRefresh")?.addEventListener("click", loadForecast);
    });
})();
