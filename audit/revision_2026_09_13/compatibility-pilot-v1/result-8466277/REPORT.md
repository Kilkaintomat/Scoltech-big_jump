# Отдельная диагностика native_decide и совместимости

Основные журналы, версии и задания сохранены. Новая генерация не запускалась. Проверены диагностические копии сохранённых доказательств.

## Результаты

{
  "native": {
    "cases": 8,
    "original_status": {
      "accepted": 8
    },
    "candidate_status": {
      "accepted": 8
    },
    "candidate_strict_proofs": 8
  },
  "symbol": {
    "cases": 6,
    "original_status": {
      "rejected": 6
    },
    "candidate_status": {
      "accepted": 2,
      "not_applicable_no_literal_token": 1,
      "rejected": 3
    },
    "candidate_strict_proofs": 2
  },
  "positive_control": {
    "cases": 3,
    "original_status": {
      "accepted": 3
    },
    "candidate_status": {
      "not_requested": 3
    },
    "candidate_strict_proofs": 0
  }
}

Протокол: детерминированный выбор различных задач по хешу; восемь native-кандидатов, до двух примеров для каждого фиксированного соответствия имён, положительные контроли от каждой модели. В кандидатах заменяются только выбранные токены вне комментариев и строк; условие теоремы сохраняется. Бюджет каждого вызова — 20 секунд и 400000 heartbeats.

Точная конфигурация текущего Lean/Mathlib, все ответы компилятора, аксиомы, исходные и изменённые копии — рядом с этим отчётом.

Старые исходники Mathlib v4.9.0: {
  "available": true,
  "url": "https://codeload.github.com/leanprover-community/mathlib4/tar.gz/refs/tags/v4.9.0",
  "sha256": "381b84b89ec9696683f91e4abb1568be30f932b2a5d73c160e12494b6fc35d40",
  "declaration_name_hits": {
    "Real.sqrt_eq_iff_sq_eq": [
      "mathlib4-4.9.0/Mathlib/Data/Real/Sqrt.lean"
    ],
    "le_div_iff": [
      "mathlib4-4.9.0/Mathlib/Algebra/Algebra/Operations.lean",
      "mathlib4-4.9.0/Mathlib/Algebra/Order/Field/Basic.lean",
      "mathlib4-4.9.0/Mathlib/Data/NNReal/Basic.lean",
      "mathlib4-4.9.0/Mathlib/Order/Filter/Pointwise.lean"
    ],
    "ZMod.nat_cast_self": [],
    "Nat.pow_le_pow_of_le_left": [],
    "le_div_iff₀": [
      "mathlib4-4.9.0/Mathlib/Algebra/Order/GroupWithZero/Canonical.lean"
    ],
    "ZMod.natCast_self": [
      "mathlib4-4.9.0/Mathlib/Data/Fin/Basic.lean",
      "mathlib4-4.9.0/Mathlib/Data/ZMod/Basic.lean"
    ],
    "Nat.pow_le_pow_left": [
      "mathlib4-4.9.0/Mathlib/Algebra/Order/Ring/Basic.lean"
    ]
  },
  "limitation": "Static tagged Mathlib source only; namespace/type equivalence and Lean 4.9 executable compatibility are not established."
}

## Следующий этап

Если диагностическая копия компилируется с базовыми аксиомами, это подтверждает возможность доказательства данной теоремы и конкретный путь исправления; исходная генерация при этом не становится автоматически успешной.
Проверка другой версии требует отдельного совместимого Lean + Mathlib + проверяющего окружения. Просто повысить номер Lean недостаточно: текущая версия уже новее опубликованной конфигурации Goedel.
Следующий GPU-пилот следует запускать после основного извлечения активаций: фиксированный набор задач для разработки, сравнение бюджетов 8192 и 16384 при остальных одинаковых настройках, учёт GPU-времени. Не ограничивать выбор задач уже решёнными; их можно включить как положительные контроли.

Ограничения: Selected diagnostic cases, not a random estimate of population rescue rate. Candidate proofs are edited diagnostic copies, not the original generated traces. No other Lean version was installed or executed. Static source lookup alone does not prove cross-version compatibility. A diagnostic timeout is not a mathematical rejection.
