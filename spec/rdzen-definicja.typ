// =====================================================================
//  Rdzeń — formalna definicja języka programowania (wersja 0.1)
// =====================================================================

#set document(title: "Rdzeń — formalna definicja języka, wersja 0.1")
#set page(
  paper: "a4",
  margin: (x: 2.3cm, y: 2.4cm),
  numbering: "1",
  number-align: center,
)
#set text(lang: "pl", size: 10.5pt)
#set par(justify: true, leading: 0.62em)
#set heading(numbering: "1.1")
#show heading.where(level: 1): it => {
  counter("thm").update(0)
  v(1.4em)
  it
  v(0.4em)
}
#show raw.where(block: true): it => block(
  width: 100%,
  inset: (x: 8pt, y: 7pt),
  fill: luma(246),
  stroke: (left: 1.5pt + luma(190)),
  text(size: 8.4pt, it),
)
#show raw.where(block: false): set text(size: 9.5pt)

// ---------- operatory i nazwy w trybie matematycznym ----------
#let wp = math.op("wp")
#let VC = math.op("VC")
#let wd = math.op("wd")
#let len = math.op("len")
#let old = math.op("old")
#let fv = math.op("fv")
#let dom = math.op("dom")
#let ws = math.op("ws")
#let exh = math.op("exhaustive")
#let erase = math.op("erase")
#let solve = math.op("Solve")
#let Pre = math.op("Pre")
#let Post = math.op("Post")
#let Dec = math.op("Dec")
#let fmt = math.op("fmt")
#let parse = math.op("parse")
#let MIN = math.op("MIN")
#let MAX = math.op("MAX")

// ---------- środowiska twierdzeń ----------
#let thm-counter = counter("thm")
#let env(kind, title: none, body) = {
  thm-counter.step()
  block(width: 100%, above: 0.9em, below: 0.9em)[
    *#kind #context [#counter(heading).get().first().#thm-counter.get().first()]*#if title != none [ (#title)]*.*
    #body
  ]
}
#let definicja = env.with("Definicja")
#let twierdzenie = env.with("Twierdzenie")
#let lemat = env.with("Lemat")
#let hipoteza = env.with("Hipoteza")
#let dowod(body) = block(width: 100%, above: 0.5em, below: 1em)[
  _Szkic dowodu._ #body #h(1fr) $square$
]
#let uwaga(body) = block(
  width: 100%,
  inset: (x: 8pt, y: 6pt),
  stroke: (left: 1.5pt + rgb("#b08a3a")),
  fill: rgb("#fbf7ee"),
)[*Uwaga.* #body]

// ---------- reguły wnioskowania ----------
#let infer(name, concl, ..prems) = context {
  let ps = prems.pos()
  let top = if ps.len() == 0 { [] } else { ps.join(h(1.6em)) }
  let wt = measure(top).width
  let wb = measure(concl).width
  let w = calc.max(wt, wb) + 6pt
  box(inset: (y: 4pt))[
    #stack(
      dir: ttb,
      spacing: 3pt,
      block(width: w, align(center, top)),
      line(length: w, stroke: 0.5pt),
      block(width: w, align(center, concl)),
    )
  ]
  h(0.35em)
  box(inset: (bottom: 6pt), text(size: 8pt, smallcaps(name)))
}
#let rules(..rs) = align(center, block(width: 100%,
  rs.pos().join(h(2.2em, weak: true))
))

// ---------- strona tytułowa ----------
#align(center)[
  #v(3cm)
  #text(size: 26pt, weight: "bold")[Rdzeń]
  #v(0.3em)
  #text(size: 14pt)[Formalna definicja języka programowania]
  #v(0.6em)
  #text(size: 11pt)[Wersja 0.2 — szkic normatywny]
  #v(0.4em)
  #text(size: 10pt, style: "italic")[29 października 2026]
  #v(2.5cm)
  #block(width: 80%)[
    #set par(justify: true)
    #set text(size: 10pt)
    Dokument definiuje składnię, statyczną semantykę, semantykę weryfikacyjną
    (warunki weryfikacji), dynamiczną semantykę oraz format diagnostyki języka
    *Rdzeń* — małego, statycznie typowanego języka ogólnego przeznaczenia,
    zaprojektowanego tak, aby jego pełna specyfikacja mieściła się w kontekście
    modelu językowego, a kompilator maksymalizował automatycznie sprawdzane
    gwarancje poprawności i informację zwrotną o błędach. Definicja ma postać
    jądra kalkulusowego $lambda_"Rz"$ oraz elaboracji pełnej składni do jądra.
  ]
]

#pagebreak()
#outline(depth: 2, indent: auto)

= Wprowadzenie

== Status i zakres

Dokument jest *normatywny* w rozdziałach 2–8 i *informacyjny* w dodatkach.
Definicja obejmuje wersję 0.1 języka. Elementy oznaczone jako _poza wersją 0.1_
są zarezerwowane składniowo, ale nie mają semantyki.

Definicja ma budowę warstwową, wzorowaną na definicji Standard ML:

+ *Składnia konkretna* (rozdz. 2): leksyka, reguła układu, gramatyka, forma kanoniczna.
+ *Jądro* $lambda_"Rz"$ (rozdz. 3): mały kalkulus, do którego elaborowana jest pełna składnia.
+ *Elaboracja* (rozdz. 4): tłumaczenie składni konkretnej na jądro, w tym wstawianie zobowiązań dowodowych.
+ *Statyczna semantyka* (rozdz. 5): typy kształtu, efekty, wyłączność dostępu, wyczerpywalność, totalność.
+ *Semantyka weryfikacyjna* (rozdz. 6): fragment logiki, warunki weryfikacji, rozstrzyganie zobowiązań, weryfikacja stopniowana.
+ *Dynamiczna semantyka* (rozdz. 7): semantyka operacyjna small-step z etykietowanymi zdarzeniami, aktorzy.
+ *Metateoria* (rozdz. 8): twierdzenia o poprawności z ich statusem dowodowym.
+ *Diagnostyka* (rozdz. 9): normatywny format komunikatów kompilatora.

== Zasady projektowe

#table(
  columns: (auto, 1fr),
  stroke: none,
  inset: (x: 4pt, y: 3pt),
  [*Z1*], [*Małość.* Specyfikacja z biblioteką standardową w postaci sygnatur mieści się w ok. 25 tys. tokenów.],
  [*Z2*], [*Jeden sposób zapisu.* Program jest poprawny składniowo tylko w formie kanonicznej (§2.5).],
  [*Z3*], [*Brak fałszywych przyjaciół.* Konstrukcja zapisana tak jak w Kotlinie lub Ruście ma tę samą semantykę. Gdzie semantyka się różni, zapis jest inny. Odstępstwa wymienia §2.6.],
  [*Z4*], [*Jawność.* Brak niejawnych konwersji, przeciążania, dziedziczenia, makr, refleksji, wyjątków, wartości `null` i globalnego stanu mutowalnego.],
  [*Z5*], [*Lokacje nie są wartościami.* Mutowalne zmienne nie mogą być przechowywane, zwracane ani przechwytywane. Jedynym sposobem współdzielenia lokacji jest parametr `inout`, objęty prawem wyłączności. Z tego wynika brak aliasingu (§8).],
  [*Z6*], [*Każda formuła jest wykonywalna.* Fragment logiki specyfikacji zawiera wyłącznie kwantyfikatory ograniczone, więc każdy kontrakt można sprawdzić w czasie wykonania (tw. 8.8). To umożliwia weryfikację stopniowaną.],
  [*Z7*], [*Determinizm diagnostyki.* Ten sam program daje tę samą listę diagnostyk w tej samej kolejności, niezależnie od maszyny i czasu.],
)

== Konwencje notacyjne

- $overline(x)$ oznacza skończony ciąg $x_1, dots, x_n$; $|overline(x)|$ to jego długość.
- $Gamma$ — kontekst typowania, $Delta$ — kontekst zmiennych typowych i efektowych, $Lambda$ — typowanie lokacji (pamięci), $Sigma$ — sygnatury globalne.
- $e[v slash x]$ — podstawienie bez przechwytywania zmiennych.
- $phi, psi$ — formuły logiki specyfikacji; $tack.r.double phi$ — prawdziwość w modelu standardowym.
- $arrow.r$ — krok redukcji, $arrow.r^*$ — domknięcie zwrotno-przechodnie, $arrow.r.squiggly$ — elaboracja.
- Słowa kluczowe składni konkretnej pisane są czcionką maszynową (`while`), a w jądrze pismem prostym ($"while"$).

= Składnia konkretna

== Leksyka

*Kodowanie.* Plik źródłowy jest poprawnym tekstem UTF-8 z rozszerzeniem `.rz`. Znaki spoza ASCII mogą występować wyłącznie w literałach napisowych i komentarzach.

*Identyfikatory.* Kategoria leksykalna rozróżnia rolę nazwy, co usuwa niejednoznaczność wzorców (zmienna czy konstruktor):

```
ident   = [a-z_] [a-zA-Z0-9_]*        (* wartości, funkcje, pola *)
Tident  = [A-Z]  [a-zA-Z0-9]*         (* typy, konstruktory, rodzaje kapabilności *)
hole    = "?" [a-z_] [a-zA-Z0-9_]*    (* dziury *)
```

*Słowa kluczowe* (zarezerwowane, nie mogą być identyfikatorami):

```
actor  as  assert  break  const  continue  data  decreases  else  ensures
examples  exists  extern  false  fn  for  forall  if  import  in  inout
invariant  lemma  let  match
old  partial  pub  receives  recv  requires  result  return  self  send  spawn  spec
true  type  var  where  while
```

*Literały.*
- całkowite: `0`, `42`, `1_000_000`, `0xFF`, `0b1010` (separator `_` tylko między cyframi);
- bajtowe: `b'a'`, `b'\n'`;
- zmiennoprzecinkowe: `1.5`, `2.0e-3` (zawsze z kropką i cyfrą po obu stronach);
- napisowe: `"..."` z sekwencjami `\n \t \\ \" \u{XXXX}`.

*Komentarze.* `//` do końca wiersza; `///` komentarz dokumentacyjny, przypisany do następnej deklaracji. Komentarzy blokowych nie ma (Z2).

== Reguła układu

Średniki nie są pisane. Lekser wstawia token `;` na końcu wiersza wtedy i tylko wtedy, gdy ostatni token w tym wierszu należy do zbioru

```
ident  Tident  hole  literał  )  ]  }  return  break  continue  ?  true  false
```

Reguła jest identyczna z regułą wstawiania średników w języku Go. Wynika z niej, że operator dwuargumentowy kontynuujący wyrażenie musi stać na końcu wiersza, a nie na początku następnego.

== Gramatyka

Gramatyka jest LL(1) po wstawieniu średników. Notacja: `{ x }` — zero lub więcej, `[ x ]` — opcjonalne, `|` — alternatywa.

```
program     = { item } ;
item        = [ "pub" ] ( fn_decl | data_decl | type_decl | spec_decl
                         | const_decl | extern_decl | actor_decl ) | import ;
import      = "import" path [ "as" ident ] ";" ;
path        = ident { "." ident } ;

(* ---- typy ---- *)
type        = base_type [ "where" formula ] ;
base_type   = Tident [ "<" type { "," type } ">" ]
            | "fn" "(" [ type { "," type } ] ")" "->" type [ "!" effects ] ;
effects     = "{" [ effect { "," effect } ] "}" ;
effect      = Tident | ident ;           (* etykieta lub zmienna efektowa *)
tparams     = "<" tparam { "," tparam } ">" ;
tparam      = Tident [ ":" ( "Eq" | "Ord" ) ] | ident ;   (* ident = zm. efektowa *)

(* ---- deklaracje ---- *)
data_decl   = "data" Tident [ tparams ] "{" ctor { "," ctor } [ "," ] "}"
              [ "where" formula ] ;
ctor        = Tident [ "(" field { "," field } ")" ] ;
field       = ident ":" type ;
type_decl   = "type" Tident [ tparams ] "=" type ";" ;
const_decl  = "const" ident ":" type "=" expr ";" ;   (* wyrażenie stałe *)
spec_decl   = "spec" "fn" ident [ tparams ] "(" [ params ] ")" "->" type [ ";" ]
              [ "decreases" term [ ";" ] ] "=" formula ";" ;
extern_decl = "extern" "fn" ident "(" [ params ] ")" [ "->" type ]
              "!" effects [ ";" ] { contract } ;
fn_decl     = [ "partial" | "lemma" ] "fn" ident [ tparams ] "(" [ params ] ")"
              [ "->" type ] [ "!" effects ] [ ";" ]
              { contract } [ examples [ ";" ] ] block ;
params      = param { "," param } ;
param       = [ "inout" ] ident ":" type ;
contract    = ( "requires" formula | "ensures" formula
              | "decreases" term ) ";" ;
examples    = "examples" "{" { ( expr | "forall" binders ":" expr ) ";" } "}" ;
binders     = ident ":" type { "," ident ":" type } ;
actor_decl  = "actor" ident "(" [ params ] ")" "receives" type block ;

(* ---- instrukcje i wyrażenia ---- *)
block       = "{" { stmt ";" } [ expr ] "}" ;
stmt        = "let" ident [ ":" type ] "=" expr
            | "var" ident [ ":" type ] "=" expr
            | lvalue "=" expr
            | "while" expr [ ";" ] { loop_ann } block
            | "for" ident "in" expr [ ";" ] { loop_ann } block
            | "assert" formula
            | "return" [ expr ] | "break" | "continue"
            | expr ;
loop_ann    = ( "invariant" formula | "decreases" term ) ";" ;
lvalue      = ident { "." ident } [ "[" expr "]" ] ;

expr        = or_expr ;
or_expr     = and_expr { "||" and_expr } ;
and_expr    = cmp_expr { "&&" cmp_expr } ;
cmp_expr    = add_expr [ ( "==" | "!=" | "<" | "<=" | ">" | ">=" ) add_expr ] ;
add_expr    = mul_expr { ( "+" | "-" ) mul_expr } ;
mul_expr    = unary { ( "*" | "/" | "%" ) unary } ;
unary       = [ "-" | "!" ] postfix ;
postfix     = primary { "(" [ args ] ")" | "[" expr "]" | "." ident | "?" } ;
args        = arg { "," arg } ;
arg         = expr | "&" ident ;                    (* & — argument inout *)
primary     = literal | ident | Tident [ "(" [ args ] ")" ] | hole
            | "(" expr ")" | "[" [ expr { "," expr } ] "]"
            | block | if_expr | match_expr
            | "fn" "(" [ params ] ")" [ "->" type ] "=>" expr
            | "spawn" ident "(" [ args ] ")"
            | "send" "(" expr "," expr ")" | "recv" "(" "&" ident ")" ;
if_expr     = "if" expr block [ "else" ( if_expr | block ) ] ;
match_expr  = "match" expr "{" arm { "," arm } [ "," ] "}" ;
arm         = pattern [ "if" expr ] "=>" expr ;      (* instrukcje: w bloku { … } *)
pattern     = "_" | ident | literal | Tident [ "(" pattern { "," pattern } ")" ] ;

(* ---- formuły i termy specyfikacji (podzbiór wyrażeń) ---- *)
formula     = expr                                    (* ograniczenia: §6.1 *)
            | ( "forall" | "exists" ) ident "in" expr ".." expr ":" formula
            | "old" "(" ident ")" ;
term        = expr ;
```

Ograniczenia kontekstowe na `formula` i `term` definiuje §6.1. Kwantyfikatory `forall`, `exists`
oraz `old(…)`, `result` i `self` są dopuszczalne wyłącznie w formułach.

