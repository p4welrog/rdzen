# Studium przypadku: zweryfikowany kod Huffmana w Rdzeniu → C

Sesja z 30 października 2026. Zadanie użytkownika: „kod kodowania Huffmana w C, z formalnie
zweryfikowaną poprawnością”. Wykonawca: Claude (Opus 5.5) z użyciem skilla `rdzen-verified-code`.
Dokument opisuje wynik, przebieg, zdiagnozowane problemy narzędzia, wprowadzone poprawki
i dalsze zalecenia.

## 1. Wynik

Plik `examples/huffman.rz` (832 wiersze po porządkach z sekcji 4.4) — 647 zobowiązań, wszystkie
udowodnione, 0 sprawdzeń dynamicznych w kodzie C.

| Część | Funkcje | Co jest udowodnione |
|---|---|---|
| Budowa drzewa | `huffman_tree`, `merge_step`, `reassign`, `two_min` | korzeń jest węzłem; każdy symbol 0..n−1 jest w drzewie; wysokość ≤ n; brak przepełnień (niezmiennik sumy wag); każdy krok scala dwa drzewa o najmniejszych wagach |
| Kodowanie | `make_codes`, `emit_path`, `encode` | każdy kod to ścieżka korzeń → liść symbolu; segmenty bitów odpowiadają kolejnym symbolom |
| Dekodowanie | `dec_one`, `decode` | wynik to dokładnie łańcuch dekodera zachłannego (z informacją o błędzie) |
| Twierdzenie | `decode_correct`, `huffman_roundtrip` | jeśli bity mają podział na ścieżki symboli `msg`, dekoder zwraca `ok` i dokładnie `msg` (jednoznaczna dekodowalność kodu prefiksowego); `huffman_roundtrip(freqs, msg) == msg` |

**Nieudowodnione:** optymalność (minimalna średnia długość kodu). Sprawdzona empirycznie:
2000 losowych alfabetów, koszt równy referencyjnemu Huffmanowi (`heapq`).

**Wydajność:** budowa drzewa O(n²) (liniowe szukanie minimów i przepinanie tablicy `own`).
Użytkownik słusznie zapytał, czemu nie O(n log n) — patrz zalecenie S1.

Struktura pliku: 21 funkcji `spec`, 21 lematów, 12 funkcji wykonywalnych. Około ¾ wierszy to
specyfikacja i dowód; sam algorytm to ~200–250 wierszy.

## 2. Przebieg

Praca trwała ok. 35–40 minut i kilkadziesiąt przebiegów `rzc check` po 10–30 s. Czas rozkładał się mniej
więcej tak:

| Etap | Uwagi |
|---|---|
| Specyfikacja ścieżek i dekodowania, lematy `path_decodes`, `path_shift` | przeszło od razu — dobra część języka |
| Kodowanie (`encode`) | **najdłuższy etap**: nierozstrzygnięte zobowiązania mimo udowodnionych przesłanek (§3.1), wynik zmienny między uruchomieniami (§3.2) |
| Dekodowanie i twierdzenie o jednoznaczności | sprawnie, gdy predykaty były już rekurencyjne |
| Budowa drzewa | niestabilne zobowiązania w dużym ciele pętli; ustąpiły po podziale na `merge_step` i `reassign` |
| Kod C | OOM przy wiadomości 16 000 symboli (§3.3) |

Najważniejsza obserwacja z perspektywy: **dwie usterki kompilatora (§3.1, §3.2) generowały
mylące sygnały**, na które reagowałem dopisywaniem asercji pośrednich. Po ich usunięciu
45 z 46 asercji w końcowym pliku okazało się zbędnych (§4.4).

## 3. Zdiagnozowane problemy i poprawki

Wszystkie poprawki mają testy regresyjne; `tests/run_tests.py`, `tests/diff_test.py`
i `tests/diff_c.py` (także z `RLIMIT=1`) przechodzą.

### 3.1. Z3 nie łączy argumentów funkcji rekurencyjnych → próba zapasowa z UF

**Objaw.** W `encode` udowodnione były `has_path(t, s, bits, p, c.len + p)` oraz
`c.len + p == bits.len`, a `has_path(t, s, bits, p, bits.len)` — `unknown`. To samo
z `mem(f[own[s]], s)` przy `own[s] == 0`.

**Diagnoza.** Zapytanie zrzucone do SMT-LIB i zminimalizowane do 3 asercji (hipoteza,
równość, zaprzeczony cel) nadal daje `unknown` (`max. resource limit exceeded`). Statystyki Z3:
12 454 rozwinięć ciał i 6 473 rozwinięć przypadków `has_path` przed scaleniem argumentów.
Równość arytmetyczna `a + b = len(bits)` trafia do E-grafu z opóźnieniem, a rozwijanie
`RecFunction` (z nieznanym konstruktorem drzewa) wyczerpuje limit wcześniej. W izolacji
(małe drzewo definicji) ten sam schemat przechodzi — problem ujawnia się w kontekście.

