# Rdzeń

Mały język programowania z kontraktami weryfikowanymi statycznie (Z3), projektowany pod
generowanie kodu przez modele językowe: pełna specyfikacja mieści się w kontekście modelu,
a kompilator zwraca strukturalną diagnostykę z kontrprzykładami.

- `spec/` — formalna definicja języka (Typst + PDF, wersja 0.6)
- `rzc`, `rdzen/` — prototyp kompilatora (weryfikacja, formatter, generatory Pythona i C)
- `lean/` — mechanizacja metateorii fragmentu jądra w Lean 4 (tw. 8.5–8.7)
- `REFERENCE.md` — zwięzła referencja dla piszącego kod
- `SKILL.md` — skill dla Claude: specyfikacja → weryfikacja → generowanie Pythona

## rzc — prototyp kompilatora

Weryfikuje programy w podzbiorze Rdzenia zgodnie z definicją formalną:
typowanie (rozdz. 5) → zobowiązania dowodowe (rozdz. 6) → Z3 → przykłady i testy
właściwości → diagnostyka w formacie z rozdz. 9 (tekst lub JSON).

Wymagania: Python ≥ 3.10, `pip install z3-solver`.

```
./rzc check plik.rz            # weryfikacja, przykłady, diagnostyka
./rzc check plik.rz --json     # diagnostyka strukturalna
./rzc check plik.rz --fn f,g   # tylko wskazane funkcje (kontrakty pozostałych są używane)
                               # wyniki w pełni udowodnionych funkcji są zapamiętywane
                               # (~/.cache/rzc lub $RZ_CACHE; --no-cache wyłącza)
./rzc fmt plik.rz -w           # postać kanoniczna (check odrzuca inną błędem E0100)
./rzc emit plik.rz -o m.py     # moduł Pythona; sprawdzenia tylko dla zobowiązań bez dowodu
./rzc emit-c plik.rz -o m.c    # jednostka kompilacji C (GCC/Clang, gnu11)
./rzc run plik.rz f ARG...     # wykonanie funkcji w interpreterze (ze sprawdzeniami)
python3 tests/run_tests.py     # testy regresyjne (tests/cases)
python3 tests/cache_test.py    # pamięć wyników i --fn nie ukrywają błędów
python3 tests/fmt_test.py      # formatter: zachowanie drzewa i komentarzy, idempotencja,
                               #   niezależność od odstępów
python3 tests/diff_test.py     # testy różnicowe: wygenerowany Python vs interpreter
python3 tests/diff_c.py        # testy różnicowe: skompilowane C (UBSan, ASan) vs interpreter
                               #   RLIMIT=1 — wszystkie sprawdzenia dynamiczne;
                               #   ERRORS=1 — także programy z obalonymi zobowiązaniami (pułapki)
python3 tests/mutate.py P.rz…  # testy mutacyjne
cd lean && lake build          # dowody w Lean 4 (v4.15, bez bibliotek zewnętrznych)
```

`REFERENCE.md` — zwięzła referencja języka dla piszącego kod; `SKILL.md` — skill z przepływem
pracy (specyfikacja → weryfikacja → emisja). `eval/` — programy napisane wyłącznie na podstawie
referencji.

## Zakres prototypu

Obsługiwane: `Int`, `Bool`, `Unit`, `Array<T>`, typy danych (także generyczne
i rekurencyjne), aliasy z uściśleniami (`type Nat = Int where self >= 0`), stałe, `spec fn`
(także rekurencyjne i wzajemnie rekurencyjne, z uściślonym wynikiem), `lemma fn`, miary
strukturalne (`decreases t` dla typów danych), niezmienniki typów danych (`data … where φ`),
operator `?` dla `Option` i `Result`, napisy (`Str = Array<Byte>`, literały `"…"` i `b'x'`,
`concat`, `slice`, klasy znaków ASCII), typy funkcyjne z uściśleniami (także zależnymi od
parametrów), domknięcia i funkcje nazwane jako wartości,
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

