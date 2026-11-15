# Баланс скобок


## Шаг 1 Исходный код QuixBugs

```python
def is_valid_parenthesization(parens):
    depth = 0
    for paren in parens:
        if paren == '(':
            depth += 1
        else:
            depth -= 1
            if depth < 0:
                return False

    return True
```

Файл: `python_programs/is_valid_parenthesization.py`. Номера строк замечаний относятся к полному исходному файлу; копия сохранена в `data/QuixBugs/python_programs/is_valid_parenthesization.py`.

## Шаг 2 Что проверяющий знает об ошибке

Оставшиеся незакрытые скобки не учитываются при финальном возврате True.

Наглядный вход: `is_valid_parenthesization('(')`. Ожидается `False`. Это поясняющий пример, а A/T/R ниже рассчитаны по тестам из зафиксированного манифеста.

В манифесте: 1 целевых и 2 регрессионных тестов. Эталон и тесты служат материалами оценивания.

## Шаг 3 Ответ Gemma

```text
В конце возвращается True даже при незакрытых открывающих скобках. Нужно убедиться, что скобки сбалансированы к окончанию обхода.
```

Локализация: строка 12 исходного файла.

Предлагаемый patch:

```diff
--- a/python_programs/is_valid_parenthesization.py
+++ b/python_programs/is_valid_parenthesization.py
@@ -1,31 +1,2 @@
-
 def is_valid_parenthesization(parens):
-    depth = 0
-    for paren in parens:
-        if paren == '(':
-            depth += 1
-        else:
-            depth -= 1
-            if depth < 0:
-                return False
-
-    return True
-
-
-"""
-Nested Parens
-Input:
-    parens: A string of parentheses
-
-Precondition:
-    all(paren in '()' for paren in parens)
-
-Output:
-    Whether the parentheses are properly nested
-
-Examples:
-    >>> is_valid_parenthesization('((()()))()')
-    True
-    >>> is_valid_parenthesization(')()(')
-    False
-"""
+    return parens.count('(') == parens.count(')')
```

### Шаг 4 Тесты patch Gemma

Целевые: 1/1; регрессионные: 1/2.

A=1; T=1; R=0.500.

### Шаг 5 Оценки E1 и E2 Gemma

| Эксперт | Метки замечаний | Конкретность | Объяснение | Действие | S | Основание |
|---|---|---:|---:|---:|---:|---|
| E1 | primary_match | 2 | 2 | 1 | 0 | Количество открывающих и закрывающих скобок совпадать должно, но этого недостаточно: порядок теряется. |
| E2 | primary_match | 2 | 2 | 1 | 0.5 | Частично решён исходный случай, однако строка )()( ошибочно принимается. Исправление требует доработки. |

Тире означает «не применяется», а не нулевую оценку эксперта.

### Шаг 6 CCRQS для Gemma

TP=1, FP=0, FN=0; D=1.000.

Медианы C: [2.0, 2.0, 1.0]; C=0.833.

S=0.25; Q=0.125.

**CCRQS = (1.000 + 0.833 + 0.125) / 3 = 0.653.** Расчёт выполнен по неокруглённым значениям.

## Шаг 3 Ответ Qwen-Coder

```text
Проверка отрицательной глубины ловит лишние закрывающие скобки, но финальный return True принимает незакрытые открывающие. Возвращайте depth == 0 после цикла; ранний отказ при depth < 0 сохраните.
```

Локализация: строка 12 исходного файла.

Предлагаемый patch:

```diff
--- a/python_programs/is_valid_parenthesization.py
+++ b/python_programs/is_valid_parenthesization.py
@@ -9,7 +9,7 @@
             if depth < 0:
                 return False
 
-    return True
+    return depth == 0
 
 
 """
```

### Шаг 4 Тесты patch Qwen-Coder

Целевые: 1/1; регрессионные: 2/2.

A=1; T=1; R=1.000.

### Шаг 5 Оценки E1 и E2 Qwen-Coder

| Эксперт | Метки замечаний | Конкретность | Объяснение | Действие | S | Основание |
|---|---|---:|---:|---:|---:|---|
| E1 | primary_match | 2 | 2 | 2 | 1 | Учитываются оба условия правильной последовательности. |
| E2 | primary_match | 2 | 2 | 2 | 1 | Минимальный patch сохраняет проверку порядка скобок. |

Тире означает «не применяется», а не нулевую оценку эксперта.

### Шаг 6 CCRQS для Qwen-Coder

TP=1, FP=0, FN=0; D=1.000.

Медианы C: [2.0, 2.0, 2.0]; C=1.000.

S=1.0; Q=1.000.

**CCRQS = (1.000 + 1.000 + 1.000) / 3 = 1.000.** Расчёт выполнен по неокруглённым значениям.
