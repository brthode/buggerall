# Python Style Guide

**Target: Python 3.14+**

PEP 649 makes deferred annotation evaluation the language default in 3.14 — `from __future__ import annotations` is never needed.

---

## Type Annotations

Every function must have annotated parameters and a return type. Annotate variables when the type isn't immediately obvious from the right-hand side. `-> None` is required on functions that don't return a value.

```python
# Good
def greet(name: str) -> str:
    return f"Hello, {name}"

def log(message: str) -> None:
    print(message)

MAX_RETRIES: Final = 3

# Bad
def greet(name):
    return f"Hello, {name}"
```

---

## Built-in Generic Collections (PEP 585)

Never import `Dict`, `List`, `Tuple`, `Set` from `typing`. Use the built-in lowercase forms directly.

```python
# Good
def process(items: list[str]) -> dict[str, int]: ...
coords: tuple[float, float]
seen: set[int]
cache: dict[str, list[tuple[int, str]]]

# Bad
from typing import Dict, List, Tuple
def process(items: List[str]) -> Dict[str, int]: ...
```

---

## Union & Optional (PEP 604)

Never use `Optional` or `Union`. Use `|` syntax.

```python
# Good
def find(key: str) -> str | None: ...
def parse(value: str | int | bytes) -> str: ...

# Bad
from typing import Optional, Union
def find(key: str) -> Optional[str]: ...
def parse(value: Union[str, int, bytes]) -> str: ...
```

---

## Generic Syntax (PEP 695)

Use the new `[T]` type parameter syntax. Never define `TypeVar` manually. Use the `type` statement for aliases — never `TypeAlias` from `typing`.

```python
# Generic function
def first[T](items: list[T]) -> T:
    return items[0]

# Generic class
class Stack[T]:
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()

# Type aliases
type Vector = list[float]
type Matrix = list[Vector]
type Callback[T] = Callable[[T], None]
```

---

## Protocols (Structural Typing)

Prefer `Protocol` over base classes for interface contracts. A class satisfies a `Protocol` simply by having the right methods — no inheritance required. This is the primary mechanism for composition over inheritance.

```python
from typing import Protocol

class Drawable(Protocol):
    def draw(self) -> None: ...

class Serializable(Protocol):
    def to_dict(self) -> dict[str, object]: ...

# Compose protocols by inheriting from multiple Protocol bases
class DrawableRecord(Drawable, Serializable, Protocol): ...

# Circle satisfies Drawable with no subclassing
class Circle:
    def draw(self) -> None:
        ...
```

- Define interfaces as `Protocol` classes, not abstract base classes
- Inherit from `Protocol` only to compose smaller protocols into larger ones
- Avoid deep inheritance trees — prefer small, focused protocols and dataclasses

---

## Dataclasses

Use `@dataclass` as the default class pattern. Prefer `frozen=True` for value objects. Always set `slots=True` unless you need dynamic attribute assignment.

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float

@dataclass(slots=True)
class Config:
    retries: int = 3
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
```

Never write `__init__` manually when a dataclass can replace it.

---

## TypedDict

Use `TypedDict` for structured dictionaries with known keys. Use `NotRequired` for optional keys. In Python 3.14, inline dict literal syntax (PEP 764) is available for one-off call-site types.

```python
from typing import TypedDict, NotRequired

class UserRecord(TypedDict):
    id: int
    name: str
    email: NotRequired[str]

# PEP 764 inline form (Python 3.14) — for one-off local use
def create_user(data: {"id": int, "name": str}) -> None: ...
```

---

## Comprehensions

Always prefer comprehensions and generator expressions over imperative loops that build or transform collections.

```python
# Good
squares = [x**2 for x in range(10)]
index = {name: i for i, name in enumerate(names)}
evens = {x for x in data if x % 2 == 0}
total = sum(x**2 for x in values)  # generator — avoids materialising a list

# Nested comprehension — acceptable when it reads naturally on one line
flat = [item for row in matrix for item in row]

# Nested comprehension — extract to a named helper when it needs multiple lines
def _parse_row(row: list[str]) -> list[int]:
    return [int(cell) for cell in row if cell.strip()]

parsed = [_parse_row(row) for row in raw_rows]

# Bad — imperative loop building a collection
result = []
for x in data:
    if x > 0:
        result.append(x * 2)
```

---

## Pattern Matching

Use `match`/`case` instead of `isinstance` chains and string/enum dispatch `if`/`elif` chains. Always include a `case _:` fallback or pair with `assert_never` for exhaustiveness.

```python
# Replacing isinstance chains
def handle_event(event: MouseEvent | KeyEvent | QuitEvent) -> str:
    match event:
        case MouseEvent(x=x, y=y) if x > 1920:
            return f"off-screen at {x},{y}"
        case MouseEvent(x=x, y=y):
            return f"click at {x},{y}"
        case KeyEvent(key="q" | "Q"):
            return "quit key"
        case KeyEvent(key=k):
            return f"key: {k}"
        case QuitEvent():
            return "quit"

# Matching on dict structure
def process_payload(payload: dict[str, object]) -> None:
    match payload:
        case {"type": "create", "id": int(id_), "data": dict(data)}:
            create(id_, data)
        case {"type": "delete", "id": int(id_)}:
            delete(id_)
        case _:
            raise ValueError(f"unknown payload: {payload}")
```

---

## Modern Typing Utilities

```python
from typing import Self, TypeIs, Never, LiteralString, Final, assert_never

# Final — module-level constants
MAX_RETRIES: Final = 3

# Self — fluent builder / factory APIs
class QueryBuilder:
    def where(self, clause: str) -> Self:
        self._clauses.append(clause)
        return self

# TypeIs — precise narrowing guard (prefer over TypeGuard)
def is_str_list(val: list[object]) -> TypeIs[list[str]]:
    return all(isinstance(x, str) for x in val)

# assert_never — exhaustiveness check in match and if/elif
def area(shape: Circle | Square) -> float:
    match shape:
        case Circle():
            return shape.area()
        case Square():
            return shape.area()
        case _ as unreachable:
            assert_never(unreachable)

# LiteralString — marks security-sensitive parameters (SQL, shell commands)
def query(sql: LiteralString) -> list[dict[str, object]]: ...
```

---

## What to Avoid

| Banned | Use instead |
|---|---|
| `from typing import Dict` | `dict[...]` |
| `from typing import List` | `list[...]` |
| `from typing import Tuple` | `tuple[...]` |
| `from typing import Set` | `set[...]` |
| `from typing import Optional` | `X \| None` |
| `from typing import Union` | `X \| Y` |
| `from typing import TypeAlias` | `type Alias = ...` |
| Manual `TypeVar` | `def f[T](...)` |
| Abstract base classes for interfaces | `Protocol` |
| Imperative loops building collections | Comprehensions |
| Untyped function signatures | Always annotate |
| Bare `Any` | Allowed only with `# type: ignore  # reason:` |
