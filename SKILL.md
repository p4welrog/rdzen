---
name: rdzen-verified-code
description: Gdy użytkownik chce funkcji lub algorytmu z mechanicznie sprawdzoną poprawnością (kontrakty dowodzone przez Z3) albo prosi o kod w języku Rdzeń — pisze go w Rdzeniu, weryfikuje kompilatorem rzc i generuje moduł Pythona.
---

# Zweryfikowany kod w języku Rdzeń

Rdzeń to mały język z kontraktami (`requires`, `ensures`, niezmienniki, warianty), których
poprawność kompilator `rzc` dowodzi przez Z3. Kod wynikowy to moduł Pythona, w którym
sprawdzenia czasu wykonania zostają tylko tam, gdzie dowodu nie znaleziono.

Używaj, gdy liczy się poprawność: algorytmy na tablicach, wyszukiwanie, sortowanie, operacje
z granicami i przepełnieniami, logika z przypadkami, drzewa i listy (typy algebraiczne,
rekursja strukturalna, lematy indukcyjne). Napisy są obsługiwane jako tablice bajtów UTF-8
(parsery, walidatory, przekształcenia tekstu). Funkcje wyższego rzędu (`map`, `filter`,
`fold`, predykaty i komparatory jako parametry) są obsługiwane z uściśleniami w typach
funkcyjnych. Nie używaj do kodu z plikami, siecią ani liczbami zmiennoprzecinkowymi —
prototyp ich nie obsługuje; wtedy napisz zwykły kod.

## 1. Przygotowanie kompilatora

1. Sprawdź, czy `rzc` jest dostępny: `ls ~/rdzen/rzc`.
2. Jeśli nie: `git clone --depth 1 https://github.com/p4welrog/rdzen ~/rdzen`.
   Gdy sieć nie pozwala na klonowanie, poszukaj archiwum `rdzen-prototyp.zip` wśród plików
   przesłanych przez użytkownika i rozpakuj je do `~` (powstaje `~/rdzen`); gdy go nie ma,
   poproś użytkownika o archiwum lub dostęp do repozytorium i zatrzymaj się.
3. `pip install z3-solver --break-system-packages -q`, potem `python3 ~/rdzen/tests/run_tests.py`
   — wszystkie testy muszą przejść.

## 2. Przepływ pracy

1. **Najpierw specyfikacja.** Zapisz sygnaturę, `requires`, `ensures` i 2–4 `examples`
   (w tym test właściwości `forall`, jeśli to naturalne). Specyfikacja ma oddawać intencję
   użytkownika w całości — słaba specyfikacja (np. `None => true`) przepuszcza błędy.
   Przy niejasnej intencji pokaż użytkownikowi kontrakty, zanim napiszesz ciało.
2. **Algorytm i złożoność.** Wybierz algorytm o złożoności, której użytkownik może oczekiwać
   (np. Huffman: O(n log n) przez sortowanie i dwie kolejki, nie O(n²) przez liniowe szukanie
   minimów). Jeśli dla prostoty dowodu wybierasz wolniejszy wariant, powiedz to użytkownikowi
   przed pracą, nie w raporcie końcowym. Przy większym programie zaplanuj podział na funkcje
   (sekcja 4.10).
3. **Ciało z niezmiennikami.** Każda pętla: niezmiennik z granicami indeksów, faktami o każdej
   zapisywanej zmiennej (także `xs.len == old(xs).len` przy zapisie elementów) i `decreases`.
   W miejscach niepewnych wstaw dziurę `?nazwa` i przeczytaj raport `H7001`.
4. **Pętla kompilacji:** `python3 ~/rdzen/rzc fmt -w plik.rz`, potem
   `python3 ~/rdzen/rzc check plik.rz --json`. Czytaj `code`,
   `obligation.formula`, `counterexample` (`class`: `real` = błąd w kodzie lub specyfikacji;
   `inductive` = za słaby niezmiennik albo `ensures` wywoływanej funkcji) i `notes`.
   Poprawiaj i powtarzaj; do ok. 8 iteracji na funkcję, potem opisz użytkownikowi, co nie
   przechodzi. Sprawdzaj funkcje przyrostowo (dopisuj i weryfikuj po jednej), bo pełne `check`
   dużego pliku trwa dziesiątki sekund.
