/* ==========================================================================
   Vista Giornaliera — /daily
   ========================================================================== */

(() => {
    "use strict";

    const degreesToCompass = (deg) => {
        if (deg == null || isNaN(deg)) return "N/D";
        const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
        return dirs[Math.round(((Number(deg) % 360) + 360) % 360 / 45) % 8];
    };

    const parseNum = (v) => {
        if (v == null || v === "" || v === "None") return null;
        const n = Number(v);
        return isNaN(n) ? null : n;
    };

    const fmt = (v, dec = 1) => {
        const n = parseNum(v);
        return n == null ? "N/D" : n.toFixed(dec);
    };

    const isNullRow = (row) => {
        const keys = [
            "temp_c", "heat_index_c", "dew_point_c", "wind_chill_c",
            "humidity_pct", "pressure_hpa", "wind_speed_kmh", "wind_gust_kmh",
            "wind_dir_deg", "precip_rate_mmh", "precip_total_mm",
            "solar_radiation_wm2", "uv_index",
        ];
        return keys.every((k) => row[k] == null || row[k] === "None");
    };

    const todayISO = () => new Date().toISOString().slice(0, 10);

    // Metric key mapping: checkbox value -> DB column(s)
    const METRIC_MAP = {
        temp:     [{ key: "temp_c",           label: "Temperatura (\u00B0C)",  color: "#ff7043", yaxis: "y" }],
        humidity: [{ key: "humidity_pct",      label: "Umidit\u00E0 (%)",      color: "#42a5f5", yaxis: "y2" }],
        pressure: [{ key: "pressure_hpa",      label: "Pressione (hPa)",       color: "#ab47bc", yaxis: "y3" }],
        wind:     [{ key: "wind_speed_kmh",    label: "Vento (km/h)",          color: "#26a69a", yaxis: "y4" }],
        precip:   [{ key: "precip_rate_mmh",   label: "Precipitazioni (mm/h)", color: "#5c6bc0", yaxis: "y4" }],
        uv:       [{ key: "uv_index",          label: "UV",                    color: "#ffa726", yaxis: "y4" }],
    };

    let rawData = [];
    let dataTable = null;

    const getSource = () => {
        const el = document.querySelector('input[name="source"]:checked');
        return el ? el.value : "rapid";
    };

    const getDate = () => document.getElementById("dateSelect")?.value || todayISO();

    const fetchData = async () => {
        const source = getSource();
        const dateStr = getDate();
        const url = source === "rapid"
            ? `/api/rapid?date=${dateStr}`
            : `/api/hourly?date=${dateStr}`;

        try {
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            rawData = await resp.json();
            updateChart();
            updateTable();
        } catch (err) {
            console.error("daily fetchData error:", err);
            rawData = [];
            updateTable();
        }
    };

    const getCheckedMetrics = () => {
        const boxes = document.querySelectorAll(".metric-check:checked");
        return Array.from(boxes).map((cb) => cb.value);
    };

    const updateChart = () => {
        const container = document.getElementById("dailyChart");
        if (!container) return;

        if (!rawData.length) {
            container.innerHTML = '<div class="ws-no-data">Nessun dato per la data selezionata</div>';
            return;
        }

        const checked = getCheckedMetrics();
        if (!checked.length) {
            container.innerHTML = '<div class="ws-no-data">Seleziona almeno una metrica</div>';
            return;
        }

        const times = rawData.map((r) => r.observed_at_local);
        const isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
        const gridColor = isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)";
        const fontColor = isDark ? "#ccc" : "#666";

        const traces = [];
        checked.forEach((group) => {
            const defs = METRIC_MAP[group];
            if (!defs) return;
            defs.forEach((def) => {
                traces.push({
                    x: times,
                    y: rawData.map((r) => parseNum(r[def.key])),
                    name: def.label,
                    type: "scatter",
                    mode: "lines",
                    line: { color: def.color, width: 2 },
                    connectgaps: false,
                    yaxis: def.yaxis,
                });
            });
        });

        const hasY2 = checked.includes("humidity");
        const hasY3 = checked.includes("pressure");
        const hasY4 = checked.some((k) => ["wind", "precip", "uv"].includes(k));

        const layout = {
            margin: { t: 20, r: 80, b: 50, l: 60 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { size: 11, color: fontColor },
            legend: { orientation: "h", y: -0.25 },
            xaxis: { type: "date", gridcolor: gridColor, title: "Orario", tickformat: "%H:%M" },
            yaxis: { title: "Temperatura (\u00B0C)", gridcolor: gridColor, side: "left" },
        };

        if (hasY2) layout.yaxis2 = { title: "Umidit\u00E0 (%)", overlaying: "y", side: "right", range: [0, 100], gridcolor: "transparent" };
        if (hasY3) layout.yaxis3 = { title: "Pressione (hPa)", overlaying: "y", side: "right", position: 0.95, anchor: "free", gridcolor: "transparent" };
        if (hasY4) layout.yaxis4 = { title: "Vento / Pioggia / UV", overlaying: "y", side: "right", position: hasY3 ? 0.90 : 0.95, anchor: "free", gridcolor: "transparent" };

        Plotly.newPlot(container, traces, layout, { responsive: true, displaylogo: false });
    };

    const TABLE_COLUMNS = [
        { data: "observed_at_local", title: "Orario", render: (v) => v ? v.split(" ").pop()?.slice(0, 5) || v : "N/D" },
        { data: "temp_c",            title: "Temp (\u00B0C)", render: (v) => fmt(v) },
        { data: "humidity_pct",      title: "Umid. (%)", render: (v) => fmt(v, 0) },
        { data: "pressure_hpa",      title: "Press. (hPa)", render: (v) => fmt(v, 1) },
        { data: "wind_speed_kmh",    title: "Vento (km/h)", render: (v) => fmt(v) },
        { data: "wind_gust_kmh",     title: "Raffica (km/h)", render: (v) => fmt(v) },
        { data: "wind_dir_deg",      title: "Dir. Vento", render: (v) => { const n = parseNum(v); return n != null ? `${degreesToCompass(n)} (${n}\u00B0)` : "N/D"; } },
        { data: "precip_rate_mmh",   title: "Pioggia (mm/h)", render: (v) => fmt(v, 2) },
        { data: "precip_total_mm",   title: "Pioggia Tot (mm)", render: (v) => fmt(v, 2) },
        { data: "solar_radiation_wm2", title: "Solare (W/m\u00B2)", render: (v) => fmt(v, 0) },
        { data: "uv_index",          title: "UV", render: (v) => fmt(v, 0) },
    ];

    const updateTable = () => {
        if (dataTable) { dataTable.destroy(); dataTable = null; }

        dataTable = new DataTable("#dailyTable", {
            data: rawData,
            columns: TABLE_COLUMNS.map((col) => ({
                data: col.data, title: col.title, render: col.render, defaultContent: "N/D",
            })),
            order: [[0, "asc"]],
            pageLength: 25,
            searching: true,
            ordering: true,
            paging: true,
            info: true,
            language: { url: "//cdn.datatables.net/plug-ins/2.0.0/i18n/it-IT.json" },
            createdRow: (row, data) => { if (isNullRow(data)) row.classList.add("row-null"); },
            destroy: true,
        });
    };

    document.addEventListener("DOMContentLoaded", () => {
        const datePicker = document.getElementById("dateSelect");
        if (datePicker) datePicker.value = todayISO();

        // Fetch on date change, source change, or Load button
        datePicker?.addEventListener("change", fetchData);
        document.querySelectorAll('input[name="source"]').forEach((r) => r.addEventListener("change", fetchData));
        document.getElementById("btnLoad")?.addEventListener("click", fetchData);

        // Metric checkboxes only redraw chart
        document.querySelectorAll(".metric-check").forEach((cb) => cb.addEventListener("change", updateChart));

        fetchData();
    });
})();