**Poprawka** (`vcgen.py`, `_uf_fallback`). Gdy zobowiązanie wychodzi `unknown`, kompilator
ponawia je z każdą funkcją rekurencyjną zastąpioną nieinterpretowaną (bez definicji).
Abstrakcja jest poprawna: sprzeczność dla dowolnej interpretacji symbolu oznacza sprzeczność
także dla jego definicji. Koszt: zero dla zobowiązań rozstrzygniętych normalnie
(`huffman.rz` w wersji z 737 zobowiązaniami: 11,1 s z poprawką vs 11,4 s bez). Wyłączenie: `RZ_NO_UF=1`.

**Efekt.** „Naturalna” postać z kwantyfikatorem
(`forall i in 0..k: has_path(..., ends[i], ends[i + 1])`) i prosty lemat ramy przechodzą;
bez poprawki — `unknown` (`tests/cases/cong_frame_ok.rz`).

### 3.2. Niedeterminizm weryfikacji → deterministyczne nazwy zmiennych związanych

**Objaw.** Ten sam plik raz przechodził w całości, raz miał 1 nierozstrzygnięte zobowiązanie,
zależnie od `PYTHONHASHSEED`.

**Diagnoza.** Zrzuty wszystkich zapytań dla dwóch ziaren: w `huffman.rz` różniło się 436
z 644 zapytań, w `examples/sort.rz` 37 z 40, w `examples/hof.rz` 38 z 59. Jedyna różnica to
nazwy zmiennych związanych `i!q{id(e) % 100000}` — `id()` zależy od rozmieszczenia obiektów
w pamięci. Nazwy zmieniają kolejność termów w Z3, a ta przebieg przeszukiwania.

**Poprawka.** Numer kolejny węzła kwantyfikatora (`self.qnames`). Po poprawce: 0 różnic.
Test: `tests/determinism_test.py` (z przywróconym `id()` wykrywa różnice w `sort.rz`, `hof.rz`).

**Znaczenie.** Niedeterminizm jest gorszy niż brak dowodu: przy zobowiązaniach na granicy
limitu każda zmiana pliku losuje wynik, więc poprawki „działają” przypadkowo. Większość
zbędnych asercji (§4.4) powstała jako reakcja na ten szum.

### 3.3. Kopie widmowe w kodzie wynikowym → analiza `ghost.py`

**Objaw.** `encode` i `decode` w C kwadratowe w czasie i pamięci; brak `free`, więc OOM.

| Wiadomość (symbole) | przed | po |
|---|---|---|
| 1 000 | 0,137 s | 0,002 s |
| 4 000 | 0,902 s | 0,003 s |
| 16 000 | zabity (OOM) | 0,010 s |
| 1 000 000 | — | 0,654 s |

(alfabet 256 symboli, budowa + kody + kodowanie + dekodowanie, `gcc -O2`)

**Diagnoza.** Oba generatory (C i Python) emitowały:
- `let before = bits` używane wyłącznie jako argument lematu ramy — kopia O(n) co obrót pętli;
- kopie `_old_x` parametrów `inout`, gdy `old(x)` występuje w `ensures`, nawet gdy warunek
  końcowy jest udowodniony i nie jest sprawdzany w czasie wykonania.

**Poprawka.** `rdzen/ghost.py`: zbiór nazw czytanych przez kod wykonywalny (z pominięciem
wywołań lematów, udowodnionych asercji, niezmienników i `ensures` bez sprawdzeń dynamicznych).
`let x = y` (kopia zmiennej, bez adnotacji typu), której `x` nie ma w tym zbiorze, nie jest
emitowana; `_old_` tylko gdy `old` jest czytane w czasie wykonania. Przy `RLIMIT=1` (wszystko
dynamiczne) kopie wracają. Test: `tests/ghost_test.py` + `tests/cases/ghost_copy.rz`.

Wymazywanie dotyczy tylko kopii zmiennych — wyrażenia z wywołaniami (mogące mieć pułapki)
zostają, nawet jeśli wynik czyta tylko dowód.

### 3.4. Błędna statystyka „obalone”

Nierozstrzygnięte zobowiązanie w lemacie (i w funkcji `spec`) było liczone jako „obalone”,
choć komunikat mówi „solver nie rozstrzygnął”. To sugerowało błąd w specyfikacji, kiedy
problemem był limit solvera. Poprawka w `driver.py`: liczone jako „nieznane” (nadal błąd
kompilacji, bo lematy są wymazywane).

