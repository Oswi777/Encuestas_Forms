from collections import defaultdict
from datetime import datetime

from ..models import Response, Campaign


LIKERT_PRESETS = {
    'satisfaction': ['Muy malo', 'Malo', 'Regular', 'Bueno', 'Excelente'],
    'agreement': ['Totalmente en desacuerdo', 'En desacuerdo', 'Neutral', 'De acuerdo', 'Totalmente de acuerdo'],
    'frequency': ['Nunca', 'Rara vez', 'A veces', 'Casi siempre', 'Siempre'],
}


def _get_label_text(label):
    """label puede venir como string o como dict {es,en}"""
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

    # dist[qid][raw_value_str] = count
    dist = {qid: defaultdict(int) for qid in qmeta.keys()}

    followup_count = 0
    comments = []
    followups = []

    # Identify text questions
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
        for attr in ('followup_phone', 'phone', 'telefono'):
            v = getattr(r, attr, None)
            if v:
                return v
        for k in ('followup_phone', 'phone', 'telefono'):
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

        # followup extraction
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

        # dist + comments extraction
        for qid, val in answers.items():
            if qid not in dist:
                continue
            if val is None:
                continue

            # normalize
            if isinstance(val, dict) and 'value' in val:
                v = val.get('value')
            else:
                v = val

            dist[qid][str(v)] += 1

            # text questions -> comments
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
                        'lang': getattr(r, 'lang', None),
                    })

        # optional: dedicated comment fields on model
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
                        'lang': getattr(r, 'lang', None),
                    })
                break

    # ---- build output for charts + tables (FULL stats) ----
    question_stats = []
    for qid, d in dist.items():
        q = qmeta.get(qid, {}) or {}
        qtype = (q.get('type') or '').lower()

        q_text = q.get('text') or {}
        q_required = bool(q.get('required', False))

        labels = []
        values = []
        counts_by_label = {}
        total_n = 0

        if qtype == 'likert':
            scale = int(q.get('scale') or 5)
            preset = (q.get('likert_preset') or 'satisfaction').strip().lower()
            preset_labels = LIKERT_PRESETS.get(preset)

            for i in range(1, scale + 1):
                lab = preset_labels[i - 1] if (preset_labels and scale == 5) else str(i)
                cnt = int(d.get(str(i), 0))
                labels.append(lab)
                values.append(cnt)
                counts_by_label[lab] = cnt
                total_n += cnt

        elif qtype == 'single':
            opts = q.get('options') or []
            # preserve option order defined in schema
            for opt in opts:
                raw_val = str(opt.get('value'))
                lab = _get_label_text(opt.get('label')) or raw_val
                cnt = int(d.get(raw_val, 0))
                labels.append(lab)
                values.append(cnt)
                counts_by_label[lab] = cnt
                total_n += cnt

            # if answers contain unexpected options, include them as "Otros"
            known_raw = {str(o.get('value')) for o in opts}
            extra_total = 0
            for raw_val, cnt in d.items():
                if raw_val not in known_raw:
                    extra_total += int(cnt)
            if extra_total:
                labels.append("Otros")
                values.append(extra_total)
                counts_by_label["Otros"] = extra_total
                total_n += extra_total

        else:
            # text/other -> count filled answers (d has each different text as key, we just sum)
            total_n = int(sum(d.values()))
            labels = ['Respuestas con texto']
            values = [total_n]
            counts_by_label = {'Respuestas con texto': total_n}

        # percentages
        perc_by_label = {}
        if total_n > 0:
            for lab, cnt in counts_by_label.items():
                perc_by_label[lab] = round((cnt / total_n) * 100.0, 1)
        else:
            for lab in labels:
                perc_by_label[lab] = 0.0

        question_stats.append({
            'id': qid,
            'type': qtype,
            'required': q_required,
            'likert_preset': q.get('likert_preset') or None,
            'scale': int(q.get('scale') or 0) if qtype == 'likert' else None,
            'text': q_text,
            'labels': labels,          # in display order
            'values': values,          # counts aligned with labels
            'total_n': total_n,
            'counts': counts_by_label, # label -> count
            'percentages': perc_by_label, # label -> %
        })

    # ---- Category-specific helpers ----
    def _find_first_likert():
        for q in questions:
            if q.get('type') == 'likert' and q.get('id'):
                return q
        return None

    def _avg_from_dist(qid: str):
        d = dist.get(qid) or {}
        total_n = sum(d.values())
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