Opcjonalne średniki w nagłówkach funkcji i pętli pozwalają umieścić kontrakty i adnotacje
w osobnych wierszach (reguła układu wstawia średnik po ostatnim tokenie nagłówka).
Gałąź `match` zawiera wyrażenie; instrukcje (przypisanie, `return`) zapisuje się w bloku:
`Less => { lo = mid + 1 }`.

== Priorytety i łączność

Od najsłabszego: `||`, `&&`, porównania (niełączne — `a < b < c` jest błędem składni), `+ -`, `* / %`, jednoargumentowe `- !`, przyrostkowe `() [] . ?`. Operatory dwuargumentowe łączą lewostronnie.

== Forma kanoniczna

#definicja(title: "forma kanoniczna")[
  Niech $fmt : "AST" -> "Tekst"$ będzie deterministyczną funkcją formatowania
  (wcięcie 4 spacje, jeden znak spacji wokół operatorów dwuargumentowych,
  maksymalna szerokość wiersza 100 znaków z deterministycznym łamaniem, kolejność
  importów leksykograficzna). Program $P$ jest *kanoniczny*, gdy $fmt(parse(P)) = P$.
]

Forma kanoniczna umieszcza klauzule `requires`, `ensures`, `decreases`, `invariant` w osobnych
wierszach z wcięciem o jeden poziom, a klamrę otwierającą ciało — w osobnym wierszu, jeśli
występuje co najmniej jedna klauzula; w przeciwnym razie klamra kończy wiersz nagłówka.

Kompilator odrzuca program niekanoniczny błędem `E0100`, załączając jako
poprawkę wynik $fmt(parse(P))$. Komentarze są częścią AST i zachowują pozycję
względem węzłów.

== Odstępstwa od języków wzorcowych

Zgodnie z Z3 poniższe konstrukcje mają semantykę *inną* niż w Kotlinie lub Ruście,
więc ich zapis albo jest identyczny z językiem o tej samej semantyce, albo jest nowy:

#table(
  columns: (auto, 1fr),
  inset: 5pt,
  stroke: 0.4pt + luma(200),
  [*Konstrukcja*], [*Semantyka w Rdzeniu*],
  [`a + b` na `Int`], [Przepełnienie powoduje pułapkę `overflow` (jak Rust w trybie debug i Swift). Kotlin zawija — w Rdzeniu nie ma operatora zawijającego, jest funkcja `wrapping_add`.],
  [`a / b`, `a % b`], [Obcinanie w stronę zera (jak Kotlin, Rust, C, Go; inaczej niż Python).],
  [`==`], [Równość strukturalna. Niezdefiniowana dla typów funkcyjnych (błąd typu).],
  [`let` / `var`], [`let` jak w Ruście (niemutowalne wiązanie). `var` jak w Kotlinie, ale lokacja nie może uciec z zasięgu (Z5).],
  [`&x`], [*Nie* jest referencją ani wskaźnikiem. Oznacza wyłącznie przekazanie zmiennej jako argumentu `inout` (semantyka Swiftowego `inout`).],
  [`?`], [Jak w Ruście: wczesny powrót z `None` lub `Err(e)`, bez konwersji typu błędu.],
)

= Jądro $lambda_"Rz"$

Jądro jest językiem pośrednim, do którego elaborowany jest każdy program (rozdz. 4).
Wszystkie pozostałe rozdziały normatywne definiują semantykę na poziomie jądra.

== Typy

```
K   ::= Io | Fs | Net | Clock | Rand | Ffi | Spawn      rodzaje kapabilności
ℓε  ::= K | Div                                         etykiety efektów
ε   ::= ∅ | {ℓε} | ρ | ε ∪ ε                            efekty (ρ — zmienna)

B   ::= Int | Bool | Byte | F64 | Unit | Str            typy bazowe
τ   ::= B                                               typy kształtu
     |  T⟨τ̄⟩                                            typ danych
     |  Array⟨τ⟩
     |  α                                               zmienna typowa
     |  (τ̄) →ε τ                                        funkcja (bez inout)
     |  Cap⟨K⟩ | Chan⟨τ⟩ | Mailbox⟨τ⟩
T   ::= {ν : τ | φ}                                     typ uściślony, φ ∈ F
```

Typ uściślony $\{nu : tau | top\}$ utożsamiamy z $tau$. Składnia konkretna
`τ where φ` oznacza $\{nu : tau | phi[nu slash "self"]\}$. Funkcja
$erase(\{nu : tau | phi\}) = tau$ usuwa uściślenia; statyczna semantyka
(rozdz. 5) operuje na typach kształtu, a uściślenia są obsługiwane wyłącznie
przez semantykę weryfikacyjną (rozdz. 6).

Typy `Nat` i `Ordering` są zdefiniowane w preludium (dodatek B):
`type Nat = Int where self >= 0`.

== Wyrażenia

Zmienne dzielą się na trzy rozłączne kategorie syntaktyczne, co jest podstawą
twierdzenia o braku aliasingu:

- $x, y, z$ — zmienne *niemutowalne* (wiązane przez `let`, parametry wartościowe, wzorce);
- $m$ — zmienne *mutowalne* (wiązane przez `var` i parametry `inout`);
- $ell$ — *lokacje*, występujące wyłącznie w konfiguracjach czasu wykonania, nigdy w programie źródłowym.

```
v  ::= n | b | () | c | s                               literały
    |  C⟨τ̄⟩(v̄)                                          konstruktor
    |  [v̄]                                              tablica
    |  fn(x̄ : τ̄) ⇒ e     gdzie fv(e) ⊆ {x̄}              domknięcie zamknięte
    |  cap⟨K⟩ | chan(a) | mbox(a)

μ  ::= m | ℓ                                            cele mutacji

e  ::= v | x | f
    |  !μ                                               odczyt
    |  μ := e  |  μ[e] := e                             zapis, zapis elementu
    |  let x = e in e  |  var m : τ = e in e
    |  op(ē)                                            operacja pierwotna
    |  C⟨τ̄⟩(ē)  |  [ē]
    |  if e then e else e
    |  match e { p̄ when ḡ ⇒ ē }
    |  while e inv φ̄ dec t do e
    |  break  |  continue  |  return e
    |  f⟨τ̄,ε̄⟩(ā)                                        wywołanie globalne
    |  e(ē)                                             wywołanie domknięcia
    |  fn(x̄ : τ̄) ⇒ e
    |  assert[κ] φ                                      zobowiązanie
    |  check[κ] φ                                       sprawdzenie dynamiczne
    |  snap[κ] t₀ := t in e                             migawka wariantu
    |  trap(k)  |  hole[h]                              pułapka, dziura
    |  spawn f(ā)  |  send(e, e)  |  recv(μ)

a  ::= e | &μ                                           argument (&μ: inout)
p  ::= _ | x | n | b | C(p̄)                             wzorce
k  ::= overflow | div0 | bounds | contract(κ)           rodzaje pułapek
    |  unreachable | stack

e  ::= … | ret{e} | brk{e} | cnt{e} | iter(e, e)        ramki (tylko w czasie
                                                        wykonania)
```

Identyfikatory zobowiązań $kappa$ są unikalne w programie i niosą rodzaj zobowiązania
(§6.5) oraz pozycję w źródle.

== Operacje pierwotne

```
arytmetyka   add sub mul div rem : (Int, Int) → Int     pułapki: overflow, div0
             neg : (Int) → Int                          pułapka: overflow
porównania   eq ne lt le gt ge                          eq, ne: typy Eq
logika       not                                        && i || — §4.1
tablice      len  : (Array⟨τ⟩) → Int
             get  : (Array⟨τ⟩, Int) → τ                 pułapka: bounds
             push : (inout Array⟨τ⟩, τ) → Unit
             pop  : (inout Array⟨τ⟩) → Option⟨τ⟩
napisy       str_concat, str_eq, parse_int, …           dodatek B
kapabilności print : (Cap⟨Io⟩, Str) →{Io} Unit
             read_line : (Cap⟨Io⟩) →{Io} Option⟨Str⟩
             now : (Cap⟨Clock⟩) →{Clock} Int
             random : (Cap⟨Rand⟩, Int, Int) →{Rand} Int
```

Operacje `push` i `pop` przyjmują tablicę jako argument `inout`; w jądrze zapisuje się je
$"push"(\&mu, e)$. Pełny wykaz operacji z kontraktami zawiera dodatek B.

== Deklaracje globalne

Program jądra to sygnatura $Sigma$ i zbiór definicji. Funkcja globalna ma postać

$ f chevron.l overline(alpha), overline(rho) chevron.r(overline(x) : overline(tau), "inout" overline(m) : overline(sigma)) -> tau ! epsilon quad "requires" P quad "ensures" Q quad "decreases" t quad = e $

gdzie: parametry wartościowe $overline(x)$ poprzedzają parametry `inout` $overline(m)$ (elaboracja
porządkuje parametry i dopasowuje argumenty; kolejność źródłowa jest zachowana w diagnostyce);
$P$ może mówić o $overline(x), overline(m)$; $Q$ może mówić o $overline(x)$, $overline(m)$ (stan końcowy),
$old(m_i)$ (stan początkowy) oraz $"result"$; $t$ jest termem fragmentu całkowitoliczbowego,
obecnym wtedy i tylko wtedy, gdy $f$ należy do nietrywialnej silnie spójnej składowej grafu
wywołań i $"Div" in.not epsilon$.

Funkcja `extern` ma tę samą sygnaturę bez ciała; jej kontrakt jest *założeniem zaufanym*
(§6.7) i jej efekt musi zawierać $"Ffi"$.

Typ danych ma postać $"data" T chevron.l overline(alpha) chevron.r = C_1(overline(tau_1)) | dots | C_n (overline(tau_n)) "where" phi_T$;
niezmiennik $phi_T$ (domyślnie $top$) obowiązuje każdą wartość typu $T$ (§4.4).
Typy danych mogą być rekurencyjne; ponieważ wartości są drzewami (brak lokacji w wartościach),
nie mogą tworzyć cykli.

= Elaboracja

Elaboracja jest funkcją częściową $cal(E)$ z poprawnie sformułowanych (kanonicznych, rozwiązanych
nazwowo) programów konkretnych w programy jądra. Jest zdefiniowana przez przypadki poniżej;
przypadki nie wymienione tłumaczą się homomorficznie. Elaboracja jest kierowana typami: korzysta
z typów kształtu wyznaczonych przez statyczną semantykę (rozdz. 5), którą wykonuje się
na składni konkretnej z tymi samymi regułami.

Elaboracja wstawia trzy rodzaje węzłów: $"assert"[kappa] phi$ (zobowiązania), $"snap"$
(migawki wariantów) oraz ramki sterowania. Nie wstawia węzłów $"check"$ — te powstają dopiero
w fazie rozstrzygania (§6.6).

== Bloki, wiązania i sterowanie

#table(
  columns: (1fr, 1.25fr),
  inset: 5pt,
  stroke: 0.4pt + luma(200),
  [*Składnia konkretna*], [*Jądro*],
  [`{ s; rest }` gdzie `s = let x = e`], [$"let" x = cal(E)(e) "in" cal(E)({"rest"})$],
  [`{ s; rest }` gdzie `s = var m = e`], [$"var" m : tau = cal(E)(e) "in" cal(E)({"rest"})$],
  [`{ s; rest }` gdzie `s` to wyrażenie], [$"let" \_ = cal(E)(s) "in" cal(E)({"rest"})$],
  [`{ }` (pusty blok)], [$()$],
  [`{ e }`], [$cal(E)(e)$],
  [`m = e` (`m` mutowalna)], [$m := cal(E)(e)$],
  [`m[i] = e`], [$m[cal(E)(i)] := cal(E)(e)$],
  [`m.f = e` (typ jednokonstruktorowy `C(f₁…fₙ)`)], [$m := "match" !m { C(overline(y)) => C(y_1, dots, cal(E)(e), dots, y_n) }$],
  [`x` (`x` mutowalna)], [$!x$],
  [`if c { a }` (bez `else`)], [$"if" cal(E)(c) "then" cal(E)(a) "else" ()$],
  [`a && b`], [$"if" cal(E)(a) "then" cal(E)(b) "else" "false"$],
  [`a || b`], [$"if" cal(E)(a) "then" "true" "else" cal(E)(b)$],
  [`e.f` (pole typu jednokonstruktorowego)], [$"match" cal(E)(e) { C(overline(y)) => y_i }$],
  [`a[i]`], [$"get"(cal(E)(a), cal(E)(i))$],
  [`a.len`], [$len(cal(E)(a))$],
  [`return` (bez wyrażenia)], [$"return" ()$],
)

Kolejność obliczania argumentów, operandów i pól jest *od lewej do prawej*. Zmienna mutowalna
użyta jako argument wartościowy jest odczytywana (kopia wartości) w momencie obliczania tego
argumentu.

== Operator `?`

Dla `e?` z `e : Option⟨τ⟩` w funkcji o typie wyniku `Option⟨σ⟩`:

$ cal(E)(e"?") = "match" cal(E)(e) { "Some"(x) => x, "None" => "return" "None" } $

Dla `e : Result⟨τ, ε⟩` w funkcji o wyniku `Result⟨σ, ε⟩` (ten sam typ błędu — brak niejawnej konwersji, Z4):

$ cal(E)(e"?") = "match" cal(E)(e) { "Ok"(x) => x, "Err"(y) => "return" "Err"(y) } $

Użycie `?` w innym kontekście jest błędem `E2140`.

== Pętle

Pętla `while` przenosi adnotacje bez zmian:

$ cal(E)("while" c "invariant" overline(phi) "decreases" t { b }) = "while" cal(E)(c) "inv" overline(phi) "dec" t "do" cal(E)(b) $

Brak `decreases` oznacza $t = bot$ (pętla bez wariantu), co wymaga $"Div"$ w efekcie
otaczającej funkcji (§5.3). Warunek pętli musi być czysty (efekt $emptyset$, brak zapisu).

Pętla `for x in a` po tablicy elaboruje się z *automatycznymi* adnotacjami, do których
dołącza się adnotacje użytkownika $overline(phi)$ (w których `x` jest niedostępne,
a dostępny jest licznik pod nazwą `it`):

$ cal(E)("for" x "in" a "invariant" overline(phi) { b }) =
  & "let" a_0 = cal(E)(a) "in" "var" "it" : "Int" = 0 "in" \
  & "while" "lt"(!"it", len(a_0)) \
  & quad "inv" (0 <= "it" <= len(a_0)), overline(phi) quad "dec" len(a_0) - "it" \
  & quad "do" ("let" x = "get"(a_0, !"it") "in" cal(E)(b) ; "it" := "add"(!"it", 1)) $

Tablica jest migawkowana ($a_0$), więc modyfikacja źródłowej zmiennej w ciele pętli nie wpływa
na iterację. `continue` w ciele `for` elaborowane jest tak, aby inkrementacja licznika nastąpiła
(ciało owijane jest w blok, z którego `continue` wychodzi do inkrementacji).

== Uściślenia jako zobowiązania

Każde miejsce, w którym wartość typu kształtu $tau$ trafia w pozycję typu uściślonego
$\{nu : tau | phi\}$, otrzymuje zobowiązanie. Pozycje te to:

#table(
  columns: (auto, 1fr),
  inset: 5pt,
  stroke: 0.4pt + luma(200),
  [*Pozycja*], [*Wstawiony węzeł*],
  [`let x: τ where φ = e`], [$"let" x = cal(E)(e) "in" ("assert"[kappa_"ref"] phi[x slash nu] ; dots)$],
  [przypisanie do `var m: τ where φ`], [$m := e' ; "assert"[kappa_"ref"] phi[!m slash nu]$ — niezmiennik zmiennej],
  [argument dla parametru uściślonego], [włączany do warunku wstępnego wywoływanej funkcji (§6.4)],
  [wynik funkcji o typie uściślonym], [włączany do warunku końcowego funkcji],
  [konstrukcja wartości typu z `where φ_T`], [$"let" y = C(overline(v)) "in" ("assert"[kappa_"inv"] phi_T [y slash "self"] ; y)$],
  [zapis elementu `Array⟨τ where φ⟩`], [zobowiązanie $phi$ dla zapisywanej wartości],
)

