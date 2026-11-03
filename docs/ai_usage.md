# Документирование использования ИИ-инструмента

## 1. Общие сведения

| Параметр | Значение |
|---|---|
| Инструмент | ИИ-ассистент OpenCode |
| Модель | Big Pickle |
| Дата работы | 03.11.2026 |
| Язык проекта | Python 3.14 |
| Что генерировалось | Валидация даты, обработка ошибок JSON, подтверждение удаления, вспомогательные функции ввода |
| Что делалось вручную | Постановка требований, ревью, интеграция, тесты, README |

ИИ использовался как «ускоритель» для типовых, хорошо формализуемых
фрагментов. Каждый сгенерированный блок был прочитан, проверен на
соответствие PEP 8 и требованиям кейса, после чего покрыт тестами.
Ниже приведены реальные запросы, суть ответов и итоговый код, который
попал в проект.

---

## 2. Запрос №1. Валидация даты и сравнение с текущей датой

### Запрос

> Напиши на Python функцию `parse_due_date(raw_date, today=None)`, которая:
>
> - принимает строку от пользователя;
> - проверяет строгий формат `ДД.ММ.ГГГГ` (ровно 2 цифры дня, 2 цифры
>   месяца и 4 цифры года);
> - использует `datetime.strptime` и перехватывает `ValueError`;
> - не разрешает дату раньше `today`;
> - возвращает `datetime.date`;
> - при ошибке бросает кастомное `ValidationError` с понятным русским
>   сообщением;
> - добавь докстринг и возможность подменить текущую дату в тестах.

### Что ответил ИИ (кратко)

ИИ предложил функцию с `datetime.strptime`, проверкой `parsed < today` и
тремя разными сообщениями об ошибках: пустая дата, неверный формат,
несуществующая дата. Для тестируемости было предложено добавить
необязательный параметр `today`.

### Итоговый код

```python
DATE_FORMAT = "%d.%m.%Y"
DATE_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def parse_due_date(raw_date: str, *, today: date | None = None) -> date:
    """Parse a date in ``ДД.ММ.ГГГГ`` format and reject past dates."""
    text = raw_date.strip()
    if not text:
        raise ValidationError(
            "Срок выполнения не может быть пустым. "
            "Укажите дату в формате ДД.ММ.ГГГГ, например 31.12.2026."
        )
    if not DATE_PATTERN.fullmatch(text):
        raise ValidationError(
            f"Дата «{text}» не соответствует формату ДД.ММ.ГГГГ. "
            "Пример: 31.12.2026."
        )
    try:
        parsed = datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        raise ValidationError(
            f"Дата «{text}» не существует. Проверьте день и месяц."
        ) from None

    current = today or date.today()
    if parsed < current:
        raise ValidationError(
            "Срок выполнения не может быть в прошлом "
            f"(сегодня {current.strftime(DATE_FORMAT)})."
        )
    return parsed
```

### Ревью и доработки

- **Добавлена регулярка.** Одного `strptime` недостаточно: он принимает
  `1.1.2026`, хотя по заданию формат строгий — ровно две цифры дня и
  месяца.
- **Добавлен `today`.** Без него тесты зависели бы от реальной даты.
- **Сегодняшняя дата разрешена.** Проверка именно `parsed < current`, а не
  `<=`.
- **Разные сообщения.** Пользователь понимает, что именно не так: пусто,
  формат или несуществующая дата.

### Тесты

`tests/test_validation.py`:

- корректные даты, включая сегодняшнюю;
- `31.02.2026`, `31.13.2026` — несуществующие;
- `2026-12-31`, `31/12/2026`, `1.1.2026` — неверный формат;
- вчерашняя дата — ошибка;
- пустая строка и пробелы — ошибка.

---

## 3. Запрос №2. Обработка ошибок чтения и записи JSON

### Запрос