5. **Nie osłabiaj `ensures` ani nie usuwaj przykładów, żeby przejść weryfikację**, chyba że
   specyfikacja była błędna — wtedy powiedz to użytkownikowi wprost.
6. **Ostrzeżenia `W4200`/`W4400`** oznaczają sprawdzenie dynamiczne w kodzie wynikowym.
   Spróbuj je usunąć (fakt w niezmienniku, ograniczenie w `requires`, `checked_*`); pozostałe
   wymień w raporcie.
7. **Generowanie:** `python3 ~/rdzen/rzc emit plik.rz -o modul.py`, zaimportuj moduł i wywołaj
   funkcję na przykładach. Pułapka czasu wykonania to wyjątek `RdzenTrap(kind, loc)`.
   Napisy przekazuj przez `modul.rz_str("…")`, wynik czytaj przez `modul.py_str(b)`.
   Gdy użytkownik potrzebuje C: `python3 ~/rdzen/rzc emit-c plik.rz -o modul.c` (GCC/Clang,
   `-std=gnu11`); funkcja `f` ma w C nazwę `fn_f`, `Int` to `int64_t`, tablica `A_Int_`
   (`.len`, `.d`), pułapka kończy program komunikatem (albo `longjmp`, gdy ustawiono `rz_jb`).
   Wygenerowany kod C nie zwalnia pamięci, a tablice są wartościami: `let y = xs` czytane
   w czasie wykonania to kopia O(n). Przy kodzie z pętlami zmierz czas na dużym wejściu
   (np. 10⁶ elementów), zanim przekażesz wynik.

## 3. Wynik dla użytkownika

Przekaż plik `.rz` i wygenerowany `.py` oraz krótki raport: liczba udowodnionych zobowiązań,
lista pozostałych sprawdzeń dynamicznych (jeśli są), oraz co jest zaufane bez dowodu:
kontrakty funkcji preludium, Z3, generator kodu Pythona lub C (nieweryfikowany, testowany
różnicowo względem interpretera). Gwarancja dotyczy zgodności ze specyfikacją — specyfikację warto
pokazać użytkownikowi do przejrzenia. Nie przypisuj programowi własności, których kontrakty nie
wyrażają (np. optymalności), nawet jeśli wynikają z lektury kodu.

## 4. Referencja języka

Rdzeń to mały język z kontraktami sprawdzanymi statycznie przez Z3. Program przechodzi
kompilację tylko wtedy, gdy każde zobowiązanie (warunki, niezmienniki, indeksy, przepełnienia)
jest udowodnione albo — gdy solver nie rozstrzygnie — zamienione na sprawdzenie w czasie
wykonania. Wynik to moduł Pythona (`rzc emit`) albo plik C (`rzc emit-c`).

### 1. Układ tekstu

- Brak średników. Koniec wiersza kończy instrukcję, jeśli ostatni token to nazwa, literał,
  `)`, `]`, `}`, `return`, `break`, `continue`, `true`, `false`, `result`, `self`.
  Dlatego operator dwuargumentowy kontynuujący wyrażenie stawiaj **na końcu** wiersza
  (`a &&` ↵ `b`), nie na początku następnego.
- Kontrakty i adnotacje pętli — każdy w osobnym wierszu, klamra ciała w osobnym wierszu.
- Komentarze: `//`. Brak komentarzy blokowych.
- Porównania są niełączne: `0 <= i < n` to błąd; pisz `0 <= i && i < n`.
- `} else {` w jednym wierszu (po `}` na końcu wiersza instrukcja się kończy).
- Nazwy wartości i funkcji małą literą, typy i konstruktory wielką.
- Program musi być w postaci kanonicznej (`E0100`). Nie formatuj ręcznie: przed sprawdzeniem
  uruchom `rzc fmt -w plik.rz` (zachowuje komentarze; łamie wiersze dłuższe niż 100 znaków).

### 2. Typy