Symetrycznie, każda zmienna typu uściślonego jest w warunkach weryfikacji *hipotezą*: przy
wiązaniu zmiennej $x : \{nu : tau | phi\}$ dodaje się do kontekstu logicznego fakt $phi[x slash nu]$
(§6.3). Dla tablic o elementach uściślonych hipotezą jest $forall k in [0, len(a)). phi[a[k] slash nu]$.

== Kontrakty, przykłady i właściwości

- `requires P` i `ensures Q` stają się składowymi $P, Q$ deklaracji jądra (koniunkcja wielu klauzul).
- Blok `examples { e₁; …; eₙ }` tworzy zobowiązania $kappa_"ex"$ rozstrzygane *obliczeniem* w czasie
  kompilacji: każde $e_i : "Bool"$ jest wartościowane przez interpreter jądra z budżetem kroków;
  wynik `false` to błąd `E4300` z wartościami podwyrażeń, przekroczenie budżetu to `W4301`.
  Przykłady nie mają dostępu do kapabilności.
- `forall x̄: e` w `examples` jest *testem właściwości*, a nie dowodem: kompilator generuje
  deterministycznie (ziarno = skrót tekstu funkcji) $N = 256$ wartości wejściowych spełniających
  uściślenia typów $overline(x)$ i wartościuje $e$; kontrprzykład jest minimalizowany (shrinking)
  i raportowany jako `E4310`.

== Domknięcia

Wyrażenie `fn(x̄: τ̄) => e` elaboruje się do domknięcia zamkniętego. Niech
$overline(y)$ będą wolnymi zmiennymi niemutowalnymi, a $overline(m)$ wolnymi zmiennymi mutowalnymi
ciała. Wtedy

$ cal(E)("fn"(overline(x)) => e) = "let" overline(z) = overline(!m) "in" ("fn"(overline(x)) => cal(E)(e)[overline(z) slash overline(m)]) $

czyli zmienne mutowalne są *migawkowane* w chwili utworzenia domknięcia (przechwycenie przez
wartość). Zapis do przechwyconej zmiennej mutowalnej w ciele domknięcia jest błędem `E6010`
(Z5: lokacja nie może uciec z zasięgu). Wolne zmienne niemutowalne są po prostu podstawiane
w czasie wykonania (wartości są zamknięte).

== Aktorzy

Deklaracja `actor a(x̄: τ̄) receives M { b }` elaboruje się do funkcji

$ a(overline(x) : overline(tau), "inout" "mb" : "Mailbox"chevron.l M chevron.r) -> "Unit" ! {"Div"} union epsilon_b $

a wyrażenie `spawn a(ē)` do węzła jądra $"spawn" a(overline(e))$ o typie $"Chan"chevron.l M chevron.r$
i efekcie $\{"Spawn"\}$; jego kapabilność jest wymagana jako pierwszy argument
(`spawn a(sp, …)`, gdzie `sp : Cap⟨Spawn⟩`).

= Statyczna semantyka

Statyczna semantyka określa, które programy jądra są *dobrze typowane*. Operuje na typach kształtu
(uściślenia są wymazywane funkcją $erase$); poprawność względem uściśleń i kontraktów
należy do semantyki weryfikacyjnej.

== Konteksty i osądy

$ Gamma ::= dot | Gamma, x : tau | Gamma, m : "mut" tau | Gamma, "ret" : tau | Gamma, "loop" $

Wpis $"ret" : tau$ określa typ wyniku bieżącej funkcji, wpis $"loop"$ — że jesteśmy wewnątrz
ciała pętli. $Gamma|_"imm"$ oznacza $Gamma$ z usuniętymi wpisami $m : "mut" tau$, $"ret"$ i $"loop"$.
$Lambda$ przypisuje lokacjom typy ($Lambda(ell) = tau$) i jest pusty dla programów źródłowych.

Główny osąd ma postać
$ Delta ; Gamma ; Lambda tack.r e : tau ! epsilon $
i czytamy go: _w kontekście $Gamma$ wyrażenie $e$ ma typ $tau$, a jego obliczenie może wywołać
efekty co najwyżej z $epsilon$_. W regułach pomijamy $Delta$ i $Lambda$, jeśli nie ulegają zmianie.
Pozostałe osądy:

- $Delta tack.r tau "wf"$ — poprawność typu (zmienne typowe w $Delta$, liczba argumentów zgodna z deklaracją);
- $Gamma tack.r_F phi$ — formuła $phi$ jest poprawnie posortowana i należy do fragmentu $F$ (§6.1);
- $tack.r p : tau gt.tri Gamma'$ — wzorzec $p$ dopasowuje się do typu $tau$ i wiąże zmienne $Gamma'$;
- $tack.r d "ok"$ — deklaracja globalna jest poprawna.

== Reguły typowania wyrażeń

=== Zmienne, odczyt i zapis

#rules(
  infer("T-Var", $Gamma tack.r x : tau ! emptyset$, $x : tau in Gamma$),
  infer("T-Read", $Gamma tack.r !m : tau ! emptyset$, $m : "mut" tau in Gamma$),
  infer("T-ReadLoc", $Gamma ; Lambda tack.r !ell : tau ! emptyset$, $Lambda(ell) = tau$),
)

#rules(
  infer("T-Write", $Gamma tack.r m := e : "Unit" ! epsilon$,
    $m : "mut" tau in Gamma$, $Gamma tack.r e : tau ! epsilon$),
  infer("T-WriteEl", $Gamma tack.r m[e_1] := e_2 : "Unit" ! epsilon_1 union epsilon_2$,
    $m : "mut" "Array"chevron.l tau chevron.r in Gamma$,
    $Gamma tack.r e_1 : "Int" ! epsilon_1$,
    $Gamma tack.r e_2 : tau ! epsilon_2$),
)

Reguły dla lokacji ($ell := e$, $ell[e_1] := e_2$) są analogiczne z $Lambda(ell)$ w miejsce $Gamma$.

=== Wiązania

#rules(
  infer("T-Let", $Gamma tack.r "let" x = e_1 "in" e_2 : tau_2 ! epsilon_1 union epsilon_2$,
    $Gamma tack.r e_1 : tau_1 ! epsilon_1$,
    $Gamma, x : tau_1 tack.r e_2 : tau_2 ! epsilon_2$),
)

#rules(
  infer("T-VarDecl", $Gamma tack.r "var" m : tau_1 = e_1 "in" e_2 : tau_2 ! epsilon_1 union epsilon_2$,
    $Gamma tack.r e_1 : tau_1 ! epsilon_1$,
    $Gamma, m : "mut" tau_1 tack.r e_2 : tau_2 ! epsilon_2$),
)

Typ $tau_2$ jest typem wartości, więc $m$ nie może opuścić zasięgu: lokacje nie są wartościami,
a domknięcia nie mają wolnych zmiennych mutowalnych (T-Lam).

=== Wartości złożone i operacje pierwotne

#rules(
  infer("T-Lit", $Gamma tack.r n : "Int" ! emptyset$),
  infer("T-Ctor", $Gamma tack.r C chevron.l overline(tau) chevron.r (overline(e)) : T chevron.l overline(tau) chevron.r ! union.big_i epsilon_i$,
    $C(overline(sigma)) in T chevron.l overline(alpha) chevron.r$,
    $Gamma tack.r e_i : sigma_i [overline(tau) slash overline(alpha)] ! epsilon_i$),
)

#rules(
  infer("T-Arr", $Gamma tack.r [overline(e)] : "Array"chevron.l tau chevron.r ! union.big_i epsilon_i$,
    $Gamma tack.r e_i : tau ! epsilon_i$),
  infer("T-Prim", $Gamma tack.r "op"(overline(e)) : tau ! epsilon_"op" union union.big_i epsilon_i$,
    $"op" : (overline(tau)) ->^(epsilon_"op") tau$,
    $Gamma tack.r e_i : tau_i ! epsilon_i$),
)

Analogiczne reguły dla literałów $"true", "false" : "Bool"$, $() : "Unit"$, literałów bajtowych,
zmiennoprzecinkowych i napisowych pomijamy. Operacje pierwotne z parametrem `inout` (np. `push`)
typuje się regułą T-Call z sygnaturą z dodatku B.

=== Sterowanie

#rules(
  infer("T-If", $Gamma tack.r "if" e "then" e_1 "else" e_2 : tau ! epsilon union epsilon_1 union epsilon_2$,
    $Gamma tack.r e : "Bool" ! epsilon$,
    $Gamma tack.r e_1 : tau ! epsilon_1$,
    $Gamma tack.r e_2 : tau ! epsilon_2$),
)

#rules(
  infer("T-Match", $Gamma tack.r "match" e { overline(p "when" g => e') } : sigma ! epsilon_0 union union.big_i epsilon_i$,
    $Gamma tack.r e : tau ! epsilon_0$,
    $tack.r p_i : tau gt.tri Gamma_i$,
    $Gamma, Gamma_i tack.r g_i : "Bool" ! emptyset$,
    $Gamma, Gamma_i tack.r e'_i : sigma ! epsilon_i$,
    $exh(overline(p), overline(g), tau)$),
)

Strażnik $g_i$ musi być czysty. Brak strażnika oznacza $g_i = "true"$.

#rules(
  infer("T-While", $Gamma tack.r "while" c "inv" overline(phi) "dec" t "do" s : "Unit" ! epsilon$,
    $Gamma tack.r c : "Bool" ! emptyset$,
    $Gamma tack.r_F phi_i$,
    $Gamma tack.r_F t : "Int"$,
    $Gamma, "loop" tack.r s : "Unit" ! epsilon$),
)

#rules(
  infer("T-WhileDiv", $Gamma tack.r "while" c "inv" overline(phi) "dec" bot "do" s : "Unit" ! epsilon union {"Div"}$,
    $Gamma tack.r c : "Bool" ! emptyset$,
    $Gamma tack.r_F phi_i$,
    $Gamma, "loop" tack.r s : "Unit" ! epsilon$),
)

#rules(
  infer("T-Break", $Gamma tack.r "break" : tau ! emptyset$, $"loop" in Gamma$),
  infer("T-Cont", $Gamma tack.r "continue" : tau ! emptyset$, $"loop" in Gamma$),
  infer("T-Ret", $Gamma tack.r "return" e : sigma ! epsilon$, $"ret" : tau in Gamma$, $Gamma tack.r e : tau ! epsilon$),
)

Wyrażenia `break`, `continue`, `return` i `trap` mają dowolny typ, bo nie zwracają sterowania
do kontekstu. Wpis $"loop"$ jest usuwany przy wejściu do ciała domknięcia, więc `break` nie może
przekroczyć granicy funkcji.

=== Funkcje i wywołania

#rules(
  infer("T-Lam", $Gamma tack.r "fn"(overline(x) : overline(tau)) => e : (overline(tau)) ->^epsilon sigma ! emptyset$,
    $Gamma|_"imm", overline(x) : overline(tau), "ret" : sigma tack.r e : sigma ! epsilon$),
)

Ponieważ $Gamma|_"imm"$ nie zawiera zmiennych mutowalnych, ciało domknięcia nie może ich
odczytywać ani zapisywać. Elaboracja (§4.6) migawkuje je wcześniej.

#rules(
  infer("T-App", $Gamma tack.r e(overline(e')) : sigma ! epsilon_0 union union.big_i epsilon_i union epsilon$,
    $Gamma tack.r e : (overline(tau)) ->^epsilon sigma ! epsilon_0$,
    $Gamma tack.r e'_i : tau_i ! epsilon_i$),
)

Dla wywołania funkcji globalnej niech
$Sigma(f) = forall overline(alpha), overline(rho). (overline(x) : overline(tau), "inout" overline(m) : overline(sigma)) -> tau_r ! epsilon_f$
oraz $theta = [overline(tau') slash overline(alpha), overline(epsilon') slash overline(rho)]$.

#rules(
  infer("T-Call", $Gamma tack.r f chevron.l overline(tau'), overline(epsilon') chevron.r (overline(e), overline(\&mu)) : theta tau_r ! union.big_i epsilon_i union theta epsilon_f$,
    $Gamma tack.r e_i : theta tau_i ! epsilon_i$,
    $mu_j : "mut" theta sigma_j in Gamma union Lambda$,
    $i != j => mu_i != mu_j$,
    $tau'_k tack.r "bounds"(alpha_k)$),
)

Przesłanka $i != j => mu_i != mu_j$ to *prawo wyłączności* (§5.4). Ograniczenia
`Eq` i `Ord` parametrów typowych sprawdza osąd $tau tack.r "bounds"(alpha)$ (§5.5).

=== Zobowiązania, pułapki, dziury

#rules(
  infer("T-Assert", $Gamma tack.r "assert"[kappa] phi : "Unit" ! emptyset$, $Gamma tack.r_F phi$),
  infer("T-Check", $Gamma tack.r "check"[kappa] phi : "Unit" ! emptyset$, $Gamma tack.r_F phi$),
  infer("T-Trap", $Gamma tack.r "trap"(k) : tau ! emptyset$),
  infer("T-Hole", $Gamma tack.r "hole"[h] : tau ! epsilon$),
)

#rules(
  infer("T-Snap", $Gamma tack.r "snap"[kappa] t_0 := t "in" e : tau ! epsilon$,
    $Gamma tack.r_F t : "Int"$, $Gamma, t_0 : "Int" tack.r e : tau ! epsilon$),
)

Program zawierający $"hole"[h]$ jest dobrze typowany, ale *niekompletny*: kompilator raportuje
dla każdej dziury jej oczekiwany typ i kontekst (§9.5) i nie generuje kodu wykonywalnego.

=== Aktorzy

#rules(
  infer("T-Spawn", $Gamma tack.r "spawn" a(e_0, overline(e)) : "Chan"chevron.l M chevron.r ! {"Spawn"} union union.big_i epsilon_i$,
    $Sigma(a) = "actor"(overline(tau)) "receives" M$,
    $Gamma tack.r e_0 : "Cap"chevron.l "Spawn" chevron.r ! epsilon_0$,
    $Gamma tack.r e_i : tau_i ! epsilon_i$),
)

#rules(
  infer("T-Send", $Gamma tack.r "send"(e_1, e_2) : "Unit" ! epsilon_1 union epsilon_2$,
    $Gamma tack.r e_1 : "Chan"chevron.l M chevron.r ! epsilon_1$,
    $Gamma tack.r e_2 : M ! epsilon_2$),
  infer("T-Recv", $Gamma tack.r "recv"(mu) : M ! {"Div"}$,
    $mu : "mut" "Mailbox"chevron.l M chevron.r in Gamma union Lambda$),
)

Odbiór ma efekt $"Div"$, bo może blokować bez końca.

=== Osłabienie efektu

#rules(
  infer("T-Sub", $Gamma tack.r e : tau ! epsilon'$, $Gamma tack.r e : tau ! epsilon$, $epsilon subset.eq epsilon'$),
)

Zawieranie efektów $epsilon subset.eq epsilon'$ rozstrzyga się syntaktycznie modulo łączność,
przemienność i idempotentność $union$ (zmienne efektowe traktowane jak stałe).

== Deklaracje i totalność

