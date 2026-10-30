# Rdzeń: stan projektu

Aktualizowany w commicie zamykającym każde zadanie. Ostatnia aktualizacja: 30.10.2026.

Wersja specyfikacji: 0.6 (`spec/rdzen-definicja.typ` i PDF).

## Cel

Rdzeń to mały język z kontraktami weryfikowanymi statycznie przez Z3, przeznaczony do generowania kodu przez modele językowe. Pełna referencja mieści się w kontekście modelu. Kompilator zwraca diagnostykę strukturalną z kontrprzykładami. Z programu generowany jest moduł Pythona albo plik C. W kodzie wynikowym zostają sprawdzenia tylko dla zobowiązań, których nie udało się udowodnić (weryfikacja stopniowana).

## Układ repozytorium

| Ścieżka | Zawartość |
|---|---|
| `rzc` | CLI z poleceniami `check [--json] [--fn f,g] [--no-cache]`, `fmt [-w\|--check]`, `emit`, `emit-c`, `run` |
| `rdzen/lexer.py`, `parser.py`, `ast.py`, `front.py` | analiza składniowa i AST |
| `rdzen/check.py` | typowanie, uściślenia, typy funkcyjne, prawo wyłączności `inout` |
| `rdzen/vcgen.py` | wykonanie symboliczne ze scalaniem ścieżek → zobowiązania; Z3 z rlimit; zastąpienie funkcji rekurencyjnych nieinterpretowanymi przy `unknown`; instancjonowanie hipotez ∀ dla funkcji wyższego rzędu; filtr jednostek `only`; pamięć wyników |
| `rdzen/smt.py`, `prelude.rz` | kodowanie w Z3, prelude |
| `rdzen/interp.py` | interpreter (odtwarzanie kontrprzykładów, przykłady, `rzc run`) |
| `rdzen/ghost.py` | usuwanie kodu „ghost” (kopie i parametry czytane tylko przez dowody) |
| `rdzen/emit_py.py`, `emit_c.py` | generatory Pythona i C |
| `rdzen/fmt.py`, `pp.py` | formatter kanoniczny; spełnia fmt(parse(P)) = P; szerokość wiersza 100 |
| `rdzen/cache.py` | pamięć wyników weryfikacji (K2) |
| `rdzen/driver.py`, `diag.py` | sterowanie kompilacją, kody diagnostyk |
| `lean/Rdzen/*.lean` | mechanizacja metateorii |
| `REFERENCE.md`, `SKILL.md` | referencja dla piszącego kod; skill `rdzen-verified-code` (zsynchronizowany z kontem) |
| `examples/`, `eval/`, `tests/cases/` | programy; `examples/sum.rz` i `tests/cases/fail_*` są celowo błędne |
| `docs/stan-projektu.md` | ten plik |
| `docs/studium-huffman.md` | studium przypadku Huffmana (`examples/huffman.rz`) |

## Zakres języka

`Int`, `Bool`, `Unit`, `Array<T>`, `Str = Array<Byte>`.

Typy danych: generyczne, rekurencyjne, z niezmiennikami `data … where φ`. Aliasy z uściśleniami.

Specyfikacje i dowody: `spec fn` (także rekurencyjne), `lemma fn`, miary strukturalne. Funkcje z `requires`/`ensures`/`decreases`/`examples`, dziury `?h`, `assert`, `old`, kwantyfikatory ograniczone.

Konstrukcje imperatywne: `inout`, `let`/`var`, `while` z niezmiennikami i wariantem, `for`, `match` ze strażnikami, operator `?`.

Funkcje wyższego rzędu: typy `fn(x: A) -> R where ψ` (zależne), domknięcia.

Nieobsługiwane: `F64`, funkcje zwracające funkcje, funkcje w tablicach, polach i zmiennych `var`, efekty, `extern`, `import`.

## Najważniejsze decyzje

- Funkcje wyższego rzędu:
  - Domknięcie wyrażalne w logice jest kodowane przez `z3.Lambda`. Inne domknięcia są nieprzezroczyste, czyli znane tylko z typu.
  - Przekazanie funkcji daje zobowiązania kontrawariancji parametrów i kowariancji wyniku.
  - Nieudowodnione zobowiązania stają się monitorami w Pythonie, C i interpreterze.
- Kontrprzykłady są odtwarzane w interpreterze i klasyfikowane jako rzeczywiste albo indukcyjne. Zobowiązania nierozstrzygnięte przez solver są dodatkowo testowane losowo.
- Determinizm: żadnych nazw opartych na `id()`; scalanie ścieżek iteruje po posortowanych kluczach. Pilnuje tego `tests/determinism_test.py`.
- Usuwanie ghost dotyczy tylko `let` z czystym wyrażeniem. `var` nie jest usuwany.
- Backend C:
  - `Int` to `int64_t`; formuły w sprawdzeniach dynamicznych liczone są w `__int128`.
  - Tablice mają semantykę wartości.
  - Nierekurencyjne typy danych to struktury przekazywane przez wartość, rekurencyjne to wskaźniki z etykietą.
  - Generyczność przez monomorfizację; domknięcia jako {env, f}; pułapki przez `longjmp`.
  - `prune()` usuwa nieużywane funkcje pomocnicze; kod kompiluje się bez ostrzeżeń `-Wall -Wextra`.
  - **Pamięć nie jest zwalniana.**