| Typ | Uwagi |
|---|---|
| `Int` | 64-bitowy ze znakiem; przepełnienie to zobowiązanie `overflow` (nie zawija) |
| `Bool`, `Unit` | `Unit` to typ funkcji bez `->` |
| `Array<T>` | wartość (kopiowana), `xs.len`, `xs[i]` |
| `Byte`, `Str` | `Byte = Int where 0 <= self && self < 256`, `Str = Array<Byte>` — napis to tablica bajtów UTF-8 |
| `data T<A> { C1, C2(f: Int, g: A) }` | typy algebraiczne, mogą być rekurencyjne |
| `data T { … } where φ` | niezmiennik typu (`self` = wartość); sprawdzany przy każdej konstrukcji, zakładany dla każdej wartości typu |
| `T where φ` | typ uściślony, `self` oznacza wartość, np. `Int where self >= 0` |
| `type N = …` | alias, np. `type Percent = Int where 0 <= self && self <= 100` |
| `fn(x: A, y: B) -> R` | typ funkcyjny; uściślenia parametrów i wyniku (wynik może zależeć od parametrów: `fn(x: Int) -> Int where self > x`); tylko jako typ parametru, `let` lub parametru `spec fn` |

Literały: `"tekst\n"` (bajty UTF-8: `"ść".len == 4`; sekwencje `\n \t \r \0 \\ \" \' \u{XXXX}`),
`b'a'` (jeden bajt, typ `Byte`). Napisy porównuje się `==`.

Preludium: `Option<T> { None, Some(value: T) }`, `Result<T, E> { Ok(value: T), Err(error: E) }`,
`Ordering { Less, Equal, Greater }`, `type Nat = Int where self >= 0`, stałe `int_min`, `int_max`.

Brak w prototypie: `F64`, `extern`, `import`, aktorów; funkcji zwracających funkcje, funkcji
w tablicach i polach typów danych, parametrów funkcyjnych `inout` oraz zmiennych `var` typu
funkcyjnego (`E2015`).

### 3. Deklaracje

```
const limit: Int = 1000

spec fn sorted(xs: Array<Int>) -> Bool =
    forall i in 0..xs.len: forall j in i..xs.len: xs[i] <= xs[j]

spec fn size(t: Tree) -> Nat            // rekurencyjna: wymaga `decreases`
    decreases t
=
    match t { Leaf => 0, Node(l, _, r) => 1 + size(l) + size(r) }

lemma fn lt_not_mem(t: Tree, b: Int, k: Int)   // dowód indukcyjny, wymazywany z kodu
    requires all_lt(t, b) && k >= b
    ensures !mem(t, k)
    decreases t
{
    match t {
        Leaf => { },
        Node(l, _, r) => {
            lt_not_mem(l, b, k)        // hipoteza indukcyjna dla poddrzew
            lt_not_mem(r, b, k)
        },
    }
}

fn name<T>(a: Int, inout buf: Array<T>) -> Option<Nat>
    requires a >= 0
    ensures match result { Some(i) => i < buf.len, None => true }
    ensures buf.len == old(buf).len
    decreases a                      // tylko dla funkcji rekurencyjnych
    examples {
        name(3, …) == Some(1)        // obliczane przy kompilacji
        forall xs: Array<Int>: …     // test właściwości, 256 losowych przypadków
    }
{
    …
}
```

- `requires` / `ensures` może być wiele (koniunkcja). `result` i `old(x)` tylko w `ensures`
  (oraz `old(x)` w niezmiennikach i `assert`). `old` dotyczy parametrów `inout`.
- Funkcje są domyślnie **totalne**: każda pętla `while` wymaga `decreases`, rekursja wymaga
  `decreases` na funkcji. `partial fn` zwalnia z tego, ale funkcja totalna nie może wołać częściowej.
- `spec fn` — czysta funkcja logiczna o dowolnym typie wyniku; używalna w kontraktach,
  niezmiennikach i `examples`, nie w kodzie. Rekurencyjna (także wzajemnie) wymaga `decreases`;
  jej spadek miary, określoność ciała i uściślenie wyniku (np. `-> Nat`) są dowodzone, a uściślenie
  wyniku jest potem dostępne przy każdym wywołaniu.
- `decreases m`: `m` typu `Int` (nieujemne, maleje) albo wartość typu danych — porządek
  strukturalny: wywołanie rekurencyjne lub kolejny obrót pętli musi dostać ścisłą podstrukturę
  (np. `l` z `Node(l, x, r)`, `t` z `Cons(_, t)`).
