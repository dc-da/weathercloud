/* ==========================================================================
   Dashboard (Vista Istantanea) — /dashboard
   ========================================================================== */

(() => {
    "use strict";

    const wsUrl = (path) => (window.WS_API_PREFIX || "") + path;

    const degreesToCompass = (deg) => {
        if (deg == null || isNaN(deg)) return "N/D";
        const directions = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
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

    // --- Gauge helpers ---
    const setGauge = (id, value, min, max, color) => {
        const el = document.getElementById(id);
        if (!el) return;
        const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
        const angle = (pct / 100) * 360;
        el.style.background = `conic-gradient(${color} ${angle}deg, rgba(255,255,255,0.08) ${angle}deg)`;
    };

    // --- UV helpers ---
    const uvLevel = (uv) => {
        if (uv == null) return { text: "--", color: "" };
        if (uv <= 2) return { text: "Basso", color: "var(--ws-uv-low)" };
        if (uv <= 5) return { text: "Moderato", color: "var(--ws-uv-moderate)" };
        if (uv <= 7) return { text: "Alto", color: "var(--ws-uv-high)" };
        if (uv <= 10) return { text: "Molto Alto", color: "var(--ws-uv-very-high)" };
        return { text: "Estremo", color: "var(--ws-uv-extreme)" };
    };

    const setUVBar = (uv) => {
        const marker = document.getElementById("uvMarker");
        const levelText = document.getElementById("uv-level-text");
        if (!marker) return;
        const val = Number(uv) || 0;
        const pct = Math.min(100, (val / 12) * 100);
        marker.style.left = `${pct}%`;
        const info = uvLevel(val);
        if (levelText) {
            levelText.textContent = info.text;
            levelText.style.color = info.color;
        }
    };

    // --- Compass ---
    const setCompass = (deg) => {
        const needle = document.getElementById("compassNeedle");
        if (!needle) return;
        if (deg == null || isNaN(deg)) {
            needle.style.opacity = "0.2";
            return;
        }
        needle.style.opacity = "1";
        needle.style.transform = `rotate(${deg}deg)`;
    };

    // --- Feels like calculation ---
    const calcFeelsLike = (d) => {
        // Use heat index if hot, wind chill if cold, else actual temp
        if (d.heat_index_c != null && d.temp_c >= 27) return d.heat_index_c;
        if (d.wind_chill_c != null && d.temp_c <= 10) return d.wind_chill_c;
        return d.temp_c;
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
            const resp = await fetch(wsUrl("/api/current"));
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const d = await resp.json();

            // Temperature
            setText("val-temp", fmt(d.temp_c));
            setTempColor("val-temp", d.temp_c);

            // Feels like
            const fl = calcFeelsLike(d);
            setText("val-feels-like", fmt(fl));
            setTempColor("val-feels-like", fl);

            // Dew point
            setText("val-dewpoint", fmt(d.dew_point_c));

            // Humidity gauge
            const hum = Number(d.humidity_pct) || 0;
            setText("val-humidity", fmt(d.humidity_pct, 0));
            setGauge("humidityGauge", hum, 0, 100, "var(--ws-accent)");

            // Pressure gauge (range 980-1040)
            const press = Number(d.pressure_hpa) || 1013;
            setText("val-pressure", fmt(d.pressure_hpa, 1));
            setGauge("pressureGauge", press, 980, 1050, "var(--ws-success)");

            // Wind compass
            setCompass(d.wind_dir_deg);
            setText("val-wind", fmt(d.wind_speed_kmh));
            setText("val-wind-gust", fmt(d.wind_gust_kmh));
            const windDir = degreesToCompass(d.wind_dir_deg);
            setText("val-wind-dir", d.wind_dir_deg != null ? `${windDir} ${d.wind_dir_deg}\u00B0` : "N/D");

            // Rain
            setText("val-rain-rate", fmt(d.precip_rate_mmh));
            setText("val-rain-total", fmt(d.precip_total_mm));

            // Solar
            setText("val-solar", fmt(d.solar_radiation_wm2, 0));

            // UV
            setText("val-uv", fmt(d.uv_index, 0));
            setUVBar(d.uv_index);

            // Heat index & wind chill
            setText("val-heat-index", fmt(d.heat_index_c));
            setText("val-wind-chill", fmt(d.wind_chill_c));

            setText("lastUpdate", new Date().toLocaleTimeString("it-IT"));
            setStatusDot("online");
        } catch (err) {
            console.error("fetchCurrent error:", err);
            setStatusDot("offline");
        }
    };

    const fetchSparkline = async () => {
        const container = document.getElementById("sparklineChart");
        if (!container) return;

        try {
            const resp = await fetch(wsUrl("/api/rapid/last24h"));
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            if (!data.length) {
                container.innerHTML = '<div class="ws-no-data">Nessun dato disponibile per le ultime 24h</div>';
                return;
            }

            const times = data.map((r) => r.time);
            const temps = data.map((r) => r.temp_c);
            const hums = data.map((r) => r.humidity_pct);
            const rains = data.map((r) => r.precip_rate_mmh);

            const gridColor = "rgba(255,255,255,0.06)";
            const fontColor = "#9aa0a8";

            const traces = [
                {
                    x: times, y: temps, name: "Temperatura (\u00B0C)",
                    type: "scatter", mode: "lines",
                    line: { color: "#ff7043", width: 2.5, shape: "spline" },
                    fill: "tozeroy",
                    fillcolor: "rgba(255, 112, 67, 0.08)",
                    connectgaps: false, yaxis: "y",
                },
                {
                    x: times, y: hums, name: "Umidit\u00E0 (%)",
                    type: "scatter", mode: "lines",
                    line: { color: "#42a5f5", width: 2, shape: "spline" },
                    connectgaps: false, yaxis: "y2",
                },
                {
                    x: times, y: rains, name: "Pioggia (mm/h)",
                    type: "bar",
                    marker: { color: "rgba(91, 164, 245, 0.5)" },
                    yaxis: "y3",
                },
            ];

            const layout = {
                margin: { t: 10, r: 60, b: 40, l: 50 },
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
                font: { family: "Inter, sans-serif", size: 11, color: fontColor },
                legend: { orientation: "h", y: -0.15, font: { size: 10 } },
                xaxis: { type: "date", gridcolor: gridColor, tickformat: "%H:%M" },
                yaxis: { title: "\u00B0C", gridcolor: gridColor, side: "left" },
                yaxis2: { title: "%", overlaying: "y", side: "right", range: [0, 100], gridcolor: "transparent" },
                yaxis3: { overlaying: "y", side: "right", visible: false, range: [0, 20] },
                bargap: 0.1,
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
