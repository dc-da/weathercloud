/* ==========================================================================
   Homepage — All Stations Overview (SSE progressive loading)
   ========================================================================== */

(() => {
    "use strict";

    const fmt = (v, dec = 1) => {
        if (v == null || v === "" || v === "None") return "--";
        const n = Number(v);
        return isNaN(n) ? "--" : n.toFixed(dec);
    };

    const tempColor = (t) => {
        if (t == null) return "var(--ws-text)";
        if (t < 5) return "var(--ws-temp-cold)";
        if (t < 18) return "var(--ws-temp-mild)";
        if (t < 30) return "var(--ws-temp-warm)";
        return "var(--ws-temp-hot)";
    };

    const windIcon = (kmh) => {
        if (kmh == null) return "bi-wind";
        if (kmh < 20) return "bi-wind";
        return "bi-tornado";
    };

    const uvColor = (uv) => {
        if (uv == null) return "var(--ws-text-muted)";
        if (uv <= 2) return "var(--ws-uv-low)";
        if (uv <= 5) return "var(--ws-uv-moderate)";
        if (uv <= 7) return "var(--ws-uv-high)";
        if (uv <= 10) return "var(--ws-uv-very-high)";
        return "var(--ws-uv-extreme)";
    };

    // ---- Primary station: full-width hero card ----
    const renderPrimaryCard = (station) => {
        const c = station.conditions;
        if (!c) {
            return `
            <div class="col-12 mb-2" id="station-${station.station_id}">
                <div class="card border-primary" style="border-width:2px">
                    <div class="card-header d-flex justify-content-between align-items-center" style="background: linear-gradient(135deg, var(--ws-surface) 0%, var(--ws-bg-light) 100%)">
                        <span><i class="bi bi-star-fill me-2" style="color: var(--ws-warning)"></i><strong>${station.name}</strong>
                        <span class="badge bg-info ms-2">Principale</span></span>
                        <small style="color: var(--ws-text-muted)">${station.station_id}</small>
                    </div>
                    <div class="card-body">
                        <div class="ws-no-data" style="min-height:80px">
                            <i class="bi bi-exclamation-triangle me-2"></i>Stazione offline — nessun dato disponibile
                        </div>
                    </div>
                </div>
            </div>`;
        }

        const tc = tempColor(c.temp_c != null ? Number(c.temp_c) : null);

        return `
        <div class="col-12 mb-2" id="station-${station.station_id}">
            <div class="card" style="border: 2px solid var(--ws-accent); background: linear-gradient(135deg, var(--ws-surface) 0%, rgba(91,164,245,0.05) 100%)">
                <div class="card-body py-3">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div>
                            <i class="bi bi-star-fill me-2" style="color: var(--ws-warning); font-size:1.1rem"></i>
                            <strong style="font-size:1.1rem">${station.name}</strong>
                            <span class="badge bg-info ms-2">Principale</span>
                            ${c.lat != null ? `<small class="ms-3" style="color:var(--ws-text-muted)"><i class="bi bi-geo-alt"></i> ${Number(c.lat).toFixed(3)}, ${Number(c.lon).toFixed(3)}</small>` : ''}
                        </div>
                        <a href="/station/${station.station_id}/dashboard" class="btn btn-sm btn-primary">
                            <i class="bi bi-box-arrow-in-right me-1"></i>Dashboard
                        </a>
                    </div>
                    <div class="row g-3 align-items-center">
                        <!-- Temperature hero -->
                        <div class="col-md-3 text-center">
                            <div style="font-size:3rem; font-weight:700; line-height:1; color:${tc}">
                                ${fmt(c.temp_c)}<span style="font-size:1.5rem">&deg;C</span>
                            </div>
                            <div style="color:var(--ws-text-secondary); font-size:0.85rem" class="mt-1">
                                <i class="bi bi-thermometer-half me-1"></i>Temperatura
                            </div>
                        </div>
                        <!-- Key metrics -->
                        <div class="col-md-9">
                            <div class="row g-2 text-center">
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-droplet-fill me-1" style="color:var(--ws-accent)"></i>Umid.</div>
                                    <div class="fw-bold">${fmt(c.humidity_pct, 0)}%</div>
                                </div>
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-speedometer me-1" style="color:var(--ws-success)"></i>Press.</div>
                                    <div class="fw-bold">${fmt(c.pressure_hpa, 0)} hPa</div>
                                </div>
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi ${windIcon(c.wind_speed_kmh)} me-1" style="color:var(--ws-temp-mild)"></i>Vento</div>
                                    <div class="fw-bold">${fmt(c.wind_speed_kmh)} km/h</div>
                                </div>
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-cloud-rain-fill me-1" style="color:var(--ws-accent)"></i>Pioggia</div>
                                    <div class="fw-bold">${fmt(c.precip_rate_mmh)} mm/h</div>
                                </div>
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-moisture me-1" style="color:#4dd0e1"></i>Rugiada</div>
                                    <div class="fw-bold">${fmt(c.dew_point_c)}&deg;C</div>
                                </div>
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-sun-fill me-1" style="color:${uvColor(c.uv_index != null ? Number(c.uv_index) : null)}"></i>UV</div>
                                    <div class="fw-bold">${fmt(c.uv_index, 0)}</div>
                                </div>
                            </div>
                            <div class="row g-2 text-center mt-1">
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-wind me-1" style="color:var(--ws-temp-mild)"></i>Raffica</div>
                                    <div class="fw-bold">${fmt(c.wind_gust_kmh)} km/h</div>
                                </div>
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-bucket-fill me-1" style="color:var(--ws-accent)"></i>Prec. Tot.</div>
                                    <div class="fw-bold">${fmt(c.precip_total_mm)} mm</div>
                                </div>
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-brightness-high-fill me-1" style="color:#ffca28"></i>Solare</div>
                                    <div class="fw-bold">${fmt(c.solar_radiation_wm2, 0)} W/m&sup2;</div>
                                </div>
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-fire me-1" style="color:var(--ws-temp-hot)"></i>Calore</div>
                                    <div class="fw-bold">${fmt(c.heat_index_c)}&deg;C</div>
                                </div>
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-snow2 me-1" style="color:var(--ws-temp-cold)"></i>Wind Ch.</div>
                                    <div class="fw-bold">${fmt(c.wind_chill_c)}&deg;C</div>
                                </div>
                                <div class="col-4 col-lg-2">
                                    <div class="metric-label"><i class="bi bi-compass me-1" style="color:var(--ws-text-secondary)"></i>Dir.</div>
                                    <div class="fw-bold">${c.wind_dir_deg != null ? c.wind_dir_deg + '&deg;' : '--'}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;
    };

    // ---- Secondary station: compact card ----
    const renderSecondaryCard = (station) => {
        const c = station.conditions;
        const distLabel = station.distance_km != null
            ? `<span class="badge bg-secondary ms-1" style="font-size:0.65rem">${station.distance_km} km</span>`
            : '';

        if (!c) {
            return `
            <div class="col-xl-3 col-lg-4 col-md-6 station-card" id="station-${station.station_id}" data-name="${station.name.toLowerCase()}" data-id="${station.station_id.toLowerCase()}" data-online="0">
                <a href="/station/${station.station_id}/dashboard" class="text-decoration-none">
                    <div class="card h-100" style="opacity:0.45; border-color: var(--ws-border)">
                        <div class="card-body py-2 px-3">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <i class="bi bi-wifi-off me-1" style="color:var(--ws-danger); font-size:0.75rem"></i>
                                    <strong style="font-size:0.85rem; color:var(--ws-text)">${station.name}</strong>
                                    ${distLabel}
                                </div>
                                <small style="color:var(--ws-text-muted); font-size:0.7rem">${station.station_id}</small>
                            </div>
                            <div style="color:var(--ws-text-muted); font-size:0.75rem" class="mt-1">Offline</div>
                        </div>
                    </div>
                </a>
            </div>`;
        }

        const tc = tempColor(c.temp_c != null ? Number(c.temp_c) : null);

        return `
        <div class="col-xl-3 col-lg-4 col-md-6 station-card" id="station-${station.station_id}" data-name="${station.name.toLowerCase()}" data-id="${station.station_id.toLowerCase()}" data-online="1">
            <a href="/station/${station.station_id}/dashboard" class="text-decoration-none">
                <div class="card metric-card h-100">
                    <div class="card-body py-2 px-3">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <div>
                                <i class="bi bi-broadcast-pin me-1" style="color:var(--ws-success); font-size:0.75rem"></i>
                                <strong style="font-size:0.85rem; color:var(--ws-text)">${station.name}</strong>
                                ${distLabel}
                            </div>
                            <small style="color:var(--ws-text-muted); font-size:0.7rem">${station.station_id}</small>
                        </div>
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="d-flex align-items-center gap-3">
                                <div class="text-center">
                                    <div style="font-size:1.4rem; font-weight:700; color:${tc}; line-height:1">
                                        ${fmt(c.temp_c)}<span style="font-size:0.8rem">&deg;</span>
                                    </div>
                                </div>
                                <div style="font-size:0.78rem; color:var(--ws-text-secondary); line-height:1.6">
                                    <span><i class="bi bi-droplet-fill" style="color:var(--ws-accent); font-size:0.65rem"></i> ${fmt(c.humidity_pct, 0)}%</span>
                                    <span class="ms-2"><i class="bi bi-speedometer" style="color:var(--ws-success); font-size:0.65rem"></i> ${fmt(c.pressure_hpa, 0)}</span>
                                    <span class="ms-2"><i class="bi bi-wind" style="color:var(--ws-temp-mild); font-size:0.65rem"></i> ${fmt(c.wind_speed_kmh)} km/h</span>
                                </div>
                            </div>
                            <div style="font-size:0.75rem; text-align:right; color:var(--ws-text-muted); line-height:1.6">
                                ${c.precip_rate_mmh != null && Number(c.precip_rate_mmh) > 0
                                    ? `<div><i class="bi bi-cloud-rain-fill" style="color:var(--ws-accent)"></i> ${fmt(c.precip_rate_mmh)} mm/h</div>`
                                    : ''}
                                ${c.lat != null
                                    ? `<div><i class="bi bi-geo-alt" style="font-size:0.6rem"></i> ${Number(c.lat).toFixed(2)}, ${Number(c.lon).toFixed(2)}</div>`
                                    : ''}
                            </div>
                        </div>
                    </div>
                </div>
            </a>
        </div>`;
    };

    // ---- Placeholder card (shown while waiting for data) ----
    // Note: station list from config uses "id", API results use "station_id"
    const stationId = (s) => s.station_id || s.id;

    const renderPlaceholderCard = (station) => {
        const sid = stationId(station);
        if (station.is_primary) {
            return `
            <div class="col-12 mb-2" id="station-${sid}">
                <div class="card" style="border: 2px solid var(--ws-border); opacity: 0.5">
                    <div class="card-body py-3">
                        <div class="d-flex align-items-center">
                            <i class="bi bi-star-fill me-2" style="color: var(--ws-warning); font-size:1.1rem"></i>
                            <strong style="font-size:1.1rem">${station.name}</strong>
                            <span class="badge bg-info ms-2">Principale</span>
                            <span class="spinner-border spinner-border-sm ms-3" style="width:0.9rem;height:0.9rem"></span>
                            <small class="ms-2" style="color:var(--ws-text-muted)">In attesa…</small>
                        </div>
                    </div>
                </div>
            </div>`;
        }
        return `
        <div class="col-xl-3 col-lg-4 col-md-6 station-card" id="station-${sid}" data-name="${station.name.toLowerCase()}" data-id="${sid.toLowerCase()}" data-online="-1">
            <div class="card h-100" style="opacity:0.35; border-color: var(--ws-border)">
                <div class="card-body py-2 px-3">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <span class="spinner-border spinner-border-sm me-1" style="width:0.7rem;height:0.7rem;color:var(--ws-text-muted)"></span>
                            <strong style="font-size:0.85rem; color:var(--ws-text)">${station.name}</strong>
                        </div>
                        <small style="color:var(--ws-text-muted); font-size:0.7rem">${sid}</small>
                    </div>
                    <div style="color:var(--ws-text-muted); font-size:0.75rem" class="mt-1">In attesa…</div>
                </div>
            </div>
        </div>`;
    };

    // ---- Search filter ----
    const filterStations = (query) => {
        const q = query.toLowerCase().trim();
        document.querySelectorAll(".station-card").forEach((card) => {
            const name = card.dataset.name || "";
            const id = card.dataset.id || "";
            card.style.display = (!q || name.includes(q) || id.includes(q)) ? "" : "none";
        });
    };

    // ---- Streaming load via SSE ----
    let activeSource = null; // current EventSource, if any

    const loadStations = () => {
        const grid = document.getElementById("stationsGrid");
        if (!grid) return;

        // Abort any in-progress stream
        if (activeSource) {
            activeSource.close();
            activeSource = null;
        }

        const btn = document.getElementById("btnRefresh");
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>0 / …';
        }

        // Build placeholder grid from station list embedded in page
        const stationList = window.WS_STATIONS || [];
        if (stationList.length > 0) {
            // Primary first, then secondary header, then secondary placeholders
            const primary = stationList.find((s) => s.is_primary);
            const secondary = stationList.filter((s) => !s.is_primary);
            let html = "";
            if (primary) html += renderPlaceholderCard(primary);
            html += `<div class="col-12 mt-2 mb-1" id="secondary-header">
                <div class="d-flex justify-content-between align-items-center">
                    <small style="color:var(--ws-text-secondary)">
                        <i class="bi bi-diagram-3 me-1"></i>
                        ${secondary.length} stazioni secondarie
                        <span class="spinner-border spinner-border-sm ms-2" style="width:0.7rem;height:0.7rem"></span>
                    </small>
                </div>
            </div>`;
            html += secondary.map(renderPlaceholderCard).join("");
            grid.innerHTML = html;
        } else {
            grid.innerHTML = '<div class="ws-loading"><div class="spinner-border spinner-border-sm"></div><span>Caricamento stazioni…</span></div>';
        }

        const startTime = Date.now();
        let received = 0;
        let total = stationList.length || "…";
        const allStations = []; // collect for final sort

        const source = new EventSource("/api/stations/stream");
        activeSource = source;

        source.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const station = data.station;
            total = data.total;
            received++;
            allStations.push(station);

            // Update button progress
            if (btn) {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${received}/${total} (${elapsed}s)`;
            }

            // Replace the placeholder with the real card
            const placeholder = document.getElementById(`station-${station.station_id}`);
            if (placeholder) {
                const html = station.is_primary
                    ? renderPrimaryCard(station)
                    : renderSecondaryCard(station);
                const tmp = document.createElement("div");
                tmp.innerHTML = html;
                const newEl = tmp.firstElementChild;
                placeholder.replaceWith(newEl);
            }

            // Re-apply search filter if active
            const searchInput = document.getElementById("stationSearch");
            if (searchInput && searchInput.value) filterStations(searchInput.value);
        };

        source.addEventListener("done", () => {
            source.close();
            activeSource = null;
            _onStreamComplete(grid, btn, allStations);
        });

        source.onerror = () => {
            source.close();
            activeSource = null;
            // If we received some stations, finalize what we have
            if (allStations.length > 0) {
                _onStreamComplete(grid, btn, allStations);
            } else {
                grid.innerHTML = '<div class="ws-no-data"><i class="bi bi-exclamation-triangle me-2"></i>Errore nel caricamento delle stazioni</div>';
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Aggiorna';
                }
            }
        };
    };

    const _onStreamComplete = (grid, btn, allStations) => {
        // Re-sort secondary cards: online first, then by distance
        const secondary = allStations.filter((s) => !s.is_primary);
        const onlineCount = secondary.filter((s) => s.conditions).length;
        const offlineCount = secondary.length - onlineCount;

        secondary.sort((a, b) => {
            const aOnline = a.conditions ? 1 : 0;
            const bOnline = b.conditions ? 1 : 0;
            if (aOnline !== bOnline) return bOnline - aOnline;
            const aDist = a.distance_km ?? 9999;
            const bDist = b.distance_km ?? 9999;
            return aDist - bDist;
        });

        // Rebuild secondary section in sorted order
        const header = document.getElementById("secondary-header");
        if (header) {
            header.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <small style="color:var(--ws-text-secondary)">
                        <i class="bi bi-diagram-3 me-1"></i>
                        ${secondary.length} stazioni secondarie
                        <span class="badge bg-success ms-1">${onlineCount} online</span>
                        ${offlineCount > 0 ? `<span class="badge bg-secondary ms-1">${offlineCount} offline</span>` : ''}
                    </small>
                </div>`;
            // Re-append secondary cards in sorted order after the header
            const parent = header.parentElement;
            secondary.forEach((s) => {
                const el = document.getElementById(`station-${s.station_id}`);
                if (el) parent.appendChild(el);
            });
        }

        // Update timestamp
        const updateEl = document.getElementById("lastUpdate");
        if (updateEl) updateEl.textContent = new Date().toLocaleTimeString("it-IT");

        // Reset button
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Aggiorna';
        }

        // Re-apply filter
        const searchInput = document.getElementById("stationSearch");
        if (searchInput && searchInput.value) filterStations(searchInput.value);
    };

    document.addEventListener("DOMContentLoaded", () => {
        loadStations();

        document.getElementById("btnRefresh")?.addEventListener("click", loadStations);

        const searchInput = document.getElementById("stationSearch");
        if (searchInput) {
            searchInput.addEventListener("input", () => filterStations(searchInput.value));
        }

        // Auto-refresh driven by YAML config
        if (window.WS_HOME_AUTO_REFRESH && window.WS_HOME_REFRESH_MS > 0) {
            setInterval(loadStations, window.WS_HOME_REFRESH_MS);
        }
    });
})();
