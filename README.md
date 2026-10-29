# Rdzeń

Mały język programowania z kontraktami weryfikowanymi statycznie (Z3), projektowany pod
generowanie kodu przez modele językowe: pełna specyfikacja mieści się w kontekście modelu,
a kompilator zwraca strukturalną diagnostykę z kontrprzykładami.

- `spec/` — formalna definicja języka (Typst + PDF, wersja 0.3)
- `rzc`, `rdzen/` — prototyp kompilatora
- `REFERENCE.md` — zwięzła referencja dla piszącego kod
- `SKILL.md` — skill dla Claude: specyfikacja → weryfikacja → generowanie Pythona

## rzc — prototyp kompilatora

Weryfikuje programy w podzbiorze Rdzenia zgodnie z definicją formalną (wersja 0.1):
typowanie (rozdz. 5) → zobowiązania dowodowe (rozdz. 6) → Z3 → przykłady i testy
właściwości → diagnostyka w formacie z rozdz. 9 (tekst lub JSON).

Wymagania: Python ≥ 3.10, `pip install z3-solver`.

```
./rzc check plik.rz            # weryfikacja, przykłady, diagnostyka
./rzc check plik.rz --json     # diagnostyka strukturalna
./rzc emit plik.rz -o m.py     # moduł Pythona; sprawdzenia tylko dla zobowiązań bez dowodu
./rzc run plik.rz f ARG...     # wykonanie funkcji w interpreterze (ze sprawdzeniami)
python3 tests/run_tests.py     # testy regresyjne (tests/cases)
python3 tests/diff_test.py     # testy różnicowe: wygenerowany Python vs interpreter
                               #   (RLIMIT=1 wymusza wszystkie sprawdzenia dynamiczne)
python3 tests/mutate.py P.rz…  # testy mutacyjne
```

`REFERENCE.md` — zwięzła referencja języka dla piszącego kod; `SKILL.md` — skill z przepływem
pracy (specyfikacja → weryfikacja → emisja). `eval/` — programy napisane wyłącznie na podstawie
referencji.

## Zakres prototypu

Obsługiwane: `Int`, `Bool`, `Unit`, `Array<T>`, typy danych (także generyczne
i rekurencyjne), aliasy z uściśleniami (`type Nat = Int where self >= 0`), stałe, `spec fn`
(także rekurencyjne i wzajemnie rekurencyjne, z uściślonym wynikiem), `lemma fn`, miary
strukturalne (`decreases t` dla typów danych), niezmienniki typów danych (`data … where φ`),
operator `?` dla `Option` i `Result`,
funkcje z `requires`/`ensures`/`decreases`/`examples`, parametry `inout` z prawem wyłączności,
`let`/`var`, przypisania, `while` z niezmiennikami i wariantem, `for`, `if`, `match`
ze strażnikami, `break`/`continue`/`return`, `assert`, dziury `?h`, kwantyfikatory ograniczone,
`old(…)`, wbudowane `push`, `pop`, `compare`, `min`, `max`, `contains`, `filled`, `checked_*`.

Zobowiązania: `pre`, `post`, `inv-init`, `inv-pres`, `var-nn`, `var-dec`, `term`, `refine`,
`assert`, `wd`, `data-inv`, `bounds`, `overflow`, `div0`. Kontrprzykłady są odtwarzane w interpreterze
i klasyfikowane jako rzeczywiste lub indukcyjne (§6.6). Zobowiązania nierozstrzygnięte przez
solver są dodatkowo obalane testowaniem losowym.

Rekurencyjne `spec fn` są kodowane jako funkcje rekurencyjne Z3 (`RecFunction`); miara
strukturalna to ranga wartości (1 + suma rang pól tego samego typu). Uściślenie wyniku
rekurencyjnej `spec fn` jest dowodzone indukcyjnie (hipoteza dla wywołań o mniejszej mierze)
i dodawane jako aksjomat dla pozostałych zobowiązań.

Nieobsługiwane (błąd `E0003`/`E2002`): napisy, `Byte`, `F64`, typy funkcyjne i domknięcia,
kapabilności i efekty poza totalnością, aktorzy, `extern`, `import`, sprawdzanie formy kanonicznej (`E0100`), generowanie kodu C (zamiast niego: Python).

## Różnice względem specyfikacji

- Warunki weryfikacji są liczone wykonaniem symbolicznym ze scalaniem ścieżek, a nie
  podstawianiem w `wp`; dla pętli z niezmiennikami i wywołań z kontraktami daje to te same
  zobowiązania.
- Zobowiązanie `inv-init` nie jest zakładane po sprawdzeniu, żeby błąd przy wejściu do pętli
  nie maskował błędu zachowania niezmiennika.
- Wyrażenie `==` jest niedostępne dla typów danych zawierających tablice (`E2030`).
- Cel dziury jest wyznaczany tylko dla dziur w pozycji wyniku funkcji.

## Licencje

| Część | Licencja |
|---|---|
| Kompilator i testy (`rzc`, `rdzen/`, `tests/`) | `MIT OR Apache-2.0` — do wyboru ([LICENSE-MIT](LICENSE-MIT), [LICENSE-APACHE](LICENSE-APACHE)) |
| Specyfikacja i dokumentacja (`spec/`, `REFERENCE.md`, `README.md`, `SKILL.md`) | [CC BY 4.0](LICENSE-CC-BY) |
| Środowisko wykonawcze wklejane do modułów generowanych przez `rzc emit` | [0BSD](LICENSE-0BSD-RUNTIME) — wygenerowany kod nie wymaga noty licencyjnej |
| Przykłady (`examples/`, `eval/`, `tests/cases/`) | `MIT OR Apache-2.0` |

Program napisany w Rdzeniu i wygenerowany z niego moduł należą do autora programu.

## Pochodzenie kodu

Specyfikacja, kompilator, testy i dokumentacja powstały we współpracy z modelem Claude
(Anthropic); kod został w dużej części wygenerowany przez model i sprawdzony testami
regresyjnymi, różnicowymi i mutacyjnymi opisanymi wyżej.
