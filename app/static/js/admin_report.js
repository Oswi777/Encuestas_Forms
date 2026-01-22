(async function () {
  const campaignId = window.__REPORT__?.campaignId;
  if (!campaignId) return;

  const kpiRow = document.getElementById('kpiRow');
  const reasonsRow = document.getElementById('reasonsRow');
  const generalMatrix = document.getElementById('generalMatrix');
  const reportSubtitle = document.getElementById('reportSubtitle');

  const ctxByDay = document.getElementById('chartByDay');
  const ctxByShift = document.getElementById('chartByShift');
  const ctxMain = document.getElementById('chartMain');
  const ctxPos = document.getElementById('chartReasonsPos');
  const ctxNeg = document.getElementById('chartReasonsNeg');
  const ctxGeneral = document.getElementById('chartGeneralStacked');

  function escapeHtml(s) {
    return String(s ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function kpi(label, value, sub) {
    const d = document.createElement('div');
    d.className = 'kpi';
    d.innerHTML =
      `<div class="label">${escapeHtml(label)}</div>` +
      `<div class="value">${escapeHtml(value)}</div>` +
      (sub ? `<div class="sub">${escapeHtml(sub)}</div>` : '');
    return d;
  }

  function pct(values) {
    const total = values.reduce((a, b) => a + b, 0) || 1;
    return values.map(v => Math.round((v * 1000) / total) / 10); // 1 decimal
  }

  const uiLang = (document.documentElement.getAttribute('lang') || 'es')
    .toLowerCase()
    .startsWith('en')
    ? 'en'
    : 'es';

  function likertLabels(preset, lang) {
    const p = String(preset || 'satisfaction');
    const dict = {
      satisfaction: {
        es: ['Muy malo', 'Malo', 'Regular', 'Bueno', 'Excelente'],
        en: ['Very bad', 'Bad', 'Fair', 'Good', 'Excellent'],
      },
      agreement: {
        es: [
          'Totalmente en desacuerdo',
          'En desacuerdo',
          'Neutral',
          'De acuerdo',
          'Totalmente de acuerdo',
        ],
        en: [
          'Strongly disagree',
          'Disagree',
          'Neutral',
          'Agree',
          'Strongly agree',
        ],
      },
      frequency: {
        es: ['Nunca', 'Rara vez', 'A veces', 'Casi siempre', 'Siempre'],
        en: ['Never', 'Rarely', 'Sometimes', 'Often', 'Always'],
      },
    };
    return (
      (dict[p] && dict[p][lang]) ||
      (dict[p] && dict[p].es) ||
      ['1', '2', '3', '4', '5']
    );
  }

  function avgWithLabel(avg, preset) {
    if (avg == null || isNaN(Number(avg))) return '—';
    const a = Number(avg);
    const idx = Math.min(4, Math.max(0, Math.round(a) - 1));
    const lab = likertLabels(preset, uiLang)[idx] || '';
    return `${a.toFixed(2)} (${lab})`;
  }

  // ---------------- Fetch analytics ----------------
  const res = await fetch(`/admin/api/campaigns/${campaignId}/analytics`, { cache: 'no-store' });
  if (!res.ok) return;
  const data = await res.json();

  const category = (data?.campaign?.category || data?.special?.category || 'GENERAL').toUpperCase();

  if (reportSubtitle) {
    const map = { COMEDOR: 'Comedor', BANOS: 'Baños', TRANSPORTE: 'Transporte', GENERAL: 'Satisfacción general' };
    reportSubtitle.textContent = `Categoría: ${map[category] || category}. Gráficas optimizadas para interpretación rápida.`;
  }

  // ---------------- KPIs ----------------
  if (kpiRow) {
    const total = data?.totals?.responses ?? 0;
    const followup = data?.totals?.followup_opt_in ?? 0;
    const mainAvg = data?.special?.main_likert?.avg;

    kpiRow.innerHTML = '';
    kpiRow.appendChild(kpi('Respuestas', String(total), 'Total en la campaña'));
    kpiRow.appendChild(kpi('Opt-in seguimiento', String(followup), 'Solicitudes de contacto'));
    kpiRow.appendChild(kpi('Categoría', category, 'Tipo de encuesta'));
    kpiRow.appendChild(
      kpi(
        'Promedio principal',
        avgWithLabel(mainAvg, data?.special?.main_likert?.likert_preset || 'satisfaction'),
        'Sobre escala Likert'
      )
    );
  }

  // ---------------- Activity by day ----------------
  if (ctxByDay) {
    const byDay = data.by_day || [];
    new Chart(ctxByDay, {
      type: 'line',
      data: {
        labels: byDay.map(x => x[0]),
        datasets: [{ label: 'Respuestas por día', data: byDay.map(x => x[1]), tension: 0.25, fill: true }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    });
  }

  // ---------------- By shift ----------------
  if (ctxByShift) {
    const byShift = data.by_shift || [];
    new Chart(ctxByShift, {
      type: 'bar',
      data: {
        labels: byShift.map(x => x[0]),
        datasets: [{ label: 'Respuestas', data: byShift.map(x => x[1]) }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    });
  }

  // ---------------- Main distribution (Likert) ----------------
  const main = data?.special?.main_likert;
  if (main && ctxMain) {
    const scale = Number(main.scale || 5);
    const codes = Array.from({ length: scale }, (_, i) => String(i + 1));
    const labels = likertLabels(main.likert_preset || 'satisfaction', uiLang).slice(0, scale);
    const counts = codes.map(c => Number(main.dist?.[c] || 0));
    const totalN = counts.reduce((a, b) => a + b, 0) || 1;

    const datasets = labels.map((lab, i) => ({
      label: lab,
      data: [Math.round((counts[i] * 1000) / totalN) / 10], // 1 decimal
      _count: counts[i],
    }));

    new Chart(ctxMain, {
      type: 'bar',
      data: {
        labels: [uiLang === 'en' ? 'Distribution' : 'Distribución'],
        datasets,
      },
      options: {
        responsive: true,
        indexAxis: 'y',
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              label: ctx => {
                const ds = ctx.dataset || {};
                const pctv = ctx.raw;
                const c = ds._count ?? 0;
                return `${ds.label}: ${pctv}% (${c})`;
              },
            },
          },
        },
        scales: {
          x: { stacked: true, beginAtZero: true, max: 100, ticks: { callback: v => `${v}%` } },
          y: { stacked: true },
        },
      },
    });
  } else if (ctxMain?.parentElement) {
    ctxMain.parentElement.setAttribute('hidden', 'hidden');
  }

  // ---------------- Reasons (Comedor/Transporte style) ----------------
  const pos = data?.special?.reasons_positive;
  const neg = data?.special?.reasons_negative;

  if (reasonsRow) {
    if ((category === 'COMEDOR' || category === 'TRANSPORTE') && (pos || neg)) {
      reasonsRow.hidden = false;

      if (pos && ctxPos) {
        const labels = pos.top.map(x => x[0]);
        const values = pos.top.map(x => x[1]);
        new Chart(ctxPos, {
          type: 'bar',
          data: { labels, datasets: [{ label: 'Conteo', data: values }] },
          options: {
            indexAxis: 'y',
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
          },
        });
      }

      if (neg && ctxNeg) {
        const labels = neg.top.map(x => x[0]);
        const values = neg.top.map(x => x[1]);
        new Chart(ctxNeg, {
          type: 'bar',
          data: { labels, datasets: [{ label: 'Conteo', data: values }] },
          options: {
            indexAxis: 'y',
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
          },
        });
      }
    } else {
      reasonsRow.hidden = true;
    }
  }

  // ---------------- General: stacked Likert matrix (percentages) ----------------
  if (category === 'GENERAL' && ctxGeneral) {
    const likertQs = (data.questions || []).filter(q => q.type === 'likert');
    if (likertQs.length) {
      if (generalMatrix) generalMatrix.hidden = false;

      const scale = Number(likertQs[0]?.labels?.length || 5);
      const xLabels = likertQs.map(q => (q.text?.es || q.text?.en || q.id).slice(0, 60));

      const presetForMatrix = (likertQs.find(q => q.likert_preset)?.likert_preset) || 'agreement';
      const stackLabels = likertLabels(presetForMatrix, uiLang).slice(0, scale);

      const stacks = Array.from({ length: scale }, (_, i) => ({
        label: stackLabels[i] || String(i + 1),
        data: [],
      }));

      likertQs.forEach(q => {
        const values = (q.values || []).map(Number);
        const p = pct(values);
        for (let i = 0; i < scale; i++) {
          stacks[i].data.push(p[i] ?? 0);
        }
      });

      new Chart(ctxGeneral, {
        type: 'bar',
        data: { labels: xLabels, datasets: stacks },
        options: {
          responsive: true,
          indexAxis: 'y',
          scales: {
            x: { stacked: true, beginAtZero: true, max: 100, ticks: { callback: v => `${v}%` } },
            y: { stacked: true },
          },
          plugins: {
            tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw}%` } },
            legend: { position: 'bottom' },
          },
        },
      });
    } else if (generalMatrix) {
      generalMatrix.hidden = true;
    }
  } else if (generalMatrix) {
    generalMatrix.hidden = true;
  }

  // ---------------- Detail per question (compact) ----------------
  const container = document.getElementById('questionCharts');
  if (container) {
    container.innerHTML = '';

    (data.questions || []).slice(0, 16).forEach(q => {
      const card = document.createElement('div');
      card.className = 'card';

      const title = document.createElement('div');
      title.style.fontWeight = '800';
      title.style.marginBottom = '8px';
      title.textContent = (q.text?.es || q.text?.en || q.id);

      const canvas = document.createElement('canvas');
      canvas.height = 160;

      card.appendChild(title);
      card.appendChild(canvas);
      container.appendChild(card);

      const values = (q.values || []).map(Number);
      let labels = (q.labels || []).map(String);

      if (q.type === 'likert') {
        const preset = q.likert_preset || 'satisfaction';
        const scale = labels.length || 5;
        const looksNumeric = labels.every(x => /^[0-9]+$/.test(x));
        if (looksNumeric) {
          labels = likertLabels(preset, uiLang).slice(0, scale);
        }
      }

      const baseOpts = {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
      };

      new Chart(canvas, {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Conteo', data: values }] },
        options: (q.type === 'likert' || q.type === 'single') ? { ...baseOpts, indexAxis: 'y' } : baseOpts,
      });
    });
  }

  // ---------------- Tables: latest responses / comments / followups ----------------
  const tblResponses = document.getElementById('tblResponses');
  const tblComments = document.getElementById('tblComments');
  const tblFollowups = document.getElementById('tblFollowups');
  const pagerResponses = document.getElementById('pagerResponses');
  const pagerComments = document.getElementById('pagerComments');
  const pagerFollowups = document.getElementById('pagerFollowups');

  function fmtDate(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
      });
    } catch (e) {
      return iso;
    }
  }

  function renderPager(el, meta, onPage) {
    if (!el || !meta) return;
    el.innerHTML = '';

    const info = document.createElement('div');
    info.className = 'muted';
    info.textContent = `Mostrando página ${meta.page} de ${meta.pages} · Total: ${meta.total}`;
    el.appendChild(info);

    const prev = document.createElement('button');
    prev.className = 'btn small';
    prev.textContent = 'Anterior';
    prev.disabled = meta.page <= 1;
    prev.onclick = () => onPage(meta.page - 1);
    el.appendChild(prev);

    const next = document.createElement('button');
    next.className = 'btn small';
    next.textContent = 'Siguiente';
    next.disabled = meta.page >= meta.pages;
    next.onclick = () => onPage(meta.page + 1);
    el.appendChild(next);
  }

  async function loadResponses(page = 1) {
    const res = await fetch(`/admin/api/campaigns/${campaignId}/responses?page=${page}&per_page=10`, { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();

    if (tblResponses) {
      const tbody = tblResponses.querySelector('tbody');
      if (tbody) {
        tbody.innerHTML = '';
        for (const r of data.items || []) {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${escapeHtml(r.submitted_at_mx || fmtDate(r.submitted_at))}</td>
            <td>${escapeHtml(r.area || '-')}</td>
            <td>${escapeHtml(r.shift || '-')}</td>
            <td>${escapeHtml(r.source || '-')}</td>
            <td>${escapeHtml((r.lang || '').toUpperCase())}</td>
            <td><code>${escapeHtml(r.id)}</code></td>
          `;
          tbody.appendChild(tr);
        }
      }
    }
    renderPager(pagerResponses, data, loadResponses);
  }

  async function loadFollowups(page = 1) {
    const res = await fetch(`/admin/api/campaigns/${campaignId}/followups?page=${page}&per_page=10`, { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();

    if (tblFollowups) {
      const tbody = tblFollowups.querySelector('tbody');
      if (tbody) {
        tbody.innerHTML = '';
        for (const r of data.items || []) {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${escapeHtml(r.submitted_at_mx || fmtDate(r.submitted_at))}</td>
            <td>${escapeHtml(r.name || '-')}</td>
            <td>${escapeHtml(r.employee_no || '-')}</td>
            <td>${escapeHtml(r.area || '-')}</td>
            <td>${escapeHtml(r.shift || '-')}</td>
            <td><code>${escapeHtml(r.response_id)}</code></td>
          `;
          tbody.appendChild(tr);
        }
      }
    }
    renderPager(pagerFollowups, data, loadFollowups);
  }

  async function loadComments(page = 1) {
    const res = await fetch(`/admin/api/campaigns/${campaignId}/comments?page=${page}&per_page=10`, { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();

    if (tblComments) {
      const tbody = tblComments.querySelector('tbody');
      if (tbody) {
        tbody.innerHTML = '';
        for (const r of data.items || []) {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${escapeHtml(r.submitted_at_mx || fmtDate(r.submitted_at))}</td>
            <td>${escapeHtml(r.question || '-')}</td>
            <td>${escapeHtml(r.text || '')}</td>
            <td>${escapeHtml(r.area || '-')}</td>
            <td>${escapeHtml(r.shift || '-')}</td>
            <td><code>${escapeHtml(r.response_id)}</code></td>
          `;
          tbody.appendChild(tr);
        }
      }
    }
    renderPager(pagerComments, data, loadComments);
  }

  loadResponses(1);
  loadComments(1);
  loadFollowups(1);
})();