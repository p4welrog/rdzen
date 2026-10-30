# Ewaluacja: Python, Python z testami, Rdzeń

Materiały do zadania 1 z `docs/stan-projektu.md`. Pytanie: czy pisanie w Rdzeniu z `rzc` zmniejsza
liczbę **błędów niewykrytych** — rozwiązań, które przeszły kontrolę dostępną modelowi (własne testy
albo `rzc check`), a są błędne według testów ukrytych.

## Zadania

| Zestaw | Liczba | Źródło | Cel |
|---|---|---|---|
| A | 50 | VeraBench (aallan/vera-bench, MIT), poziomy 1–4 | porównywalność z opublikowanymi wynikami Very |
| B | 32 | nowe | błędy, których nie widać w kilku przykładach |

Zestaw A — zmiany względem VeraBench:
- każde zadanie ma zdanie o dziedzinie wejść (Rdzeń ma `Int` 64-bitowy, testy ukryte wykraczają
  poza 3–5 przykładów VeraBench);
- typy danych (lista, drzewo, wyrażenie) są podane w treści. W VeraBench definiuje je model, a ocena
  opiera się na heurystycznym odczycie typów;
- poziom 5 (efekty IO/State/Exn) pominięto, bo Rdzeń nie ma efektów;
- miarę zgodną z VeraBench (`pass1_verabench_A`) liczy się tylko na ich przypadkach testowych.

Zestaw B: wyszukiwanie i scalanie, rotacja z dużym `k`, Kadane, dominanta, inwersje, sortowanie,
podział parzyste/nieparzyste dla liczb ujemnych, two-sum z wieloma poprawnymi odpowiedziami, następna
permutacja, scalanie przedziałów, `isqrt` do 2⁶³−1, potęgowanie modularne, odwracanie cyfr z zakresem
32-bitowym, dodawanie z nasyceniem, średnia z zaokrągleniem w dół, dzień roku, NWW z przepełnieniem,
parsowanie liczby całkowitej (z `int_min`), palindrom, nawiasy, kompresja RLE, szyfr Cezara z ujemnym
`k`, liczby rzymskie, liczenie słów, odległość edycyjna, LIS, sprawdzenie BST, wartościowanie wyrażeń
z dzieleniem obcinanym i przepełnieniem.

Każde zadanie (`zestaw_a.py`, `zestaw_b.py`) zawiera:
- opis po angielsku;
- sygnatury w Pythonie i w Rdzeniu;
- wyrocznię w Pythonie;
- generator poprawnych wejść;
- przypadki brzegowe, w tym maksymalne rozmiary z dziedziny;
- opcjonalnie funkcję sprawdzającą, gdy poprawnych wyników jest wiele.

Testy ukryte to przypadki brzegowe, przypadki VeraBench i 200 losowych, deterministycznie z `ID/ziarno`, czyli około 210 na zadanie.

`ref/ID.rz` to wzorzec w Rdzeniu dla każdego z 82 zadań. Przechodzi `rzc check` i testy ukryte, a jego
`requires` zapisuje dziedzinę. Dzięki temu samotest pilnuje, że generatory nie wychodzą poza dziedzinę.
Wzorce nie są wzorem kontraktów: część ma tylko kontrakty bezpieczeństwa (np. B-19 nie ma `ensures`).

## Warianty

| Wariant | Kontekst modelu | Informacja zwrotna | Akceptacja |
|---|---|---|---|
| P | opis + sygnatura | brak, jedna odpowiedź (jak linia bazowa VeraBench) | zawsze |
| PT | jak P + polecenie napisania testów `test_*` | wynik własnych testów | wszystkie własne testy przechodzą |
| R | `REFERENCE.md` + opis + sygnatura Rdzenia | diagnostyka `rzc check` | brak błędów i dziur (ostrzeżenia dozwolone) |

Wspólne ustalenia:
- PT i R mają do 6 prób.
- W R uprząż sama uruchamia `rzc fmt -w` przed `rzc check`, tak jak przepływ skilla.
- Model nie widzi testów ukrytych ani wyroczni.
- W R sygnatura musi się zgadzać z podaną co do typów bez uściśleń. Uściślenia i `requires` są
  dowolne, ale odrzucenie wejścia z dziedziny liczy się jako błąd (`requires-za-silny`). Sprawdza to
  kod `requires` skompilowany emiterem `rzc`.
- Rozwiązanie w R jest testowane jako moduł Pythona z `rzc emit` z pozostawionymi sprawdzeniami
  dynamicznymi. Pułapka (`RdzenTrap`) to błąd.

## Miary (`raport.py`)

Każda miara jest liczona na wariant i zestaw:
- odsetek poprawnych;
- zaakceptowane;
- błędy niewykryte, względem wszystkich zadań i względem zaakceptowanych;
- poprawne odrzucone przez bramkę;
- średnia liczba iteracji, czas, tokeny wyjściowe;
- `pass1_verabench_A`;
- tylko dla R: odsetek zobowiązań udowodnionych statycznie i średnia liczba sprawdzeń dynamicznych.

`mutacje.py` sprawdza siłę kontraktów na próbce poprawnych rozwiązań R. Mutuje ciała funkcji, kontraktów nie zmienia. Mutant, który przechodzi `rzc check`, a nie przechodzi testów ukrytych, to luka w kontrakcie. Miara: luki / (zabite + luki).

## Uruchomienie

```
python3 eval/bench/samotest.py            # 82 wzorce, kontrole negatywne, pętla z odpowiedziami odtwarzanymi (~1 min)
python3 eval/bench/uruchom.py --model claude-opus-5-5 --warianty P,PT,R          # ANTHROPIC_API_KEY
python3 eval/bench/uruchom.py --model M --backend polecenie --polecenie "…"     # dowolny model przez stdin/stdout
python3 eval/bench/raport.py eval/bench/wyniki/PRZEBIEG
python3 eval/bench/mutacje.py eval/bench/wyniki/PRZEBIEG --proba 15
python3 eval/bench/ocen.py ID PLIK.(py|rz)                                     # ocena pojedynczego rozwiązania
```

Przerwany przebieg wznawia się tym samym `--wyjscie`. `meta.json` zapisuje commit repozytorium, a więc
wersję `REFERENCE.md` i kompilatora.

## Zastrzeżenia

- **Testy ukryte są ukryte przed modelem w sesji, ale nie przed światem.** Repozytorium jest publiczne.
  Model nie może mieć dostępu do repozytorium ani narzędzi w trakcie przebiegu. W wynikach podaje się
  datę i commit.
- Zestaw A jest nasycony dla Pythona (VeraBench: 96,7–99,7%). Rozróżnia warianty głównie przez błędy
  niewykryte na rozszerzonych testach, a nie przez pass@1.
- Prompt R jest o rząd wielkości dłuższy (`REFERENCE.md`). Porównania kosztu podaje się w tokenach.
- Opisy są po angielsku, a referencja Rdzenia po polsku. Tak samo jest przy normalnym użyciu skilla.

## Licencje

Kod: `MIT OR Apache-2.0`. Ten plik: CC BY 4.0. `dane/verabench_t1_t4.json` oraz opisy i przypadki
testowe zestawu A pochodzą z VeraBench (MIT, © 2026 Alasdair Allan, `LICENSE-VeraBench`).