#definicja(title: "poprawność funkcji")[
  Deklaracja $f chevron.l overline(alpha), overline(rho) chevron.r (overline(x) : overline(tau), "inout" overline(m) : overline(sigma)) -> tau_r ! epsilon_f "requires" P "ensures" Q "decreases" t = e$
  jest poprawna ($tack.r f "ok"$), gdy:
  + $overline(alpha), overline(rho) ; overline(x) : overline(tau), overline(m) : "mut" overline(sigma), "ret" : tau_r tack.r e : tau_r ! epsilon'$ oraz $epsilon' subset.eq epsilon_f$;
  + $overline(x) : overline(tau), overline(m) : "mut" overline(sigma) tack.r_F P$ oraz $overline(x) : overline(tau), overline(m) : "mut" overline(sigma), old(overline(m)) : overline(sigma), "result" : tau_r tack.r_F Q$;
  + jeśli $f$ leży w nietrywialnej silnie spójnej składowej grafu wywołań (lub wywołuje sama siebie) i $"Div" in.not epsilon_f$, to $t != bot$ oraz $tack.r_F t : "Int"$ albo $tack.r_F t : T chevron.l overline(tau) chevron.r$ (miara strukturalna, §6.4);
  + jeśli $f$ jest zadeklarowana bez słowa `partial`, to $"Div" in.not epsilon_f$.
]

Efekt $epsilon_f$ funkcji zadeklarowanej w składni konkretnej jest *wyznaczany*: jest to
najmniejszy zbiór spełniający punkt 1, powiększony o $"Div"$ dla funkcji `partial`. Wyznaczony
efekt jest jawnie wypisywany przez narzędzia (np. w podpowiedziach i dokumentacji), a dla funkcji
`pub` musi zgadzać się z deklaracją `!` w typie, jeśli taka występuje.

Z punktu 4 i reguły T-Sub wynika, że *funkcja totalna nie może wywołać funkcji częściowej*:
efekt $"Div"$ wywołanej funkcji musiałby zawierać się w $epsilon_f$.

*Lematy.* Deklaracja `lemma fn` jest funkcją totalną bez parametrów `inout`, o typie wyniku
`Unit` i efekcie $emptyset$ (błąd `E3014` w przeciwnym razie). Jej warunek końcowy jest twierdzeniem
dostępnym w miejscu wywołania (reguła wywołania z §6.4); rekurencyjne wywołania w ciele lematu
pełnią rolę hipotezy indukcyjnej. Przekształcenie $cal(R)$ (§6.6) usuwa wywołania lematów i ich
definicje z programu wykonywalnego; jest to poprawne, bo lemat jest totalny i nie ma efektów,
pod warunkiem że wszystkie jego zobowiązania mają status `proved` — dlatego zobowiązanie lematu
o statusie innym niż `proved` jest błędem kompilacji, a nie sprawdzeniem dynamicznym.

== Prawo wyłączności

#definicja(title: "prawo wyłączności")[
  W każdym wywołaniu $f(overline(e), \&mu_1, dots, \&mu_k)$ cele $mu_1, dots, mu_k$ są parami różne.
  Argumentem `inout` może być wyłącznie cała zmienna mutowalna (nie element tablicy ani pole).
]

Ponieważ argumenty wartościowe $overline(e)$ są obliczane *przed* wywołaniem do wartości
(kopii), wystąpienie $mu_j$ w $overline(e)$ nie narusza wyłączności. Przekazywanie elementu
tablicy jako `inout` jest _poza wersją 0.1_; w wersji 0.1 wyraża się je przez odczyt, wywołanie
i zapis.

== Polimorfizm, ograniczenia i inferencja

- Parametry typowe deklaruje się jawnie; argumenty typowe wywołań są *wnioskowane* przez
  unifikację pierwszego rzędu typów argumentów z sygnaturą (bez uogólniania `let`).
- Ograniczenie `Eq` spełniają: `Int`, `Bool`, `Byte`, `Unit`, `Str`, typy danych i tablice
  o argumentach `Eq`. Nie spełniają: `F64` (z powodu NaN — porównanie zapewnia `f64_eq`),
  typy funkcyjne, `Cap`, `Chan`, `Mailbox`.
- Ograniczenie `Ord` spełniają: `Int`, `Byte`, `Bool`, `Str` (porządek leksykograficzny bajtów).
- Zmienne efektowe $rho$ instancjonuje się przez dopasowanie typów funkcyjnych argumentów.

#lemat(title: "rozstrzygalność typowania")[
  Dla programów, w których każda deklaracja globalna ma pełne adnotacje typów parametrów
  i wyniku, relacja $tack.r P "ok"$ jest rozstrzygalna w czasie wielomianowym względem rozmiaru
  programu, z wyjątkiem sprawdzania wyczerpywalności (§5.6), które jest wykładnicze w najgorszym
  przypadku i liniowe w praktyce.
]

== Wyczerpywalność dopasowań

Niech $Pi = (p_i)_(i in I)$, gdzie $I = {i | g_i = "true"}$, będzie macierzą wzorców gałęzi
*bez strażników*. Dopasowanie jest *wyczerpujące*, $exh(overline(p), overline(g), tau)$, gdy wektor
$(\_)$ nie jest użyteczny względem $Pi$ w sensie algorytmu użyteczności Maranget
(_Warnings for pattern matching_, JFP 2007). Gałąź ze strażnikiem nie liczy się do pokrycia.

Gdy dopasowanie nie jest wyczerpujące, algorytm wyznacza *świadka* — wzorzec wartości nieobjętej
żadną gałęzią — który jest częścią diagnostyki `E5001`. Gałąź nieużyteczna względem gałęzi
poprzednich daje ostrzeżenie `W5002`.

== Kapabilności i brak władzy otoczenia

Wartości $"cap"chevron.l K chevron.r$ nie mają nazwy w składni konkretnej i nie mogą być
skonstruowane w programie. Jedynym źródłem kapabilności jest punkt wejścia

```
fn main(caps: Caps) -> Int
```

gdzie `Caps` jest typem danych preludium z polami `io`, `fs`, `net`, `clock`, `rand`, `ffi`, `spawn`.

#lemat(title: "władza tylko przez parametry")[
  Jeżeli $tack.r f "ok"$ i ciało $f$ wywołuje efekt $K in "Cap"$, to wartość
  $"cap"chevron.l K chevron.r$ jest osiągalna z parametrów $f$ (bezpośrednio lub przez
  wolne zmienne domknięcia przekazanego jako parametr).
]

Wynika stąd, że sygnatura funkcji (typy parametrów) jest górnym ograniczeniem jej władzy —
co jest podstawą bezpieczeństwa w modelu kapabilności obiektowych.

= Semantyka weryfikacyjna

Rozdział definiuje: logikę specyfikacji (§6.1–6.3), warunki weryfikacji i rodzaje zobowiązań
(§6.4–6.5), rozstrzyganie zobowiązań i przekształcenie programu do postaci wykonywalnej (§6.6)
oraz zaufaną bazę (§6.7).

== Fragment logiki $F$

*Sorty:* `Int` (liczby całkowite matematyczne, bez ograniczeń), `Bool`, sorty danych
algebraicznych $T chevron.l overline(s) chevron.r$, sort tablic $"Array"chevron.l s chevron.r$
modelowany jako para (długość $len : "Int"$, funkcja selekcji $"Int" -> s$), `Byte` jako `Int`
z ograniczeniem $[0, 256)$, `Str` jako $"Array"chevron.l "Byte" chevron.r$. Sort `F64`
oraz sorty funkcyjne i kapabilności *nie występują* w formułach (błąd `E6101`).

*Termy i formuły:*

```
t  ::=  x | m | old(m) | result | n | t + t | t − t | n · t | t · t
     |  t ÷ n | t mod n | len(t) | t[t] | C(t̄) | t.f | if φ then t else t | s(t̄)
φ  ::=  true | false | t ⋈ t | t is C | p(t̄)
     |  ¬φ | φ ∧ φ | φ ∨ φ | φ ⇒ φ
     |  ∀k ∈ [t, t). φ | ∃k ∈ [t, t). φ | match t { C(x̄) ⇒ φ, … }
⋈  ::=  = | ≠ | < | ≤ | > | ≥
```

gdzie $s, p$ to funkcje i predykaty zadeklarowane przez `spec fn`. W formule zmienna mutowalna
$m$ oznacza jej *bieżącą* wartość; $old(m)$ — wartość przy wejściu do funkcji (tylko w `ensures`
i niezmiennikach pętli); $"result"$ — wynik (tylko w `ensures`). Zapis konkretny
`forall k in a..b: φ` oznacza $forall k in [a, b). phi$.

*Funkcje specyfikacyjne* są czyste i totalne; typ wyniku jest dowolnym typem dozwolonym
w formułach (także uściślonym). Funkcja specyfikacyjna nierekurencyjna jest w warunkach
weryfikacji *rozwijana* (makro logiczne). Funkcja należąca do nietrywialnej silnie spójnej
składowej grafu wywołań funkcji specyfikacyjnych (*rekurencyjna*, także wzajemnie) musi mieć
`decreases` (błąd `E3013`) i jest w logice *funkcją definiowaną rekurencyjnie*: symbolem
$s$ z aksjomatem $forall overline(x). s(overline(x)) = b_s (overline(x))$, który procedura decyzyjna
rozwija leniwie. Dla każdej takiej funkcji powstają zobowiązania (błąd przy statusie innym niż
`proved`, bo funkcje specyfikacyjne nie mają sprawdzeń dynamicznych):

- `wd` — ciało jest określone dla każdego argumentu spełniającego uściślenia parametrów;
- `term` (`E4043`) — w każdym wywołaniu w obrębie składowej, przy warunkach ścieżki
  (gałęzie `match` i `if`, lewy argument `&&`/`||`, zakres kwantyfikatora), miara argumentów
  jest nieujemna i mniejsza niż miara parametrów;
- `post` — jeśli typ wyniku jest uściślony, ciało spełnia uściślenie przy *hipotezie indukcyjnej*
  $forall overline(y). mu(overline(y)) < mu(overline(x)) and H(overline(y)) => h(s(overline(y)), tau_r)$
  dla wszystkich funkcji składowej.

Po udowodnieniu uściślenie wyniku jest dodawane do pozostałych warunków weryfikacji jako aksjomat
$forall overline(x). H(overline(x)) => h(s(overline(x)), tau_r)$ (wzorzec: $s(overline(x))$).
Poprawność wynika z indukcji dobrze ufundowanej po mierze (zobowiązania `term`).

#definicja(title: [fragment rozstrzygalny $F_0$])[
  $F_0 subset F$ to formuły bez mnożenia zmiennych przez zmienne, bez rekurencyjnych funkcji
  specyfikacyjnych, w których kwantyfikatory po zanegowaniu i skolemizacji tworzą formułę
  _fragmentu własności tablic_ (Bradley, Manna, Sipma, _What's decidable about arrays?_, VMCAI 2006)
  z teorią elementów będącą liniową arytmetyką całkowitoliczbową.
]

#twierdzenie(title: [rozstrzygalność $F_0$])[
  Prawdziwość formuł $F_0$ jest rozstrzygalna.
]
#dowod[Bezpośrednio z rozstrzygalności fragmentu własności tablic nad LIA [BMS06]
  po rozwinięciu nierekurencyjnych funkcji specyfikacyjnych (rozwinięcie zachowuje fragment,
  bo ciała funkcji specyfikacyjnych należą do $F_0$ z definicji).]

#hipoteza[
  Fragment $F_0$ rozszerzony o teorię skończonych typów danych algebraicznych (konstruktory,
  testery, selektory) pozostaje rozstrzygalny. Uzasadnienie: kombinacja Nelsona–Oppena teorii
  rozłącznych sygnatur z teorią ADT (Oppen 1980), przy czym wymaga sprawdzenia warunku
  stabilnej nieskończoności dla sortów elementów. Status: do dowodu.
]

Rozstrzygalność nie jest warunkiem poprawności: dla formuł spoza $F_0$ procedura może zwrócić
_nieznane_, co prowadzi do sprawdzenia w czasie wykonania (§6.6), a nie do utraty poprawności.

== Dobra określoność formuł

Termy $t[u]$ i $t.f$ są częściowe. Każda formuła z kontraktu, niezmiennika lub uściślenia
musi być *dobrze określona* w miejscu użycia. Warunek dobrej określoności $wd$ jest
zdefiniowany z obliczaniem leniwym od lewej do prawej:

$ wd(t[u]) &= wd(t) and wd(u) and 0 <= u < len(t) \
  wd(t.f_C) &= wd(t) and t "is" C \
  wd(phi and psi) &= wd(phi) and (phi => wd(psi)) \
  wd(phi or psi) &= wd(phi) and (not phi => wd(psi)) \
  wd(phi => psi) &= wd(phi) and (phi => wd(psi)) \
  wd(forall k in [a, b). phi) &= wd(a) and wd(b) and forall k in [a, b). wd(phi) \
  wd("if" phi "then" t_1 "else" t_2) &= wd(phi) and (phi => wd(t_1)) and (not phi => wd(t_2)) $

i homomorficznie w pozostałych przypadkach. Dla każdej formuły $phi$ użytkownika powstaje
zobowiązanie rodzaju `wd`: $wd(phi)$ ma zachodzić przy hipotezach obowiązujących w miejscu
jej użycia (dla `ensures` — przy $P$ i hipotezach typów; dla niezmiennika — przy poprzednich
klauzulach niezmiennika).

== Hipotezy typów

Dla kontekstu $Gamma$ definiujemy formułę hipotez
$ H(Gamma) = and.big_(x : tau in Gamma) h(x, tau) quad "gdzie" quad
  h(x, \{nu : tau | phi\}) = phi[x slash nu] and h(x, tau) $
oraz dla typów kształtu: $h(x, T chevron.l dots chevron.r) = phi_T[x slash "self"]$ (niezmiennik typu danych),
$h(x, "Array"chevron.l sigma chevron.r) = 0 <= len(x) <= MAX and forall k in [0, len(x)). h(x[k], sigma)$,
$h(x, "Int") = MIN <= x <= MAX$, $h(x, "Byte") = 0 <= x < 256$ i $top$ w pozostałych przypadkach.
Dla typu danych o argumentach uściślonych, np. $"Option"chevron.l \{nu : "Int" | nu >= 0\} chevron.r$,
$h$ zawiera ponadto warunki na polach:
$"match" x { C(overline(y)) => and.big_j h(y_j, tau_j) }$ dla każdego konstruktora $C$.
Stałe $MIN = -2^63$, $MAX = 2^63 - 1$ są w programach dostępne jako `int_min` i `int_max`.

== Warunki weryfikacji

=== Zobowiązania i fokus

Każde zobowiązanie $kappa$ jest weryfikowane *osobno*, przy założeniu wszystkich pozostałych
(weryfikacja „assume-after-assert”). Dla ustalonego zobowiązania w fokusie $kappa^*$ definiujemy

$ "ob"_kappa (phi, X) = cases(phi and X & "gdy" kappa = kappa^*, phi => X & "gdy" kappa != kappa^*) $

Poprawność tej konstrukcji przy zobowiązaniach nieudowodnionych gwarantuje to, że stają się one
sprawdzeniami w czasie wykonania (tw. 8.6).

=== Postkondycje strukturalne

