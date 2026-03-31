/* ==========================================================================
   Vista Storica — /historical
   ========================================================================== */

(() => {
    "use strict";

    const wsUrl = (path) => (window.WS_API_PREFIX || "") + path;

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

    const METRIC_MAP = {
        temp_avg:        { key: "temp_avg_c",          label: "Temp. Media (\u00B0C)",     color: "#ff7043", yaxis: "y" },
        temp_high:       { key: "temp_high_c",         label: "Temp. Max (\u00B0C)",       color: "#ef5350", yaxis: "y" },
        temp_low:        { key: "temp_low_c",          label: "Temp. Min (\u00B0C)",       color: "#29b6f6", yaxis: "y" },
        dewpt_avg:       { key: "dew_point_avg_c",     label: "Pt. Rugiada Med (\u00B0C)", color: "#4dd0e1", yaxis: "y" },
        dewpt_high:      { key: "dew_point_high_c",    label: "Pt. Rugiada Max (\u00B0C)", color: "#00bcd4", yaxis: "y" },
        dewpt_low:       { key: "dew_point_low_c",     label: "Pt. Rugiada Min (\u00B0C)", color: "#80deea", yaxis: "y" },
        humidity_avg:    { key: "humidity_avg_pct",     label: "Umidit\u00E0 Media (%)",   color: "#42a5f5", yaxis: "y2" },
        pressure_avg:    { key: "pressure_avg_hpa",     label: "Press. Media (hPa)",       color: "#ab47bc", yaxis: "y3" },
        pressure_max:    { key: "pressure_max_hpa",     label: "Press. Max (hPa)",         color: "#ce93d8", yaxis: "y3" },
        pressure_min:    { key: "pressure_min_hpa",     label: "Press. Min (hPa)",         color: "#9575cd", yaxis: "y3" },
        wind_speed_avg:  { key: "wind_speed_avg_kmh",   label: "Vento Medio (km/h)",       color: "#26a69a", yaxis: "y4" },
        wind_speed_high: { key: "wind_speed_high_kmh",  label: "Vento Max (km/h)",         color: "#00897b", yaxis: "y4" },
        wind_gust_high:  { key: "wind_gust_high_kmh",   label: "Raffica Max (km/h)",       color: "#4db6ac", yaxis: "y4" },
        precip_total:    { key: "precip_total_mm",      label: "Precipitazioni (mm)",      color: "#5c6bc0", yaxis: "y4" },
    };

    let rawData = [];
    let dataTable = null;
    let sseSource = null;

    const getDateValue = (id) => {
        const el = document.getElementById(id);
        if (el && el._flatpickr && el._flatpickr.selectedDates.length) {
            return el._flatpickr.formatDate(el._flatpickr.selectedDates[0], "Y-m-d");
        }
        return el?.value || "";
    };

    const fetchData = async () => {
        const from = getDateValue("dateFrom");
        const to = getDateValue("dateTo");
        if (!from || !to) return;

        try {
            const resp = await fetch(wsUrl(`/api/daily?from=${from}&to=${to}`));
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
        const gridColor = "rgba(255,255,255,0.06)";
        const fontColor = "#9aa0a8";

        const traces = [];
        const gapFillIndices = rawData.map((r, i) => r.data_source === "gap_fill" ? i : -1).filter(i => i >= 0);

        checked.forEach((group) => {
            const def = METRIC_MAP[group];
            if (!def) return;

            const isPrecip = group === "precip_total";
            const yValues = rawData.map((r) => parseNum(r[def.key]));

            // Skip traces where ALL values are null (sensor not available)
            if (yValues.every((v) => v == null)) return;

            const trace = {
                x: dates,
                y: yValues,
                name: def.label,
                connectgaps: false,
                yaxis: def.yaxis,
            };

            if (isPrecip) {
                trace.type = "bar";
                // Color gap-filled bars with amber tint
                const colors = rawData.map((r) =>
                    r.data_source === "gap_fill" ? "rgba(245, 166, 35, 0.5)" : def.color
                );
                trace.marker = { color: colors, opacity: 0.6 };
            } else {
                trace.type = "scatter";
                trace.mode = "lines+markers";
                trace.line = { color: def.color, width: 2, shape: "spline" };
                // Mark gap-filled points with diamond shape and amber border
                const symbols = rawData.map((r) =>
                    r.data_source === "gap_fill" ? "diamond" : "circle"
                );
                const markerColors = rawData.map((r) =>
                    r.data_source === "gap_fill" ? "rgba(245, 166, 35, 0.8)" : def.color
                );
                trace.marker = { size: 5, symbol: symbols, color: markerColors };
            }

            traces.push(trace);
        });

        const hasY2 = checked.includes("humidity_avg");
        const hasY3 = checked.some((k) => ["pressure_avg", "pressure_max", "pressure_min"].includes(k));
        const hasY4 = checked.some((k) => ["wind_speed_avg", "wind_speed_high", "wind_gust_high", "precip_total"].includes(k));

        const layout = {
            margin: { t: 10, r: 80, b: 70, l: 60 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: "Inter, sans-serif", size: 11, color: fontColor },
            legend: { orientation: "h", y: -0.3, font: { size: 10 } },
            xaxis: { type: "date", gridcolor: gridColor, title: "Data", rangeslider: { visible: true } },
            yaxis: { title: "\u00B0C", gridcolor: gridColor, side: "left" },
            bargap: 0.2,
        };

        if (hasY2) layout.yaxis2 = { title: "%", overlaying: "y", side: "right", range: [0, 100], gridcolor: "transparent" };
        if (hasY3) layout.yaxis3 = { title: "hPa", overlaying: "y", side: "right", position: 0.95, anchor: "free", gridcolor: "transparent" };
        if (hasY4) layout.yaxis4 = { title: "Vento / Precip.", overlaying: "y", side: "right", position: hasY3 ? 0.90 : 0.95, anchor: "free", gridcolor: "transparent" };

        Plotly.newPlot(container, traces, layout, { responsive: true, displaylogo: false });
    };

    const TABLE_COLUMNS = [
        { data: "obs_date",            title: "Data" },
        { data: "temp_avg_c",          title: "T. Med (\u00B0C)",       render: (v) => fmt(v) },
        { data: "temp_high_c",         title: "T. Max (\u00B0C)",       render: (v) => fmt(v) },
        { data: "temp_low_c",          title: "T. Min (\u00B0C)",       render: (v) => fmt(v) },
        { data: "dew_point_avg_c",     title: "Rug. Med (\u00B0C)",     render: (v) => fmt(v) },
        { data: "dew_point_high_c",    title: "Rug. Max (\u00B0C)",     render: (v) => fmt(v) },
        { data: "dew_point_low_c",     title: "Rug. Min (\u00B0C)",     render: (v) => fmt(v) },
        { data: "humidity_avg_pct",    title: "Umid. Med (%)",          render: (v) => fmt(v, 0) },
        { data: "humidity_high_pct",   title: "Umid. Max (%)",          render: (v) => fmt(v, 0) },
        { data: "humidity_low_pct",    title: "Umid. Min (%)",          render: (v) => fmt(v, 0) },
        { data: "pressure_avg_hpa",    title: "Press. Med (hPa)",       render: (v) => fmt(v, 1) },
        { data: "pressure_max_hpa",    title: "Press. Max (hPa)",       render: (v) => fmt(v, 1) },
        { data: "pressure_min_hpa",    title: "Press. Min (hPa)",       render: (v) => fmt(v, 1) },
        { data: "wind_speed_avg_kmh",  title: "Vento Med (km/h)",       render: (v) => fmt(v) },
        { data: "wind_speed_high_kmh", title: "Vento Max (km/h)",       render: (v) => fmt(v) },
        { data: "wind_gust_high_kmh",  title: "Raff. Max (km/h)",       render: (v) => fmt(v) },
        { data: "precip_total_mm",     title: "Prec. Tot (mm)",         render: (v) => fmt(v, 2) },
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
            createdRow: (row, data) => {
                if (isNullRow(data)) row.classList.add("row-null");
                else if (data.data_source === "gap_fill") row.classList.add("row-gap-fill");
            },
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
        const labelEl = document.getElementById("backfillLabel");

        if (btnStart) btnStart.disabled = running;
        if (btnStop) btnStop.classList.toggle("d-none", !running);
        if (area) area.classList.toggle("d-none", !running && !detail);
        if (bar) {
            bar.style.width = `${percent}%`;
            bar.setAttribute("aria-valuenow", percent);
        }
        if (pctEl) pctEl.textContent = `${Math.round(percent)}%`;
        if (detailEl) detailEl.textContent = detail;
        if (labelEl) labelEl.textContent = running ? "Download in corso..." : (detail || "");
    };

    const getBackfillDate = (id) => {
        const el = document.getElementById(id);
        if (el && el._flatpickr && el._flatpickr.selectedDates.length) {
            return el._flatpickr.formatDate(el._flatpickr.selectedDates[0], "Y-m-d");
        }
        return el?.value || null;
    };

    const autoDetectStartDate = async () => {
        const btnStart = document.getElementById("btnStartBackfill");
        if (btnStart) btnStart.disabled = true;
        setBackfillUI(true, 0, "Ricerca automatica data di inizio raccolta dati...");

        try {
            const resp = await fetch(wsUrl("/api/sync/historical/detect-start"), { method: "POST" });
            const data = await resp.json();
            if (!resp.ok || !data.found) {
                setBackfillUI(false, 0, "");
                alert("Impossibile trovare dati storici per questa stazione negli ultimi 10 anni.");
                return null;
            }
            // Set the detected date in the input
            const el = document.getElementById("backfillStartDate");
            if (el && el._flatpickr) el._flatpickr.setDate(data.start_date, true);
            else if (el) el.value = data.start_date;
            return data.start_date;
        } catch (err) {
            console.error("autoDetectStartDate error:", err);
            setBackfillUI(false, 0, "");
            alert("Errore durante la ricerca automatica della data di inizio.");
            return null;
        }
    };

    const startBackfill = async () => {
        const resume = document.getElementById("chkResume")?.checked || false;

        let startDate = null;
        let endDate = null;

        if (resume) {
            // Resume mode: no dates needed, backend picks up from last synced + 1
        } else {
            startDate = getBackfillDate("backfillStartDate");
            endDate = getBackfillDate("backfillEndDate");

            // If no start date, auto-detect via binary search
            if (!startDate) {
                startDate = await autoDetectStartDate();
                if (!startDate) return;
            }
        }

        try {
            const body = {};
            if (startDate) body.start_date = startDate;
            if (endDate) body.end_date = endDate;

            const resp = await fetch(wsUrl("/api/sync/historical/start"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await resp.json();

            if (!resp.ok) {
                alert(`Errore: ${data.error || "Impossibile avviare il backfill"}`);
                setBackfillUI(false, 0, "");
                return;
            }

            listenProgress();
            setBackfillUI(true, 0, "Avvio in corso...");
        } catch (err) {
            console.error("startBackfill error:", err);
            alert("Errore di connessione durante l'avvio del backfill.");
            setBackfillUI(false, 0, "");
        }
    };

    const stopBackfill = async () => {
        try {
            await fetch(wsUrl("/api/sync/historical/stop"), { method: "POST" });
        } catch (err) {
            console.error("stopBackfill error:", err);
        }
    };

    const listenProgress = () => {
        if (sseSource) { sseSource.close(); sseSource = null; }

        sseSource = new EventSource(wsUrl("/api/sync/historical/progress"));

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

        // Set initial dates via flatpickr or fallback
        const setInitialDate = (el, val) => {
            if (el && el._flatpickr) el._flatpickr.setDate(val, false);
            else if (el) el.value = val;
        };
        setInitialDate(fromEl, thirtyDaysAgo());
        setInitialDate(toEl, todayISO());

        document.getElementById("btnFilter")?.addEventListener("click", fetchData);
        fromEl?.addEventListener("change", fetchData);
        toEl?.addEventListener("change", fetchData);

        document.querySelectorAll(".hist-metric").forEach((cb) => cb.addEventListener("change", updateChart));

        document.getElementById("btnStartBackfill")?.addEventListener("click", startBackfill);
        document.getElementById("btnStopBackfill")?.addEventListener("click", stopBackfill);

        // Toggle date fields visibility when "resume" checkbox changes
        const chkResume = document.getElementById("chkResume");
        const dateFields = document.getElementById("backfillDateFields");
        if (chkResume && dateFields) {
            chkResume.addEventListener("change", () => {
                dateFields.style.display = chkResume.checked ? "none" : "";
            });
        }

        fetchData();
    });
})();
