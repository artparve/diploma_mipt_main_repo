# Структура датасета CCRQS

```mermaid
flowchart TB
    source["Источник<br/>sources"]
    code["Задача на Python<br/>code_examples"]
    reference["Эталон и тесты<br/>reference_data"]
    run["Конфигурация запуска<br/>runs"]
    review["Ответ модели и замечания<br/>model_reviews"]
    check["Проверка патча<br/>automatic_checks"]
    expert["Независимые экспертные оценки<br/>expert_evaluations"]
    metrics["Результат расчёта<br/>metric_results"]

    source -->|source_id| code
    code -->|example_id| reference
    code -->|example_id| review
    run -->|run_id| review
    review -->|review_id и issue_index| check
    reference -->|reference_id| check
    review -->|через пакет и сессию| expert
    review -->|review_id| metrics
    check -->|check_ids| metrics
    expert -->|evaluation_ids| metrics
```

Рисунок — Связи основных таблиц датасета CCRQS. Для расчёта CCRQS используются результаты проверки патчей и экспертные оценки по ролям M, C и S. Независимая целостная оценка H сохраняется для проверки согласованности с CCRQS.
