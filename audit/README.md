# Статический аудит источников v6

Скрипт [audit_static.py](audit_static.py) извлекает метаданные кандидатов для CCRQS из трёх закреплённых снимков. [Сводка](dataset_static_audit_v6.json) сохраняет счётчики, статические признаки и пересечения по SHA исправления. В QuixBugs дополнительно выполнена проверка quicksort на его фиксированных входах. Статусы воспроизведения и проверки лицензий привязаны к отдельным записям.

Для повторения из каталога `audit/` установите `openpyxl` и подготовьте следующие рабочие копии. У PyResBugs скрипт читает `PyresBugs.xlsx`.

```sh
python -m pip install openpyxl
git clone https://github.com/soarsmu/BugsInPy.git
git -C BugsInPy checkout --detach 11c5f1eea954a42132cfd06bf257766a7963e0fd
git clone https://github.com/dessertlab/PyResBugs.git
git -C PyResBugs checkout --detach 27d2a38682d861339275e37c17b52826292dd458
git clone https://github.com/jkoppel/QuixBugs.git
git -C QuixBugs checkout --detach 4257f44b0ff1181dedaedee6a447e133219fcebf
python audit_static.py
```

Прогон пересоздаёт сводку и формирует локальный индекс `dataset_candidates_v6.jsonl`.
