/* ==========================================================================
   Homepage — All Stations Overview
   ========================================================================== */

(() => {
    "use strict";

    const fmt = (v, dec = 1) => {
        if (v == null || v === "" || v === "None") return "--";
        const n = Number(v);
        return isNaN(n) ? "--" : n.toFixed(dec);
    };

    const renderStationCard = (station) => {
        const c = station.conditions;
        const noData = !c;
        const primaryBadge = station.is_primary
            ? '<span class="badge bg-info ms-2">Principale</span>'
            : '';

        if (noData) {
            return `
            <div class="col-lg-4 col-md-6">
                <div class="card metric-card h-100" style="opacity: 0.6">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span><strong>${station.name}</strong>${primaryBadge}</span>
                        <small style="color: var(--ws-text-muted)">${station.station_id}</small>
                    </div>
                    <div class="card-body">
                        <div class="ws-no-data" style="min-height:120px">Nessun dato disponibile</div>
                    </div>
                    <div class="card-footer text-center">
                        <a href="/station/${station.station_id}/dashboard" class="btn btn-sm btn-outline-primary">
                            <i class="bi bi-box-arrow-in-right me-1"></i>Apri
                        </a>
                    </div>
                </div>
            </div>`;
        }

        return `
        <div class="col-lg-4 col-md-6">
            <div class="card metric-card h-100">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span><strong>${station.name}</strong>${primaryBadge}</span>
                    <small style="color: var(--ws-text-muted)">${station.station_id}</small>
                </div>
                <div class="card-body">
                    ${c.lat != null ? `<div class="mb-2" style="font-size:0.75rem; color:var(--ws-text-muted)"><i class="bi bi-geo-alt me-1"></i>${Number(c.lat).toFixed(3)}, ${Number(c.lon).toFixed(3)}</div>` : ''}
                    <div class="row g-2 text-center">
                        <div class="col-4">
                            <div class="metric-label">Temp.</div>
                            <div class="fw-bold" style="font-size:1.3rem">${fmt(c.temp_c)}&deg;</div>
                        </div>
                        <div class="col-4">
                            <div class="metric-label">Umidit&agrave;</div>
                            <div class="fw-bold" style="font-size:1.3rem">${fmt(c.humidity_pct, 0)}%</div>
                        </div>
                        <div class="col-4">
                            <div class="metric-label">Pressione</div>
                            <div class="fw-bold" style="font-size:1.3rem">${fmt(c.pressure_hpa, 0)}</div>
                        </div>
                    </div>
                    <hr style="border-color: var(--ws-border); margin: 0.75rem 0">
                    <div class="row g-2 text-center" style="font-size:0.85rem">
                        <div class="col-3">
                            <div class="metric-label">Vento</div>
                            <div>${fmt(c.wind_speed_kmh)} km/h</div>
                        </div>
                        <div class="col-3">
                            <div class="metric-label">Raffica</div>
                            <div>${fmt(c.wind_gust_kmh)} km/h</div>
                        </div>
                        <div class="col-3">
                            <div class="metric-label">Pioggia</div>
                            <div>${fmt(c.precip_rate_mmh)} mm/h</div>
                        </div>
                        <div class="col-3">
                            <div class="metric-label">UV</div>
                            <div>${fmt(c.uv_index, 0)}</div>
                        </div>
                    </div>
                    <hr style="border-color: var(--ws-border); margin: 0.75rem 0">
                    <div class="row g-2 text-center" style="font-size:0.85rem">
                        <div class="col-4">
                            <div class="metric-label">Pt. Rugiada</div>
                            <div>${fmt(c.dew_point_c)}&deg;C</div>
                        </div>
                        <div class="col-4">
                            <div class="metric-label">Solare</div>
                            <div>${fmt(c.solar_radiation_wm2, 0)} W/m&sup2;</div>
                        </div>
                        <div class="col-4">
                            <div class="metric-label">Precip. Tot.</div>
                            <div>${fmt(c.precip_total_mm)} mm</div>
                        </div>
                    </div>
                </div>
                <div class="card-footer text-center">
                    <a href="/station/${station.station_id}/dashboard" class="btn btn-sm btn-outline-primary">
                        <i class="bi bi-box-arrow-in-right me-1"></i>Apri Stazione
                    </a>
                </div>
            </div>
        </div>`;
    };

    const loadStations = async () => {
        const grid = document.getElementById("stationsGrid");
        if (!grid) return;

        try {
            const resp = await fetch("/api/stations/current");
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const stations = await resp.json();

            grid.innerHTML = stations.map(renderStationCard).join("");

            const updateEl = document.getElementById("lastUpdate");
            if (updateEl) updateEl.textContent = new Date().toLocaleTimeString("it-IT");
        } catch (err) {
            console.error("loadStations error:", err);
            grid.innerHTML = '<div class="ws-no-data">Errore nel caricamento delle stazioni</div>';
        }
    };

    document.addEventListener("DOMContentLoaded", () => {
        loadStations();
        // Auto-refresh every 60 seconds
        setInterval(loadStations, 60000);
    });
})();