Wartość typu `fn(x̄: P̄) -> R where ψ` jest tablicą Z3 z hipotezą ∀x̄. P̄(x̄) ⇒ ψ(f(x̄)); domknięcie
o ciele wyrażalnym w logice jest kodowane dokładnie (`z3.Lambda`), inne — przez typ, a uściślenie
wyniku z typu oczekiwanego jest dowodzone w jego ciele. Przekazanie funkcji daje zobowiązania
kontrawariancji parametrów i kowariancji wyniku. Gdy solver nie rozstrzyga zobowiązania
z parametrem funkcyjnym, hipotezy ∀ są zastępowane instancjami w punktach zastosowania; model
jest kontrprzykładem, jeśli typ funkcyjny jest punktowo zamieszkany. Niedowiedzione zobowiązania
typów funkcyjnych w kodzie wynikowym stają się monitorami opakowującymi przekazaną funkcję.

Nieobsługiwane (błąd `E0003`/`E2002`/`E2015`): `F64`, funkcje zwracające funkcje oraz funkcje
w tablicach, polach i zmiennych `var`, kapabilności i efekty poza totalnością, aktorzy,
`extern`, `import`.

Forma kanoniczna (§2.5): `rzc fmt` wypisuje postać kanoniczną z zachowaniem komentarzy,
zapisu literałów i pustych wierszy między instrukcjami; `rzc check` zgłasza różnicę jako `E0100`
z poprawką. Opcja `--no-canon` wyłącza to sprawdzenie.

Backend C: `Int` → `int64_t`, tablice z semantyką wartości (kopie w tych samych miejscach co
w backendzie Pythona), typy danych jako niemutowalne struktury z etykietą (nierekurencyjne —
przez wartość, bez sterty; rekurencyjne — wskaźnik), monomorfizacja
generyczności, domknięcia jako pary {środowisko, funkcja}, monitory kontraktów wyższego rzędu,
formuły w sprawdzeniach dynamicznych liczone w 128 bitach, pułapki przez `longjmp`. Plik
wynikowy zawiera tylko używane funkcje pomocnicze; kopie i parametry czytane wyłącznie przez
dowód nie są emitowane, a kod kompiluje się bez ostrzeżeń `-Wall -Wextra`
(`tests/c_warnings_test.py`). Pamięć nie jest zwalniana (prototyp).

Mechanizacja (`lean/`): fragment sekwencyjny z `break`/`continue`/`return`, pętlami
z niezmiennikami i wariantami, zobowiązaniami w trybach udowodnione/sprawdzane/usunięte
i modularnymi wywołaniami z `inout`. Udowodnione: ramka zapisu (lemat 8.3), poprawność warunków
weryfikacji (tw. 8.5), brak pułapek w programie bez sprawdzeń, poprawność weryfikacji stopniowanej
i przekształcenia R (tw. 8.6), terminacja pętli (tw. 8.7), konieczność prawa wyłączności
(kontrprzykład). Szczegóły i zakres: specyfikacja §8.5.

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
| Środowisko wykonawcze wklejane do modułów generowanych przez `rzc emit` i `rzc emit-c` | [0BSD](LICENSE-0BSD-RUNTIME) — wygenerowany kod nie wymaga noty licencyjnej |
| Mechanizacja (`lean/`) | `MIT OR Apache-2.0` |
| Przykłady (`examples/`, `eval/`, `tests/cases/`) | `MIT OR Apache-2.0` |

Program napisany w Rdzeniu i wygenerowany z niego moduł należą do autora programu.

## Pochodzenie kodu

Specyfikacja, kompilator, testy i dokumentacja powstały we współpracy z modelem Claude
(Anthropic); kod został w dużej części wygenerowany przez model i sprawdzony testami
regresyjnymi, różnicowymi i mutacyjnymi opisanymi wyżej.