- `lemma fn` — funkcja-dowód: bez wyniku i `inout`, totalna; jej `ensures` jest twierdzeniem
  dostępnym po wywołaniu. Wywołania lematów są usuwane z kodu wynikowego, dlatego wszystkie
  zobowiązania lematu muszą być udowodnione (brak sprawdzeń dynamicznych).

### 4. Instrukcje i wyrażenia

```
let x = e                  // niemutowalne
var y: Array<Int> = []     // mutowalne; adnotacja potrzebna przy pustej tablicy
y = e
y[i] = e
while c
    invariant φ
    decreases t
{ … }
for x in xs                // `it` = indeks bieżącego elementu (0..xs.len)
    invariant φ            // bez `decreases` (automatyczny)
{ … }
if c { a } else { b }      // wyrażenie
match e {
    Some(v) if v > 0 => v,
    Some(_) => 0,
    None => { y = 1; 0 },  // instrukcje tylko w bloku { … }
}
return e    break    continue    assert φ
let v = e?                 // Option w funkcji zwracającej Option: None → return None
                           // Result<_, E> w funkcji zwracającej Result<_, E>: Err(x) → return Err(x)
map(xs, fn(x) => x * 2)    // domknięcie; typy parametrów i wyniku z kontekstu
let lim = 5
let p = fn(x: Int) -> Bool => x > lim   // poza kontekstem: adnotacja typów parametrów
filter(xs, inc_ok)         // funkcja nazwana jako wartość
```

**Funkcje jako wartości.**
- Domknięcie `fn(x, y) => e` — ciało jest wyrażeniem bez efektów: bez pętli, `return`,
  `break`/`continue`, przypisań, argumentów `inout`, zagnieżdżonych domknięć (`E3015`); do tego
  służy funkcja nazwana. Przechwytuje wartości zmiennych z chwili utworzenia.
- Gdy typ oczekiwany jest znany (argument, `let f: T = …`), domknięcie dostaje ten typ: parametry
  spełniają jego uściślenia, a uściślenie wyniku jest dowodzone w ciele domknięcia (`E4050`).
  Własna adnotacja z innym uściśleniem — `E2141` (pomiń ją).
- Funkcja nazwana jako wartość: bez `requires` (warunek zapisz w typie parametru,
  `x: Int where self > 0`), bez `inout`, nie generyczna, nie częściowa, nie lemat, bez parametrów
  funkcyjnych, nie wewnątrz własnej rekursji (`E3016`). Znaczy tyle, ile jej kontrakt (`ensures`,
  uściślenie wyniku).
- Przekazanie funkcji do parametru typu `fn(x: P) -> R where ψ` daje zobowiązanie `pre` (`E4010`):
  argumenty dozwolone przez `P` spełniają uściślenia parametrów przekazanej funkcji, a jej wynik
  spełnia `ψ`. Wewnątrz funkcji przyjmującej `f` wiadomo o `f(x)` tylko `ψ`.
- Funkcji nie porównuje się `==` (`E2031`). Domknięć nie ma w formułach; parametr funkcyjny
  można wywołać w `ensures` (`ensures result == f(x)`).

Ostatnie wyrażenie bloku jest jego wartością. `match` musi być wyczerpujący (gałęzie ze
strażnikiem `if` się nie liczą). Operatory: `+ - * / %` (dzielenie obcinane do zera),
`== != < <= > >=`, `&& || !`. `==` na typach danych zawierających tablice — niedostępne.

### 5. Mutowalność i `inout`

- Wszystko jest wartością: `let b = a` kopiuje tablicę; nie ma referencji ani aliasingu.
- Funkcja zmienia argument tylko przez parametr `inout`; wywołanie `f(&y)` wymaga zmiennej `var`
  (lub parametru `inout`). Ta sama zmienna nie może być przekazana dwa razy (`E6002`).
- Wbudowane: `push(&a, v)`, `pop(&a) -> Option<T>`.

### 6. Formuły

