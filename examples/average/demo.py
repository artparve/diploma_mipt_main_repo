"""Учебная проверка доверенных фикстур; не запуск LLM и не эксперимент."""
from pathlib import Path
import ast
import copy
import difflib
import hashlib
import json
import platform
import re
from statistics import median
from time import perf_counter

ROOT = Path(__file__).resolve().parent
SOURCE = ('def average(values):\n'
          '    """Среднее списка чисел; для пустого списка вернуть None."""\n'
          '    return sum(values) / len(values)\n')
GOOD = SOURCE.replace('    return', '    if not values:\n        return None\n    return')
BAD = SOURCE.replace('    return', '    if not sum(values):\n        return None\n    return')
TESTS = [('empty', [], None, 'target'), ('positive', [2, 4], 3.0, 'regression'),
         ('zero', [0], 0.0, 'regression'), ('balanced', [-2, 2], 0.0, 'regression')]

def diff(updated):
    return ''.join(difflib.unified_diff(SOURCE.splitlines(True), updated.splitlines(True),
                                     fromfile='a/average.py', tofile='b/average.py'))

def exact_apply(patch):
    """Только доверенный однофайловый diff этого примера; точное совпадение."""
    lines = patch.splitlines(True)
    assert lines[:2] == ['--- a/average.py\n', '+++ b/average.py\n']
    match = re.fullmatch(r'@@ -1,(\d+) \+1,(\d+) @@\n', lines[2])
    assert match
    old = ''.join(line[1:] for line in lines[3:] if line.startswith((' ', '-')))
    new = ''.join(line[1:] for line in lines[3:] if line.startswith((' ', '+')))
    assert old == SOURCE
    assert len(old.splitlines()) == int(match[1])
    assert len(new.splitlines()) == int(match[2])
    ast.parse(new)
    return new

def run_tests(source):
    scope = {}
    exec(compile(source, 'average.py', 'exec'), scope)
    outcomes = []
    for name, values, expected, group in TESTS:
        try:
            actual = scope['average'](values)
            passed = actual == expected
            error = None
        except Exception as exc:
            actual, passed, error = None, False, type(exc).__name__
        outcomes.append(dict(test=name, group=group, expected=expected,
                             actual=actual, passed=passed, error=error))
    return outcomes

def issue(comment, patch):
    return dict(file='average.py', line_start=3, line_end=3, category='runtime',
                severity='medium', comment=comment, proposed_patch=patch, confidence=0.9)

FULL = ('В строке 3 при values=[] длина списка равна нулю, поэтому возникает '
        'ZeroDivisionError вместо предусмотренного None. До деления добавьте '
        'проверку if not values и возврат None; для непустого списка сохраните вычисление среднего.')
BRIEF = ('В строке 3 при values=[] len(values)=0, поэтому возникает '
         'ZeroDivisionError. Добавьте отдельную ветку для пустого списка.')
A = dict(schema_version='1.0', issues=[issue(FULL, diff(GOOD))])
B = dict(schema_version='1.0', issues=[issue(BRIEF, diff(BAD)),
    dict(file='average.py', line_start=3, line_end=3, category='functional',
         severity='medium', comment='Оператор / в Python 3 выполняет целочисленное деление; '
         'замените его, чтобы не терять дробную часть.', proposed_patch=None, confidence=0.95)])
C = dict(schema_version='1.0', issues=[issue(FULL, None)])
D = dict(schema_version='1.0', issues=[])

ANNOTATIONS = {
    'A': dict(matches=['primary_match'], c=[[2,2,2],[2,2,2],[2,2,1]], s=[1,1,1], h=[4,4,3]),
    'B': dict(matches=['primary_match','false_positive'], c=[[2,2,1],[2,2,1],[2,1,1]], s=[0,0,0.5], h=[1,1,2]),
    'C': dict(matches=['primary_match'], c=[[2,2,2],[2,2,2],[2,2,1]], s=None, h=[2,2,3]),
    'D': dict(matches=[], c=None, s=None, h=[0,0,0]),
}

def main():
    from jsonschema import Draft202012Validator
    start = perf_counter()
    schema = json.loads((ROOT.parents[1] / 'contracts/review_response_v4.schema.json').read_text(encoding='utf-8-sig'))
    validator = Draft202012Validator(schema)
    baseline = run_tests(SOURCE)
    reference = run_tests(GOOD)
    assert baseline[0]['error'] == 'ZeroDivisionError'
    assert all(test['passed'] for test in baseline[1:] + reference)
    (ROOT / 'average.py').write_text(SOURCE, encoding='utf-8')
    payload = dict(synthetic=True, real_llm_called=False, expert_scores_are_simulated=True,
        execution_scope='trusted educational fixture only; not production pipeline or container test',
        python_version=platform.python_version(), source_sha256=hashlib.sha256(SOURCE.encode()).hexdigest(),
        instance_id='demo_average_001', baseline=baseline, reference=reference, reviews={})
    for name, response in [('A',A),('B',B),('C',C),('D',D)]:
        validator.validate(response)
        assert all(x['file'] == 'average.py' and 1 <= x['line_start'] <= x['line_end'] <= 3
                   for x in response['issues'])
        annotation = ANNOTATIONS[name]
        paths = ROOT / 'responses'
        paths.mkdir(exist_ok=True)
        (paths / f'{name}.json').write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding='utf-8')
        primary = next((idx for idx, label in enumerate(annotation['matches']) if label == 'primary_match'), None)
        tp = int(primary is not None)
        fp = annotation['matches'].count('false_positive')
        fn = 1-tp
        detection = 2*tp/(2*tp+fp+fn)
        comments = sum(median(row[k] for row in annotation['c']) for k in range(3))/6 if tp else 0
        patch_results = []
        for idx, entry in enumerate(response['issues']):
            if entry['proposed_patch'] is None:
                patch_results.append(dict(issue_index=idx, A=None, T=None, R=None, S=None,
                                          Q=0, status='patch_absent'))
                continue
            updated = exact_apply(entry['proposed_patch'])
            outcomes = run_tests(updated)
            target = int(all(t['passed'] for t in outcomes if t['group']=='target'))
            regressions = [t for t in outcomes if t['group']=='regression']
            retained = sum(t['passed'] for t in regressions)/len(regressions)
            meaning = median(annotation['s'])
            patch_results.append(dict(issue_index=idx, A=1, T=target, R=retained,
                S=meaning, Q=target*retained*meaning, Q_before_expert_annotation=None,
                tests=outcomes, status='evaluated_with_simulated_expert_scores'))
        quality = patch_results[primary]['Q'] if tp else 0
        total = (detection+comments+quality)/3
        payload['reviews'][name] = dict(schema_valid=True, semantic_valid=True,
            annotations_simulated=copy.deepcopy(annotation), TP=tp, FP=fp, FN=fn,
            D=detection, C=comments, Q=quality, CCRQS=total,
            H=median(annotation['h']), patches=patch_results)
    assert abs(payload['reviews']['A']['CCRQS']-1) < 1e-12
    assert abs(payload['reviews']['B']['CCRQS']-0.5) < 1e-12
    assert abs(payload['reviews']['C']['CCRQS']-2/3) < 1e-12
    assert payload['reviews']['D']['CCRQS'] == 0
    payload['elapsed_seconds'] = perf_counter()-start
    (ROOT / 'Проверка примера.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(python_version=payload['python_version'], baseline=baseline,
        results={k: {x: v[x] for x in ['D','C','Q','CCRQS','H']} for k,v in payload['reviews'].items()},
        synthetic=True), ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
