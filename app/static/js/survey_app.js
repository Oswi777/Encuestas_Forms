(function(){
  const token = window.__CAMPAIGN__?.token;
  if(!token){return;}

  const root = document.getElementById('surveyRoot');
  const btnBack = document.getElementById('btnBack');
  const progressText = document.getElementById('progressText');
  const langToggle = document.getElementById('langToggle');
  const offlineBanner = document.getElementById('offlineBanner');

  const QUEUE_KEY = 'bw_survey_queue_v1';
  const IDLE_MS = 60000;
  let idleTimer = null;

  let lang = localStorage.getItem('bw_lang') || 'es';
  let shifts = [];
  let campaign = null;
  let schema = null;
  let questions = [];
  let requireArea = false;
  let requireShift = false;
  let currentIndex = 0;
  let answers = {};
  let areaId = '';
  let shift = '';
  let wantsFollowup = false;
  let contactName = '';
  let employeeNo = '';

  function t(obj){
    if(!obj) return '';
    return obj[lang] || obj.es || obj.en || '';
  }

  function resetIdle(){
    if(idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      window.location.href = '/menu';
    }, IDLE_MS);
  }
  ['click','touchstart','keydown'].forEach(evt => document.addEventListener(evt, resetIdle, {passive:true}));

  function setOfflineUI(){
    const online = navigator.onLine;
    offlineBanner.hidden = online;
  }
  window.addEventListener('online', () => { setOfflineUI(); flushQueue(); });
  window.addEventListener('offline', setOfflineUI);

  function loadQueue(){
    try{ return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]'); }catch(e){ return []; }
  }
  function saveQueue(items){
    localStorage.setItem(QUEUE_KEY, JSON.stringify(items));
  }

  async function flushQueue(){
    if(!navigator.onLine) return;
    const items = loadQueue();
    if(items.length === 0) return;
    const remaining = [];
    for(const item of items){
      try{
        const res = await fetch(`/api/submit/${encodeURIComponent(item.token)}`, {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify(item.payload)
        });
        if(!res.ok) throw new Error('submit failed');
      }catch(e){
        remaining.push(item);
      }
    }
    saveQueue(remaining);
  }

  function visibleQuestions(){
    const vis = [];
    for(const q of questions){
      if(isVisible(q)) vis.push(q);
    }
    return vis;
  }

  function isVisible(q){
    const conds = q.show_if;
    if(!conds) return true;
    const list = Array.isArray(conds) ? conds : [conds];
    for(const c of list){
      const qid = c.question;
      const op = c.op || 'eq';
      const v = c.value;
      const a = answers[qid];
      const av = (typeof a === 'object' && a !== null && 'value' in a) ? a.value : a;
      if(op === 'eq'){
        if(String(av) !== String(v)) return false;
      }else if(op === 'neq'){
        if(String(av) === String(v)) return false;
      }else if(op === 'in'){
        // v may be an array (preferred) or a comma-separated string (legacy templates)
        let arr = [];
        if(Array.isArray(v)) arr = v;
        else if(typeof v === 'string') arr = v.split(',').map(s => s.trim()).filter(Boolean);
        if(!arr.map(String).includes(String(av))) return false;
      }
    }
    return true;
  }

  function renderStep(){
    const vis = visibleQuestions();
    const total = vis.length + 1; // + final step
    const isFinal = currentIndex === vis.length;

    btnBack.disabled = currentIndex === 0;

    if(isFinal){
      root.innerHTML = renderFinal();
      bindFinal();
      progressText.textContent = `${currentIndex+1}/${total}`;
      return;
    }

    const q = vis[currentIndex];
    root.innerHTML = renderQuestion(q);
    bindQuestion(q);
    progressText.textContent = `${currentIndex+1}/${total}`;
  }

  function advance(){
    const v = validateCurrent();
    if(!v.ok){ alert(v.msg); return; }
    currentIndex += 1;
    // if some questions became invisible/visible due to branching, clamp index
    const vis2 = visibleQuestions();
    if(currentIndex > vis2.length) currentIndex = vis2.length;
    renderStep();
  }

  function renderMeta(){
    const parts = [];
    if(requireArea){
      parts.push(`
        <div class="field">
          <label>${lang==='es'?'Área':'Area'}</label>
          <select id="areaSelect" class="input">
            <option value="">--</option>
          </select>
        </div>
      `);
    }
    if(requireShift){
      parts.push(`
        <div class="field">
          <label>${lang==='es'?'Turno':'Shift'}</label>
          <select id="shiftSelect" class="input">
            <option value="">--</option>
            ${shifts.map(s => `<option value="${s}">${s}</option>`).join('')}
          </select>
        </div>
      `);
    }
    return `<div class="meta">${parts.join('')}</div>`;
  }

  function renderQuestion(q){
    const title = t(q.text) || q.id;
    let body = '';
    if(q.type === 'likert'){
      const scale = Number(q.scale || 5);
      const current = answers[q.id];
      const preset = q.likert_preset || 'satisfaction';
      const presetLabels = likertLabels(preset, lang);
      const labels = Array.isArray(q.labels) && q.labels.length ? q.labels : presetLabels;
      body = `
        <div class="likert">
          ${Array.from({length: scale}, (_,i)=>i+1).map(n => {
            const active = String(current)===String(n) ? 'active' : '';
            const lbl = labels[n-1] || '';
            return `<button class="btn choice state-${n} ${active}" type="button" data-val="${n}">
              <div>
                <div class="emoji">${likertEmoji(n)}</div>
                <span class="sub">${escapeHtml(lbl)}</span>
              </div>
            </button>`;
          }).join('')}
        </div>
      `;
    }else if(q.type === 'single'){
      const opts = q.options || [];
      const current = answers[q.id];
      body = `
        <div class="choices">
          ${opts.map(opt => {
            const v = opt.value;
            const label = t(opt.label) || String(v);
            const active = String(current)===String(v) ? 'active' : '';
            return `<button class="btn choice ${active}" type="button" data-val="${String(v)}">${escapeHtml(label)}</button>`;
          }).join('')}
        </div>
      `;
    }else if(q.type === 'text'){
      const current = answers[q.id] || '';
      body = `
        <textarea id="textAnswer" class="input" rows="4" placeholder="${lang==='es'?'Escribe aquí...':'Type here...'}">${escapeHtml(current)}</textarea>
        <div style="margin-top:12px">
          <button class="btn primary" id="btnTextContinue" type="button">${lang==='es'?'Continuar':'Continue'}</button>
        </div>
      `;
    }else{
      body = `<div class="muted">Tipo no soportado: ${escapeHtml(q.type||'')}</div>`;
    }

    const req = q.required ? `<span class="req">${lang==='es'?'Requerida':'Required'}</span>` : '';
    return `
      <div class="question">
        <div class="qhead">
          <h2>${escapeHtml(title)}</h2>
          ${req}
        </div>
        ${body}
      </div>
    `;
  }

  function likertEmoji(value){
    // Visual aid for kiosk mode (1..5)
    const v = Number(value);
    if(v <= 1) return '😡';
    if(v === 2) return '😞';
    if(v === 3) return '😐';
    if(v === 4) return '🙂';
    return '😄';
  }

  function likertLabels(preset, lang){
    const es = {
      satisfaction: ['Muy malo','Malo','Regular','Bueno','Excelente'],
      agreement: ['Totalmente en desacuerdo','En desacuerdo','Neutral','De acuerdo','Totalmente de acuerdo'],
      frequency: ['Nunca','Rara vez','A veces','Casi siempre','Siempre'],
    };
    const en = {
      satisfaction: ['Very bad','Bad','Neutral','Good','Excellent'],
      agreement: ['Strongly disagree','Disagree','Neutral','Agree','Strongly agree'],
      frequency: ['Never','Rarely','Sometimes','Often','Always'],
    };
    const map = (lang === 'es') ? es : en;
    return map[preset] || map.satisfaction;
  }

  function renderFinal(){
    return `
      <div class="question">
        <h2>${lang==='es'?'Antes de enviar':'Before submitting'}</h2>
        ${renderMeta()}

        <div class="field">
          <label class="row">
            <input type="checkbox" id="followupCheck">
            <span>${lang==='es'?'Deseo ser contactado para seguimiento':'I want to be contacted for follow-up'}</span>
          </label>
        </div>

        <div id="followupFields" class="grid2" style="display:none">
          <div class="field">
            <label>${lang==='es'?'Nombre':'Name'}</label>
            <input id="contactName" class="input" placeholder="${lang==='es'?'Tu nombre':'Your name'}">
          </div>
          <div class="field">
            <label>${lang==='es'?'No. Empleado':'Employee No.'}</label>
            <input id="employeeNo" class="input" placeholder="${lang==='es'?'Ej. 12345':'e.g. 12345'}">
          </div>
        </div>

        <div class="muted">${lang==='es'?'Tus respuestas se almacenan de forma anónima. Los datos de contacto sólo se guardan si activas seguimiento.':'Your responses are stored anonymously. Contact info is stored only if you opt in.'}</div>

        <div style="margin-top:14px; display:flex; gap:10px; justify-content:flex-end">
          <button class="btn primary" id="btnSubmit" type="button">${lang==='es'?'Enviar':'Submit'}</button>
        </div>
      </div>
    `;
  }

  function bindQuestion(q){
    if(q.type === 'likert' || q.type === 'single'){
      root.querySelectorAll('button.choice').forEach(btn => {
        btn.addEventListener('click', () => {
          const val = btn.getAttribute('data-val');
          if(q.type === 'likert') answers[q.id] = Number(val);
          else answers[q.id] = val;
          advance(); // sin botón "Siguiente"
        });
      });
    }
    if(q.type === 'text'){
      const ta = document.getElementById('textAnswer');
      ta.addEventListener('input', () => {
        answers[q.id] = ta.value;
      });
      const cont = document.getElementById('btnTextContinue');
      if(cont){
        cont.addEventListener('click', () => {
          // asegurar último valor
          answers[q.id] = ta.value;
          advance();
        });
      }
    }
  }

  async function bindFinal(){
    // populate area list if needed
    if(requireArea){
      try{
        const res = await fetch('/api/areas', { cache: 'no-store' });
        if(res.ok){
          const data = await res.json();
          const sel = document.getElementById('areaSelect');
          const items = data.items || [];
          sel.innerHTML = '<option value="">--</option>' + items.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('');
          sel.value = areaId;
          sel.addEventListener('change', () => { areaId = sel.value; });
        }
      }catch(e){}
    }
    if(requireShift){
      const shiftSel = document.getElementById('shiftSelect');
      if(shiftSel){
        shiftSel.value = shift;
        shiftSel.addEventListener('change', () => { shift = shiftSel.value; });
      }
    }

    const check = document.getElementById('followupCheck');
    const fields = document.getElementById('followupFields');
    const nameInput = document.getElementById('contactName');
    const empInput = document.getElementById('employeeNo');

    check.checked = wantsFollowup;
    fields.style.display = wantsFollowup ? 'grid' : 'none';
    nameInput.value = contactName;
    empInput.value = employeeNo;

    check.addEventListener('change', () => {
      wantsFollowup = check.checked;
      fields.style.display = wantsFollowup ? 'grid' : 'none';
    });
    nameInput.addEventListener('input', () => { contactName = nameInput.value; });
    empInput.addEventListener('input', () => { employeeNo = empInput.value; });

    const submitBtn = document.getElementById('btnSubmit');
    if(submitBtn){
      submitBtn.addEventListener('click', async () => {
        resetIdle();
        const vf = validateFinal();
        if(!vf.ok){ alert(vf.msg); return; }
        submitBtn.disabled = true;
        btnBack.disabled = true;
        await submit();
      });
    }
  }

  function validateCurrent(){
    const vis = visibleQuestions();
    if(currentIndex >= vis.length) return {ok:true};
    const q = vis[currentIndex];
    if(!q.required) return {ok:true};
    const v = answers[q.id];
    if(q.type === 'text'){
      if(!v || String(v).trim() === '') return {ok:false, msg: lang==='es'?'Completa la respuesta.':'Please answer.'};
    }else{
      if(v === undefined || v === null || v === '') return {ok:false, msg: lang==='es'?'Selecciona una opción.':'Select an option.'};
    }
    return {ok:true};
  }

  function validateFinal(){
    if(requireArea && !areaId){
      return {ok:false, msg: lang==='es'?'Selecciona un área.':'Select an area.'};
    }
    if(requireShift){
      if(shift && !shifts.includes(shift)){
        return {ok:false, msg: lang==='es'?'Selecciona un turno válido.':'Select a valid shift.'};
      }
      if(!shift){
        return {ok:false, msg: lang==='es'?'Selecciona un turno.':'Select a shift.'};
      }
    }else{
      // Optional shift
      if(shift && !shifts.includes(shift)){
        return {ok:false, msg: lang==='es'?'Selecciona un turno válido.':'Select a valid shift.'};
      }
    }
    if(wantsFollowup){
      if(!contactName.trim() || !employeeNo.trim()){
        return {ok:false, msg: lang==='es'?'Completa nombre y número de empleado.':'Fill name and employee number.'};
      }
    }
    return {ok:true};
  }

  function normalizeAnswersForSubmit(){
    const vis = visibleQuestions();
    const allowed = new Set(vis.map(q=>q.id));
    const out = {};
    for(const [k,v] of Object.entries(answers)){
      if(allowed.has(k)) out[k]=v;
    }
    return out;
  }

  async function submit(){
    const payload = {
      lang,
      area_id: requireArea ? Number(areaId) : null,
      shift,
      wants_followup: wantsFollowup,
      contact_name: wantsFollowup ? contactName : null,
      employee_no: wantsFollowup ? employeeNo : null,
      answers: normalizeAnswersForSubmit(),
      source: 'kiosko'
    };

    try{
      const res = await fetch(`/api/submit/${encodeURIComponent(token)}`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      if(!res.ok) throw new Error('bad');
      // success
      showThankYou();
    }catch(e){
      const items = loadQueue();
      items.push({token, payload, at: Date.now()});
      saveQueue(items);
      setOfflineUI();
      showThankYou(true);
    }
  }

  function showThankYou(queued){
    root.innerHTML = `
      <div class="card center">
        <h2>${lang==='es'?'Gracias por tu respuesta':'Thank you for your response'}</h2>
        <p class="muted">${queued ? (lang==='es'?'Guardada sin conexión. Se enviará automáticamente.':'Saved offline. Will auto-send.') : ''}</p>
        <a class="btn primary" href="/menu">${lang==='es'?'Volver al menú':'Back to menu'}</a>
      </div>
    `;
    btnBack.disabled = true;
  }

  function escapeHtml(s){
    return String(s||'')
      .replaceAll('&','&amp;')
      .replaceAll('<','&lt;')
      .replaceAll('>','&gt;')
      .replaceAll('"','&quot;')
      .replaceAll("'",'&#39;');
  }

  async function init(){
    resetIdle();
    setOfflineUI();
    await flushQueue();

    const res = await fetch(`/api/campaign/${encodeURIComponent(token)}`);
    if(!res.ok){
      root.innerHTML = '<div class="card">No disponible</div>';
      btnBack.disabled = true;
      return;
    }
    const data = await res.json();
    campaign = data;
    shifts = data.shifts || [];
    requireArea = !!data.require_area;
    requireShift = !!data.require_shift;
    schema = data.snapshot?.schema || {};
    questions = schema.questions || [];

    if(langToggle){
      langToggle.addEventListener('click', () => {
        lang = (lang === 'es') ? 'en' : 'es';
        localStorage.setItem('bw_lang', lang);
        renderStep();
      });
    }

    btnBack.addEventListener('click', () => {
      resetIdle();
      if(currentIndex > 0){
        currentIndex -= 1;
        renderStep();
      }
    });

    renderStep();
  }

  init();
})();
