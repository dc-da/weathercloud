/* ==========================================================================
   Vista Report — /reports
   ========================================================================== */

(() => {
    "use strict";

    const wsUrl = (path) => (window.WS_API_PREFIX || "") + path;

    const parseNum = (v) => {
        if (v == null || v === "" || v === "None") return null;
        const n = Number(v);
        return isNaN(n) ? null : n;
    };

    const fmt = (v, dec = 2) => {
        const n = parseNum(v);
        return n == null ? "N/D" : n.toFixed(dec);
    };

    const todayISO = () => new Date().toISOString().slice(0, 10);
    const thirtyDaysAgo = () => {
        const d = new Date();
        d.setDate(d.getDate() - 30);
        return d.toISOString().slice(0, 10);
    };

    const getSource = () => {
        const el = document.querySelector('input[name="rptSource"]:checked');
        return el ? el.value : "rapid";
    };

    const getDateValue = (id) => {
        const el = document.getElementById(id);
        if (el && el._flatpickr && el._flatpickr.selectedDates.length) {
            return el._flatpickr.formatDate(el._flatpickr.selectedDates[0], "Y-m-d");
        }
        return el?.value || "";
    };

    const gridColor = "rgba(255,255,255,0.06)";
    const fontColor = "#9aa0a8";

    let statsTable = null;

    /* ------------------------------------------------------------------
       Section 1: Medie Giornaliere Min/Max
       ------------------------------------------------------------------ */
    const generateReport = async () => {
        const source = getSource();
        const from = getDateValue("rptDateFrom");
        const to = getDateValue("rptDateTo");
        if (!from || !to) return alert("Seleziona un periodo");

        try {
            const resp = await fetch(wsUrl(`/api/report/daily-stats?source=${source}&from=${from}&to=${to}`));
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            drawStatsChart(data);
            drawStatsTable(data);
        } catch (e) {
            console.error("generateReport error:", e);
        }
    };

    const drawStatsChart = (data) => {
        const dates = data.map((d) => d.obs_date);

        const traces = [
            {
                x: dates,
                y: data.map((d) => parseNum(d.temp_max)),
                name: "Temp Max",
                type: "bar",
                marker: { color: "rgba(239, 83, 80, 0.7)" },
            },
            {
                x: dates,
                y: data.map((d) => parseNum(d.temp_min)),
                name: "Temp Min",
                type: "bar",
                marker: { color: "rgba(66, 165, 245, 0.7)" },
            },
            {
                x: dates,
                y: data.map((d) => parseNum(d.temp_avg)),
                name: "Temp Media",
                type: "scatter",
                mode: "lines+markers",
                line: { color: "#ff7043", width: 3, shape: "spline" },
                marker: { size: 5 },
            },
        ];

        const layout = {
            barmode: "group",
            margin: { t: 10, r: 30, b: 60, l: 60 },
            xaxis: { title: "Data", type: "date", gridcolor: gridColor },
            yaxis: { title: "\u00B0C", gridcolor: gridColor },
            showlegend: true,
            legend: { orientation: "h", y: -0.2, font: { size: 10 } },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: "Inter, sans-serif", color: fontColor },
            bargap: 0.15,
        };

        Plotly.newPlot("dailyStatsChart", traces, layout, { responsive: true, displaylogo: false });
    };

    const drawStatsTable = (data) => {
        if (statsTable) {
            statsTable.destroy();
            statsTable = null;
        }

        statsTable = new DataTable("#dailyStatsTable", {
            data: data,
            columns: [
                { data: "obs_date", title: "Data" },
                { data: "temp_avg", title: "T media", render: (v) => fmt(v, 1) },
                { data: "temp_min", title: "T min", render: (v) => fmt(v, 1) },
                { data: "temp_max", title: "T max", render: (v) => fmt(v, 1) },
                { data: "humidity_avg", title: "Um. media", render: (v) => fmt(v, 0) },
                { data: "humidity_min", title: "Um. min", render: (v) => fmt(v, 0) },
                { data: "humidity_max", title: "Um. max", render: (v) => fmt(v, 0) },
                { data: "pressure_avg", title: "Press. media", render: (v) => fmt(v, 1) },
                { data: "wind_avg", title: "Vento medio", render: (v) => fmt(v, 1) },
                { data: "wind_gust_max", title: "Raffica max", render: (v) => fmt(v, 1) },
                { data: "precip_total_max", title: "Pioggia", render: (v) => fmt(v, 1) },
                { data: "solar_avg", title: "Solare media", render: (v) => fmt(v, 0) },
                { data: "uv_max", title: "UV max", render: (v) => fmt(v, 0) },
            ],
            order: [[0, "asc"]],
            pageLength: 25,
            searching: true,
            ordering: true,
            paging: true,
            info: true,
            language: {
                url: "//cdn.datatables.net/plug-ins/2.0.0/i18n/it-IT.json",
            },
            destroy: true,
        });
    };

    /* ------------------------------------------------------------------
       Section 2: Confronto tra Periodi
       ------------------------------------------------------------------ */
    const comparePeriods = async () => {
        const source = getSource();
        const metric = document.getElementById("cmpMetric")?.value || "temp_c";
        const aFrom = getDateValue("cmpAFrom");
        const aTo = getDateValue("cmpATo");
        const bFrom = getDateValue("cmpBFrom");
        const bTo = getDateValue("cmpBTo");

        if (!aFrom || !aTo || !bFrom || !bTo) return alert("Compila tutti i campi periodo");

        try {
            const resp = await fetch(
                wsUrl(`/api/report/comparison?source=${source}&metric=${metric}` +
                `&a_from=${aFrom}&a_to=${aTo}&b_from=${bFrom}&b_to=${bTo}`)
            );
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            drawComparisonChart(data);
            drawComparisonTable(data);
        } catch (e) {
            console.error("comparePeriods error:", e);
        }
    };

    const drawComparisonChart = (data) => {
        const aData = data.period_a.data;
        const bData = data.period_b.data;

        const traces = [
            {
                x: aData.map((_, i) => i + 1),
                y: aData.map((d) => d.avg),
                name: "Periodo A",
                type: "scatter",
                mode: "lines+markers",
                line: { color: "#5ba4f5", width: 2, shape: "spline" },
                marker: { size: 5 },
            },
            {
                x: bData.map((_, i) => i + 1),
                y: bData.map((d) => d.avg),
                name: "Periodo B",
                type: "scatter",
                mode: "lines+markers",
                line: { color: "#4ecb71", width: 2, shape: "spline" },
                marker: { size: 5 },
            },
        ];

        const layout = {
            margin: { t: 10, r: 30, b: 60, l: 60 },
            xaxis: { title: "Giorno relativo", gridcolor: gridColor },
            yaxis: { title: data.metric, gridcolor: gridColor },
            showlegend: true,
            legend: { orientation: "h", y: -0.2, font: { size: 10 } },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: "Inter, sans-serif", color: fontColor },
        };

        Plotly.newPlot("comparisonChart", traces, layout, { responsive: true, displaylogo: false });
    };

    const drawComparisonTable = (data) => {
        const sa = data.period_a.summary;
        const sb = data.period_b.summary;
        const delta = (a, b) => (a != null && b != null) ? (b - a).toFixed(2) : "N/D";

        const setText = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        setText("cmpAvgA", fmt(sa.avg));
        setText("cmpAvgB", fmt(sb.avg));
        setText("cmpAvgDiff", delta(sa.avg, sb.avg));
        setText("cmpMinA", fmt(sa.min));
        setText("cmpMinB", fmt(sb.min));
        setText("cmpMinDiff", delta(sa.min, sb.min));
        setText("cmpMaxA", fmt(sa.max));
        setText("cmpMaxB", fmt(sb.max));
        setText("cmpMaxDiff", delta(sa.max, sb.max));
        setText("cmpStdA", fmt(sa.stddev));
        setText("cmpStdB", fmt(sb.stddev));
        setText("cmpStdDiff", delta(sa.stddev, sb.stddev));
    };

    /* ------------------------------------------------------------------
       Section 3: Heatmap Oraria
       ------------------------------------------------------------------ */
    const generateHeatmap = async () => {
        const source = getSource();
        const metric = document.getElementById("heatmapMetric")?.value || "temp_c";
        const from = getDateValue("rptDateFrom");
        const to = getDateValue("rptDateTo");
        if (!from || !to) return alert("Seleziona un periodo");

        try {
            const resp = await fetch(
                wsUrl(`/api/report/heatmap?source=${source}&metric=${metric}&from=${from}&to=${to}`)
            );
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            drawHeatmap(data);
        } catch (e) {
            console.error("generateHeatmap error:", e);
        }
    };

    const drawHeatmap = (result) => {
        const data = result.data;
        if (!data.length) {
            document.getElementById("heatmapChart").innerHTML =
                '<div class="ws-no-data">Nessun dato per il periodo selezionato</div>';
            return;
        }

        const dates = [...new Set(data.map((d) => d.date))].sort();
        const hours = Array.from({ length: 24 }, (_, i) => i);

        const lookup = {};
        for (const d of data) {
            lookup[`${d.date}-${d.hour}`] = d.value;
        }

        const z = dates.map((date) =>
            hours.map((h) => lookup[`${date}-${h}`] ?? null)
        );

        const traces = [{
            z: z,
            x: hours,
            y: dates,
            type: "heatmap",
            colorscale: [
                [0, "#42a5f5"],
                [0.25, "#66bb6a"],
                [0.5, "#ffa726"],
                [0.75, "#ef5350"],
                [1, "#9c27b0"],
            ],
            colorbar: { title: result.metric, tickfont: { color: fontColor } },
        }];

        const layout = {
            margin: { t: 10, r: 30, b: 60, l: 100 },
            xaxis: { title: "Ora", dtick: 1, gridcolor: gridColor },
            yaxis: { title: "Data", type: "category" },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: "Inter, sans-serif", color: fontColor },
        };

        Plotly.newPlot("heatmapChart", traces, layout, { responsive: true, displaylogo: false });
    };

    /* ------------------------------------------------------------------
       Export
       ------------------------------------------------------------------ */
    const exportCSV = () => {
        const source = getSource();
        const from = getDateValue("rptDateFrom");
        const to = getDateValue("rptDateTo");
        if (!from || !to) return;
        window.location.href = `/api/export/csv?source=${source}&from=${from}&to=${to}`;
    };

    const exportXLSX = () => {
        const source = getSource();
        const from = getDateValue("rptDateFrom");
        const to = getDateValue("rptDateTo");
        if (!from || !to) return;
        window.location.href = `/api/export/xlsx?source=${source}&from=${from}&to=${to}`;
    };

    /* ------------------------------------------------------------------
       Init
       ------------------------------------------------------------------ */
    document.addEventListener("DOMContentLoaded", () => {
        const setInitialDate = (id, val) => {
            const el = document.getElementById(id);
            if (el && el._flatpickr) el._flatpickr.setDate(val, false);
            else if (el) el.value = val;
        };

        setInitialDate("rptDateFrom", thirtyDaysAgo());
        setInitialDate("rptDateTo", todayISO());

        document.getElementById("btnGenerate")?.addEventListener("click", generateReport);
        document.getElementById("btnCompare")?.addEventListener("click", comparePeriods);

        document.getElementById("heatmapMetric")?.addEventListener("change", generateHeatmap);

        document.getElementById("btnExportCSV")?.addEventListener("click", exportCSV);
        document.getElementById("btnExportXLSX")?.addEventListener("click", exportXLSX);
    });
})();