Warunek weryfikacji wyrażenia liczony jest względem czwórki
$Q = chevron.l N, B, C, R chevron.r$: $N$ — predykat na wartości $nu$ przy normalnym zakończeniu,
$B$ — formuła przy `break`, $C$ — formuła przy `continue`, $R$ — predykat na $nu$ przy `return`.
Zapis $Q[N := N']$ oznacza zamianę jednej składowej. $N(v)$ skraca $N[v slash nu]$.
Dla ciągu argumentów $wp(overline(e), lambda overline(v). X)$ oznacza złożenie od lewej do prawej:
$wp(e_1, Q[N := lambda v_1. wp(e_2, dots wp(e_n, Q[N := lambda v_n. X]) dots)])$.

=== Reguły

Zmienne związane przez $"let"$, $"var"$ i wzorce są przemianowane tak, by były unikalne
(konwencja Barendregta), więc podstawienia nie przechwytują zmiennych.

$ wp(v, Q) &= N(v) \
  wp(x, Q) &= N(x) \
  wp(!m, Q) &= N(m) \
  wp("let" x = e_1 "in" e_2, Q) &= wp(e_1, Q[N := lambda nu. wp(e_2, Q)[nu slash x]]) \
  wp("var" m : tau = e_1 "in" e_2, Q) &= wp(e_1, Q[N := lambda nu. wp(e_2, Q)[nu slash m]]) \
  wp(m := e, Q) &= wp(e, Q[N := lambda nu. N(())[nu slash m]]) \
  wp(m[e_1] := e_2, Q) &= wp((e_1, e_2), lambda (i, v). "ob"_kappa (0 <= i < len(m), N(())[m chevron.l i |-> v chevron.r slash m])) $

Operacje pierwotne mają kontrakty $("pre"_"op", "post"_"op")$ z dodatku B; w szczególności:

$ wp("add"(e_1, e_2), Q) &= wp((e_1, e_2), lambda (a, b). "ob"_kappa (MIN <= a + b <= MAX, N(a + b))) \
  wp("div"(e_1, e_2), Q) &= wp((e_1, e_2), lambda (a, b). "ob"_kappa (b != 0 and not(a = MIN and b = -1), N(a div b))) \
  wp("get"(e_1, e_2), Q) &= wp((e_1, e_2), lambda (a, i). "ob"_kappa (0 <= i < len(a), N(a[i]))) \
  wp("op"(overline(e)), Q) &= wp(overline(e), lambda overline(v). "ob"_kappa ("pre"_"op" (overline(v)), forall r. "post"_"op" (overline(v), r) => N(r))) $

gdzie $div$ oznacza dzielenie obcinane w stronę zera. Sterowanie:

$ wp("if" e "then" e_1 "else" e_2, Q) &= wp(e, Q[N := lambda b. (b => wp(e_1, Q)) and (not b => wp(e_2, Q))]) \
  wp("break", Q) &= B \
  wp("continue", Q) &= C \
  wp("return" e, Q) &= wp(e, Q[N := R]) \
  wp("trap"("unreachable"), Q) &= "ob"_kappa ("false", top) $

Dopasowanie definiuje się przez rozwinięcie do kaskady testów: $"match" e { p_1 "when" g_1 => e_1, rho }$
to $"let" v = e "in" "if" "test"(p_1, v) "then" ("let" overline(x) = "sel"(p_1, v) "in" "if" g_1 "then" e_1 "else" M_rho) "else" M_rho$,
gdzie $M_rho$ jest rozwinięciem reszty gałęzi, a pusta reszta to $"trap"("unreachable")$
(zobowiązanie rodzaju `unreach`, zawsze dowodliwe dla dopasowań wyczerpujących). Funkcje
$"test"$ i $"sel"$ wyrażają się testerami i selektorami teorii ADT.

=== Pętle

Niech $I = phi_1 and dots and phi_k$ będzie niezmiennikiem (każda klauzula $phi_i$ ma własne
zobowiązania rodzajów `inv-init` i `inv-pres`), $overline(w) = ws(c) union ws(s)$ zbiorem zmiennych
mutowalnych, do których pętla może pisać (cele $:=$, zapisów elementów, argumentów `inout`),
a warunek $c$ — czysty. Dla pętli z wariantem $t$:

$ wp("while" c "inv" I "dec" t "do" s, Q) = "ob"_(kappa_"init") (I, forall overline(w). I => wp(c, Q[N := lambda b. Phi_b])) $

$ Phi_b = (b => forall t_0. t_0 = t => "ob"_(kappa_"nn") (t_0 >= 0, wp(s, Q_s))) and (not b => N(())) $

$ Q_s = chevron.l lambda \_. J, thick N(()), thick J, thick R chevron.r, quad J = "ob"_(kappa_"pres") (I, "ob"_(kappa_"dec") (t < t_0, top)) $

Dla pętli bez wariantu ($t = bot$) usuwa się zobowiązania $kappa_"nn"$ i $kappa_"dec"$.
`break` prowadzi do $N(())$, czyli postkondycji normalnego zakończenia pętli; `continue` — do $J$.

=== Wywołania

Dla $Sigma(f)$ z warunkami $P_f$, $Q_f$, miarą $t_f$ i wywołania w ciele funkcji $g$:

$ wp(f(overline(e), \&overline(mu)), Q) = wp(overline(e), lambda overline(v). "ob"_(kappa_"pre") (P_f [overline(v) slash overline(x), overline(mu) slash overline(m)], thick "ob"_(kappa_"term") (T, thick Psi))) $

$ Psi = forall r, overline(mu'). thick Q_f [overline(v) slash overline(x), overline(mu) slash old(overline(m)), overline(mu') slash overline(m), r slash "result"] => N(r)[overline(mu') slash overline(mu)] $

Obligacja terminacji $T = 0 <= t_f [overline(v) slash overline(x), overline(mu) slash overline(m)] < t_g^0$
występuje wtedy i tylko wtedy, gdy $f$ i $g$ należą do tej samej silnie spójnej składowej
grafu wywołań oraz $"Div" in.not epsilon_g$; $t_g^0$ to wartość miary $g$ przy wejściu.
W pozostałych przypadkach $T = top$.

Kwantyfikacja tylko po $overline(mu')$ (a nie po wszystkich zmiennych) jest poprawna dzięki
*własności ramki* (lemat 8.3): wywołanie może zmienić wyłącznie lokacje przekazane jako `inout`.

Wywołanie domknięcia $e(overline(e'))$ o typie $(overline(\{nu : tau | phi\})) ->^epsilon \{nu : sigma | psi\}$
daje obligację $and.big_i phi_i (v_i)$ rodzaju `pre` i hipotezę $psi(r)$ dla wyniku. Utworzenie
domknięcia $"fn"(overline(x)) => e$ generuje w miejscu utworzenia koniunkcję
$forall overline(x). H(overline(x) : overline(tau)) => wp(e, chevron.l psi, top, top, psi chevron.r)$, w której
zobowiązania $psi$ mają rodzaj `post`.

=== Zobowiązania jawne, sprawdzenia, dziury i aktorzy

$ wp("assert"[kappa] phi, Q) &= "ob"_kappa (phi, N(())) \
  wp("check"[kappa] phi, Q) &= phi => N(()) \
  wp("snap"[kappa] t_0 := t "in" e, Q) &= wp(e, Q)[t slash t_0] \
  wp("hole"[h], Q) &= top \
  wp("recv"(mu), Q) &= forall v. h(v, M) => N(v) \
  wp("send"(e_1, e_2), Q) &= wp((e_1, e_2), lambda (c, v). "ob"_kappa (h(v, M), N(()))) $

Dziura jest interpretowana *anielsko* ($top$): zobowiązania na ścieżkach przez dziurę są
spełnione. W zamian raport dziury (§9.5) zawiera jej *cel*: predykat $N$ (oraz $B, C, R$),
który musi spełniać wartość wstawiona w miejsce dziury.

=== Warunek weryfikacji funkcji

Dla $f$ z parametrami $overline(x) : overline(tau)$, $overline(m) : overline(sigma)$, warunkami $P, Q$,
miarą $t$ i ciałem $e$ oraz zobowiązania $kappa^*$ leżącego w $f$:

$ Q_"ret" = chevron.l lambda nu. "ob"_(kappa_"post") (Q[nu slash "result"], top), thick top, thick top, thick lambda nu. "ob"_(kappa_"post") (Q[nu slash "result"], top) chevron.r $

$ VC_(kappa^*)(f) = forall overline(x), overline(m). thick H(overline(x) : overline(tau), overline(m) : overline(sigma)) and P => wp(e, Q_"ret")[overline(m) slash old(overline(m)), t slash t^0] $

Podstawienie $[overline(m) slash old(overline(m))]$ utożsamia wartości początkowe parametrów `inout`
z ich wartościami przy wejściu, a $t^0$ — wartość miary przy wejściu — z $t$.

Program jest *zweryfikowany*, gdy $tack.r.double VC_kappa (f)$ dla każdego zobowiązania $kappa$ każdej funkcji $f$.

=== Miary

Miara `decreases t` (funkcji, pętli lub funkcji specyfikacyjnej) jest termem typu `Int` albo
typu danych $T chevron.l overline(tau) chevron.r$. Dla typu danych miarą jest *ranga*:

$ "rank"_T (C(v_1, dots, v_n)) = 1 + sum_(i : tau_i = T chevron.l overline(tau) chevron.r) "rank"_T (v_i) $

czyli liczba węzłów wartości wzdłuż pól tego samego typu. Ranga jest dodatnia, więc warunek
nieujemności jest spełniony trywialnie (procedura decyzyjna otrzymuje aksjomat
$forall x. "rank"_T (x) >= 1$), a warunek spadku $"rank"(t') < "rank"(t)$ zachodzi dla każdej ścisłej
podstruktury: argument wywołania rekurencyjnego musi być polem (lub polem pola) wartości
dopasowanej do parametru. Spadek rangi jest dobrze ufundowany, bo wartości są drzewami skończonymi.

== Rodzaje zobowiązań

#table(
  columns: (auto, 1fr, auto, auto),
  inset: 4.5pt,
  stroke: 0.4pt + luma(200),
  [*Rodzaj*], [*Źródło*], [*Jawne?*], [*Kod błędu*],
  [`pre`], [warunek wstępny wywoływanej funkcji (w tym uściślenia parametrów)], [tak], [E4010],
  [`post`], [warunek końcowy (w tym uściślenie wyniku)], [tak], [E4020],
  [`inv-init`], [niezmiennik pętli przy wejściu], [tak], [E4030],
  [`inv-pres`], [zachowanie niezmiennika przez obrót pętli], [tak], [E4031],
  [`var-nn`], [nieujemność wariantu], [tak], [E4040],
  [`var-dec`], [spadek wariantu], [tak], [E4041],
  [`term`], [spadek miary w wywołaniu rekurencyjnym (funkcja / funkcja specyfikacyjna)], [tak], [E4042 / E4043],
  [`refine`], [uściślenie przy wiązaniu lub przypisaniu], [tak], [E4050],
  [`data-inv`], [niezmiennik typu danych przy konstrukcji], [tak], [E4051],
  [`assert`], [instrukcja `assert`], [tak], [E4060],
  [`wd`], [dobra określoność formuły], [tak], [E4070],
  [`unreach`], [osiągalność końca dopasowania], [tak], [E4080],
  [`bounds`], [indeks w zakresie], [nie], [E4110],
  [`overflow`], [brak przepełnienia], [nie], [E4120],
  [`div0`], [dzielnik niezerowy i brak przepełnienia dzielenia], [nie], [E4130],
  [`example`], [przykład z bloku `examples`], [tak], [E4300],
  [`property`], [test właściwości `forall`], [tak], [E4310],
)

Zobowiązania *jawne* wynikają ze specyfikacji napisanej przez użytkownika; *niejawne* — z semantyki
operacji. Rozróżnienie wpływa na rozstrzyganie kontrprzykładów indukcyjnych (§6.6).

== Rozstrzyganie zobowiązań

=== Interfejs procedury decyzyjnej

Procedura decyzyjna to funkcja $solve_beta : "Formuła" -> {"Valid", "Invalid"(M), "Unknown"}$
z budżetem $beta in NN$ mierzonym w krokach wnioskowania (nie w czasie). Implementacja *musi*
spełniać:

#table(
  columns: (auto, 1fr),
  stroke: none,
  inset: (x: 4pt, y: 3pt),
  [*(S1)*], [_Poprawność:_ $solve_beta (Psi) = "Valid" => tack.r.double Psi$.],
  [*(S2)*], [_Walidowane kontrprzykłady:_ $solve_beta (Psi) = "Invalid"(M) => M tack.r.double.not Psi$, przy czym implementacja sprawdza to bezpośrednim wartościowaniem $Psi$ w $M$ (każda formuła $F$ jest wykonywalna, tw. 8.8).],
  [*(S3)*], [_Determinizm:_ wynik zależy wyłącznie od $(Psi, beta)$ i wersji kompilatora.],
  [*(S4)*], [_Monotoniczność budżetu:_ jeśli $solve_beta (Psi) != "Unknown"$, to $solve_(beta') (Psi) = solve_beta (Psi)$ dla $beta' >= beta$.],
)

=== Klasyfikacja kontrprzykładów

Model $M$ zanegowanego $VC_kappa (f)$ przypisuje wartości parametrom $f$ oraz zmiennym
kwantyfikowanym wewnątrz warunku (zmienne pętli po „havoc”, wyniki wywołań). Kontrprzykład jest:

- *rzeczywisty*, gdy wykonanie $f$ na wartościach parametrów z $M$ (interpreter jądra, budżet
  kroków, bez kapabilności) kończy się naruszeniem $kappa$ — wtedy dołącza się ślad wykonania;
  także gdy $kappa$ leży na ścieżce bez pętli i wywołań (wtedy $M$ jest rzeczywisty z konstrukcji);
- *indukcyjny*, w pozostałych przypadkach: stan z $M$ spełnia hipotezy (niezmienniki, postkondycje
  wywołań), ale może być nieosiągalny. Diagnoza brzmi wówczas: _niezmiennik lub kontrakt wywoływanej
  funkcji jest za słaby_.

Gdy $f$ wymaga kapabilności, odtworzenie nie jest wykonywane i kontrprzykład otrzymuje status
`not-replayable`.

=== Status i przekształcenie programu

Dla każdego zobowiązania $kappa$ z formułą $phi_kappa$:

#table(
  columns: (auto, 1fr),
  inset: 5pt,
  stroke: 0.4pt + luma(200),
  [*Wynik*], [*Skutek*],
  [Valid], [Status `proved`. Węzeł $"assert"[kappa]$ jest usuwany; dla zobowiązań niejawnych sprawdzenie dynamiczne (granic, przepełnienia, dzielenia) jest *eliminowane* z kodu.],
  [Unknown], [Najpierw *próba obalenia testowaniem*: deterministycznie generowane wejścia spełniające warunki wstępne (ziarno wyznaczone z identyfikatora zobowiązania) są wykonywane w interpreterze; naruszenie tego samego zobowiązania daje status `refuted` z kontrprzykładem rzeczywistym (zminimalizowanym). W przeciwnym razie status `unknown`: węzeł zastępowany przez $"check"[kappa] phi_kappa$ (dla niejawnych zostaje sprawdzenie dynamiczne), ostrzeżenie `W4200` z listą „niedowiedzionych obietnic”. W funkcjach specyfikacyjnych i lematach `unknown` jest błędem.],
  [Invalid, rzeczywisty], [Status `refuted`. Błąd kompilacji o kodzie z tabeli §6.5.],
  [Invalid, indukcyjny, jawne], [Status `refuted`. Błąd kompilacji.],
  [Invalid, indukcyjny, niejawne], [Status `refuted-inductive`. Ostrzeżenie `W4400`, sprawdzenie dynamiczne pozostaje.],
)

Wymienione przekształcenie oznaczamy $cal(R)$; usuwa ono ponadto definicje i wywołania lematów.
Program wykonywalny to $cal(R)(cal(E)(P))$; nie zawiera on węzłów $"assert"$ ani $"hole"$. Domyślny budżet $beta$ jest stałą kompilatora; zmiana budżetu
może jedynie zamienić `unknown` na `proved` lub `refuted` (S4).

== Zaufana baza

Gwarancje rozdziału 8 zależą od następujących założeń, które kompilator wypisuje w raporcie
weryfikacji:

+ poprawność procedury decyzyjnej (S1);
+ kontrakty funkcji `extern` — przyjmowane bez dowodu; każde wywołanie `extern` ma ponadto
  sprawdzenie dynamiczne warunku końcowego, o ile jest on wykonywalny;
+ poprawność kompilatora z jądra do kodu docelowego (C lub WebAssembly) i środowiska wykonawczego;
+ zgodność modelu kosztów: nieobecność przepełnienia stosu wywołań nie jest gwarantowana
  (przepełnienie stosu jest pułapką `stack`, traktowaną jak $"Div"$).

= Dynamiczna semantyka

Semantyka jest zdefiniowana dla programów wykonywalnych $cal(R)(cal(E)(P))$ (bez węzłów
$"assert"$ i $"hole"$). Po przekształceniu $cal(R)$ adnotacje pętli nie mają znaczenia operacyjnego:
pozostałe sprawdzenia niezmienników i wariantów występują jako jawne węzły $"check"$ i $"snap"$
na początku obliczania warunku i na końcu ciała pętli, a odwołania do $old(m)$ są zastępowane
zmiennymi migawkowanymi przy wejściu do funkcji.

== Konfiguracje i zdarzenia

Pamięć to skończona funkcja częściowa $sigma : "Loc" harpoon "Val"$. Konfiguracja pojedynczego
aktora to para $chevron.l e, sigma chevron.r$. Przejścia są etykietowane zdarzeniami
$alpha ::= tau | K."op"(overline(v))$, gdzie $tau$ oznacza krok wewnętrzny, a $K."op"(overline(v))$
— obserwowalne użycie kapabilności $K$ (np. $"Io"."print"(s)$). Piszemy $arrow.r$ zamiast $arrow.r^tau$.

Wartości semantyczne są *drzewami skończonymi*: gramatyka wartości (§3.2) nie zawiera lokacji,
więc wartość nie może wskazywać na pamięć. Tablica w pamięci jest wartością, a zapis elementu
tworzy (semantycznie) nową wartość.

== Konteksty obliczeń

```
E  ::=  [ ]
     |  let x = E in e  |  var m : τ = E in e
     |  op(v̄, E, ē)  |  C⟨τ̄⟩(v̄, E, ē)  |  [v̄, E, ē]
     |  if E then e else e  |  match E { … }
     |  ℓ := E  |  ℓ[E] := e  |  ℓ[v] := E
     |  f⟨τ̄,ε̄⟩(v̄, E, ē, &ℓ̄)  |  E(ē)  |  v(v̄, E, ē)
     |  return E  |  send(E, e)  |  send(v, E)  |  spawn a(v̄, E, ē)
     |  ret{E}  |  brk{E}  |  cnt{E}
```

Konteksty ograniczone: $E_r$ — bez ramek $"ret"$; $E_b$ — bez ramek $"brk"$ i $"ret"$;
$E_c$ — bez ramek $"cnt"$ i $"ret"$. Wiązanie zmiennych w kontekstach jest standardowe;
obliczanie przebiega od lewej do prawej.

== Reguły redukcji

=== Wiązania i pamięć

$ & "let" x = v "in" e & arrow.r & e[v slash x] && "(R-Let)" \
  & chevron.l "var" m : tau = v "in" e, sigma chevron.r & arrow.r & chevron.l e[ell slash m], sigma[ell |-> v] chevron.r quad ell in.not dom(sigma) && "(R-Var)" \
  & chevron.l !ell, sigma chevron.r & arrow.r & chevron.l sigma(ell), sigma chevron.r && "(R-Read)" \
  & chevron.l ell := v, sigma chevron.r & arrow.r & chevron.l (), sigma[ell |-> v] chevron.r && "(R-Write)" \
  & chevron.l ell[n] := v, sigma chevron.r & arrow.r & chevron.l (), sigma[ell |-> sigma(ell) chevron.l n |-> v chevron.r] chevron.r quad 0 <= n < |sigma(ell)| && "(R-WrEl)" \
  & chevron.l ell[n] := v, sigma chevron.r & arrow.r & chevron.l "trap"("bounds"), sigma chevron.r quad "w p.p." && "(R-WrElT)" $

Lokacja przydzielona przez R-Var jest martwa po zakończeniu obliczania $e$ (nie występuje
w żadnej wartości ani w kontynuacji); implementacja zwalnia ją przy wyjściu z zasięgu. Semantyka
nie modeluje zwalniania, bo nie ma ono obserwowalnych skutków.

=== Operacje pierwotne

$ & "add"(n_1, n_2) & arrow.r & n_1 + n_2 quad "gdy" MIN <= n_1 + n_2 <= MAX, "w p.p." "trap"("overflow") && "(R-Add)" \
  & "div"(n_1, 0) & arrow.r & "trap"("div0") && "(R-Div0)" \
  & "div"(MIN, -1) & arrow.r & "trap"("overflow") && "(R-DivOv)" \
  & "div"(n_1, n_2) & arrow.r & n_1 div n_2 quad "w p.p." && "(R-Div)" \
  & "get"([v_0, dots, v_(k-1)], n) & arrow.r & v_n quad "gdy" 0 <= n < k, "w p.p." "trap"("bounds") && "(R-Get)" \
  & len([v_0, dots, v_(k-1)]) & arrow.r & k && "(R-Len)" \
  & chevron.l "push"(\&ell, v), sigma chevron.r & arrow.r & chevron.l (), sigma[ell |-> sigma(ell) dot.op [v]] chevron.r && "(R-Push)" $

Pozostałe operacje (`sub`, `mul`, `rem`, porównania, `pop`, napisy) są zdefiniowane analogicznie
w dodatku B.

=== Sterowanie

$ & "if" "true" "then" e_1 "else" e_2 & arrow.r & e_1 && "(R-IfT)" \
  & "if" "false" "then" e_1 "else" e_2 & arrow.r & e_2 && "(R-IfF)" \
  & "match" v { p_1 "when" g_1 => e_1, rho } & arrow.r & "if" g_1 theta "then" e_1 theta "else" "match" v { rho } quad "gdy" "match"(p_1, v) = theta && "(R-Match)" \
  & "match" v { p_1 "when" g_1 => e_1, rho } & arrow.r & "match" v { rho } quad "gdy" "match"(p_1, v) "nie istnieje" && "(R-MatchN)" \
  & "match" v { } & arrow.r & "trap"("unreachable") && "(R-Match0)" $

$ & "while" c "do" s & arrow.r & "brk"{"iter"(c, s)} && "(R-While)" \
  & "iter"(c, s) & arrow.r & "if" c "then" ("cnt"{s} ; "iter"(c, s)) "else" () && "(R-Iter)" \
  & "brk"{E_b ["break"]} & arrow.r & () && "(R-Brk)" \
  & "cnt"{E_c ["continue"]} & arrow.r & () && "(R-Cnt)" \
  & "ret"{E_r ["return" v]} & arrow.r & v && "(R-Ret)" \
  & "brk"{v} arrow.r () quad "cnt"{v} arrow.r v quad "ret"{v} & arrow.r & v && "(R-Frame)" $

=== Wywołania

$ & f chevron.l overline(tau), overline(epsilon) chevron.r (overline(v), \&overline(ell)) & arrow.r & "ret"{e_f [overline(tau) slash overline(alpha)][overline(v) slash overline(x)][overline(ell) slash overline(m)]} quad "gdy" ell_i "parami różne" && "(R-Call)" \
  & ("fn"(overline(x) : overline(tau)) => e)(overline(v)) & arrow.r & "ret"{e[overline(v) slash overline(x)]} && "(R-App)" $

Parametr `inout` jest wiązany *bezpośrednio z lokacją* wywołującego. Nie ma kopiowania przy
wejściu i wyjściu: semantyka „przez lokację” jest równoważna semantyce copy-in/copy-out dzięki
prawu wyłączności (lemat 8.3).

=== Sprawdzenia i pułapki

$ & chevron.l "check"[kappa] phi, sigma chevron.r & arrow.r & chevron.l (), sigma chevron.r quad "gdy" [| phi |]_sigma = "true" && "(R-Chk)" \
  & chevron.l "check"[kappa] phi, sigma chevron.r & arrow.r & chevron.l "trap"("contract"(kappa)), sigma chevron.r quad "gdy" [| phi |]_sigma = "false" && "(R-ChkF)" \
  & chevron.l "snap"[kappa] t_0 := t "in" e, sigma chevron.r & arrow.r & chevron.l e[[| t |]_sigma slash t_0], sigma chevron.r && "(R-Snap)" \
  & E["trap"(k)] & arrow.r & "trap"(k) quad E != [ ] && "(R-Trap)" $

$[| phi |]_sigma$ to wartościowanie formuły, w którym lokacje są odczytywane z $sigma$; jest
zawsze zdefiniowane i obliczalne (tw. 8.8). Pułapka kończy wykonanie całego programu
z kodem wyjścia zależnym od rodzaju $k$.

=== Kapabilności

$ & chevron.l "print"("cap"chevron.l "Io" chevron.r, s), sigma chevron.r & arrow.r^("Io.print"(s)) & chevron.l (), sigma chevron.r && "(R-Print)" \
  & chevron.l "read_line"("cap"chevron.l "Io" chevron.r), sigma chevron.r & arrow.r^("Io.read"(r)) & chevron.l r, sigma chevron.r quad r in "Option"chevron.l "Str" chevron.r && "(R-ReadLine)" $

Wejście z otoczenia jest jedynym źródłem niedeterminizmu w obrębie aktora: dla ustalonego
ciągu odpowiedzi otoczenia wykonanie jest deterministyczne.

=== Domknięcie kontekstowe

#rules(
  infer("R-Ctx", $chevron.l E[e], sigma chevron.r arrow.r^alpha chevron.l E[e'], sigma' chevron.r$,
    $chevron.l e, sigma chevron.r arrow.r^alpha chevron.l e', sigma' chevron.r$),
)

== Aktorzy

Konfiguracja programu to skończony multizbiór aktorów
$Pi = {chevron.l a_i, e_i, sigma_i, q_i chevron.r}$, gdzie $q_i$ jest kolejką wiadomości (ciągiem
wartości). Pamięci aktorów są rozłączne. Reguły (zapis $Pi parallel A$ oznacza multizbiór z wyróżnionym aktorem $A$):

#rules(
  infer("A-Local", $Pi parallel chevron.l a, e, sigma, q chevron.r arrow.r^alpha Pi parallel chevron.l a, e', sigma', q chevron.r$,
    $chevron.l e, sigma chevron.r arrow.r^alpha chevron.l e', sigma' chevron.r$),
)

#rules(
  infer("A-Spawn", $Pi parallel chevron.l a, E["spawn" b(c, overline(v))], sigma, q chevron.r arrow.r Pi parallel chevron.l a, E["chan"(b')], sigma, q chevron.r parallel chevron.l b', "ret"{e_b [overline(v) slash overline(x)][ell slash "mb"]}, {ell |-> "mbox"(b')}, epsilon chevron.r$,
    $c = "cap"chevron.l "Spawn" chevron.r$, $b' "świeży"$),
)

#rules(
  infer("A-Send", $Pi parallel chevron.l a, E["send"("chan"(b), v)], sigma, q chevron.r parallel chevron.l b, e_b, sigma_b, q_b chevron.r arrow.r Pi parallel chevron.l a, E[()], sigma, q chevron.r parallel chevron.l b, e_b, sigma_b, q_b dot.op v chevron.r$),
)

#rules(
  infer("A-Recv", $Pi parallel chevron.l a, E["recv"(ell)], sigma, v dot.op q chevron.r arrow.r Pi parallel chevron.l a, E[v], sigma, q chevron.r$,
    $sigma(ell) = "mbox"(a)$),
)

Wysłanie do aktora zakończonego jest operacją pustą. `recv` przy pustej kolejce blokuje aktora.
Ponieważ wartości nie zawierają lokacji, wysłanie wartości *kopiuje* drzewo, a aktorzy nie
współdzielą stanu mutowalnego — wyścigi danych są niemożliwe z konstrukcji.

== Zachowanie obserwowalne

Program startuje z konfiguracji złożonej z jednego aktora wykonującego $"main"("caps")$, gdzie
$"caps"$ zawiera wszystkie kapabilności. *Zachowanie* programu to zbiór śladów zdarzeń
obserwowalnych zakończonych jednym z: $"exit"(n)$ (gdy $"main"$ zwróci $n$; pozostali aktorzy są
wtedy kończeni), $"trap"(k)$, albo nieskończonych. Planista aktorów jest niedeterministyczny
z założeniem słabej sprawiedliwości.

#uwaga[
  Implementacja realizuje zapis elementu tablicy i `push` *w miejscu*. Jest to poprawne, bo
  w każdym osiągalnym stanie wartość przechowywana w lokacji nie jest współdzielona z żadną
  inną lokacją ani zmienną (wartości są kopiowane przy odczycie). Implementacja może unikać
  kopiowania przez zliczanie referencji z kopiowaniem przy zapisie (copy-on-write); tożsamość
  obserwowalna obu strategii wynika z braku lokacji w wartościach.
]

= Metateoria

Rozdział formułuje gwarancje języka. Dowody mają postać szkiców; ich status i ocenę ryzyka
podsumowuje §8.4. Do typowania konfiguracji czasu wykonania używa się dodatkowych reguł dla
ramek: $Gamma, "ret" : tau tack.r e : tau ! epsilon$ daje $Gamma tack.r "ret"{e} : tau ! epsilon$;
$Gamma, "loop" tack.r e : "Unit" ! epsilon$ daje $Gamma tack.r "brk"{e} : "Unit" ! epsilon$ oraz
$Gamma tack.r "cnt"{e} : "Unit" ! epsilon$; pamięć jest dobrze typowana ($Lambda tack.r sigma$), gdy
$dom(sigma) = dom(Lambda)$ i $dot ; dot ; Lambda tack.r sigma(ell) : Lambda(ell) ! emptyset$ dla każdej lokacji.

== Bezpieczeństwo pamięci i brak aliasingu

#lemat(title: "brak lokacji w wartościach")[
  W każdej konfiguracji osiągalnej z programu wykonywalnego: (a) żadna wartość nie zawiera
  lokacji; (b) żadna wartość w $sigma$ nie zawiera lokacji; (c) ciało każdego domknięcia nie zawiera
  lokacji ani zmiennych mutowalnych.
]
#dowod[Indukcja po długości wykonania. Gramatyka wartości nie ma lokacji. Jedyną regułą
  wprowadzającą lokację do wyrażenia jest R-Var (podstawienie $ell$ za $m$) i R-Call
  (za parametry `inout`). Podstawienie nie może umieścić lokacji w ciele domknięcia, bo na mocy
  T-Lam ciało domknięcia nie ma wolnych zmiennych mutowalnych. Odczyt R-Read zwraca $sigma(ell)$,
  które z (b) nie zawiera lokacji; zapisy umieszczają w $sigma$ wyłącznie wartości.]

#lemat(title: "injektywność wiązań mutowalnych")[
  W każdej osiągalnej konfiguracji, w obrębie każdej ramki $"ret"{dots}$, różne zmienne mutowalne
  wiązane w tej aktywacji są związane z różnymi lokacjami. W szczególności warunek poboczny
  reguły R-Call jest zawsze spełniony dla programów dobrze typowanych.
]
#dowod[R-Var przydziela lokację świeżą. W R-Call parametry `inout` otrzymują lokacje
  $overline(ell)$, które są obrazami parami różnych celów $overline(mu)$ (przesłanka T-Call);
  z założenia indukcyjnego dla aktywacji wywołującej różne cele wskazują różne lokacje.]