> Реализуй класс `JsonTaskRepository` с методами `load()` и `save()` для
> списка задач. Требования:
>
> - если файла нет — вернуть пустой список, это не ошибка;
> - если файл пустой — предупредить и вернуть пустой список;
> - если JSON повреждён — не падать, сохранить резервную копию
>   `<имя>.corrupt-<дата>-<время>` и продолжить с пустым списком;
> - если структура неожиданная — поступить так же;
> - битые отдельные записи пропускать с предупреждением;
> - при `PermissionError` и других `OSError` бросать кастомный
>   `StorageError` с понятным сообщением;
> - запись делать атомарно через временный файл и `os.replace`;
> - не оставлять временный файл при ошибке.

### Что ответил ИИ (кратко)

ИИ предложил структуру документа `{"version": ..., "tasks": [...]}`,
разделил чтение и запись, добавил `_recover_from_corruption`,
`_backup_corrupted_file` и `_extract_records`, а также атомарную запись
через `tasks.json.tmp` + `os.replace`.

### Итоговые фрагменты

Чтение с восстановлением:

```python
if not self._path.exists():
    return LoadResult()

try:
    raw = self._path.read_text(encoding="utf-8")
except PermissionError:
    raise StorageError(
        f"Нет прав на чтение файла «{self._path}». "
        "Проверьте права доступа или укажите другой файл "
        "через --data-file."
    ) from None
except OSError as exc:
    raise StorageError(
        f"Не удалось прочитать файл «{self._path}»: {exc}."
    ) from exc

try:
    document = json.loads(raw)
except json.JSONDecodeError as exc:
    return self._recover_from_corruption(
        f"Файл «{self._path}» повреждён (строка {exc.lineno}, "
        f"колонка {exc.colno}): {exc.msg}."
    )
```

Восстановление после повреждения:

```python
def _recover_from_corruption(self, message: str) -> LoadResult:
    backup = self._backup_corrupted_file()
    warning = f"{message} Список задач будет пустым."
    if backup is not None:
        warning += f" Резервная копия сохранена в «{backup}»."
    else:
        warning += " Создать резервную копию не удалось."

    # Replace the broken file with a valid empty document so that the
    # next launch does not create yet another backup.
    try:
        self.save([])
    except StorageError:
        pass

    return LoadResult(warnings=[warning])
```

Атомарная запись:

```python
def save(self, tasks: Sequence[Task]) -> None:
    payload = self._serialise(tasks)
    temporary = self._path.with_name(f"{self._path.name}.tmp")

    try:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self._path)
    except PermissionError:
        temporary.unlink(missing_ok=True)
        raise StorageError(
            f"Нет прав на запись в файл «{self._path}». "
            "Проверьте права доступа к каталогу."
        ) from None
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise StorageError(
            f"Не удалось сохранить задачи в файл «{self._path}»: {exc}."
        ) from exc
```

### Ревью и доработки

- **Добавлено пересоздание файла после повреждения.** Иначе при каждом
  запуске создавалась бы новая резервная копия одного и того же битого
  файла.
- **Добавлена проверка дублей `id`.** Повторяющийся идентификатор
  пропускается, чтобы не сломать выбор задачи по номеру.
- **Добавлена поддержка «плоского» массива.** Старый или упрощённый
  формат `[ {...}, {...} ]` тоже читается.
- **Ошибки сохранения не меняют состояние в памяти.** `TaskService`
  сначала вызывает `save()`, и только потом обновляет `self._tasks`.
  Это даёт откат: при ошибке записи пользователь не увидит задачу,
  которой нет на диске.

### Тесты

`tests/test_repository.py`:

- отсутствующий файл;
- пустой файл;
- битый JSON + наличие резервной копии;
- неожиданная структура;
- битые записи и дубли `id`;
- `PermissionError` при чтении и записи (через `monkeypatch`);
- `OSError` при `os.replace`;
- отсутствие `.tmp` после успешной записи.

---

## 4. Запрос №3. Подтверждение удаления

### Запрос

> Сделай функцию `ask_confirm(prompt, palette, default=False)` для
> консольного приложения. Она должна:
>
> - принимать `да/д/yes/y/1` и `нет/н/no/n/0` в любом регистре;
> - пустой ввод трактовать как `default`;
> - при неверном ответе печатать сообщение и спрашивать снова;
> - возвращать `bool`;
> - не перехватывать `EOFError`/`KeyboardInterrupt`, чтобы приложение
>   могло корректно завершиться.

