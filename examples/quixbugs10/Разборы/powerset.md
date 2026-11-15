# Все подмножества


## Шаг 1 Исходный код QuixBugs

```python
def powerset(arr):
    if arr:
        first, *rest = arr #python3 just like car and cdr (in this case anyway..)
        rest_subsets = powerset(rest)
        return [[first] + subset for subset in rest_subsets]
    else:
        return [[]]
```

Файл: `python_programs/powerset.py`. Номера строк замечаний относятся к полному исходному файлу; копия сохранена в `data/QuixBugs/python_programs/powerset.py`.

## Шаг 2 Что проверяющий знает об ошибке

Возвращаются только подмножества с первым элементом, остальные пропущены.

Наглядный вход: `powerset([1, 2])`. Ожидается `[[], [2], [1], [1, 2]]`. Это поясняющий пример, а A/T/R ниже рассчитаны по тестам из зафиксированного манифеста.

В манифесте: 4 целевых и 1 регрессионных тестов. Эталон и тесты служат материалами оценивания.

## Шаг 3 Ответ Gemma

```text
Функция не возвращает подмножества без первого элемента. Добавьте их к результату, чтобы получить полный набор подмножеств.
```

Локализация: строка 6 исходного файла.

Предлагаемый patch:

```diff
--- a/python_programs/powerset.py
+++ b/python_programs/powerset.py
@@ -3,7 +3,7 @@
     if arr:
         first, *rest = arr #python3 just like car and cdr (in this case anyway..)
         rest_subsets = powerset(rest)
-        return [[first] + subset for subset in rest_subsets]
+        return [[]] + [[first] + subset for subset in rest_subsets]
     else:
         return [[]]
```

### Шаг 4 Тесты patch Gemma

Целевые: 1/4; регрессионные: 1/1.

A=1; T=0; R=1.000.

### Шаг 5 Оценки E1 и E2 Gemma

| Эксперт | Метки замечаний | Конкретность | Объяснение | Действие | S | Основание |
|---|---|---:|---:|---:|---:|---|
| E1 | primary_match | 2 | 1 | 1 | — | Направление верное, но patch добавляет только пустое множество, а не все rest_subsets. |
| E2 | primary_match | 2 | 2 | 1 | — | Для [1, 2] по-прежнему отсутствует [2]; полный набор не восстановлен. |

Тире означает «не применяется», а не нулевую оценку эксперта.

### Шаг 6 CCRQS для Gemma

TP=1, FP=0, FN=0; D=1.000.

Медианы C: [2.0, 1.5, 1.0]; C=0.750.

S=не применяется; Q=0.000.

**CCRQS = (1.000 + 0.750 + 0.000) / 3 = 0.583.** Расчёт выполнен по неокруглённым значениям.

## Шаг 3 Ответ Qwen-Coder

```text
Результат включает только подмножества с first. Все rest_subsets, не содержащие first, тоже нужны. Верните rest_subsets + [[first] + subset for subset in rest_subsets]; тогда число подмножеств удвоится на каждом шаге.
```

Локализация: строка 6 исходного файла.

Предлагаемый patch:

```diff
--- a/python_programs/powerset.py
+++ b/python_programs/powerset.py
@@ -3,7 +3,7 @@
     if arr:
         first, *rest = arr #python3 just like car and cdr (in this case anyway..)
         rest_subsets = powerset(rest)
-        return [[first] + subset for subset in rest_subsets]
+        return rest_subsets + [[first] + subset for subset in rest_subsets]
     else:
         return [[]]
```

### Шаг 4 Тесты patch Qwen-Coder

Целевые: 4/4; регрессионные: 1/1.

A=1; T=1; R=1.000.

### Шаг 5 Оценки E1 и E2 Qwen-Coder

| Эксперт | Метки замечаний | Конкретность | Объяснение | Действие | S | Основание |
|---|---|---:|---:|---:|---:|---|
| E1 | primary_match | 2 | 2 | 2 | 1 | Выявлена пропущенная половина результата и дано точное действие. |
| E2 | primary_match | 2 | 2 | 2 | 1 | Корректное рекурсивное построение всех подмножеств. |

Тире означает «не применяется», а не нулевую оценку эксперта.

### Шаг 6 CCRQS для Qwen-Coder

TP=1, FP=0, FN=0; D=1.000.

Медианы C: [2.0, 2.0, 2.0]; C=1.000.

S=1.0; Q=1.000.

**CCRQS = (1.000 + 1.000 + 1.000) / 3 = 1.000.** Расчёт выполнен по неокруглённым значениям.
