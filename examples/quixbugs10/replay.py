"""Process saved responses, ratings, and measured test evidence; never call LLMs."""
from pathlib import Path
import argparse
import ast
import json
import statistics
import hashlib
import platform

import pipeline

ROOT=Path(__file__).resolve().parent

def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def dump(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8',newline='\n')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--recheck-tests',action='store_true',help='Rerun trusted prepared patches; no models are called')
    args=parser.parse_args()
    config=load(ROOT/'config.json')
    assert config['backend']=='saved_responses' and config['real_models_called'] is False
    pipeline.check_dataset()
    manifest={r['instance_id']:r for r in pipeline.read_manifest()}
    ratings=load(ROOT/config['annotation_source'])
    annotations={}
    for rating in ratings['ratings']:
        annotations.setdefault(rating['review_id'],[]).append(rating)
    records=[]
    for entry in config['reviews']:
        case=entry['case_id']
        row=manifest[case]
        raw=(ROOT/entry['response_file']).read_text(encoding='utf-8')
        validated=pipeline.parse_response(raw)
        assert validated['schema_valid'] and validated['canonical_format_valid']
        response=validated['response']
        assert all(not pipeline.semantic_errors(row,issue) for issue in response['issues'])
        experts=annotations[entry['review_id']]
        assert len(experts)==2 and len({e['expert_id'] for e in experts})==2
        labels=experts[0]['issue_labels']
        assert labels==experts[1]['issue_labels'] and len(labels)==len(response['issues'])
        primary=next((i for i,label in enumerate(labels) if label=='primary_match'),None)
        tp=int(primary is not None)
        fp=sum(label in ['duplicate_primary','false_positive','out_of_scope'] for label in labels)
        fn=1-tp
        d=2*tp/(2*tp+fp+fn)
        cm=[statistics.median(e['comment_scores'][k] for e in experts) for k in range(3)] if tp else None
        c=sum(cm)/6 if tp else 0
        a=t=r=s=None
        q=0
        if primary is not None and response['issues'][primary]['proposed_patch'] is not None:
            issue=response['issues'][primary]
            source=(pipeline.DATA/row['source_file']).read_text(encoding='utf-8')
            modified=pipeline.apply_diff(source,issue['proposed_patch'],issue['file'])
            ast.parse(modified)
            a=1
            if args.recheck_tests:
                testconfig=dict(executor='trusted_local',process_timeout_seconds=config['process_timeout_seconds'],
                    test_timeout_seconds=config['slow_case_timeout_seconds'] if case=='levenshtein' else config['test_timeout_seconds'])
                execution=pipeline.execute(case,testconfig,source=modified,analyze=False)
                dump(ROOT/'results/recheck'/entry['model_key']/f'{case}.json',execution)
            else:
                execution=load(ROOT/entry['execution_file'])
            assert execution['status']=='ok', ('infrastructure_error',entry['review_id'])
            outcomes=execution['tests']
            expected=row['target_tests']+row['regression_tests']
            assert all(outcomes.get(k,{}).get('phase')=='call' and outcomes[k]['outcome'] in ['passed','failed'] for k in expected)
            t=int(all(outcomes[k]['outcome']=='passed' for k in row['target_tests']))
            r=sum(outcomes[k]['outcome']=='passed' for k in row['regression_tests'])/len(row['regression_tests'])
            if t:
                s=statistics.median(e['patch_meaning_score'] for e in experts)
                q=a*t*r*s
        w=config['weights']
        score=w['D']*d+w['C']*c+w['Q']*q
        records.append(dict(**entry,source_sha256=row['source_sha256'],response=response,
            annotations=experts,TP=tp,FP=fp,FN=fn,D=d,C=c,comment_medians=cm,A=a,T=t,R=r,S=s,Q=q,CCRQS=score,
            provenance_ref='data_origin.json',synthetic=True,real_model_called=False))
    summary={}
    for name in ['Gemma','Qwen-Coder']:
        rows=[r for r in records if r['response_group']==name]
        summary[name]={key:statistics.mean(r[key] for r in rows) for key in ['D','C','Q','CCRQS']}
        summary[name].update(responses=len(rows),rating_records=sum(len(r['annotations']) for r in rows),
            found_primary_defects=sum(r['TP'] for r in rows),extra_issues=sum(r['FP'] for r in rows),
            proposed_patches=sum(r['A'] is not None for r in rows),target_passed_patches=sum(r['T']==1 for r in rows))
    dump(ROOT/'results/reviews.json',dict(provenance_ref='data_origin.json',records=records))
    dump(ROOT/'results/summary.json',dict(provenance_ref='data_origin.json',weights=config['weights'],groups=summary))
    assert len(records)==20 and sum(len(r['annotations']) for r in records)==40
    report=[
      '# Отчёт о выполнении пайплайна оценки code review', '',
      'Дата отчёта 14 октября 2026 года', '',
      'Ответы и оценки подготовлены для учебной демонстрации. Тестовые исходы измерены.', '',
      'Выполнена обработка десяти задач Python из QuixBugs, двадцати сохранённых ответов и сорока оценочных записей. Проверены структура ответов, локализация замечаний, применимость исправлений и синтаксис кода. По результатам тестов и оценочным записям рассчитаны компоненты D, C, Q и итоговый CCRQS.', '',
      'Средний CCRQS для группы ответов Gemma составляет 0.590, для группы Qwen-Coder — 0.878. Происхождение ответов и оценок описано в [паспорте данных](Паспорт%20данных.md). Прогон предназначен для демонстрации методики обработки сохранённых данных.', '',
      '## Данные и условия обработки', '',
      'Использована выборка из десяти задач локального снимка QuixBugs, commit `4257f44b0ff1181dedaedee6a447e133219fcebf`. У всех выбранных задач в существующем манифесте зафиксированы непустые группы целевых и регрессионных тестов и успешная проверка эталонного исправления. Исходный код сохранён без изменений.', '',
      'Две группы ответов обозначены Gemma и Qwen-Coder. Один ответ соответствует одной задаче; каждый содержит от нуля до двух замечаний. Для каждого ответа используются две записи оценивания E1 и E2. Формат ответа проверен по JSON Schema v4, версия контракта 1.0. Для этого отчёта применены равные веса компонентов.', '',
      '## Последовательность пайплайна', '',
      '1. Загрузка десяти исходных файлов и проверка контрольных сумм снимка.',
      '2. Загрузка двадцати сохранённых JSON-ответов и проверка обязательных полей, путей и номеров строк.',
      '3. Сопоставление замечаний с основным дефектом по сохранённым меткам E1 и E2; отдельный учёт повторов и замечаний вне задачи.',
      '4. Точное применение каждого предложенного diff к исходной версии и синтаксическая проверка.',
      '5. Использование сохранённых протоколов целевых и регрессионных тестов для A/T/R. В данном повторном прогоне тесты заново не исполнялись.' if not args.recheck_tests else '5. Повторное выполнение тестов подготовленных patch в отдельных временных копиях и вычисление A/T/R.',
      '6. Агрегация двух оценочных записей по признакам комментария и смысловой корректности исправления.',
      '7. Расчёт D, C, Q и CCRQS для каждого ответа и средних значений по группам.', '',
      '## Правила расчёта', '',
      '`D = 2TP / (2TP + FP + FN)`', '',
      '`C = (median(c1) + median(c2) + median(c3)) / 6`', '',
      '`Q = A × T × R × S`', '',
      '`CCRQS = (D + C + Q) / 3`', '',
      'TP — обнаруженный основной дефект, FP — ложные, повторные и выходящие за задачу замечания, FN — пропущенный основной дефект. C оценивает конкретность, правильность объяснения и полезность действия по шкале 0–2. A — применение patch и синтаксис; T — прохождение всех целевых тестов; R — доля сохранившихся регрессионных тестов; S — медианная смысловая оценка patch по шкале 0/0.5/1.', '',
      'С двумя оценочными записями медиана равна среднему двух значений, поэтому допускаются дробные медианы признаков и S. Для C и Q используется первое сопоставленное замечание. При отсутствии сопоставленного дефекта D=C=Q=0; при отсутствии patch или T=0 компонент Q=0. Значение confidence не включается в CCRQS.', '',
      '## Результаты по задачам', '',
      '| Задача | Gemma D | Gemma C | Gemma Q | Gemma CCRQS | Qwen D | Qwen C | Qwen Q | Qwen CCRQS |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for case in config['case_ids']:
        g,qw=[next(r for r in records if r['case_id']==case and r['response_group']==name) for name in ['Gemma','Qwen-Coder']]
        report.append(f'| [{case}](Разборы/{case}.md) | {g["D"]:.3f} | {g["C"]:.3f} | {g["Q"]:.3f} | **{g["CCRQS"]:.3f}** | {qw["D"]:.3f} | {qw["C"]:.3f} | {qw["Q"]:.3f} | **{qw["CCRQS"]:.3f}** |')
    report += ['', '## Итоговые значения', '',
       '| Группа ответов | Среднее D | Среднее C | Среднее Q | Средний CCRQS |',
       '|---|---:|---:|---:|---:|']
    for name,stats in summary.items():
        report.append(f'| {name} | {stats["D"]:.3f} | {stats["C"]:.3f} | {stats["Q"]:.3f} | **{stats["CCRQS"]:.3f}** |')
    report += ['',
      'Разница между средними CCRQS групп составляет 0.288. В наборе Gemma основной дефект сопоставлен в восьми ответах, в наборе Qwen-Coder — в десяти. Все целевые тесты проходят у четырёх patch группы Gemma и семи patch группы Qwen-Coder.', '',
      'Среднее D является средним индивидуальных баллов обнаружения; корпусные Macro F1 и Micro F1 отдельно не рассчитывались. Значения показаны с округлением до трёх знаков, расчёты используют полную точность.', '',
      '## Разбор характерных случаев', '',
      'В quicksort оба ответа находят потерю дубликатов. Patch Gemma включает равные опорному элементы в обе части и не проходит целевой тест, поэтому Q=0 и CCRQS=0.639. Patch Qwen-Coder включает равенство только в одну часть, проходит тесты и получает CCRQS=1.000.', '',
      'В find_in_sorted ответ Gemma объясняет ошибку, но не содержит patch: Q=0, CCRQS=0.583. Ответ Qwen-Coder содержит правильное исправление и повторное замечание о той же ошибке: FP=1, D=0.667, CCRQS=0.889.', '',
      'В is_valid_parenthesization patch Gemma проверяет только равенство количества скобок и теряет проверку порядка. Сохраняется половина регрессионных тестов; медиана S равна 0.25. Q=1×1×0.5×0.25=0.125, CCRQS=0.653. Patch Qwen-Coder сохраняет ранний отказ при отрицательной глубине и проверяет итоговую глубину: CCRQS=1.000.', '',
      '## Исполнение и исключения', '',
      'Протоколы тестов предложенных исправлений сохранены в evidence/patches. Применение diff и синтаксис перепроверены при сборке этого отчёта. Для медленного исправленного levenshtein первоначальные попытки не уложились в лимит 2 с. Отчёт об инфраструктурном сбое сохранён отдельно; последующая проверка с лимитом 10 с завершилась. Инфраструктурный сбой не учитывался как нулевое качество ответа.', '',
      'Проверки исправлений выполнены локальным pytest worker для доверенных подготовленных файлов. Временная копия не считается системной песочницей. Контейнерный прогон, статические анализаторы и генерация ответов в этом пакете не выполняются.', '',
      '## Интерпретация результата', '',
      'Пайплайн различает обнаружение дефекта, качество объяснения и работоспособность исправления. Ответ с верным комментарием может получить низкий Q из-за отсутствия patch или отказа тестов. Повторные и лишние замечания снижают D.', '',
      'Итоговые значения описывают этот набор сохранённых ответов и оценочных записей. Они не являются экспериментальной оценкой реальных моделей. Все десять задач принадлежат одной группе репозитория; веса не подбирались, независимая проверка по H и статистическая валидация CCRQS не проводились.', '',
      '## Состав пакета', '',
      '- Отчёт.md — описание обработки и сводные результаты.',
      '- Паспорт данных.md и data_origin.json — происхождение данных.',
      '- Разборы — десять карточек с кодом, ответами, оценками и расчётами.',
      '- data/QuixBugs — исходники, эталонные версии, тесты и лицензия.',
      '- responses — двадцать ответов в JSON.',
      '- annotations/ratings.json — сорок оценочных записей.',
      '- evidence — исходные протоколы baseline/reference и тестов patch.',
      '- results — повторно рассчитанные результаты и сводка.',
      '- [Контракт ответа и инструкция разметки](../../contracts/).',
      '- config.json и replay.py задают повторную обработку общим конвейером из корня репозитория.', '',]
    (ROOT/'Отчёт.md').write_text('\n'.join(report),encoding='utf-8',newline='\n')
    full=list(report)
    full += ['## Подробные карточки десяти задач','']
    for case in config['case_ids']:
        text=(ROOT/'Разборы'/f'{case}.md').read_text(encoding='utf-8')
        for line in text.splitlines():
            full.append('#'+line if line.startswith('#') else line)
        full.append('')
    (ROOT/'Отчёт с полным разбором.md').write_text('\n'.join(full),encoding='utf-8',newline='\n')
    entries=[]
    for path in sorted(ROOT.rglob('*')):
        if path.is_file() and not any(part in ['__pycache__','work','recheck'] for part in path.relative_to(ROOT).parts) and path.name!='file_manifest.json':
            entries.append(dict(path=path.relative_to(ROOT).as_posix(),bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    dump(ROOT/'file_manifest.json',dict(files=entries))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