Dozwolone: arytmetyka, porównania, `&& || !`, `xs[i]`, `xs.len`, pola, konstruktory, `match`,
`if c { a } else { b }`, `forall i in lo..hi: φ`, `exists i in lo..hi: φ` (przedziały półotwarte),
wywołania `spec fn` i czystych funkcji preludium. Brak `==>` — pisz `!p || q`.
Każda formuła musi być **określona**: indeks w formule też musi być w zakresie (zobowiązanie `wd`).

### 7. Preludium (funkcje)

`compare(a, b) -> Ordering`, `min`, `max`, `contains(xs, v) -> Bool`,
`filled(n: Nat, v) -> Array<T>`, `checked_add/sub/mul(a, b) -> Option<Int>`,
`push(&a, v)` (wymaga `a.len < int_max`), `pop(&a) -> Option<T>`,
`concat(a, b) -> Array<T>`, `slice(a, lo, hi) -> Array<T>` (wymaga `0 <= lo <= hi <= a.len`),
`is_digit`, `is_alpha`, `is_lower`, `is_upper`, `is_space` (bajt ASCII → `Bool`).
Czyste funkcje preludium (wszystkie poza `push`, `pop`) są dozwolone także w formułach.

### 8. Zobowiązania i reagowanie na diagnostykę

| Kod | Zobowiązanie | Typowa poprawka |
|---|---|---|
| E4010 `pre` | warunek wstępny wywołania | dodaj `requires` w wywołującej lub sprawdź przed wywołaniem |
| E4020 `post` | `ensures` / uściślenie wyniku | popraw kod lub wzmocnij niezmiennik pętli |
| E4030 `inv-init` | niezmiennik przy wejściu | niezmiennik nie zachodzi na starcie — popraw go |
| E4031 `inv-pres` | zachowanie niezmiennika | dodaj brakujące fakty do niezmiennika |
| E4040/E4041 | wariant ≥ 0 / maleje | popraw `decreases` lub krok pętli |
| E4042 `term` | miara w rekursji maleje | popraw `decreases` funkcji |
| E4050 `refine` | uściślenie przy `let x: T where …` / przypisaniu | |
| E4060 `assert`, E4070 `wd` | asercja / określoność formuły | |
| E4110 / E4120 / E4130 | indeks / przepełnienie / dzielenie | `requires` ograniczające dane, `checked_*`, niezmiennik granic |
| W4400 | niejawne (indeks, przepełnienie) z kontrprzykładem indukcyjnym | zostaje sprawdzenie dynamiczne; zwykle brak faktu w niezmienniku |
| W4200 | solver nie rozstrzygnął | uprość formułę; zostaje sprawdzenie dynamiczne |
| E4300 / E4310 | przykład / test właściwości | kod albo przykład jest zły |
| E5001 | niewyczerpujący `match` | dodaj brakujący przypadek |
| E4051 `data-inv` | konstruowana wartość łamie niezmiennik typu lub uściślenie pola (np. `Nat`) | sprawdź warunek przed konstrukcją lub dodaj `requires` |
| E2140 | `?` w funkcji o niezgodnym typie wyniku (inny typ błędu, `Option` vs `Result`) | dopasuj typ wyniku lub użyj `match` |
| E3010 / E3011 / E3013 | pętla / rekursja / rekurencyjna `spec fn` bez `decreases` | |
| E4043 | miara rekurencyjnej `spec fn` może nie maleć | argument wywołania musi być podstrukturą |
| E3014 | lemat z wynikiem lub `inout` | |
| E2015 | typ funkcyjny w niedozwolonym miejscu (wynik, tablica, pole, `var`, `inout`, zagnieżdżony) | przekaż funkcję jako parametr |
| E3015 | efekt w ciele domknięcia | przenieś do funkcji nazwanej |
| E3016 | funkcja nie może być wartością (`requires`, `inout`, generyczna, częściowa, lemat, rekursja) | warunek do typu parametru albo opakuj w domknięcie |
| E2141 | adnotacja domknięcia z uściśleniem innym niż oczekiwane | pomiń adnotację |
| H7001 | dziura `?nazwa` | raport: typ, cel, hipotezy, kandydaci |
| E0100 | program nie w postaci kanonicznej | `rzc fmt -w plik.rz` |

