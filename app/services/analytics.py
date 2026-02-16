from collections import defaultdict
from datetime import datetime

from ..models import Response, Campaign


LIKERT_PRESETS = {
    'satisfaction': ['Muy malo', 'Malo', 'Regular', 'Bueno', 'Excelente'],
    'agreement': ['Totalmente en desacuerdo', 'En desacuerdo', 'Neutral', 'De acuerdo', 'Totalmente de acuerdo'],
    'frequency': ['Nunca', 'Rara vez', 'A veces', 'Casi siempre', 'Siempre'],
}


def _get_label_text(label):
    """
    label puede venir como string o como dict {es,en}
    """
    if isinstance(label, dict):
        return label.get('es') or label.get('en') or ''
    if isinstance(label, str):
        return label
    return ''


def _safe_str(x):
    return str(x or '').strip()


def compute_campaign_analytics(campaign: Campaign) -> dict:
    responses = Response.query.filter_by(campaign_id=campaign.id).order_by(Response.submitted_at.asc()).all()
    total = len(responses)

    by_day = defaultdict(int)
    by_area = defaultdict(int)
    by_shift = defaultdict(int)

    snapshot = campaign.snapshot_json or {}
    category = (snapshot.get('category') or 'GENERAL').upper()
    schema = (snapshot.get('schema') or {})
    questions = schema.get('questions') or []
    qmeta = {q.get('id'): q for q in questions if q.get('id')}

    dist = {qid: defaultdict(int) for qid in qmeta.keys()}

    followup_count = 0
    comments = []
    followups = []

    # Identify text questions (to treat as comments)
    text_qids = [q.get('id') for q in questions if q.get('type') in ('text', 'textarea', 'comment') and q.get('id')]

    def _area_name(r):
        try:
            return r.area.name if getattr(r, 'area', None) else None
        except Exception:
            return None

    def _shift_value(r):
        try:
            return getattr(r, 'shift', None) or None
        except Exception:
            return None

    def _followup_name(r, answers):
        for attr in ('contact_name', 'followup_name', 'employee_name', 'name'):
            v = getattr(r, attr, None)
            if v:
                return v
        for k in ('contact_name', 'followup_name', 'employee_name', 'name'):
            v = answers.get(k)
            if v:
                return v
        return None

    def _followup_empno(r, answers):
        for attr in ('employee_no', 'followup_employee_no', 'no_empleado', 'emp_no'):
            v = getattr(r, attr, None)
            if v:
                return v
        for k in ('employee_no', 'followup_employee_no', 'no_empleado', 'emp_no'):
            v = answers.get(k)
            if v:
                return v
        return None

    def _followup_phone(r, answers):
        for attr in ('phone', 'followup_phone', 'telefono'):
            v = getattr(r, attr, None)
            if v:
                return v
        for k in ('phone', 'followup_phone', 'telefono'):
            v = answers.get(k)
            if v:
                return v
        return None

    for r in responses:
        day = r.submitted_at.date().isoformat()
        by_day[day] += 1

        an = _area_name(r)
        if an:
            by_area[an] += 1

        sh = _shift_value(r)
        if sh:
            by_shift[sh] += 1

        answers = r.answers_json or {}

        # Followup extraction
        if getattr(r, 'wants_followup', False):
            followup_count += 1
            followups.append({
                'submitted_at': r.submitted_at,
                'response_id': getattr(r, 'id', None),
                'name': _followup_name(r, answers),
                'employee_no': _followup_empno(r, answers),
                'phone': _followup_phone(r, answers),
                'area': an,
                'shift': sh,
            })

        # Distributions + comments from text questions
        for qid, val in answers.items():
            if qid not in dist:
                continue
            if val is None:
                continue

            # normalize
            if isinstance(val, dict) and 'value' in val:
                v = val.get('value')
            elif isinstance(val, dict) and 'text' in val:
                v = val.get('text')
            else:
                v = val

            # count distribution
            dist[qid][str(v)] += 1

            # extract comment if text question
            if qid in text_qids:
                txt = _safe_str(v)
                if txt:
                    q = qmeta.get(qid, {}) or {}
                    qtext = (q.get('text') or {})
                    question_label = qtext.get('es') or qtext.get('en') or qid
                    comments.append({
                        'submitted_at': r.submitted_at,
                        'response_id': getattr(r, 'id', None),
                        'question': question_label,
                        'text': txt,
                        'area': an,
                        'shift': sh,
                    })

        # Optional: if Response has a dedicated comment field, include it too
        for attr in ('comment', 'comments', 'comentario', 'notes', 'note'):
            v = getattr(r, attr, None)
            if v:
                txt = _safe_str(v)
                if txt:
                    comments.append({
                        'submitted_at': r.submitted_at,
                        'response_id': getattr(r, 'id', None),
                        'question': 'Comentario',
                        'text': txt,
                        'area': an,
                        'shift': sh,
                    })
                break

    # build output for charts
    question_stats = []
    for qid, d in dist.items():
        q = qmeta.get(qid, {})
        qtype = (q.get('type') or '').lower()
        labels = []
        values = []

        if qtype == 'likert':
            scale = int(q.get('scale') or 5)
            preset = (q.get('likert_preset') or 'satisfaction').strip().lower()
            preset_labels = LIKERT_PRESETS.get(preset)

            for i in range(1, scale + 1):
                if preset_labels and scale == 5:
                    labels.append(preset_labels[i - 1])
                else:
                    labels.append(str(i))
                values.append(int(d.get(str(i), 0)))

        elif qtype == 'single':
            opts = q.get('options') or []
            for opt in opts:
                v = str(opt.get('value'))
                lab = _get_label_text(opt.get('label'))
                labels.append(lab or v)
                values.append(int(d.get(v, 0)))

            # Si hay valores que no están en options (por cambios), agrégalos al final
            known_values = set(str(opt.get('value')) for opt in opts)
            for k, vv in d.items():
                if str(k) not in known_values and int(vv) > 0:
                    labels.append(str(k))
                    values.append(int(vv))

        else:
            # text: only count filled
            labels = ['filled']
            values = [sum(int(x) for x in d.values())]

        question_stats.append({
            'id': qid,
            'type': qtype,
            'likert_preset': q.get('likert_preset') or None,
            'text': q.get('text') or {},
            'labels': labels,
            'values': values,
        })

    # ---- Category-specific helpers ----
    def _find_first_likert():
        for q in questions:
            if (q.get('type') or '').lower() == 'likert' and q.get('id'):
                return q
        return None

    def _avg_from_dist(qid: str):
        d = dist.get(qid) or {}
        total_n = sum(int(x) for x in d.values())
        if total_n == 0:
            return None
        num = 0
        for k, v in d.items():
            try:
                num += int(k) * int(v)
            except Exception:
                pass
        return round(num / total_n, 2)

    special = {
        'category': category,
        'main_likert': None,
        'reasons_positive': None,
        'reasons_negative': None,
    }

    main = _find_first_likert()
    if main:
        qid = main.get('id')
        scale = int(main.get('scale') or 5)
        special['main_likert'] = {
            'qid': qid,
            'likert_preset': main.get('likert_preset') or 'satisfaction',
            'scale': scale,
            'avg': _avg_from_dist(qid),
            'dist': {str(i): int(dist.get(qid, {}).get(str(i), 0)) for i in range(1, scale + 1)}
        }

        pos_qid = None
        neg_qid = None
        for q in questions:
            if (q.get('type') or '').lower() != 'single' or not q.get('id'):
                continue
            conds = q.get('show_if') or []
            if not isinstance(conds, list):
                conds = [conds]
            for cnd in conds:
                if cnd.get('question') != qid:
                    continue
                op = (cnd.get('op') or 'eq').lower()
                val = cnd.get('value')
                if op == 'eq' and str(val) in ('5', '4'):
                    pos_qid = q.get('id')
                if op == 'in':
                    if isinstance(val, str) and ('1' in val or '2' in val):
                        neg_qid = q.get('id')
                    if isinstance(val, list) and any(str(x) in ('1', '2') for x in val):
                        neg_qid = q.get('id')

        def _top(qid_):
            if not qid_:
                return None
            d = dist.get(qid_) or {}
            items = sorted([(k, int(v)) for k, v in d.items()], key=lambda x: (-x[1], x[0]))
            return {'qid': qid_, 'top': items[:10]}

        special['reasons_positive'] = _top(pos_qid)
        special['reasons_negative'] = _top(neg_qid)

    comments_sorted = sorted(comments, key=lambda x: x.get('submitted_at') or datetime.min, reverse=True)
    followups_sorted = sorted(followups, key=lambda x: x.get('submitted_at') or datetime.min, reverse=True)

    return {
        'campaign': {
            'id': campaign.id,
            'name': campaign.name,
            'token': campaign.token,
            'is_active': campaign.is_active,
            'category': category,
        },
        'totals': {
            'responses': total,
            'followup_opt_in': followup_count,
        },
        'by_day': sorted([[k, v] for k, v in by_day.items()], key=lambda x: x[0]),
        'by_area': sorted([[k, v] for k, v in by_area.items()], key=lambda x: (-x[1], x[0])),
        'by_shift': sorted([[k, v] for k, v in by_shift.items()], key=lambda x: (-x[1], x[0])),
        'questions': question_stats,
        'special': special,
        'comments': comments_sorted,
        'followups': followups_sorted,
        'generated_at': datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    }