- Pamięć wyników (K2):
  - Klucz: sha256 z hasha kompilatora (`rdzen/*.py`, prelude, wersja Z3), rlimit, `RZ_NO_UF`, tekstu deklaracji poza funkcjami, nagłówków wszystkich funkcji, tekstu jednostki i jej silnie spójnej składowej grafu wywołań.
  - Zapamiętywane są tylko jednostki w pełni udowodnione i bez dziur.
  - Przebieg częściowy może inaczej sklasyfikować zobowiązanie po pierwszym błędzie (nieznane albo obalone). Dlatego pracę kończy pełne `check`.
- Diagnostyka:
  - `E0100`: postać inna niż kanoniczna.
  - `E1013`: nieznana nazwa w `--fn`.
  - `W4301`: przepełnienie stosu (RecursionError) w przykładach.

## Mechanizacja w Lean (lean/, Lean 4.15)

Bez `sorry`. Używane aksjomaty: propext, Quot.sound, Classical.choice.

Mechanizacja obejmuje fragment sekwencyjny z `break`/`continue`/`return`, pętle z niezmiennikami i wariantami, tryby zobowiązań (udowodnione, sprawdzane, usunięte) i modularne wywołania z `inout`.

Udowodnione twierdzenia:
- `exec_frame`: ramka zapisu (lemat 8.3);
- `soundness`, `no_fail`: poprawność warunków weryfikacji (tw. 8.5);
- `no_trap`: brak pułapek w programie bez sprawdzeń;
- `gradual`, `erase_exec`: poprawność weryfikacji stopniowanej (tw. 8.6);
- `terminates`: terminacja (tw. 8.7);
- `exclusivity_necessary`: kontrprzykład pokazujący konieczność prawa wyłączności.

Poza mechanizacją pozostają: funkcje wyższego rzędu, typy danych, tablice, `spec fn`.

## Wyniki pomiarów

- `huffman.rz`, czas `check`:
  - na zimno: 4,5 s (wcześniej 7,2 s);
  - z pamięci wyników: 1,0 s;
  - `--fn encode`: 0,3 s.
- `huffman.c`: 441 wierszy. Dla n = 10⁶: 0,28 s i 336 MB.
- Testy mutacyjne Huffmana: 204 mutanty, 9 przeżyło. Wszystkie przypadki są wyjaśnione (linie specyfikacji, mutanty równoważne, ostrzeżenia).
- Wyniki z pamięcią i bez niej są zgodne na wszystkich 56 programach repozytorium.

## Otwarte zadania (zaproponowana kolejność: 1 → 4 → 2)

1. **Ewaluacja.** Stały zestaw około 30 zadań ze specyfikacją w języku naturalnym i ukrytymi testami. Trzy warianty: Python bez skilla, Python z testami pisanymi przez model, Rdzeń z rzc. Mierzone:
   - odsetek rozwiązań przechodzących ukryte testy;
   - błędy niewykryte przez kompilator ani własne testy;
   - liczba iteracji i czas;
   - odsetek zobowiązań udowodnionych w porównaniu ze sprawdzanymi dynamicznie.

   Dodatkowo mutacje kontraktów na próbce rozwiązań.

   Punkt odniesienia: VeraBench (aallan/vera-bench, MIT). 60 zadań w JSON (opis neutralny, sygnatura, kontrakty, testy), wyniki pass@1 dla Very, Pythona i TypeScriptu. Według autorów jest nasycony (średnie 96,7–99,7%). Wniosek: część zadań można przenieść do Rdzenia jako wariant porównywalny z opublikowanymi wynikami, ale potrzebne są też zadania trudniejsze. Główną miarą zostają błędy niewykryte, czyli rozwiązania przechodzące kompilację i własne testy, a odrzucane przez testy ukryte. Porównanie projektowe z Verą: README, sekcja „Prace pokrewne”.
2. **K1: zwalnianie pamięci w C.** Najpierw arena na wywołanie funkcji eksportowanej, później ewentualnie zliczanie referencji.
3. **K8: węższe typy elementów w C.** `Int` z udowodnionym zakresem zapisywany jako `int32_t` albo `uint8_t`.
4. **K9: zweryfikowana kolejka i kopiec w bibliotece standardowej.** Huffman w O(n log n).
5. **Lean:** lambdy i pozostałe konstrukcje spoza obecnego fragmentu.

Zrobione wcześniej: funkcje wyższego rzędu, formatter i E0100, backend C, Lean, specyfikacja 0.6, studium Huffmana, porządki w backendzie C (pomocnicze funkcje na żądanie, struktury przez wartość), K2 (`--fn` i pamięć wyników).
