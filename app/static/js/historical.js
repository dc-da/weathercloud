/* ==========================================================================
   Vista Storica — /historical
   ========================================================================== */

(() => {
    "use strict";

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
            "temp_avg_c", "temp_high_c", "temp_low_c",
            "humidity_avg_pct", "humidity_high_pct", "humidity_low_pct",
            "pressure_avg_hpa", "pressure_max_hpa", "pressure_min_hpa",
            "wind_speed_avg_kmh", "wind_speed_high_kmh", "wind_gust_high_kmh",
            "precip_total_mm",
        ];
        return keys.every((k) => row[k] == null || row[k] === "None");
    };

    const todayISO = () => new Date().toISOString().slice(0, 10);
    const thirtyDaysAgo = () => {
        const d = new Date();
        d.setDate(d.getDate() - 30);
        return d.toISOString().slice(0, 10);
    };

    // Metric checkbox value -> DB column mapping
    const METRIC_MAP = {
        temp_avg:       { key: "temp_avg_c",         label: "Temp. Media (\u00B0C)",  color: "#ff7043", yaxis: "y" },
        temp_high:      { key: "temp_high_c",        label: "Temp. Max (\u00B0C)",    color: "#ef5350", yaxis: "y" },
        temp_low:       { key: "temp_low_c",         label: "Temp. Min (\u00B0C)",    color: "#29b6f6", yaxis: "y" },
        humidity_avg:   { key: "humidity_avg_pct",    label: "Umidit\u00E0 Media (%)",color: "#42a5f5", yaxis: "y2" },
        pressure_avg:   { key: "pressure_avg_hpa",    label: "Pressione Media (hPa)", color: "#ab47bc", yaxis: "y3" },
        wind_speed_avg: { key: "wind_speed_avg_kmh",  label: "Vento Medio (km/h)",    color: "#26a69a", yaxis: "y4" },
        precip_total:   { key: "precip_total_mm",     label: "Precipitazioni (mm)",   color: "#5c6bc0", yaxis: "y4" },
    };

    let rawData = [];
    let dataTable = null;
    let sseSource = null;

    const fetchData = async () => {
        const from = document.getElementById("dateFrom")?.value;
        const to = document.getElementById("dateTo")?.value;
        if (!from || !to) return;

        try {
            const resp = await fetch(`/api/daily?from=${from}&to=${to}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            rawData = await resp.json();
            updateChart();
            updateTable();
        } catch (err) {
            console.error("historical fetchData error:", err);
            rawData = [];
            updateTable();
        }
    };

    const getCheckedMetrics = () => {
        return Array.from(document.querySelectorAll(".hist-metric:checked")).map((cb) => cb.value);
    };

    const updateChart = () => {
        const container = document.getElementById("historicalChart");
        if (!container) return;

        if (!rawData.length) {
            container.innerHTML = '<div class="ws-no-data">Nessun dato per il periodo selezionato</div>';
            return;
        }

        const checked = getCheckedMetrics();
        if (!checked.length) {
            container.innerHTML = '<div class="ws-no-data">Seleziona almeno una metrica</div>';
            return;
        }

        const dates = rawData.map((r) => r.obs_date);
        const isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
        const gridColor = isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)";
        const fontColor = isDark ? "#ccc" : "#666";

        const traces = [];
        checked.forEach((group) => {
            const def = METRIC_MAP[group];
            if (!def) return;
            traces.push({
                x: dates,
                y: rawData.map((r) => parseNum(r[def.key])),
                name: def.label,
                type: "scatter",
                mode: "lines+markers",
                line: { color: def.color, width: 2 },
                marker: { size: 4 },
                connectgaps: false,
                yaxis: def.yaxis,
            });
        });

        const hasY2 = checked.includes("humidity_avg");
        const hasY3 = checked.includes("pressure_avg");
        const hasY4 = checked.some((k) => ["wind_speed_avg", "precip_total"].includes(k));

        const layout = {
            margin: { t: 20, r: 80, b: 70, l: 60 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { size: 11, color: fontColor },
            legend: { orientation: "h", y: -0.3 },
            xaxis: { type: "date", gridcolor: gridColor, title: "Data", rangeslider: { visible: true } },
            yaxis: { title: "Temperatura (\u00B0C)", gridcolor: gridColor, side: "left" },
        };

        if (hasY2) layout.yaxis2 = { title: "Umidit\u00E0 (%)", overlaying: "y", side: "right", range: [0, 100], gridcolor: "transparent" };
        if (hasY3) layout.yaxis3 = { title: "Pressione (hPa)", overlaying: "y", side: "right", position: 0.95, anchor: "free", gridcolor: "transparent" };
        if (hasY4) layout.yaxis4 = { title: "Vento / Precipitazioni", overlaying: "y", side: "right", position: hasY3 ? 0.90 : 0.95, anchor: "free", gridcolor: "transparent" };

        Plotly.newPlot(container, traces, layout, { responsive: true, displaylogo: false });
    };

    const TABLE_COLUMNS = [
        { data: "obs_date",            title: "Data" },
        { data: "temp_avg_c",          title: "T. Med (\u00B0C)",   render: (v) => fmt(v) },
        { data: "temp_high_c",         title: "T. Max (\u00B0C)",   render: (v) => fmt(v) },
        { data: "temp_low_c",          title: "T. Min (\u00B0C)",   render: (v) => fmt(v) },
        { data: "humidity_avg_pct",    title: "Umid. Med (%)",      render: (v) => fmt(v, 0) },
        { data: "humidity_high_pct",   title: "Umid. Max (%)",      render: (v) => fmt(v, 0) },
        { data: "humidity_low_pct",    title: "Umid. Min (%)",      render: (v) => fmt(v, 0) },
        { data: "pressure_avg_hpa",    title: "Press. Med (hPa)",   render: (v) => fmt(v, 1) },
        { data: "wind_speed_avg_kmh",  title: "Vento Med (km/h)",   render: (v) => fmt(v) },
        { data: "wind_speed_high_kmh", title: "Vento Max (km/h)",   render: (v) => fmt(v) },
        { data: "wind_gust_high_kmh",  title: "Raff. Max (km/h)",   render: (v) => fmt(v) },
        { data: "precip_total_mm",     title: "Prec. Tot (mm)",     render: (v) => fmt(v, 2) },
    ];

    const updateTable = () => {
        if (dataTable) { dataTable.destroy(); dataTable = null; }

        dataTable = new DataTable("#historicalTable", {
            data: rawData,
            columns: TABLE_COLUMNS.map((col) => ({
                data: col.data, title: col.title, render: col.render || undefined, defaultContent: "N/D",
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

    /* ------------------------------------------------------------------
       Backfill controls
       ------------------------------------------------------------------ */
    const setBackfillUI = (running, percent = 0, detail = "") => {
        const btnStart = document.getElementById("btnStartBackfill");
        const btnStop = document.getElementById("btnStopBackfill");
        const area = document.getElementById("backfillProgressArea");
        const bar = document.getElementById("backfillBar");
        const pctEl = document.getElementById("backfillPercent");
        const detailEl = document.getElementById("backfillDetail");

        if (btnStart) btnStart.disabled = running;
        if (btnStop) {
            btnStop.classList.toggle("d-none", !running);
        }
        if (area) area.classList.toggle("d-none", !running);
        if (bar) {
            bar.style.width = `${percent}%`;
            bar.setAttribute("aria-valuenow", percent);
        }
        if (pctEl) pctEl.textContent = `${Math.round(percent)}%`;
        if (detailEl) detailEl.textContent = detail;
    };

    const startBackfill = async () => {
        let startDate = document.getElementById("backfillStartDate")?.value || null;

        try {
            const body = startDate ? { start_date: startDate } : {};
            const resp = await fetch("/api/sync/historical/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await resp.json();

            if (!resp.ok) {
                if (data.needs_start_date) {
                    const input = prompt("Nessun dato storico esistente. Inserisci la data di inizio (YYYY-MM-DD):");
                    if (input) {
                        document.getElementById("backfillStartDate").value = input;
                        return startBackfill();
                    }
                    return;
                }
                alert(`Errore: ${data.error || "Impossibile avviare il backfill"}`);
                return;
            }

            listenProgress();
            setBackfillUI(true, 0, "Avvio in corso...");
        } catch (err) {
            console.error("startBackfill error:", err);
            alert("Errore di connessione durante l'avvio del backfill.");
        }
    };

    const stopBackfill = async () => {
        try {
            await fetch("/api/sync/historical/stop", { method: "POST" });
        } catch (err) {
            console.error("stopBackfill error:", err);
        }
    };

    const listenProgress = () => {
        if (sseSource) { sseSource.close(); sseSource = null; }

        sseSource = new EventSource("/api/sync/historical/progress");

        sseSource.onmessage = (event) => {
            try {
                const state = JSON.parse(event.data);
                const pct = state.total > 0 ? (state.progress / state.total) * 100 : 0;
                const detail = state.current_date
                    ? `Elaborazione: ${state.current_date} (${state.progress}/${state.total})`
                    : "";

                setBackfillUI(state.running, pct, detail);

                if (!state.running) {
                    sseSource.close();
                    sseSource = null;
                    if (state.error) alert("Errore: " + state.error);
                    fetchData();
                }
            } catch (e) {
                console.error("SSE parse error:", e);
            }
        };

        sseSource.onerror = () => {
            sseSource.close();
            sseSource = null;
            setBackfillUI(false, 0, "Connessione SSE persa");
        };
    };

    /* ------------------------------------------------------------------
       Init
       ------------------------------------------------------------------ */
    document.addEventListener("DOMContentLoaded", () => {
        const fromEl = document.getElementById("dateFrom");
        const toEl = document.getElementById("dateTo");
        if (fromEl && !fromEl.value) fromEl.value = thirtyDaysAgo();
        if (toEl && !toEl.value) toEl.value = todayISO();

        document.getElementById("btnFilter")?.addEventListener("click", fetchData);
        fromEl?.addEventListener("change", fetchData);
        toEl?.addEventListener("change", fetchData);

        document.querySelectorAll(".hist-metric").forEach((cb) => cb.addEventListener("change", updateChart));

        document.getElementById("btnStartBackfill")?.addEventListener("click", startBackfill);
        document.getElementById("btnStopBackfill")?.addEventListener("click", stopBackfill);

        fetchData();
    });
})();