#lemat(title: "własność ramki")[
  Jeśli $chevron.l f(overline(v), \&overline(ell)), sigma chevron.r arrow.r^* chevron.l v, sigma' chevron.r$
  w jednym aktorze, to $sigma'(ell) = sigma(ell)$ dla każdego $ell in dom(sigma) without {overline(ell)}$.
  To samo dotyczy wykonań kończących się pułapką (w chwili pułapki).
]
#dowod[Po R-Call wyrażenie $"ret"{e_f [dots]}$ zawiera tylko lokacje $overline(ell)$: ciało $f$ jest
  zamknięte poza parametrami, a z lematu 8.1 podstawione wartości nie wnoszą lokacji. Każdy krok
  redukcji zapisuje wyłącznie lokację występującą w redeksie, a nowe lokacje są świeże. Indukcja po
  długości wykonania pokazuje, że zbiór lokacji w wyrażeniu jest zawsze podzbiorem
  $overline(ell)$ i lokacji świeżych.]

Lemat 8.3 jest semantycznym rdzeniem prawa wyłączności: uzasadnia kwantyfikację tylko po
$overline(mu')$ w regule wywołania (§6.4) oraz implementację zapisów w miejscu.

#twierdzenie(title: "bezpieczeństwo typów")[
  Niech $dot ; dot ; Lambda tack.r e : tau ! epsilon$, $Lambda tack.r sigma$, a $e$ nie zawiera dziur
  ani nieobjętych ramkami `break`, `continue`, `return`. Wtedy:
  + (_postęp_) $e$ jest wartością, $e = "trap"(k)$, $e$ jest zablokowane na $"recv"$ z pustą kolejką, albo istnieje krok $chevron.l e, sigma chevron.r arrow.r^alpha chevron.l e', sigma' chevron.r$;
  + (_zachowanie_) jeśli $chevron.l e, sigma chevron.r arrow.r^alpha chevron.l e', sigma' chevron.r$, to istnieje $Lambda' supset.eq Lambda$ takie, że $dot ; dot ; Lambda' tack.r e' : tau ! epsilon$ i $Lambda' tack.r sigma'$.
]
#dowod[Standardowa indukcja po wyprowadzeniu typu (postęp) i po regule redukcji (zachowanie)
  z lematami o podstawieniu dla zmiennych niemutowalnych, mutowalnych (podstawienie lokacji)
  i typów. Przypadek R-Call korzysta z lematu 8.2. Przypadki sterowania korzystają z niezmiennika,
  że `break` występuje tylko w kontekście $E_b$ wewnątrz ramki $"brk"$ (wpis $"loop"$ jest
  dodawany wyłącznie przez T-While i usuwany przez T-Lam), i analogicznie dla `continue` i `return`.]

