# Document Extractor — Задание А (LLM Engineer)

Сервис/CLI, который принимает текст документа (счёт, КП, акт) и возвращает структурированный JSON по фиксированной схеме.

## Быстрый старт

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Запустить Ollama и скачать модель (если ещё нет)
ollama pull qwen2.5:7b

# 3. Извлечь данные из документа
python -m src.cli tests/documents/doc01.txt

# 4. Или через stdin
cat tests/documents/doc01.txt | python -m src.cli
```

## Переменные окружения

| Переменная    | По умолчанию              | Описание                        |
|---------------|---------------------------|---------------------------------|
| `OLLAMA_URL`  | `http://localhost:11434`  | URL Ollama-сервера               |
| `OLLAMA_MODEL`| `qwen2.5:7b`              | Имя модели                      |

```bash
# Пример с другой моделью
OLLAMA_MODEL=llama3.2:3b python -m src.cli tests/documents/doc01.txt
```

## Опции CLI

```
python -m src.cli [OPTIONS] [FILE]

  FILE        путь к .txt файлу; если не указан — читать из stdin
  --model     имя модели (или $OLLAMA_MODEL)
  --ollama-url URL Ollama (или $OLLAMA_URL)
  --pretty / --compact  форматировать JSON (по умолчанию --pretty)
```

## Запуск eval

```bash
# Против реального Ollama
python eval.py
# или
make eval

# Без Ollama (mock-режим: LLM возвращает эталонный JSON)
python eval.py --mock
make eval-mock
```

Отчёт печатает:
- точность по каждому полю отдельно
- число **галлюцинаций** (поле заполнено, в эталоне `null`)
- число **пропусков** (`null`, хотя в эталоне есть значение)

## Схема вывода

```json
{
  "doc_type": "invoice | commercial_offer | act | unknown",
  "supplier_name": "string | null",
  "supplier_bin": "12 цифр | null",
  "doc_number": "string | null",
  "doc_date": "YYYY-MM-DD | null",
  "currency": "KZT | USD | EUR | null",
  "total_amount": "number | null",
  "vat_amount": "number | null",
  "line_items": [{"name": "string", "qty": "number|null", "price": "number|null"}],
  "field_confidence": {"supplier_bin": 0.0},
  "warnings": ["string"]
}
```

Валидация — Pydantic v2. Если ответ модели не прошёл валидацию, система делает до 2 повторных запросов с описанием ошибки.

## Жёсткие правила (реализованы)

1. **Нет в документе → `null`**. Не выводим БИН из названия, не подставляем дату, не считаем НДС.
2. **Противоречия → `warnings`**. Правило разрешения: при двух разных суммах «итого» берём первую из пары «К оплате с учётом НДС», если она есть; иначе первую по тексту. Правило зафиксировано в промпте.
3. **Валидация программная** — Pydantic, `supplier_bin` проверяется на 12 цифр.
4. **LLM — Ollama** (локально, бесплатно). Пайплайн полностью рабочий; `--mock` обходит сетевой вызов для CI/демо.

## OCR-нормализация BIN

В документах с OCR-ошибками (`l`→`1`, `O`/`o`/`I`→`0`/`1`) модель инструктируется нормализовать BIN и снижать `field_confidence.supplier_bin`:
- 1.0 — чистый 12-значный номер
- 0.4 — 1–2 заменённых символа
- 0.3 — 3+ замены или неоднозначности

## Тестовый набор

| Doc   | Тип              | Сложность | Особенность                              |
|-------|------------------|-----------|------------------------------------------|
| doc01 | invoice          | простой   | предоставлен в ТЗ                        |
| doc02 | commercial_offer | простой   | предоставлен в ТЗ; нет BIN, нет итога    |
| doc03 | act              | сложный   | предоставлен в ТЗ; OCR + казахский текст |
| doc04 | invoice          | средний   | USD, НДС 12%                             |
| doc05 | act              | средний   | сумма прописью                           |
| doc06 | commercial_offer | средний   | нет BIN, нет даты, нет итога             |
| doc07 | invoice          | сложный   | противоречие в сумме (warnings)          |
| doc08 | invoice          | сложный   | двуязычный (каз/рус) + OCR в BIN         |
| doc09 | invoice          | сложный   | тяжёлые OCR-ошибки по всему документу    |
| doc10 | invoice          | средний   | НДС вычислен от брутто (19 034.48)       |

## Структура проекта

```
.
├── src/
│   ├── schema.py      # Pydantic-модели
│   ├── prompts.py     # системный промпт + user-промпт
│   ├── extractor.py   # вызов Ollama, парсинг, валидация, retry
│   └── cli.py         # Click CLI
├── tests/
│   ├── documents/     # 10 txt-документов
│   └── expected/      # 10 эталонных JSON
├── eval.py            # мини-eval
├── Makefile
├── requirements.txt
├── README.md
└── REFLECTION.md
```