### Что ответил ИИ (кратко)

ИИ предложил цикл `while True` с `casefold()`, двумя множествами
допустимых ответов и подсказкой `[да]`/`[нет]` в зависимости от
значения по умолчанию.

### Итоговый код

```python
YES_ANSWERS = {"да", "д", "yes", "y", "1"}
NO_ANSWERS = {"нет", "н", "no", "n", "0"}


def ask_confirm(
    prompt: str,
    palette: Palette,
    *,
    default: bool = False,
) -> bool:
    """Ask a yes/no question; an empty answer returns ``default``."""
    default_label = "да" if default else "нет"
    while True:
        raw = ask(f"{prompt} [{default_label}]: ").casefold()
        if not raw:
            return default
        if raw in YES_ANSWERS:
            return True
        if raw in NO_ANSWERS:
            return False
        print(palette.red("  ✖ Ответьте «да» или «нет»."))
```

### Ревью и доработки

- **По умолчанию — «нет».** Случайное нажатие Enter не удаляет задачу.
- **Подсказка зависит от `default`.** Пользователь сразу видит, что
  произойдёт при пустом вводе.
- **Ошибки не глотаются.** `EOFError` и `KeyboardInterrupt` уходят в
  главный цикл, где приложение завершается без traceback.
- **Ввод обрезается.** `ask()` делает `.strip()`, поэтому `" да "`
  тоже принимается.

### Тесты

`tests/test_cli.py`:

- полный сценарий с подтверждением `да`;
- отмена удаления ответом `нет` — задача остаётся в файле.

---

## 5. Запрос №4. Безопасный ввод номера задачи

### Запрос

> Напиши `ask_index(prompt, count, palette)`, которая просит номер задачи
> от `1` до `count`, принимает `0` или пустую строку как отмену, при
> неверном вводе повторяет вопрос и возвращает `int | None`.

### Итоговый код

```python
def ask_index(prompt: str, count: int, palette: Palette) -> int | None:
    """Ask for a 1-based index in ``1..count``; ``0`` cancels."""
    while True:
        raw = ask(prompt)
        if raw in {"", "0"}:
            return None
        if raw.isdigit() and 1 <= int(raw) <= count:
            return int(raw)
        print(
            palette.red(f"  ✖ Введите число от 1 до {count} или 0 для отмены.")
        )
```

### Ревью и доработки

- **`isdigit()` вместо `int()` в `try`.** Негативные числа и `1.5`
  отклоняются без исключений.
- **Проверка диапазона.** Нельзя выбрать несуществующую задачу.
- **Отмена через `0` и пустую строку.** Это единое поведение для
  выполнения и удаления.

---

## 6. Запрос №5. Исправление `UnicodeDecodeError` при вводе

### Проблема

При вводе кириллицы в некоторых терминалах и IDE-консолях программа
падала:

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd1 in position 4:
invalid continuation byte
```

Причина — `input()` декодирует байты потока кодировкой, которая не
совпадает с реальной кодировкой терминала, либо многобайтовый символ
приходит частями.

### Запрос

> Пользователь вводит кириллицу, и программа падает с
> `UnicodeDecodeError` внутри `input()`. Предложи надёжное решение:
> программа не должна падать, должна пытаться декодировать ввод в
> распространённых русских кодировках, корректно обрабатывать EOF и
> выводить понятную подсказку, если прочитать ввод не удалось.

### Что ответил ИИ (кратко)

ИИ предложил:

1. читать ввод как байты из `sys.stdin.buffer`, чтобы не зависеть от
   текстовой обёртки и не терять многобайтовые символы;
2. декодировать строку с перебором кодировок;
3. переконфигурировать stdout/stderr с `errors="replace"`;
4. завести отдельное исключение `InputError`, которое ловится в главном
   цикле меню.

### Итоговый код

```python
FALLBACK_ENCODINGS = ("utf-8", "cp1251", "koi8-r", "cp866")