== Poprawność weryfikacji

#twierdzenie(title: "poprawność warunków weryfikacji")[
  Załóżmy, że każde zobowiązanie każdej funkcji programu ma status `proved`. Wtedy dla każdej
  funkcji $f$ i każdej pamięci, w której argumenty spełniają $H and P_f$, wykonanie
  $f(overline(v), \&overline(ell))$:
  + nie kończy się pułapką innego rodzaju niż $"stack"$;
  + jeśli się kończy, to wartość wyniku $r$ oraz końcowe wartości $overline(ell)$ spełniają $Q_f$ (z $old(overline(m))$ równym wartościom początkowym) i hipotezy typu wyniku.
]
#dowod[Definiujemy semantyczną trójkę Hoare'a $tack.r.double {Phi} e {Q}$ dla czwórek $Q$ i pokazujemy
  indukcją po strukturze $e$ (z indukcją po długości wykonania dla pętli i rekursji), że
  $tack.r.double {wp(e, Q)} e {Q}$. Przypadek pętli: niezmiennik zachodzi na początku (`inv-init`),
  jest zachowywany (`inv-pres`) przy dowolnych wartościach zmiennych $overline(w)$, a wartości spoza
  $overline(w)$ nie zmieniają się w ciele (analiza syntaktyczna $ws$). Przypadek wywołania: postkondycja
  wywoływanej funkcji zachodzi z założenia indukcyjnego (po długości wykonania), a pozostała
  część pamięci jest niezmieniona z lematu 8.3. Na koniec: z prawdziwości wszystkich
  $VC_kappa$ wynika prawdziwość warunku z wszystkimi zobowiązaniami jako koniunkcjami
  (indukcja po liczbie zobowiązań na ścieżce: pierwsze naruszone zobowiązanie przeczyłoby
  odpowiadającemu mu $VC_kappa$, którego hipotezy są wtedy spełnione).]

#twierdzenie(title: "poprawność weryfikacji stopniowanej")[
  Niech $P' = cal(R)(cal(E)(P))$ dla programu bez zobowiązań o statusie `refuted`. Wtedy każde
  wykonanie $P'$ ma jedną z postaci: kończy się normalnie, kończy się pułapką
  $"trap"("contract"(kappa))$ lub pułapką niejawną dla zobowiązania $kappa$ o statusie `unknown` albo
  `refuted-inductive`, kończy się pułapką $"stack"$, albo jest nieskończone. Ponadto w każdym
  punkcie wykonania osiągającym zobowiązanie o statusie `proved` jego formuła jest prawdziwa.
]
#dowod[Przypuśćmy, że w pewnym wykonaniu formuła zobowiązania o statusie `proved` jest fałszywa.
  Rozważmy *pierwsze* w porządku wykonania naruszenie dowolnego zobowiązania. Nie jest to
  zobowiązanie sprawdzane dynamicznie, bo jego naruszenie kończy wykonanie pułapką przed
  kontynuacją. Jest to więc zobowiązanie $kappa$ o statusie `proved`. Hipotezy $VC_kappa$ to
  formuły zobowiązań napotkanych wcześniej na tej ścieżce wykonania (w tym postkondycje
  wywołań i niezmienniki z poprzednich obrotów pętli), które z minimalności były prawdziwe.
  Z tw. 8.5 (zastosowanego do wyrażeń, a nie tylko całych funkcji) w osiągniętym stanie zachodzi
  $phi_kappa$ — sprzeczność. Pierwsza część wynika z tw. 8.4 i z tego, że jedynymi źródłami pułapek
  są zobowiązania niejawne i sprawdzenia.]

To twierdzenie jest formalnym uzasadnieniem zasady Z6: niedowiedziona obietnica nigdy nie
prowadzi do zachowania niezdefiniowanego, a jedynie do kontrolowanej pułapki w miejscu, które
jest wskazane w raporcie kompilacji.

== Efekty, terminacja, wykonywalność

#twierdzenie(title: "poprawność efektów i terminacja")[
  Niech $dot ; dot ; Lambda tack.r e : tau ! epsilon$. Wtedy:
  + każde zdarzenie $K."op"(overline(v))$ emitowane w wykonaniu $e$ spełnia $K in epsilon$;
  + jeśli $"Div" in.not epsilon$ i $e$ jest wyrażeniem programu wykonywalnego, to każde wykonanie $e$ jest skończone (kończy się wartością lub pułapką), bez względu na statusy zobowiązań `var-nn`, `var-dec` i `term`.
]
#dowod[(1) Przez zachowanie typów z efektami: każda reguła emitująca zdarzenie $K$ wymaga typu
  $"Cap"chevron.l K chevron.r$ i dodaje $K$ do efektu (T-Prim). (2) Pętle w $e$ mają wariant
  (inaczej T-WhileDiv dodałoby $"Div"$). Każdy obrót albo zmniejsza nieujemną miarę całkowitą, albo
  — gdy odpowiednie zobowiązanie nie zostało udowodnione — wykonuje sprawdzenie, które przy
  naruszeniu kończy wykonanie pułapką. Analogicznie wywołania rekurencyjne w obrębie silnie
  spójnej składowej zmniejszają miarę lub kończą się pułapką. Wywoływane funkcje spoza składowej
  są totalne z założenia indukcyjnego po porządku topologicznym grafu składowych. `recv` ma
  efekt $"Div"$, więc nie występuje. Zatem miara leksykograficzna (pozycja w porządku
  topologicznym, miara wywołania, miary pętli) maleje dobrze ufundowanie; dla miar strukturalnych
  ranga jest liczbą naturalną malejącą przy przejściu do podstruktury (§6.4).]

#twierdzenie(title: "wykonywalność kontraktów")[
  Dla każdej formuły $phi in F$ i każdego wartościowania jej zmiennych wolnych spełniającego
  $wd(phi)$ wartość $[| phi |]$ jest określona i obliczalna. Ponadto funkcja specyfikacyjna rekurencyjna
  jest dopuszczona wyłącznie wtedy, gdy jej zobowiązanie `term` ma status `proved` (w przeciwnym
  razie błąd `E4043`).
]
#dowod[Indukcja po strukturze $phi$. Kwantyfikatory są ograniczone do skończonych przedziałów
  liczb całkowitych, więc są obliczalne przez wyliczenie. Termy częściowe są określone na mocy
  $wd(phi)$. Funkcje specyfikacyjne są totalne. Jeżeli zobowiązanie `wd` formuły ma status `unknown`,
  przekształcenie $cal(R)$ wstawia sprawdzenie $wd(phi)$ przed sprawdzeniem $phi$, więc
  wartościowanie zawsze odbywa się przy spełnionym $wd(phi)$.]

#twierdzenie(title: "forma kanoniczna")[
  Dla każdego drzewa składni $A$: $parse(fmt(A)) = A$ (z dokładnością do pozycji w źródle).
  W konsekwencji $fmt compose parse$ jest idempotentna na tekstach poprawnych składniowo.
]
#dowod[$fmt$ wypisuje nawiasy wszędzie tam, gdzie priorytety z §2.4 wymagają ich do odtworzenia
  drzewa, i łamie wiersze tylko po tokenach, po których reguła układu (§2.2) nie wstawia średnika
  albo gdzie wstawiony średnik jest zgodny ze strukturą. Indukcja po $A$.]

#twierdzenie(title: "determinizm kompilacji")[
  Lista diagnostyk, statusy zobowiązań i kod wynikowy zależą wyłącznie od tekstu programu,
  wersji kompilatora i jawnych opcji kompilacji.
]
#dowod[Wszystkie fazy (parsowanie, elaboracja, typowanie, generowanie warunków, przykłady
  z budżetem kroków, testy właściwości z ziarnem wyznaczonym z tekstu) są deterministyczne; $solve_beta$
  spełnia (S3); diagnostyki są sortowane według pozycji w źródle i kodu.]

== Status dowodów

#table(
  columns: (auto, auto, 1fr),
  inset: 5pt,
  stroke: 0.4pt + luma(200),
  [*Wynik*], [*Status*], [*Ocena ryzyka*],
  [Lematy 8.1–8.3], [szkic], [niskie — konstrukcja standardowa dla języków z semantyką wartości i `inout` (por. Hylo, Swift)],
  [Tw. 8.4], [szkic], [niskie — standardowe bezpieczeństwo typów z ramkami sterowania],
  [Tw. 8.5], [szkic], [*średnie* — interakcja `break`/`continue`/`return` z niezmiennikami oraz z parametrami `inout` w wywołaniach zagnieżdżonych; wymaga starannej definicji $ws$],
  [Tw. 8.6], [szkic], [*średnie* — wymaga precyzyjnego wykazania, że hipotezy $VC_kappa$ to dokładnie zobowiązania napotkane wcześniej na ścieżce, także przez granice funkcji i domknięć],
  [Tw. 8.7–8.8], [szkic], [niskie],
  [Tw. 8.9–8.10], [zobowiązanie implementacyjne], [niskie — weryfikowalne testami właściwości implementacji],
  [Hipoteza 6.3], [otwarta], [wpływa tylko na kompletność, nie na poprawność],
)

Zalecana kolejność mechanizacji (Lean 4 lub Coq): jądro sekwencyjne bez aktorów z lematami
8.1–8.3 i tw. 8.4; następnie generator warunków weryfikacji i tw. 8.5–8.6; na końcu aktorzy.

= Diagnostyka

Format diagnostyki jest *normatywny*: jest częścią interfejsu języka, tak jak składnia.
Każda diagnostyka istnieje w dwóch równoważnych postaciach: tekstowej (dla człowieka)
i strukturalnej JSON (dla narzędzi i modeli). Postać tekstowa jest funkcją postaci JSON.

== Rekord diagnostyki

```
Diagnostic = {
  code:        string,                // np. "E4020"; stabilny między wersjami
  severity:    "error" | "warning" | "info" | "hole",
  span:        Span,                  // miejsce główne
  spec_ref:    string[],              // sekcje tej specyfikacji, np. ["6.4", "6.6"]
  message:     string,                // jedno zdanie, bez żargonu implementacji
  expected?:   string,                // typ, formuła lub wzorzec oczekiwany
  found?:      string,                // typ, formuła lub wzorzec znaleziony
  obligation?: { id: string, kind: string, formula: string,
                 status: "proved" | "unknown" | "refuted" | "refuted-inductive" },
  counterexample?: {
                 assignment: { [name: string]: string }, // składnia Rdzenia
                 class:  "real" | "inductive",
                 replay: "confirmed" | "not-reproduced" | "not-replayable",
                 trace?: Step[] },
  goal?:       HoleGoal,              // tylko dla severity = "hole" (§9.5)
  fix?:        { patch: string,       // ujednolicony diff
                 confidence: "unique" | "suggested" },
  related:     { span: Span, message: string }[]
}
Span = { file: string, line: int, col: int, end_line: int, end_col: int }
Step = { span: Span, bindings: { [name: string]: string } }
```

Poprawka o pewności `unique` jest jedyną zmianą minimalną usuwającą diagnostykę (np. brakujący
import, forma kanoniczna, brakujący przypadek wzorca z dziurą jako ciałem). Poprawka
`suggested` jest jedną z wielu możliwych.

== Klasy kodów

#table(
  columns: (auto, 1fr),
  inset: 5pt,
  stroke: 0.4pt + luma(200),
  [*Zakres*], [*Klasa*],
  [`E0xxx`], [leksyka, składnia, forma kanoniczna (`E0100`)],
  [`E1xxx`], [nazwy, moduły, widoczność],
  [`E2xxx`], [typy kształtu, inferencja, ograniczenia `Eq`/`Ord`, operator `?` (`E2140`)],
  [`E3xxx`], [efekty i kapabilności (m.in. wywołanie funkcji częściowej z totalnej)],
  [`E4xxx`, `W4xxx`], [weryfikacja: zobowiązania obalone (`E40xx`–`E41xx`), nieznane (`W4200`), indukcyjne niejawne (`W4400`), przykłady i właściwości (`E43xx`)],
  [`E5xxx`, `W5xxx`], [wyczerpywalność (`E5001`) i nieużyteczne gałęzie (`W5002`)],
  [`E6xxx`], [prawo wyłączności, ucieczka lokacji (`E6010`), formuły spoza fragmentu (`E6101`)],
  [`H7xxx`], [raporty dziur],
)

== Brak kaskady

Gdy przesłanka reguły typowania nie zachodzi dla podwyrażenia $e$, kompilator zgłasza diagnostykę
i zastępuje $e$ węzłem $"err"$ typowanym regułą

#rules(infer("T-Err", $Gamma tack.r "err" : tau ! emptyset$))

dla dowolnego $tau$ (unifikującego się z każdym typem). Zmienną wiązaną wyrażeniem zawierającym
$"err"$ oznacza się jako *skażoną*. Diagnostyka typowania jest tłumiona, jeśli dotyczy wyrażenia
zawierającego $"err"$ lub zmienną skażoną. W warunkach weryfikacji $"err"$ jest traktowany jak
dziura ($wp = top$), więc błąd typu nie generuje wtórnych błędów weryfikacji. Kompilator zgłasza
w jednym przebiegu wszystkie diagnostyki *niezależne*.