Kontrprzykład **rzeczywisty** (odtworzony w interpreterze) = błąd w kodzie lub w specyfikacji.
Kontrprzykład **indukcyjny** (wartości opisane „po pętli z wiersza N” lub „wynik wywołania”) =
stan może być nieosiągalny: niezmiennik pętli albo `ensures` wywoływanej funkcji jest za słaby.
Diagnostyka podaje, które zapisywane zmienne nie występują w niezmienniku.
Gdy solver nie rozstrzygnie zobowiązania, kompilator próbuje je obalić testowaniem losowym;
znaleziony kontrprzykład (zminimalizowany) jest raportowany jako błąd rzeczywisty.

### 9. Idiomy

- **Pętla ma tylko niezmiennik.** Po pętli wiadomo wyłącznie: niezmiennik ∧ ¬warunek. Każda
  zmienna zapisywana w pętli (także tablica przy `xs[i] = …` lub `push`) traci wszystkie fakty
  poza niezmiennikiem — powtórz w nim np. `xs.len == old(xs).len` i granice indeksu
  `0 <= i && i <= xs.len`.
- Fakty o zmiennych niezapisywanych w pętli są zachowane automatycznie.
- Przepełnienia: ogranicz dane w `requires` (np. `x <= 1000`) albo użyj `checked_add`.
  Suma tablicy `Nat` może się przepełnić — sam niezmiennik `s >= 0` nie wystarczy.
- Funkcja wywoływana jest znana **tylko przez kontrakt** — `ensures` musi mówić wszystko,
  czego potrzebuje wywołujący (także o długościach tablic `inout`).
- Rekursja: `decreases n` z parametrem `Nat` albo `decreases t` dla drzew i list.
- **Z3 nie przeprowadza indukcji.** Własność wymagająca indukcji (np. „wszystkie klucze w `t`
  są `< b`, więc `k >= b` nie występuje w `t`”) wymaga lematu, którego ciało wywołuje siebie na
  podstrukturach; w miejscu użycia wywołaj lemat przed instrukcją, która tej własności potrzebuje.
- Rozwijanie definicji rekurencyjnych o jeden poziom solver robi sam: `size(Node(l, x, r))`
  jest znane jako `1 + size(l) + size(r)` bez lematu.
- Uściślenie wyniku `spec fn` (np. `-> Nat`) daje fakty typu `size(t) >= 0` za darmo.
- **Niezmiennik typu zamiast powtarzanych `requires`:** `data Bst { Bst(tree: Tree) } where
  is_bst(self.tree)` — każda funkcja przyjmująca `Bst` dostaje `is_bst(b.tree)` jako fakt, a obowiązek
  dowodu przechodzi na miejsca konstrukcji `Bst(…)`. Niezmiennik typu rekurencyjnego obowiązuje
  w każdym węźle: zmienne związane wzorcem (np. `tail`) też go spełniają.
- Konstrukcja sprawdza także uściślenia pól: `P(x)` dla `data P { P(n: Nat) }` wymaga `x >= 0`.
- Środek przedziału: `lo + (hi - lo) / 2` (bez przepełnienia).
- Napisy: długość w **bajtach** (`"Cześć"` ma 7 bajtów). Zapis do `s[i]` wymaga dowodu, że
  wartość mieści się w bajcie (np. `s[i] - 32` przy `is_lower(s[i])`). Budując napis przez `push`,
  ogranicz długość wejścia w `requires`, bo `push` wymaga `out.len < int_max`.
- Wartość liczbową cyfr opisuj rekurencyjną `spec fn` z wynikiem `Nat` (np. `num(s, k)`)
  i lematem monotoniczności — wzór w `~/rdzen/examples/strings.rz` (`parse_nat`).
- W wygenerowanym Pythonie: `rz_str("…")` zamienia napis Pythona na `Str`, `py_str(b)` odwrotnie.
- Funkcje wyższego rzędu: wymagania wobec przekazywanej funkcji pisz w jej typie, np.
  `f: fn(x: Int where self < 1000) -> Int where self > x`; funkcja `map`/`filter` z kontraktem
  `ensures forall k in 0..xs.len: result[k] == f(xs[k])` daje wywołującemu pełną wiedzę.
  Wzory: `~/rdzen/examples/hof.rz`.
