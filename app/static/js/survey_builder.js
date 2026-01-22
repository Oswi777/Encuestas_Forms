(function(){
  const initial = window.__SURVEY_SCHEMA__ || null;
  const qList = document.getElementById('qList');
  const schemaTa = document.getElementById('schemaJson');
  if(!qList || !schemaTa) return;

  // Internal model (never shown to the user)
  const schema = (initial && typeof initial === 'object') ? deepClone(initial) : {
    languages: ['es','en'],
    settings: {
      collect_area: true,
      collect_shift: true,
      collect_followup_opt_in: true,
    },
    questions: []
  };
  schema.languages = Array.isArray(schema.languages) && schema.languages.length ? schema.languages : ['es','en'];
  schema.settings = schema.settings || {collect_area:true, collect_shift:true, collect_followup_opt_in:true};
  schema.questions = Array.isArray(schema.questions) ? schema.questions : [];

  // Toolbar buttons
  document.querySelectorAll('[data-add]').forEach(btn => {
    btn.addEventListener('click', () => {
      addQuestion(btn.getAttribute('data-add'));
      render();
    });
  });

  // Ensure form submission has schema
  const form = schemaTa.closest('form');
  form.addEventListener('submit', (e) => {
    const problems = validate();
    if(problems.length){
      alert('Revisa lo siguiente:\n\n- ' + problems.join('\n- '));
      e.preventDefault();
      return;
    }
    schemaTa.value = JSON.stringify(schema, null, 2);
  });

  function validate(){
    const issues = [];
    if(schema.questions.length === 0) issues.push('Agrega al menos una pregunta.');
    for(const q of schema.questions){
      const es = (q.text && q.text.es || '').trim();
      if(!es) issues.push('Una pregunta no tiene texto en Español.');
      if(q.type === 'single'){
        const opts = Array.isArray(q.options) ? q.options : [];
        if(opts.length < 2) issues.push(`"${truncate(es, 40)}": requiere al menos 2 opciones.`);
        for(const o of opts){
          if(!(o.value||'').trim()) issues.push(`"${truncate(es, 40)}": una opción no tiene clave.`);
          if(!((o.label && o.label.es)||'').trim()) issues.push(`"${truncate(es, 40)}": una opción no tiene etiqueta ES.`);
        }
      }
    }
    return unique(issues);
  }

  function addQuestion(type){
    const id = newId('q');
    if(type === 'likert'){
      schema.questions.push({
        id,
        type:'likert',
        scale:5,
        required:true,
        text:{es:'Nueva pregunta (Likert)', en:''}
      });
    }else if(type === 'single'){
      schema.questions.push({
        id,
        type:'single',
        required:true,
        text:{es:'Nueva pregunta (Opción única)', en:''},
        options:[
          {value:'op1', label:{es:'Opción 1', en:''}},
          {value:'op2', label:{es:'Opción 2', en:''}},
        ]
      });
    }else if(type === 'text'){
      schema.questions.push({
        id,
        type:'text',
        required:false,
        text:{es:'Comentario (opcional)', en:''}
      });
    }
  }

  function render(){
    qList.innerHTML = '';
    if(schema.questions.length === 0){
      qList.innerHTML = '<div class="muted">Aún no hay preguntas. Usa los botones de abajo para agregar.</div>';
      return;
    }

    schema.questions.forEach((q, idx) => {
      const card = document.createElement('div');
      const isBranch = Array.isArray(q.show_if) && q.show_if.length;
      const isParent = schema.questions.some((x, j) => j > idx && Array.isArray(x.show_if) && x.show_if.some(c => c.question === q.id));
      card.className = 'q-card' + (isParent ? ' is-parent' : '') + (isBranch ? ' is-branch' : '');
      card.dataset.qid = q.id;

      const titleEs = escapeHtml((q.text && q.text.es) ? q.text.es : '');
      const titleEn = escapeHtml((q.text && q.text.en) ? q.text.en : '');
      const branchHint = branchHintHtml(q);

      card.innerHTML = `
        <div class="q-card-top">
          <div class="q-reorder">
            <button class="btn small" type="button" data-move="up" ${idx===0?'disabled':''}>↑</button>
            <button class="btn small" type="button" data-move="down" ${idx===schema.questions.length-1?'disabled':''}>↓</button>
          </div>
          <div class="q-badges">
            ${isParent ? '<span class="badge parent">Padre</span>' : ''}
            ${isBranch ? '<span class="badge branch">Ramificada</span>' : ''}
          </div>
          <div class="q-meta-actions">
            <button class="btn small" type="button" data-act="dup">Duplicar</button>
            <button class="btn small danger" type="button" data-act="del">Eliminar</button>
          </div>
        </div>

        ${branchHint}

        <div class="field">
          <label>Pregunta (ES)</label>
          <input class="input" data-k="q_es" placeholder="Escribe la pregunta" value="${escapeAttr(titleEs)}">
        </div>

        <details class="q-optional">
          <summary>Inglés (opcional)</summary>
          <div class="field" style="margin-top:10px">
            <label>Question (EN)</label>
            <input class="input" data-k="q_en" placeholder="Write the question" value="${escapeAttr(titleEn)}">
          </div>
        </details>

        <div class="q-grid">
          <div class="field">
            <label>Tipo</label>
            <select class="input" data-k="q_type">
              <option value="likert" ${q.type==='likert'?'selected':''}>Likert (1–5)</option>
              <option value="single" ${q.type==='single'?'selected':''}>Opción única</option>
              <option value="text" ${q.type==='text'?'selected':''}>Texto</option>
            </select>
          </div>
          <div class="field">
            <label>Requerida</label>
            <select class="input" data-k="q_req">
              <option value="1" ${q.required?'selected':''}>Sí</option>
              <option value="0" ${!q.required?'selected':''}>No</option>
            </select>
          </div>
        </div>

        <div class="q-likert-hint" style="display:${q.type==='likert'?'block':'none'}">
          <div class="q-grid">
            <div class="field">
              <label>Escala Likert (estilo)</label>
              <select class="input" data-k="likert_preset">
                <option value="satisfaction" ${((q.likert_preset||'satisfaction')==='satisfaction')?'selected':''}>Satisfacción (Muy malo → Excelente)</option>
                <option value="agreement" ${((q.likert_preset||'satisfaction')==='agreement')?'selected':''}>Acuerdo (Totalmente en desacuerdo → Totalmente de acuerdo)</option>
                <option value="frequency" ${((q.likert_preset||'satisfaction')==='frequency')?'selected':''}>Frecuencia (Nunca → Siempre)</option>
              </select>
            </div>
          </div>
          <div class="muted" style="margin-top:6px">Los botones en kiosko se muestran grandes, con colores/estado corporativo (sin emojis).</div>
        </div>

        <div class="q-options" style="display:${q.type==='single'?'block':'none'}">
          <label>Opciones (Opción única)</label>
          <div class="opt-list" data-k="opt_list"></div>
          <button class="btn" type="button" data-act="add_opt">+ Agregar opción</button>
          <div class="hint">Clave recomendada: sin espacios (ej. sabor, rapidez). Se usa para lógica y reportes.</div>
        </div>

        <details class="q-logic">
          <summary>Ramificación (opcional) – Mostrar preguntas distintas según la respuesta</summary>
          <div class="logic-box">
            <div class="muted">Crea reglas como en un formulario: <strong>Si</strong> la respuesta es X <strong>entonces</strong> mostrar estas preguntas. Puedes agregar varias reglas (Excelente/Bueno/Malo), cada una con preguntas diferentes.</div>

            <div class="branch-rules" data-k="branch_rules">
              ${branchRulesHtml(q.id, idx)}
            </div>

            <div style="margin-top:10px">
              <button class="btn" type="button" data-act="add_rule" ${!(q.type==='likert' || q.type==='single')?'disabled':''}>+ Agregar regla</button>
            </div>

            <div class="hint">Reglas: Para Likert usa 1–5. Para opción única usa la <strong>clave</strong> de la opción (ej. sabor). Para múltiples valores puedes escribir “1,2”.</div>
          </div>
        </details>
      `;

      // Bind actions
      card.querySelectorAll('[data-act]').forEach(btn => {
        btn.addEventListener('click', () => {
          const act = btn.getAttribute('data-act');
          if(act === 'add_rule'){
            if(!(q.type==='likert' || q.type==='single')) return;
            q.branch_rules = Array.isArray(q.branch_rules) ? q.branch_rules : deriveBranchRules(q.id, idx);
            q.branch_rules.push({value:'', targets:[]});
            render();
            return;
          }
          if(act === 'del_rule'){
            const ruleEl = btn.closest('.branch-rule');
            const ridx = ruleEl ? Number(ruleEl.dataset.ridx) : NaN;
            q.branch_rules = Array.isArray(q.branch_rules) ? q.branch_rules : deriveBranchRules(q.id, idx);
            if(!Number.isNaN(ridx) && ridx >= 0 && ridx < q.branch_rules.length){
              q.branch_rules.splice(ridx, 1);
              syncBranchRulesToShowIf(q.id, q.branch_rules);
            }
            render();
            return;
          }
          if(act === 'del'){
            if(confirm('¿Eliminar esta pregunta?')){
              removeQuestion(q.id);
              render();
            }
            return;
          }
          if(act === 'dup'){
            const copy = deepClone(q);
            copy.id = newId('q');
            if(copy.options){
              copy.options = copy.options.map((o, i) => ({
                ...o,
                value: (String(o.value||'op') + '_' + (i+1))
              }));
            }
            schema.questions.splice(idx+1, 0, copy);
            render();
            return;
          }
          if(act === 'add_opt'){
            q.options = Array.isArray(q.options) ? q.options : [];
            q.options.push({value:'op' + (q.options.length+1), label:{es:'Opción', en:''}});
            render();
            return;
          }
        });
      });

      // Move up/down
      card.querySelectorAll('[data-move]').forEach(btn => {
        btn.addEventListener('click', () => {
          const dir = btn.getAttribute('data-move');
          if(dir === 'up' && idx > 0){
            const [it] = schema.questions.splice(idx, 1);
            schema.questions.splice(idx-1, 0, it);
            render();
          }
          if(dir === 'down' && idx < schema.questions.length-1){
            const [it] = schema.questions.splice(idx, 1);
            schema.questions.splice(idx+1, 0, it);
            render();
          }
        });
      });

      // Bind main inputs
      card.querySelector('[data-k="q_es"]').addEventListener('input', (e)=>{
        q.text = q.text||{};
        q.text.es = e.target.value;
        // refresh logic options text only (cheap approach: re-render on blur)
      });
      const enInput = card.querySelector('[data-k="q_en"]');
      if(enInput){
        enInput.addEventListener('input', (e)=>{ q.text = q.text||{}; q.text.en = e.target.value; });
      }
      card.querySelector('[data-k="q_req"]').addEventListener('change', (e)=>{ q.required = (e.target.value === '1'); });

      card.querySelector('[data-k="q_type"]').addEventListener('change', (e)=>{
        const newType = e.target.value;
        if(newType === q.type) return;
        q.type = newType;
        if(newType === 'likert'){
          delete q.options;
          q.scale = 5;
        }else if(newType === 'single'){
          delete q.scale;
          q.options = Array.isArray(q.options) && q.options.length ? q.options : [
            {value:'op1', label:{es:'Opción 1', en:''}},
            {value:'op2', label:{es:'Opción 2', en:''}},
          ];
        }else if(newType === 'text'){
          delete q.scale;
          delete q.options;
        }
        render();
      });

      // Likert preset
      const presetSel = card.querySelector('[data-k="likert_preset"]');
      if(presetSel){
        presetSel.addEventListener('change', (e)=>{
          q.likert_preset = e.target.value;
        });
      }

      // Branching rules (multiple)
      const rulesRoot = card.querySelector('[data-k="branch_rules"]');
      if(rulesRoot){
        // Ensure we have a working UI model
        q.branch_rules = Array.isArray(q.branch_rules) ? q.branch_rules : deriveBranchRules(q.id, idx);

        const syncFromDOM = () => {
          const ruleEls = Array.from(rulesRoot.querySelectorAll('.branch-rule'));
          const rules = ruleEls.map(el => {
            const val = (el.querySelector('[data-k="rule_value"]')?.value || '').trim();
            const targets = Array.from(el.querySelectorAll('input[type="checkbox"][data-target]'))
              .filter(x => x.checked)
              .map(x => x.getAttribute('data-target'))
              .filter(Boolean);
            return {value: val, targets};
          });
          q.branch_rules = rules;
          syncBranchRulesToShowIf(q.id, rules);
          try{ schemaTa.value = JSON.stringify(schema, null, 2); }catch(_e){ schemaTa.value = ''; }
        };

        rulesRoot.addEventListener('input', (e) => {
          if(e.target && e.target.matches('[data-k="rule_value"]')){
            syncFromDOM();
          }
        });
        rulesRoot.addEventListener('change', (e) => {
          const t = e.target;
          if(t && t.matches('input[type="checkbox"][data-target]')){
            // A target question should belong to one rule per parent to avoid confusion.
            if(t.checked){
              const targetId = t.getAttribute('data-target');
              rulesRoot.querySelectorAll(`input[type="checkbox"][data-target="${cssEscape(targetId)}"]`).forEach(cb => {
                if(cb !== t) cb.checked = false;
              });
            }
            syncFromDOM();
          }
        });
      }

      // Options editor
      const optRoot = card.querySelector('[data-k="opt_list"]');
      if(optRoot && q.type === 'single'){
        const opts = Array.isArray(q.options) ? q.options : (q.options = []);
        optRoot.innerHTML = '';
        opts.forEach((opt, optIdx) => {
          const row = document.createElement('div');
          row.className = 'opt-row';
          row.innerHTML = `
            <input class="input" placeholder="Clave" value="${escapeAttr(opt.value||'')}">
            <input class="input" placeholder="Etiqueta ES" value="${escapeAttr((opt.label&&opt.label.es)||'')}">
            <input class="input" placeholder="Label EN (opcional)" value="${escapeAttr((opt.label&&opt.label.en)||'')}">
            <button class="btn small danger" type="button">X</button>
          `;
          const [iVal, iEs, iEn] = row.querySelectorAll('input');
          row.querySelector('button').addEventListener('click', ()=>{
            opts.splice(optIdx, 1);
            render();
          });
          iVal.addEventListener('input', ()=>{ opt.value = iVal.value.trim(); });
          iEs.addEventListener('input', ()=>{ opt.label = {...(opt.label||{}), es: iEs.value}; });
          iEn.addEventListener('input', ()=>{ opt.label = {...(opt.label||{}), en: iEn.value}; });
          optRoot.appendChild(row);
        });
      }

      // Logic
      const logicQ = card.querySelector('[data-k="logic_q"]');
      const logicVal = card.querySelector('[data-k="logic_val"]');
      if(logicQ && logicVal){
        const showIf = getShowIf(q);
        if(showIf){
          logicQ.value = showIf.question || '';
          logicVal.value = (showIf.value !== undefined && showIf.value !== null) ? String(showIf.value) : '';
        }
        const sync = () => {
          const src = logicQ.value;
          const val = logicVal.value.trim();
          if(!src || !val){
            delete q.show_if;
            return;
          }
          const srcQ = getQuestion(src);
          let stored = val;
          if(srcQ && srcQ.type === 'likert'){
            const n = Number(val);
            if(!Number.isNaN(n)) stored = n;
          }
          q.show_if = [{question: src, op:'eq', value: stored}];
        };
        logicQ.addEventListener('change', () => { sync(); });
        logicVal.addEventListener('input', () => { sync(); });
      }

      qList.appendChild(card);
    });

    // Keep payload always updated so the Save button works even if JS errors later.
    try{
      schemaTa.value = JSON.stringify(schema, null, 2);
    }catch(_e){
      schemaTa.value = '';
    }
  }

  // -------- Branching helpers (Forms-like / multi-regla) --------
  function deriveBranchRules(sourceQid, sourceIdx){
    // Build rules from later questions that depend on sourceQid.
    const later = schema.questions.slice(sourceIdx+1);
    const groups = new Map();
    for(const q of later){
      if(!Array.isArray(q.show_if)) continue;
      const conds = q.show_if.filter(c => c.question === sourceQid);
      for(const c of conds){
        const op = c.op || 'eq';
        const value = c.value;
        const key = op + ':' + JSON.stringify(value);
        if(!groups.has(key)){
          let raw = '';
          if(op === 'in' && Array.isArray(value)) raw = value.join(',');
          else raw = String(value ?? '');
          groups.set(key, {value: raw, targets: []});
        }
        groups.get(key).targets.push(q.id);
      }
    }
    const rules = Array.from(groups.values());
    return rules.length ? rules : [];
  }

  function branchRulesHtml(sourceQid, sourceIdx){
    const src = schema.questions[sourceIdx];
    const later = schema.questions.slice(sourceIdx+1);
    const rules = Array.isArray(src.branch_rules) ? src.branch_rules : (src.branch_rules = deriveBranchRules(sourceQid, sourceIdx));
    if(!(src.type === 'likert' || src.type === 'single')){
      return '<div class="muted">Disponible sólo para Likert u Opción única.</div>';
    }
    if(later.length === 0){
      return '<div class="muted">Agrega una pregunta debajo para poder seleccionar ramificaciones.</div>';
    }
    const safeRules = rules.length ? rules : [{value:'', targets:[]}];
    return safeRules.map((r, i) => {
      const checked = new Set((r.targets||[]).map(String));
      return `
        <div class="branch-rule" data-ridx="${i}">
          <div class="q-grid" style="margin-top:10px">
            <div class="field">
              <label>SI la respuesta es</label>
              <input class="input" data-k="rule_value" placeholder="Ej. 5 (Excelente)" value="${escapeAttr(String(r.value||''))}">
            </div>
            <div class="field" style="text-align:right">
              <label>&nbsp;</label>
              <button class="btn small danger" type="button" data-act="del_rule" ${safeRules.length<=1?'disabled':''}>Eliminar regla</button>
            </div>
          </div>
          <div class="field" style="margin-top:10px">
            <label>ENTONCES mostrar</label>
            <div class="branch-targets">${later.map(t => {
              const label = (t.text && (t.text.es || t.text.en)) ? (t.text.es || t.text.en) : t.id;
              const isChecked = checked.has(String(t.id));
              return `<label class="chk"><input type="checkbox" data-target="${escapeAttr(t.id)}" ${isChecked?'checked':''}> ${escapeHtml(label)}</label>`;
            }).join('')}</div>
          </div>
        </div>
      `;
    }).join('');
  }

  function syncBranchRulesToShowIf(sourceQid, rules){
    // Remove existing conditions for this source
    for(const t of schema.questions){
      if(!Array.isArray(t.show_if)) continue;
      t.show_if = t.show_if.filter(c => c.question !== sourceQid);
      if(t.show_if.length === 0) delete t.show_if;
    }
    const list = Array.isArray(rules) ? rules : [];
    for(const r of list){
      const val = String(r.value||'').trim();
      const targets = Array.isArray(r.targets) ? r.targets : [];
      if(!val || targets.length === 0) continue;
      let op = 'eq';
      let value = val;
      if(val.includes(',')){
        op = 'in';
        value = val.split(',').map(x => x.trim()).filter(Boolean);
      }
      for(const tid of targets){
        const tq = getQuestion(tid);
        if(!tq) continue;
        tq.show_if = Array.isArray(tq.show_if) ? tq.show_if : [];
        tq.show_if.push({question: sourceQid, op, value});
      }
    }
  }

  function cssEscape(s){
    return String(s||'').replaceAll('\\', '\\\\').replaceAll('"', '\\"');
  }

  function branchHintHtml(q){
    if(!(Array.isArray(q.show_if) && q.show_if.length)) return '';
    const c = q.show_if[0];
    const src = getQuestion(c.question);
    const srcLabel = (src && src.text && (src.text.es || src.text.en)) ? (src.text.es || src.text.en) : (c.question || '');
    let val = '';
    if((c.op||'eq') === 'in' && Array.isArray(c.value)) val = c.value.join(',');
    else val = String(c.value ?? '');
    return `<div class="branch-hint"><strong>Se muestra si:</strong> ${escapeHtml(srcLabel)} = ${escapeHtml(val)}</div>`;
  }

  function logicQuestionOptions(excludeId){
    return schema.questions
      .filter(x => x.id !== excludeId)
      .map(x => {
        const label = (x.text && (x.text.es || x.text.en)) ? (x.text.es || x.text.en) : x.id;
        return `<option value="${escapeHtml(x.id)}">${escapeHtml(label)}</option>`;
      })
      .join('');
  }

  function getShowIf(q){
    return (Array.isArray(q.show_if) && q.show_if.length) ? q.show_if[0] : null;
  }
  function getShowIfValue(q){
    const s = getShowIf(q);
    return s ? String(s.value ?? '') : '';
  }
  function getQuestion(id){
    return schema.questions.find(q => q.id === id) || null;
  }
  function removeQuestion(id){
    schema.questions = schema.questions.filter(q => q.id !== id);
    for(const q of schema.questions){
      if(!q.show_if) continue;
      q.show_if = q.show_if.filter(c => c.question !== id);
      if(q.show_if.length === 0) delete q.show_if;
    }
  }

  function newId(prefix){
    return prefix + '_' + Math.random().toString(16).slice(2,8);
  }
  function deepClone(o){ return JSON.parse(JSON.stringify(o)); }
  function escapeHtml(s){
    return String(s||'')
      .replaceAll('&','&amp;')
      .replaceAll('<','&lt;')
      .replaceAll('>','&gt;')
      .replaceAll('"','&quot;')
      .replaceAll("'",'&#39;');
  }
  function escapeAttr(s){
    return String(s||'').replaceAll('"','&quot;');
  }
  function truncate(s,n){
    s = String(s||'');
    return s.length>n ? s.slice(0,n-1)+'…' : s;
  }
  function unique(arr){
    const out=[]; const set=new Set();
    for(const x of arr){ if(!set.has(x)){ set.add(x); out.push(x); } }
    return out;
  }

  render();
})();
