# Быстрая сортировка


## Шаг 1 Исходный код QuixBugs

```python
def quicksort(arr):
    if not arr:
        return []

    pivot = arr[0]
    lesser = quicksort([x for x in arr[1:] if x < pivot])
    greater = quicksort([x for x in arr[1:] if x > pivot])
    return lesser + [pivot] + greater
```

Файл: `python_programs/quicksort.py`. Номера строк замечаний относятся к полному исходному файлу; копия сохранена в `data/QuixBugs/python_programs/quicksort.py`.

## Шаг 2 Что проверяющий знает об ошибке

Элементы, равные pivot, теряются из обеих рекурсивных частей.

Наглядный вход: `quicksort([2, 2, 1])`. Ожидается `[1, 2, 2]`. Это поясняющий пример, а A/T/R ниже рассчитаны по тестам из зафиксированного манифеста.

В манифесте: 1 целевых и 12 регрессионных тестов. Эталон и тесты служат материалами оценивания.

## Шаг 3 Ответ Gemma

```text
Оба списка исключают элементы, равные pivot, поэтому сортировка теряет дубликаты. Разрешите равенство в одной из частей, чтобы сохранить элементы.
```

Локализация: строка 7 исходного файла.

Предлагаемый patch:

```diff
--- a/python_programs/quicksort.py
+++ b/python_programs/quicksort.py
@@ -3,8 +3,8 @@
         return []
 
     pivot = arr[0]
-    lesser = quicksort([x for x in arr[1:] if x < pivot])
-    greater = quicksort([x for x in arr[1:] if x > pivot])
+    lesser = quicksort([x for x in arr[1:] if x <= pivot])
+    greater = quicksort([x for x in arr[1:] if x >= pivot])
     return lesser + [pivot] + greater
 
 """
```

### Шаг 4 Тесты patch Gemma

Целевые: 0/1; регрессионные: 12/12.

A=1; T=0; R=1.000.

### Шаг 5 Оценки E1 и E2 Gemma

| Эксперт | Метки замечаний | Конкретность | Объяснение | Действие | S | Основание |
|---|---|---:|---:|---:|---:|---|
| E1 | primary_match | 2 | 2 | 1 | — | Причина найдена. Но patch включает равные элементы сразу в обе части и размножает их. |
| E2 | primary_match | 2 | 2 | 2 | — | Комментарий верный, а diff ему противоречит: равенство добавлено в две ветки вместо одной. |

Тире означает «не применяется», а не нулевую оценку эксперта.

### Шаг 6 CCRQS для Gemma

TP=1, FP=0, FN=0; D=1.000.

Медианы C: [2.0, 2.0, 1.5]; C=0.917.

S=не применяется; Q=0.000.

**CCRQS = (1.000 + 0.917 + 0.000) / 3 = 0.639.** Расчёт выполнен по неокруглённым значениям.

## Шаг 3 Ответ Qwen-Coder

```text
Элементы arr[1:], равные pivot, не попадают ни в lesser, ни в greater. Например, [2, 2, 1] теряет одну двойку. Замените условие greater на x >= pivot; pivot по-прежнему добавляется один раз.
```

Локализация: строка 7 исходного файла.

Предлагаемый patch:

```diff
--- a/python_programs/quicksort.py
+++ b/python_programs/quicksort.py
@@ -4,7 +4,7 @@
 
     pivot = arr[0]
     lesser = quicksort([x for x in arr[1:] if x < pivot])
-    greater = quicksort([x for x in arr[1:] if x > pivot])
+    greater = quicksort([x for x in arr[1:] if x >= pivot])
     return lesser + [pivot] + greater
 
 """
```

### Шаг 4 Тесты patch Qwen-Coder

Целевые: 1/1; регрессионные: 12/12.

A=1; T=1; R=1.000.

### Шаг 5 Оценки E1 и E2 Qwen-Coder

| Эксперт | Метки замечаний | Конкретность | Объяснение | Действие | S | Основание |
|---|---|---:|---:|---:|---:|---|
| E1 | primary_match | 2 | 2 | 2 | 1 | Есть конкретный пример и точное минимальное исправление. |
| E2 | primary_match | 2 | 2 | 2 | 1 | Дубликаты сохраняются, а разбиение остаётся взаимоисключающим. |

Тире означает «не применяется», а не нулевую оценку эксперта.

### Шаг 6 CCRQS для Qwen-Coder

TP=1, FP=0, FN=0; D=1.000.

Медианы C: [2.0, 2.0, 2.0]; C=1.000.

S=1.0; Q=1.000.

**CCRQS = (1.000 + 1.000 + 1.000) / 3 = 1.000.** Расчёт выполнен по неокруглённым значениям.