== Kontrprzykłady

Kontrprzykład podaje wartości wszystkich zmiennych występujących w zanegowanym warunku
weryfikacji, w składni Rdzenia (tak, by dało się je wkleić jako literały do bloku `examples`).
Zmienne pochodzące z „havoc” pętli są opisane pozycją pętli; wyniki wywołań — pozycją wywołania.
Dla kontrprzykładów rzeczywistych dołącza się ślad: ciąg kroków ze stanem zmiennych przy każdym
rozgałęzieniu i na początku każdego obrotu pętli.

== Raport dziury

Dla każdej dziury `?h` kompilator zgłasza diagnostykę o ważności `hole` zawierającą:

```
HoleGoal = {
  type:        string,               // oczekiwany typ kształtu
  goal:        string,               // predykat N(ν) z §6.4
  on_break?:   string, on_continue?: string, on_return?: string,
  hypotheses:  string[],             // fakty logiczne obowiązujące w miejscu dziury
  context:     { name: string, type: string, mutable: bool }[],
  effects:     string,               // efekty dozwolone w tym miejscu
  candidates:  { expr: string,
                 status: "satisfies" | "satisfies-if",
                 condition?: string }[]
}
```

Kandydatami są zmienne z kontekstu i wywołania funkcji o pasującym typie wyniku z argumentami
będącymi zmiennymi kontekstu (głębokość 1). Dla każdego kandydata $c$ kompilator rozstrzyga
$H and "hipotezy" => N(c)$ procedurą $solve_beta$; wynik `satisfies-if` podaje najsłabszy warunek
z rodziny warunków atomowych występujących w hipotezach, przy którym implikacja zachodzi.

== Raport weryfikacji

Po udanej kompilacji kompilator wypisuje raport: liczbę zobowiązań według rodzaju i statusu, listę
zobowiązań `unknown` i `refuted-inductive` (czyli miejsc, w których pozostały sprawdzenia
dynamiczne) oraz zaufaną bazę (§6.7) — w szczególności wszystkie funkcje `extern`, na których
kontraktach opiera się wynik.

== Przykłady diagnostyk

*Obalenie rzeczywiste (zobowiązanie niejawne).*

```
fn abs(x: Int) -> Int
    ensures result >= 0
{
    if x < 0 { -x } else { x }
}
```

```
error[E4120]: możliwe przepełnienie w negacji                 [spec 6.5, 7.3]
  --> src/num.rz:4:16
   |
 4 |     if x < 0 { -x } else { x }
   |                ^^ zobowiązanie overflow#1: int_min <= -x <= int_max
   = kontrprzykład (rzeczywisty, odtworzony):
       x = -9223372036854775808
       ślad: x < 0 → true;  -x → trap(overflow)
   = poprawka (sugerowana):
       1 | fn abs(x: Int) -> Int
       2 +     requires x > int_min
```

To samo w postaci JSON (skrócone):

```
{ "code": "E4120", "severity": "error",
  "span": { "file": "src/num.rz", "line": 4, "col": 16,
            "end_line": 4, "end_col": 18 },
  "spec_ref": ["6.5", "7.3"],
  "message": "możliwe przepełnienie w negacji",
  "obligation": { "id": "abs/overflow#1", "kind": "overflow",
                  "formula": "int_min <= -x && -x <= int_max",
                  "status": "refuted" },
  "counterexample": { "assignment": { "x": "-9223372036854775808" },
                      "class": "real", "replay": "confirmed" },
  "fix": { "confidence": "suggested", "patch":
    "@@ -1 +1,2 @@\n fn abs(x: Int) -> Int\n+    requires x > int_min\n" },
  "related": [] }
```

*Obalenie indukcyjne (za słaby niezmiennik).*

```
fn sum_nonneg(xs: Array<Nat>) -> Nat {
    var s = 0
    for x in xs {
        s = s + x
    }
    s
}
```

```
error[E4020]: warunek końcowy może nie zachodzić                [spec 6.4, 6.6]
  --> src/sum.rz:1:34
   |
 1 | fn sum_nonneg(xs: Array<Nat>) -> Nat {
   |                                  ^^^ uściślenie wyniku: result >= 0
   = kontrprzykład (indukcyjny — stan może być nieosiągalny):
       xs = []
       s = -1      (po pętli z wiersza 3)
   = odtworzenie: xs = [] daje s = 0, naruszenie nie występuje
   = przyczyna: pętla z wiersza 3 zapisuje s, a jej niezmiennik nie mówi nic o s
   = poprawka (sugerowana):
       3 -     for x in xs {
       3 +     for x in xs
       4 +         invariant s >= 0
       5 +     {
```

W tym samym przebiegu zgłaszane jest zobowiązanie `overflow` dla `s + x`. Po dodaniu
niezmiennika zostaje ono obalone rzeczywiście (np. `xs = [int_max, 1]`): suma tablicy liczb
naturalnych może przekroczyć zakres `Int`, więc trzeba użyć `checked_add` (dodatek B) albo
dodać warunek wstępny ograniczający sumę.

*Raport dziury.*

```
fn clamp(x: Int, lo: Int, hi: Int) -> Int
    requires lo <= hi
    ensures lo <= result && result <= hi
{
    if x < lo { lo } else { ?rest }
}
```

```
hole[H7001]: ?rest : Int                                       [spec 6.4, 9.5]
  --> src/clamp.rz:5:29
   = cel:        lo <= ν && ν <= hi
   = hipotezy:   lo <= hi,  !(x < lo)
   = kontekst:   x: Int, lo: Int, hi: Int
   = efekty:     ∅
   = kandydaci:  lo        spełnia
                 hi        spełnia
                 x         spełnia, jeśli x <= hi
```

*Niewyczerpujące dopasowanie.*

```
error[E5001]: dopasowanie nie jest wyczerpujące                [spec 5.6]
  --> src/io.rz:12:5
   = brakujący przypadek: Err(_)
   = gałąź `Err(e) if e.code == 0` ma strażnika i nie liczy się do pokrycia
   = poprawka (unique):
      14 +         Err(_) => ?todo,
```

#counter(heading).update(0)
#set heading(numbering: "A.1")

= Przykład kompletny: wyszukiwanie binarne <dodatek-a>

Rozdział informacyjny. Pokazuje program kanoniczny, fragment elaboracji i pełną listę
zobowiązań z oczekiwanymi statusami.

== Program

```
spec fn sorted(xs: Array<Int>) -> Bool =
    forall i in 0..xs.len: forall j in i..xs.len: xs[i] <= xs[j]

pub fn binary_search(xs: Array<Int>, target: Int) -> Option<Nat>
    requires sorted(xs)
    ensures match result {
        Some(i) => i < xs.len && xs[i] == target,
        None => forall k in 0..xs.len: xs[k] != target,
    }
    examples {
        binary_search([1, 3, 5], 3) == Some(1)
        binary_search([], 7) == None
        forall xs: Array<Int>, t: Int:
            !sorted(xs) || (binary_search(xs, t) != None) == contains(xs, t)
    }
{
    var lo = 0
    var hi = xs.len
    while lo < hi
        invariant 0 <= lo && lo <= hi && hi <= xs.len
        invariant forall k in 0..lo: xs[k] < target
        invariant forall k in hi..xs.len: xs[k] > target
        decreases hi - lo
    {
        let mid = lo + (hi - lo) / 2
        match compare(xs[mid], target) {
            Less => { lo = mid + 1 },
            Greater => { hi = mid },
            Equal => { return Some(mid) },
        }
    }
    None
}
```

Funkcja `contains` z testu właściwości pochodzi z preludium (dodatek B); funkcje
specyfikacyjne, takie jak `sorted`, są wykonywalne (tw. 8.8), więc można je wywoływać
w przykładach. Test właściwości generuje także tablice nieposortowane, dlatego ma postać implikacji.

== Fragment elaboracji

Ciało pętli po elaboracji (zmienne mutowalne jako odczyty $!m$, operatory jako operacje pierwotne):

```
while lt(!lo, !hi) inv I₁, I₂, I₃ dec (hi − lo) do
  let mid = add(!lo, div(sub(!hi, !lo), 2)) in
  let o = compare(get(xs, mid), target) in
  if test(Less, o) then lo := add(mid, 1)
  else if test(Greater, o) then hi := mid
  else if test(Equal, o) then return Some⟨Nat⟩(mid)
  else trap(unreachable)
```

== Zobowiązania

#table(
  columns: (auto, auto, 1fr, auto),
  inset: 4.5pt,
  stroke: 0.4pt + luma(200),
  [*Nr*], [*Rodzaj*], [*Treść (skrót)*], [*Status*],
  [1], [`wd`], [`requires`: indeksy `xs[i]`, `xs[j]` w zakresie dzięki granicom kwantyfikatorów], [proved],
  [2], [`wd`], [`ensures`: `xs[i]` przy `0 <= i` (hipoteza `Nat`) i `i < xs.len`], [proved],
  [3–5], [`wd`], [niezmienniki: indeksy w zakresach kwantyfikatorów], [proved],
  [6–8], [`inv-init`], [`lo = 0`, `hi = len`: zakresy kwantyfikatorów puste], [proved],
  [9], [`overflow`], [`hi − lo`: wynik w `[0, len]`], [proved],
  [10], [`div0`], [`(hi − lo) / 2`: dzielnik stały różny od zera i od `−1`], [proved],
  [11], [`overflow`], [`lo + (hi − lo) / 2 <= hi <= int_max`], [proved],
  [12], [`bounds`], [`get(xs, mid)`: `lo <= mid < hi <= len`], [proved],
  [13], [`overflow`], [`mid + 1 <= hi <= int_max`], [proved],
  [14–16], [`inv-pres`], [gałąź `Less`: `xs[k] <= xs[mid] < target` dla `k <= mid` z `sorted`], [proved],
  [17–19], [`inv-pres`], [gałąź `Greater`: `xs[k] >= xs[mid] > target` dla `k >= mid`], [proved],
  [20], [`var-nn`], [`hi − lo >= 0` z niezmiennika], [proved],
  [21–22], [`var-dec`], [`hi − (mid + 1) < hi − lo` oraz `mid − lo < hi − lo`], [proved],
  [23], [`post`], [`return Some(mid)`: `mid >= 0`, `mid < len`, `xs[mid] == target`], [proved],
  [24], [`post`], [wyjście z pętli: `lo = hi`, więc każdy `k` leży w jednym z zakresów], [proved],
  [25], [`unreach`], [dopasowanie wyczerpujące na `Ordering`], [proved],
  [26–27], [`example`], [oba przykłady obliczone do `true`], [passed],
  [28], [`property`], [256 przypadków, ziarno z tekstu funkcji], [passed],
)

Wszystkie zobowiązania należą do fragmentu $F_0$: kwantyfikatory w `sorted` i niezmiennikach
mają postać fragmentu własności tablic (strażniki indeksowe liniowe, wartości porównywane
liniowo). Program wykonywalny nie zawiera żadnego sprawdzenia dynamicznego — w szczególności
dostęp `xs[mid]` jest skompilowany bez kontroli granic.

= Preludium <dodatek-b>

Rozdział normatywny. Preludium jest importowane niejawnie do każdego modułu. Funkcje
wbudowane podano jako sygnatury z kontraktami, bez ciał; efekty funkcji z kapabilnościami podano
jawnie. Kontrakty funkcji wbudowanych należą do zaufanej bazy (§6.7).

```
data Option<T> { None, Some(value: T) }
data Result<T, E> { Ok(value: T), Err(error: E) }
data Ordering { Less, Equal, Greater }
data Caps { Caps(io: Cap<Io>, fs: Cap<Fs>, net: Cap<Net>, clock: Cap<Clock>,
                 rand: Cap<Rand>, ffi: Cap<Ffi>, spawn: Cap<Spawn>) }

type Nat = Int where self >= 0

const int_max: Int = 0x7FFF_FFFF_FFFF_FFFF
const int_min: Int = -int_max - 1

// ---- liczby całkowite ----
fn compare(a: Int, b: Int) -> Ordering
    ensures match result { Less => a < b, Equal => a == b, Greater => a > b }
fn min(a: Int, b: Int) -> Int
    ensures result <= a && result <= b && (result == a || result == b)
fn max(a: Int, b: Int) -> Int
    ensures result >= a && result >= b && (result == a || result == b)
fn checked_add(a: Int, b: Int) -> Option<Int>
    ensures match result { Some(c) => c == a + b,
                           None => a + b > int_max || a + b < int_min }
fn checked_mul(a: Int, b: Int) -> Option<Int>        // analogicznie
fn wrapping_add(a: Int, b: Int) -> Int               // arytmetyka modulo 2^64

// ---- tablice ----
fn push<T>(inout a: Array<T>, v: T)
    requires a.len < int_max
    ensures a.len == old(a).len + 1 && a[a.len - 1] == v
    ensures forall k in 0..old(a).len: a[k] == old(a)[k]
fn pop<T>(inout a: Array<T>) -> Option<T>
    ensures match result {
        None => old(a).len == 0 && a.len == 0,
        Some(v) => a.len == old(a).len - 1 && v == old(a)[a.len]
                   && forall k in 0..a.len: a[k] == old(a)[k],
    }
fn filled<T>(n: Nat, v: T) -> Array<T>
    ensures result.len == n && forall k in 0..n: result[k] == v
fn contains<T: Eq>(a: Array<T>, v: T) -> Bool
    ensures result == exists k in 0..a.len: a[k] == v
fn slice<T>(a: Array<T>, from: Nat, to: Nat) -> Array<T>
    requires from <= to && to <= a.len
    ensures result.len == to - from
    ensures forall k in 0..result.len: result[k] == a[from + k]

// ---- napisy (Str jest w logice tablicą bajtów) ----
fn str_concat(a: Str, b: Str) -> Str
    ensures result.len == a.len + b.len
fn str_eq(a: Str, b: Str) -> Bool                    // równoważne a == b
fn parse_int(s: Str) -> Option<Int>
fn int_to_str(n: Int) -> Str

// ---- liczby zmiennoprzecinkowe (poza logiką) ----
fn f64_add(a: F64, b: F64) -> F64                    // oraz sub, mul, div, sqrt
fn f64_eq(a: F64, b: F64) -> Bool                    // IEEE 754: NaN != NaN
fn int_to_f64(n: Int) -> F64
fn f64_to_int(x: F64) -> Option<Int>                 // None dla NaN i poza zakresem

// ---- kapabilności ----
fn print(io: Cap<Io>, s: Str) ! {Io}
fn read_line(io: Cap<Io>) -> Option<Str> ! {Io}
fn read_file(fs: Cap<Fs>, path: Str) -> Result<Str, IoError> ! {Fs}
fn write_file(fs: Cap<Fs>, path: Str, data: Str) -> Result<Unit, IoError> ! {Fs}
fn now(c: Cap<Clock>) -> Int ! {Clock}               // milisekundy od epoki
fn random(r: Cap<Rand>, lo: Int, hi: Int) -> Int ! {Rand}
    requires lo < hi
    ensures lo <= result && result < hi

data IoError { NotFound, PermissionDenied, Other(code: Int) }
```

Typy `Cap<K>`, `Chan<M>`, `Mailbox<M>` nie mają konstruktorów dostępnych w programie.
Implementacja może dodawać do preludium funkcje, jeśli każda z nich ma kontrakt w powyższej
postaci i jest zweryfikowana albo oznaczona jako zaufana w raporcie (§6.7).