### 3.5. Diagnostyka

`RZ_DUMP_UNKNOWN=katalog` zapisuje zapytania SMT-LIB nierozstrzygniętych zobowiązań
z `reason_unknown`; `RZ_DUMP_ALL=katalog` — wszystkie (do porównań, jak w §3.2). Diagnozy
§3.1 i §3.2 nie byłyby możliwe bez tych zrzutów.

## 4. Wnioski

### 4.1. Co działało dobrze

- Typy algebraiczne z dopasowaniem i rekurencyjne `spec fn` z automatycznym rozwinięciem
  o jeden poziom — lematy o drzewach (`path_decodes`, `path_shift`) przeszły od pierwszej wersji.
- Lematy jako zwykłe funkcje z rekursją strukturalną — naturalny zapis indukcji.
- Kontrprzykłady z klasyfikacją `real`/`inductive` — szybko wskazywały brakujący niezmiennik
  (np. `ok` zapisywane w pętli dekodera).
- Typy danych z tablicami (`Enc`, `Dec`) i dostęp do pól w kontraktach.
- Backend C: poprawny i szybki po §3.3; testy różnicowe dają rozsądne zaufanie.

### 4.2. Stosunek dowodu do kodu

Około 3:1 w wierszach. Typowe dla weryfikatorów SMT (Dafny, Frama-C/WP: 1:1–3:1), ale
w tym przypadku zawyżone przez:
- lematy ramy (`path_frame`, `seg_frame`, `ends_frame`, `chain_frame`, `owned_frame`,
  `total_prefix`) — sześć wariantów tej samej idei;
- trójki lematów `_at`/`_prefix`/`_frame` dla każdego predykatu rekurencyjnego po prefiksie
  (`segs`, `chain`, `owned`, `all_mem`, `same`);
- mój wybór specyfikacji jednoznaczności (porównanie dwóch podziałów zamiast dekodowania
  jako funkcji `spec`);
- własny predykat równości tablic `same`, choć `==` w formułach jest ekstensjonalne (K5).

### 4.3. Główna lekcja dla narzędzia

Koszt pracy wyznaczały nie trudności matematyczne, tylko **przewidywalność solvera**.
Zobowiązanie, które jest trywialne (kongruencja), a wychodzi `unknown`, lub które raz
przechodzi, a raz nie, kieruje użytkownika — człowieka czy model — w złą stronę: do
przepisywania poprawnej specyfikacji i dopisywania asercji. Determinizm i rozstrzyganie
trywialnych przypadków są ważniejsze niż moc solvera.

### 4.4. Zbędne asercje

Ablacja końcowego pliku: każdą z 46 asercji usunięto osobno i sprawdzono plik. Zbędnych:
45, z poprawką §3.1 i bez niej; po usunięciu wszystkich 45 naraz plik nadal przechodzi
w całości. Jedyna potrzebna asercja to rozbicie warunku końcowego `decode` na dwa wyjścia
z pętli.

Wniosek: po §3.2 to struktura (predykaty rekurencyjne, podział na funkcje) wykonała pracę,
a asercje były reakcją na szum. `examples/huffman.rz` jest już po tych porządkach
(832 zamiast 878 wierszy, 647 zamiast 737 zobowiązań).

## 5. Zalecenia — język i kompilator

Priorytet: W — wysoki, Ś — średni, N — niski.