def _decode_input(data: bytes) -> str:
    """Decode a raw input line using the terminal encoding and fallbacks."""
    encodings = []
    if sys.stdin.encoding:
        encodings.append(sys.stdin.encoding)
    encodings.extend(FALLBACK_ENCODINGS)

    tried: set[str] = set()
    for encoding in encodings:
        normalized = encoding.lower()
        if normalized in tried:
            continue
        tried.add(normalized)
        try:
            return data.decode(encoding)
        except UnicodeDecodeError, LookupError:
            continue

    # Last resort: never crash because of one bad byte.
    return data.decode("utf-8", errors="replace")


def _read_line(prompt: str) -> str:
    """Print ``prompt`` and read one line without crashing on bad bytes."""
    print(prompt, end="", flush=True)
    stream = getattr(sys.stdin, "buffer", None)

    if stream is None:
        try:
            return input()
        except UnicodeDecodeError as exc:
            raise InputError(ENCODING_HINT) from exc

    try:
        data = stream.readline()
    except (OSError, ValueError) as exc:
        raise InputError(f"Не удалось прочитать ввод: {exc}.") from exc

    if not data:
        raise EOFError

    return _decode_input(data).rstrip("\r\n")
```

Настройка потоков вывода:

```python
def configure_console() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except OSError, ValueError:
            continue
```

### Ревью и доработки

- **Чтение полной строки.** `readline()` возвращает строку целиком, поэтому
  многобайтовый символ не разрезается между вызовами.
- **Порядок кодировок.** Сначала используется кодировка stdin (обычно
  UTF-8), затем UTF-8, CP1251, KOI8-R и CP866.
- **Последний рубеж.** Если ни одна кодировка не подошла, байты заменяются
  на `�`, но программа продолжает работу.
- **EOF и Ctrl+C не глотаются.** `EOFError` и `KeyboardInterrupt`
  пробрасываются в главный цикл, который корректно завершает программу.
- **Понятная подсказка.** При невозможности чтения выводится совет
  настроить `LANG`/`LC_ALL` или включить `PYTHONUTF8=1`.

### Тесты

`tests/test_prompts.py` (9 тестов):

- декодирование UTF-8, CP1251, KOI8-R;
- замена нечитаемых байтов;
- чтение полной строки из бинарного буфера;
- `EOFError` на пустом вводе;
- `InputError` при ошибке потока и при `UnicodeDecodeError` без буфера.

Дополнительно `tests/test_cli.py` проверяет, что `InputError` в меню
показывается пользователю и не приводит к traceback.

---

## 7. Что ИИ не делал

Чтобы документация была честной, перечислим части, написанные и
спроектированные вручную:

- структура пакетов и выбор архитектуры (Repository + слои);
- контракты `TaskRepository`, `LoadResult`, `TaskService`;
- модель `Task`, `Priority`, формат JSON;
- логика отката при ошибке сохранения;
- сортировки и их приоритеты;
- консольное меню и тексты сообщений;
- тесты и настройка `pytest`/`ruff`;
- README и данный документ.

ИИ-код рассматривался как черновик: ни один фрагмент не был принят без
проверки и запуска тестов.

---

## 8. Скриншоты диалога

Для сдачи отчёта рекомендуется приложить скриншоты окна чата с
ИИ-инструментом. Сохраните их в `docs/screenshots/`:

| № | Предлагаемое имя файла | Что должно быть видно |
|---|---|---|
| 1 | `ai-date-validation.png` | Запрос про `parse_due_date` и ответ с кодом |
| 2 | `ai-json-errors.png` | Запрос про `JsonTaskRepository` и обработку ошибок |
| 3 | `ai-delete-confirm.png` | Запрос про `ask_confirm` |
| 4 | `ai-tests.png` | Запрос на генерацию тестов или вывод `pytest` |

Пример вставки в README:

```markdown
![Валидация даты](docs/screenshots/ai-date-validation.png)
```

---

## 9. Вывод

ИИ-инструмент позволил быстро получить черновики функций валидации и
обработки ошибок, но итоговое качество обеспечили:

1. точная постановка требований;
2. ручное ревью каждого фрагмента;
3. интеграция в слоистую архитектуру;
4. 102 автоматических теста;
5. проверка `ruff` и PEP 8.
