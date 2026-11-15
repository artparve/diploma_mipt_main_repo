# Источники и границы обзора

Проверка выполнена **07.10.2026**. Реестр после уточнения поиска включает **18 первичных источников**, из них 11 исследовательских публикаций. Материалы прочитаны онлайн в объёме, указанном ниже. Полный систематический поиск, независимое воспроизведение чисел и скачивание экспериментальных корпусов в этой работе не выполнялись.

`Препринт` означает формат просмотренной публикации; отсутствие здесь подтверждённого venue не означает, что работу нигде не приняли. Статус принятия указан только там, где он явно присутствует на странице первоисточника.

## Исследовательские публикации

### S01. CodeReviewer

Li et al. **Automating Code Review Activities by Large-Scale Pre-training**. 2022. [arXiv v2](https://arxiv.org/abs/2203.09095v2). На странице указан ESEC/FSE 2022, camera-ready.

- Проверены аннотация, авторы, версии и conference comment.
- Историческая точка отсчёта: три задачи review существовали до нынешних агентных систем.
- Не использовать показатели этой модели как описание актуального качества LLM 2026.

### S02. ContextCRBench

Hu et al. **Benchmarking LLMs for Fine-Grained Code Review with Enriched Context in Practice**. Первая версия 10.11.2025, просмотренная v2 от 30.12.2025. [Статья](https://arxiv.org/abs/2511.07017v2), [репозиторий авторов](https://github.com/kinesiatricssxilm14/ContextCRBench).

- Проверены аннотация, metadata и README ресурсов.
- Поддерживает обсуждение роли semantic/code context и локализации.
- Контекстные записи не приравнивать к независимо исполнимым bug-fix задачам. Доступность ссылки на данные не означает проведённый аудит корпуса.

### S03. AACR-Bench

Zhang et al. **AACR-Bench: Evaluating Automatic Code Review with Holistic Repository-Level Context**. 27.01.2026; v3 от 30.01.2026. [HTML v3](https://arxiv.org/html/2601.19494v3), [metadata](https://arxiv.org/abs/2601.19494v3).

- Проверены аннотация, обсуждение результатов по retrieval/Agent, описание агентной конфигурации.
- Важен как предшественник проверки взаимодействия модели, контекста и scaffold.
- Различие prompt и способов отбора замечаний ограничивает трактовку как чистого эффекта агентной архитектуры.

### S04. CR-Bench — Pereira et al.

Pereira, Sinha, Ghosh, Dutta. **CR-Bench: Evaluating the Real-World Utility of AI Code Review Agents**. 10.03.2026, v1. [HTML](https://arxiv.org/html/2603.11078v1), [metadata](https://arxiv.org/abs/2603.11078v1).

- Проверены определения режимов, оценочный pipeline, таблица 4 и её обсуждение.
- Наиболее близкий предшественник: single-shot против Reflexion; обнаружение отдельно от usefulness/SNR.
- Оценки зависят от CR-Evaluator и правил классификации. Это не универсальное сравнение всех агентов. Использованные модели закрытые; перенос результатов на локальные модели не установлен.

### S05. c-CRAB — Zhang et al.

Zhang, Pan, Yusuf, Ruan, Shariffdeen, Roychoudhury. **Code Review Agent Benchmark**. Первая версия 24.03.2026; v3 от 07.04.2026. [HTML](https://arxiv.org/html/2603.23448v3), [данные и pipeline](https://github.com/c-CRAB-Benchmark/dataset).

- Проверены процедура reviewer→fixer→tests, таблицы 3–6 и раздел ограничений.
- Не путать с S04: близкие названия, разные авторы, протоколы и показатели.
- В тексте есть несогласованность количества репозиториев: таблица 4 — 67, раздел external validity — 56. Без проверки released manifest не выбираем одно число как достоверное.
- Зависимость от fixer и преобладание структурных тестов учитывать при сравнении с собственным Q.

### S06. Survey of Code Review Benchmarks

Khan, Wang, Zhang, Chen. **A Survey of Code Review Benchmarks and Evaluation Practices in Pre-LLM and LLM Era**. 13.02.2026, v1. [Статья](https://arxiv.org/abs/2602.13377v1).

- Проверены аннотация и metadata. Авторы анализируют литературу 2015–2025; это не исчерпывающий обзор публикаций 2026.
- Подходит для расширения related work и разграничения задач.
- Здесь не проверены независимо все первичные исследования из его корпуса. Не выдавать обзор этой папки за обзор 99 прочитанных нами работ.

### S07. SWE-PRBench

Kumar. **SWE-PRBench: Benchmarking AI Code Review Quality Against Pull Request Feedback**. 27.03.2026, v1. [Статья](https://arxiv.org/abs/2603.26130v1).

- Проверены аннотация и metadata.
- Сравнивает три фиксированные конфигурации контекста; полезен как соседняя абляция.
- Заявления о падении качества с ростом контекста относятся к его prompt и оценщику. Здесь экспериментальные таблицы, код и judge-validation не аудировались; не использовать источник как доказательство общего вреда контекста.

### S08. MCR-Bench

Zheng et al. **From Static to Dynamic: Benchmarking Real-World Code Review with MCR-Bench**. 27.08.2026, v1. [HTML](https://arxiv.org/html/2608.27442v1), [metadata](https://arxiv.org/abs/2608.27442v1). На странице указано Accepted at ISSTA 2026.

- Проверены аннотация, введение и bibliographic metadata.
- Показывает отдельную область исследования: состояние defects между последовательными review-раундами.
- Несколько LLM-вызовов на одной версии кода не равны многопроходному review меняющегося PR. Основной эксперимент диплома эту задачу не покрывает.

## Практика и данные об использовании

### S09. Stack Overflow Developer Survey 2026: AI tool usage

Stack Exchange Inc. **AI tool usage**, 2026. [Данные вопроса](https://survey.stackoverflow.co/2026/ai/data/ai-select), [общая AI-таблица](https://survey.stackoverflow.co/2026/ai/data).

- Проверены опубликованные таблица/JSON через индексированный результат официального сайта. Прямой `open` возвращал Internal Error; полный исходный respondent-level dataset не анализировался.
- Вопрос multiselect; знаменатель относится к ответившим на конкретный вопрос.
- Категории не разделяют строго assistant и coding agent. Нельзя выводить долю полной автономии или складывать проценты вариантов. Указанная сайтом лицензия данных: ODbL 1.0.

### S10. Stack Overflow: пресс-релиз 2026

**Stack Overflow’s 2026 Developer Survey Reveals Positive Sentiment Towards AI — but Trust Remains Conditional**. [Пресс-релиз](https://stackoverflow.co/company/press/archive/stack-overflow-annual-developer-survey-ai-trust-conditional/). Публикация результатов подтверждается [анонсом 06.10.2026](https://stackoverflow.blog/2026/10/06/the-results-of-the-2026-developer-survey-are-here/).

- Проверены официальный пресс-релиз и анонс; использованы для подтверждения актуальности S09.
- Это тот же опрос, а не независимый второй массив наблюдений.
- Более ранний April 2026 pulse и annual survey имеют разные вопросы/выборки; их проценты не смешиваются в временной ряд.

### S11. Uber uReview

Mahajan et al. **uReview: Scalable, Trustworthy GenAI for Code Review at Uber**. 12.08.2025. [Engineering blog](https://www.uber.com/us/en/blog/ureview/).

- Проверены архитектура, фильтрация, описание ручной и автоматической оценки, lessons learned.
- Первичный производственный самоотчёт; полезен для постановки практической проблемы доверия к замечаниям.
- Usefulness и addressed comments не равны независимой функциональной корректности patch. Не выводить из него универсальное превосходство AI над human review.

### S12. PR-Agent

**The-PR-Agent/pr-agent**, текущий README. [Репозиторий](https://github.com/The-PR-Agent/pr-agent).

- Проверены single-call описание, варианты deployment, model integration и перенос проекта из Qodo.
- Название Agent не гарантирует tool loop. Открытый PR-Agent отличается от коммерческого продукта Qodo.
- Страница изменяема; для будущего эксперимента нужен конкретный commit, которого этот обзор не фиксирует. Утверждение README о типичном вызове не заменяет инструментирование конкретной команды.

## Кандидаты моделей и разграничение benchmark-задач

### S13. Qwen3-Coder-30B-A3B-Instruct

[Официальная model card](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct).

- Проверены доступность instruct-весов, карточка и Apache 2.0.
- Кандидат для локального сопоставления режимов; пригодность к нашему JSON/tool schema ещё проверить.
- Не зафиксирован revision весов; эксперимент не запущен. Не заявляется, что это strongest/current latest Qwen.

### S14. Devstral-Small-2-24B-Instruct-2512

[Официальная model card](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512).

- Проверены instruction/tool-use назначение, local deployment и Apache 2.0.
- Кандидат другого семейства для контроля зависимости от модели.
- Показатели SWE-bench в карточке не характеризуют качество наших review. Поддержка и скорость на имеющемся оборудовании пока не измерены.

### S15. SWE-bench

[Официальный сайт](https://www.swebench.com/).

- Проверена страница benchmark/leaderboards для разграничения оценки software issue resolution и review.
- Текущие рейтинги не переписываются в обзор: они быстро меняются, зависят от scaffold и не отвечают на основной вопрос работы.

## Дополнение: ближайшие оценочные критерии

Источники S16–S18 добавлены при уточнении вопроса о новизне самого CCRQS. Они дополняют первоначальный поиск benchmark и agent literature.

### S16. CRScore

Naik, Alenius, Fried, Rosé. **CRScore: Grounding Automated Evaluation of Code Review Comments in Code Claims and Smells**. NAACL 2025. [ACL Anthology](https://aclanthology.org/2025.naacl-long.457/), [HTML arXiv v2 от 16.03.2025](https://arxiv.org/html/2409.19801v2).

- Проверены conference metadata, аннотация, формулы метрики и процедура сопоставления с человеческими оценками.
- Ближайший baseline по теме разработки оценочного инструмента; для сравнения с CCRQS нужно учитывать разницу scope и участие человека.
- Числа из его корпуса нельзя напрямую сравнивать с будущими числами CCRQS.

### S17. DeepCRCEval

Lu et al. **DeepCRCEval: Revisiting the Evaluation of Code Review Comment Generation**. Первая версия 24.12.2024, v2 от 25.01.2025. [HTML](https://arxiv.org/html/2412.18291v2). Metadata указывает принятие на FASE 2025.

- Проверены девять критериев, human/LLM оценка и prompt ранжирования.
- Обязательный предшественник критериев оценки C; многомерное экспертное оценивание комментариев уже существует.
- Корпус и исполнимость реализации здесь не аудировались.

### S18. Deep Assessment / GradedReviews

Jiang et al. **Deep Assessment of Code Review Generation Approaches: Beyond Lexical Similarity**. 09.01.2025, v1. [Статья](https://arxiv.org/abs/2501.05176v1).

- Проверены аннотация и metadata: semantic-based оценка review и человеческая разметка GradedReviews.
- Полный метод не проверен; источник пока указывает на необходимое сопоставление, а не завершённый аудит аналога.

## Как проводился поиск

Начальные запросы: `LLM code review benchmark agents 2026 2025 code review repair open source`, `CodeReview benchmark LLM code review agent SWE bench 2025 2026 evaluation`. Затем поиск точных названий `Code Review Agent Benchmark`, `ContextCRBench`, `SWE-CARE`, `CR-Bench`, поиск official engineering blog Uber, official Stack Overflow survey и model cards Qwen/Mistral. Переходы по ссылкам arXiv, HTML-версиям и ресурсам авторов.

Включались источники, которые напрямую отвечают хотя бы на один вопрос: существующие способы оценки review; роль контекста/итераций; проверка полезности через исправления; использование AI в разработке; возможность воспроизводимого локального сравнения.

Не использовались как основание выводов Reddit, пересказы блогеров, рекламные рейтинги без проверенного протокола и страницы-зеркала arXiv. Некоторые найдены при разведке, но не включены в доказательный реестр. Полнотекстовое чтение всех работ и формальный PRISMA-flow не выполнялись.

## Что ещё остаётся проверить

1. Полные схемы оценки CR-Evaluator и похожих оценщиков: сопоставить признаки CCRQS, независимость экспертной валидации и правила агрегации.
2. Корпуса S02–S08: версии, лицензии, доступность runtime, пригодность Python-части и пересечения с источниками v6.
3. Современный набор локальных моделей на дату freeze; аппаратные ограничения и воспроизводимость tool use.
4. Статистическую мощность и экспертные трудозатраты после пилота.
5. Новый поиск перед окончательным заявлением научной новизны: текущие выводы показывают перспективное направление, но не доказывают отсутствие идентичного протокола в литературе.