- Kontrprzykład z parametrem funkcyjnym podaje funkcję jako tabelę wartości w użytych punktach:
  `f = {1 ↦ 1, …}` — typ parametru dopuszcza taką funkcję, więc kod lub typ jest za słaby.
- Przy niepewności co do kodu wstaw dziurę `?nazwa` i przeczytaj raport `H7001`.

### 10. Większe dowody (struktury danych, wiele pętli)

Wzorce ze studium `docs/studium-huffman.md`; pełny przykład: `~/rdzen/examples/huffman.rz`.

- **Najpierw podział na funkcje.** Pętla, która modyfikuje kilka tablic i potrzebuje lematów,
  powinna być osobną funkcją z kontraktem (`merge_step`, `reassign` w `huffman.rz`). Duże ciało
  pętli daje duże zobowiązania, które solver rozstrzyga niestabilnie. Dziel od razu, nie po
  pierwszych `unknown`.
- **Predykat po prefiksie definiuj rekurencyjnie, gdy będziesz go rozszerzać lub przenosić:**
  `spec fn segs(…, k: Nat) decreases k = if k == 0 { true } else { segs(…, k - 1) && seg(…, k - 1) }`.
  Rozszerzenie o element `k` to rozwinięcie definicji; postać `forall i in 0..k: …` wymaga
  instancjonowania kwantyfikatora i bywa nierozstrzygnięta. Do każdego takiego predykatu
  zwykle potrzebne są trzy lematy: `_at` (wyciągnięcie i-tego faktu), `_prefix` (k → j ≤ k)
  i `_frame` (patrz niżej).
- **Lemat ramy przy `push`/zapisie.** Jeśli niezmiennik używa funkcji rekurencyjnej zależnej
  od tablicy (`has_path(t, s, bits, …)`), to po `push(&bits, …)` solver nie wie, że fakt
  nadal zachodzi. Zrób kopię widmową przed zmianą (`let before = bits`) i wywołaj lemat:
  `requires P(a) && forall q in lo..hi: b[q] == a[q]  ensures P(b)`, dowodzony indukcyjnie po
  strukturze. Kopia czytana tylko przez lematy i asercje nie trafia do kodu wynikowego.
- **Tablica zapisywana w pętli nie może być argumentem funkcji rekurencyjnej w niezmienniku,
  jeśli da się tego uniknąć.** Fakty o zawartości wyrażaj przez indeksy (`bits[p + q] == c[q]`),
  a funkcję rekurencyjną stosuj do tablicy niezmienianej (np. `c`) i przenoś lematem przesunięcia.
- **Asercje pośrednie dopisuj oszczędnie.** W studium Huffmana 45 z 46 asercji okazało się
  zbędnych — powstały jako reakcja na niedeterminizm kompilatora (już usunięty). Gdy zobowiązanie
  wychodzi `unknown` mimo udowodnionych przesłanek, najpierw zrzuć zapytanie (`RZ_DUMP_UNKNOWN`)
  i sprawdź, czy wynik jest stały (`PYTHONHASHSEED=1` i `=2`); różny wynik to błąd kompilatora do
  zgłoszenia, nie powód do zmiany specyfikacji. Pomaga podział funkcji, nie zwiększanie `--rlimit`.
- **Nazwy z preludium są zajęte:** `contains`, `min`, `max`, `compare`, `filled`, `concat`, `slice`
  (`E1004`). Funkcji `spec` nie można przypisać do `let` (`E6105`) — pisz ją wprost w formułach.
- **Spójniki pod kwantyfikatorem:** `forall i in 0..n: A && B` obejmuje `A && B`; kolejny
  `&& forall …` też trafia do ciała. Kilka niezależnych kwantyfikatorów ujmuj w nawiasy
  albo rozbij na osobne `spec fn` (formater usuwa nawiasy tylko tam, gdzie są zbędne).
- **Równość tablic w formułach jest ekstensjonalna:** `a.len == b.len && forall i in 0..a.len:
  a[i] == b[i]` wystarcza do `a == b` — nie pisz własnego predykatu równości.
- **Diagnostyka `unknown`:** `RZ_DUMP_UNKNOWN=katalog rzc check …` zapisuje zapytania SMT-LIB
  nierozstrzygniętych zobowiązań z `reason_unknown` (zwykle „max. resource limit exceeded”).
