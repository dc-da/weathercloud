/* ==========================================================================
   Vista Giornaliera — /daily
   ========================================================================== */

(() => {
    "use strict";

    const wsUrl = (path) => (window.WS_API_PREFIX || "") + path;

    const degreesToCompass = (deg) => {
        if (deg == null || isNaN(deg)) return "N/D";
        const dirs = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
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

    // Chart colors and config per metric
    const METRIC_MAP = {
        temp: [{
            key: "temp_c", label: "Temperatura (\u00B0C)", color: "#ff7043", yaxis: "y",
            fill: "tozeroy", fillcolor: "rgba(255, 112, 67, 0.1)", shape: "spline",
        }],
        humidity: [{
            key: "humidity_pct", label: "Umidit\u00E0 (%)", color: "#42a5f5", yaxis: "y2",
            fill: "tozeroy", fillcolor: "rgba(66, 165, 245, 0.08)", shape: "spline",
        }],
        pressure: [{
            key: "pressure_hpa", label: "Pressione (hPa)", color: "#ab47bc", yaxis: "y3",
            shape: "spline",
        }],
        wind: [{
            key: "wind_speed_kmh", label: "Vento (km/h)", color: "#26a69a", yaxis: "y4",
            shape: "spline",
        }],
        precip: [{
            key: "precip_rate_mmh", label: "Precipitazioni (mm/h)", color: "#5c6bc0", yaxis: "y4",
            type: "bar",
        }],
        uv: [{
            key: "uv_index", label: "UV", color: "#ffa726", yaxis: "y4",
            type: "bar",
        }],
        dewpoint: [{
            key: "dew_point_c", label: "Punto di Rugiada (\u00B0C)", color: "#4dd0e1", yaxis: "y",
            shape: "spline",
        }],
        heatindex: [{
            key: "heat_index_c", label: "Indice di Calore (\u00B0C)", color: "#e57373", yaxis: "y",
            shape: "spline",
        }],
        windchill: [{
            key: "wind_chill_c", label: "Wind Chill (\u00B0C)", color: "#81d4fa", yaxis: "y",
            shape: "spline",
        }],
        solar: [{
            key: "solar_radiation_wm2", label: "Radiazione Solare (W/m\u00B2)", color: "#ffca28", yaxis: "y4",
            fill: "tozeroy", fillcolor: "rgba(255, 202, 40, 0.1)",
        }],
    };

    let rawData = [];
    let dataTable = null;

    const getSource = () => {
        const el = document.querySelector('input[name="source"]:checked');
        return el ? el.value : "rapid";
    };

    const getDate = () => document.getElementById("dateSelect")?._flatpickr?.selectedDates[0]
        ? document.getElementById("dateSelect")._flatpickr.formatDate(
            document.getElementById("dateSelect")._flatpickr.selectedDates[0], "Y-m-d")
        : document.getElementById("dateSelect")?.value || todayISO();

    const fetchData = async () => {
        const source = getSource();
        const dateStr = getDate();
        const url = source === "rapid"
            ? wsUrl(`/api/rapid?date=${dateStr}`)
            : wsUrl(`/api/hourly?date=${dateStr}`);

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
        const gridColor = "rgba(255,255,255,0.06)";
        const fontColor = "#9aa0a8";

        const traces = [];
        checked.forEach((group) => {
            const defs = METRIC_MAP[group];
            if (!defs) return;
            defs.forEach((def) => {
                const yValues = rawData.map((r) => parseNum(r[def.key]));

                // Skip traces where ALL values are null (sensor not available)
                if (yValues.every((v) => v == null)) return;

                const trace = {
                    x: times,
                    y: yValues,
                    name: def.label,
                    connectgaps: false,
                    yaxis: def.yaxis,
                };

                if (def.type === "bar") {
                    trace.type = "bar";
                    trace.marker = { color: def.color, opacity: 0.7 };
                } else {
                    trace.type = "scatter";
                    trace.mode = "lines";
                    trace.line = { color: def.color, width: 2, shape: def.shape || "linear" };
                    if (def.fill) {
                        trace.fill = def.fill;
                        trace.fillcolor = def.fillcolor;
                    }
                }

                traces.push(trace);
            });
        });

        const hasY2 = checked.includes("humidity");
        const hasY3 = checked.includes("pressure");
        const hasY4 = checked.some((k) => ["wind", "precip", "uv"].includes(k));

        const layout = {
            margin: { t: 10, r: 80, b: 50, l: 60 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: "Inter, sans-serif", size: 11, color: fontColor },
            legend: { orientation: "h", y: -0.2, font: { size: 10 } },
            xaxis: { type: "date", gridcolor: gridColor, title: "Orario", tickformat: "%H:%M" },
            yaxis: { title: "\u00B0C", gridcolor: gridColor, side: "left" },
            bargap: 0.15,
        };

        if (hasY2) layout.yaxis2 = { title: "%", overlaying: "y", side: "right", range: [0, 100], gridcolor: "transparent" };
        if (hasY3) layout.yaxis3 = { title: "hPa", overlaying: "y", side: "right", position: 0.95, anchor: "free", gridcolor: "transparent" };
        if (hasY4) layout.yaxis4 = { title: "Vento / Pioggia / UV", overlaying: "y", side: "right", position: hasY3 ? 0.90 : 0.95, anchor: "free", gridcolor: "transparent" };

        Plotly.newPlot(container, traces, layout, { responsive: true, displaylogo: false });
    };

    const TABLE_COLUMNS = [
        { data: "observed_at_local", title: "Orario", render: (v) => v ? v.split(" ").pop()?.slice(0, 5) || v : "N/D" },
        { data: "temp_c",            title: "Temp (\u00B0C)", render: (v) => fmt(v) },
        { data: "heat_index_c",      title: "Ind. Calore (\u00B0C)", render: (v) => fmt(v) },
        { data: "dew_point_c",       title: "Pt. Rugiada (\u00B0C)", render: (v) => fmt(v) },
        { data: "wind_chill_c",      title: "Wind Chill (\u00B0C)", render: (v) => fmt(v) },
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
        // Set initial date via flatpickr
        const datePicker = document.getElementById("dateSelect");
        if (datePicker && datePicker._flatpickr) {
            datePicker._flatpickr.setDate(todayISO(), false);
        } else if (datePicker) {
            datePicker.value = todayISO();
        }

        // Fetch on date change, source change, or Load button
        datePicker?.addEventListener("change", fetchData);
        document.querySelectorAll('input[name="source"]').forEach((r) => r.addEventListener("change", fetchData));
        document.getElementById("btnLoad")?.addEventListener("click", fetchData);

        // Metric checkboxes only redraw chart
        document.querySelectorAll(".metric-check").forEach((cb) => cb.addEventListener("change", updateChart));

        fetchData();
    });
})();