| # | Zalecenie | Priorytet | Uzasadnienie |
|---|---|---|---|
| K1 | Zwalnianie pamięci w backendzie C (arena na wywołanie z kopiowaniem wyniku albo zliczanie referencji — tablice są wartościami, więc nie ma cykli) | W | każde wywołanie przecieka; nie da się użyć w długo działającym programie |
| K2 | `rzc check --fn NAZWA` i pamięć podręczna wyników dla niezmienionych funkcji (klucz: hasz funkcji + kontraktów wywoływanych) | W | pełny `check` 10–30 s przy każdej poprawce; większość czasu sesji to czekanie |
| K3 | Jawne `ghost let` / `ghost var` | Ś | §3.3 wymazuje tylko kopie zmiennych; jawna adnotacja pozwala na widmowe obliczenia (np. `let s0 = total(w, n)` — dziś `E6105`) i sprawdzenie, że kod wykonywalny ich nie czyta |
| K4 | Automatyczne lematy ramy dla `spec fn` rekurencyjnych | Ś | dla `P(…, xs, …)` czytającego `xs` tylko w zakresie [lo, hi) kompilator może sam wygenerować i udowodnić lemat „równe na [lo, hi) ⇒ P zachowane”; usuwa ~6 lematów z Huffmana |
| K5 | Opisać w specyfikacji języka (dopisane już w idiomach `REFERENCE.md`/`SKILL.md`), że `==` tablic w formułach jest ekstensjonalne (równa długość i elementy ⇒ równość; sprawdzone lematem z pustym ciałem) | Ś | nie wiedziałem tego i napisałem własny predykat `same` z lematem `same_all`; z `==` twierdzenie końcowe byłoby prawdopodobnie krótsze (nie sprawdzałem) |
| K6 | `examples` z czasem: `bench f(args) < 1s` albo ostrzeżenie o kopiach tablic w pętlach | N | złożoność wynikowa była niewidoczna aż do OOM |
| K7 | Komunikat `E1004` dla nazw z preludium: „`contains` jest w preludium — zmień nazwę” | N | drobna, ale kosztowała iterację |
| K8 | Typ `Bool`/`Byte` jako element tablicy w C (dziś `int64_t`) | N | 64× mniej pamięci na bit kodu |
| K9 | Biblioteka zweryfikowanych struktur: kolejka FIFO, kopiec z kontraktami | N | O(n log n) dla Huffmana wymaga jednej z nich; pisanie od zera to dziesiątki lematów |

## 6. Zalecenia — skill

Wprowadzone w `SKILL.md` (sekcja „Większe dowody” także w `REFERENCE.md`):

- **S1.** Krok „Algorytm i złożoność” przed pisaniem kodu: wybierz złożoność, której użytkownik
  oczekuje; wolniejszy wariant dla prostoty dowodu zgłoś przed pracą, nie w raporcie.
- **S2.** Sekcja „Większe dowody”: podział na funkcje od początku; predykaty rekurencyjne po
  prefiksie z lematami `_at`/`_prefix`/`_frame`; lemat ramy przy `push`; unikanie funkcji
  rekurencyjnych na tablicach zapisywanych w pętli; nazwy zajęte przez preludium; zasięg
  kwantyfikatora przy `&&`; `RZ_DUMP_UNKNOWN`.
- **S3.** Weryfikacja przyrostowa (funkcja po funkcji) i limit iteracji na funkcję, nie na plik.
- **S4.** Pomiar czasu kodu wynikowego na dużym wejściu przed przekazaniem; uwaga o braku `free` w C.

Do rozważenia:

- **S5.** Szablon „kodek” (kodowanie + dekodowanie + twierdzenie o odwracalności) jako wzorzec
  w `examples/` — schemat `seg_ok`/`chain`/`decode_correct` przenosi się na inne kody prefiksowe,
  RLE, varint.
- **S6.** Gdy zobowiązanie wychodzi `unknown` mimo udowodnionych przesłanek, skill powinien
  kazać sprawdzić determinizm (dwa ziarna) i zrzucić zapytanie, zanim zmieni specyfikację.

## 7. Moje błędy (dla kalibracji skilla)

- Nazwa `contains` kolidująca z preludium; `let` na funkcji `spec`; własne `same` zamiast `==`.
- Formuła `A && forall i: B && forall j: C` — drugi kwantyfikator zagnieżdżony w pierwszym;
  semantycznie poprawne, ale cięższe dla solvera. Formater nie ostrzega.
- Za późny podział `huffman_tree` na `merge_step`/`reassign` — po podziale niestabilność ustąpiła.
- Wybór O(n²) dla budowy drzewa bez uprzedzenia użytkownika.
- Dopisywanie asercji jako odpowiedź na niedeterminizm, zamiast od razu diagnozować
  przyczynę (§4.4).

## 8. Odtworzenie

```sh
python3 rzc check examples/huffman.rz                 # 647/647
RZ_NO_UF=1 python3 rzc check tests/cases/cong_frame_ok.rz   # bez §3.1: unknown
python3 tests/determinism_test.py                     # §3.2
python3 tests/ghost_test.py                           # §3.3
python3 rzc emit-c examples/huffman.rz -o huffman.c   # 0 sprawdzeń dynamicznych
```

Zmienione pliki: `rdzen/vcgen.py` (§3.1, §3.2, §3.5), `rdzen/ghost.py`, `rdzen/emit_c.py`,
`rdzen/emit_py.py` (§3.3), `rdzen/driver.py` (§3.4), `SKILL.md`, `REFERENCE.md` (§6);
nowe: `examples/huffman.rz`, `tests/cases/cong_frame_ok.rz`, `tests/cases/ghost_copy.rz`,
`tests/ghost_test.py`, `tests/determinism_test.py`, ten dokument.
