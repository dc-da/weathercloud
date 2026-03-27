/* ==========================================================================
   Dashboard (Vista Istantanea) — /dashboard
   ========================================================================== */

(() => {
    "use strict";

    const degreesToCompass = (deg) => {
        if (deg == null || isNaN(deg)) return "N/D";
        const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
        const idx = Math.round(((deg % 360) + 360) % 360 / 45) % 8;
        return directions[idx];
    };

    const tempClass = (t) => {
        if (t == null) return "";
        if (t < 5) return "temp-cold";
        if (t < 18) return "temp-mild";
        if (t < 30) return "temp-warm";
        return "temp-hot";
    };

    const fmt = (v, decimals = 1) => {
        if (v == null || v === "" || v === "None") return "N/D";
        const n = Number(v);
        return isNaN(n) ? "N/D" : n.toFixed(decimals);
    };

    const setText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };

    const setTempColor = (id, tempValue) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.remove("temp-cold", "temp-mild", "temp-warm", "temp-hot");
        const cls = tempClass(Number(tempValue));
        if (cls) el.classList.add(cls);
    };

    const setStatusDot = (state) => {
        const dot = document.getElementById("statusDot");
        if (!dot) return;
        dot.classList.remove("online", "offline", "loading");
        dot.className = "status-dot " + state;
        const txt = document.getElementById("statusText");
        if (txt) {
            txt.textContent = state === "online" ? "Online" : state === "loading" ? "Caricamento..." : "Offline";
        }
    };

    const DEFAULT_INTERVAL = 60;
    let refreshTimer = null;

    const getInterval = () => {
        const stored = localStorage.getItem("ws_refresh_interval");
        return stored ? parseInt(stored, 10) : DEFAULT_INTERVAL;
    };

    const saveInterval = (seconds) => {
        localStorage.setItem("ws_refresh_interval", String(seconds));
    };

    const fetchCurrent = async () => {
        setStatusDot("loading");
        try {
            const resp = await fetch("/api/current");
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const d = await resp.json();

            setText("val-temp", fmt(d.temp_c));
            setTempColor("val-temp", d.temp_c);

            setText("val-humidity", fmt(d.humidity_pct, 0));

            const windDir = degreesToCompass(d.wind_dir_deg);
            setText("val-wind", fmt(d.wind_speed_kmh));
            setText("val-wind-dir", `${windDir} ${d.wind_dir_deg != null ? d.wind_dir_deg + "\u00B0" : ""}`);

            setText("val-rain-rate", fmt(d.precip_rate_mmh));
            setText("val-rain-total", fmt(d.precip_total_mm));

            setText("val-pressure", fmt(d.pressure_hpa, 1));
            setText("val-solar", fmt(d.solar_radiation_wm2, 0));
            setText("val-uv", fmt(d.uv_index, 0));
            setText("val-dewpoint", fmt(d.dew_point_c));
            setTempColor("val-dewpoint", d.dew_point_c);

            setText("lastUpdate", new Date().toLocaleTimeString("it-IT"));
            setStatusDot("online");
        } catch (err) {
            console.error("fetchCurrent error:", err);
            setStatusDot("offline");
            ["val-temp", "val-humidity", "val-wind", "val-rain-rate",
             "val-pressure", "val-solar", "val-uv", "val-dewpoint"
            ].forEach((id) => setText(id, "N/D"));
        }
    };

    const fetchSparkline = async () => {
        const container = document.getElementById("sparklineChart");
        if (!container) return;

        try {
            const resp = await fetch("/api/rapid/last24h");
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            if (!data.length) {
                container.innerHTML = '<div class="ws-no-data">Nessun dato disponibile per le ultime 24h</div>';
                return;
            }

            const times = data.map((r) => r.time);
            const temps = data.map((r) => r.temp_c);
            const hums = data.map((r) => r.humidity_pct);

            const isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
            const gridColor = isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)";
            const fontColor = isDark ? "#ccc" : "#666";

            const traces = [
                {
                    x: times, y: temps, name: "Temperatura (\u00B0C)",
                    type: "scatter", mode: "lines",
                    line: { color: "#ff7043", width: 2 },
                    connectgaps: false, yaxis: "y",
                },
                {
                    x: times, y: hums, name: "Umidit\u00E0 (%)",
                    type: "scatter", mode: "lines",
                    line: { color: "#42a5f5", width: 2 },
                    connectgaps: false, yaxis: "y2",
                },
            ];

            const layout = {
                margin: { t: 20, r: 50, b: 40, l: 50 },
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
                font: { size: 11, color: fontColor },
                legend: { orientation: "h", y: -0.2 },
                xaxis: { type: "date", gridcolor: gridColor, tickformat: "%H:%M" },
                yaxis: { title: "Temperatura (\u00B0C)", gridcolor: gridColor, side: "left" },
                yaxis2: { title: "Umidit\u00E0 (%)", overlaying: "y", side: "right", range: [0, 100], gridcolor: "transparent" },
            };

            Plotly.newPlot(container, traces, layout, { responsive: true, displayModeBar: false });
        } catch (err) {
            console.error("fetchSparkline error:", err);
        }
    };

    const startTimer = () => {
        if (refreshTimer) clearInterval(refreshTimer);
        const seconds = getInterval();
        if (seconds <= 0) return;
        refreshTimer = setInterval(() => fetchCurrent(), seconds * 1000);
    };

    document.addEventListener("DOMContentLoaded", () => {
        const sel = document.getElementById("refreshInterval");
        if (sel) {
            sel.value = String(getInterval());
            sel.addEventListener("change", () => {
                saveInterval(parseInt(sel.value, 10));
                startTimer();
            });
        }

        document.getElementById("btnRefreshNow")?.addEventListener("click", () => {
            fetchCurrent();
            fetchSparkline();
        });

        fetchCurrent();
        fetchSparkline();
        startTimer();
    });
})();
