/-
SPDX-License-Identifier: MIT OR Apache-2.0

Rdzeń — mechanizacja fragmentu jądra (rozdz. 8 specyfikacji).

Fragment: instrukcje sekwencyjne z `break`/`continue`/`return`, pętle z niezmiennikiem
i wariantem, zobowiązania jawne i sprawdzenia dynamiczne oraz modularne wywołania procedur
z parametrami wartościowymi i `inout`. Wyrażenia i formuły są osadzone płytko (funkcje stanu),
a typ wartości `Val` jest dowolny — tablice i typy danych nie zmieniają struktury dowodów.

Każde zobowiązanie ma tryb (`Mode`) odpowiadający przekształceniu R (§6.6):
* `proved`  — zobowiązanie udowodnione; jego naruszenie jest obserwowane jako `fail`
              (wynik „niemożliwy”: twierdzenia pokazują, że przy poprawnym VC nie występuje);
* `checked` — sprawdzenie dynamiczne; naruszenie kończy wykonanie pułapką `trap`;
* `erased`  — zobowiązanie usunięte z programu wykonywalnego (brak sprawdzenia).
-/

namespace Rdzen

inductive Mode where
  | proved
  | checked
  | erased
  deriving DecidableEq, Repr

abbrev Var := String
abbrev State (Val : Type) := Var → Val

section
variable {Val : Type}

def upd (σ : State Val) (x : Var) (v : Val) : State Val :=
  fun y => if y = x then v else σ y

/-- Kolejne przypisania `xs := vs` (używane przy powrocie z wywołania dla celów `inout`). -/
def updMany (σ : State Val) : List Var → List Val → State Val
  | x :: xs, v :: vs => updMany (upd σ x v) xs vs
  | _, _ => σ

end

/-- Instrukcje fragmentu jądra. Pętla nosi znacznik `first` (pierwsze wejście: zobowiązanie
`inv-init` w trybie `mI`; kolejne obroty: `inv-pres` w trybie `mP`) oraz wariant `var`
z trybem `mV` (zobowiązania `var-nn`, `var-dec`). -/
inductive Stmt (Val : Type) where
  | skip
  | assign (x : Var) (e : State Val → Val)
  | seq (s t : Stmt Val)
  | ite (b : State Val → Bool) (s t : Stmt Val)
  | loop (first : Bool) (b : State Val → Bool) (inv : State Val → Bool) (mI mP : Mode)
      (var : State Val → Int) (mV : Mode) (body : Stmt Val)
  | brk
  | cont
  | ret (e : State Val → Val)
  | obl (m : Mode) (φ : State Val → Bool)
  /-- `x := f(args, &outs)`; `m` — tryb zobowiązania `pre` w tym miejscu wywołania. -/
  | call (m : Mode) (x : Var) (f : Nat) (args : List (State Val → Val)) (outs : List Var)

/-- Procedura z kontraktem: `post σ₀ σ v` łączy stan początkowy (wartości `old`), stan
końcowy i wynik. `mPost` — tryb zobowiązania `post` przy powrocie. -/
structure Proc (Val : Type) where
  params : List Var
  inouts : List Var
  pre : State Val → Bool
  post : State Val → State Val → Val → Bool
  mPost : Mode
  body : Stmt Val

abbrev Procs (Val : Type) := Nat → Proc Val

inductive Outcome (Val : Type) where
  | normal (σ : State Val)
  | brk (σ : State Val)
  | cont (σ : State Val)
  | ret (v : Val) (σ : State Val)
  | trap
  | fail
  | timeout

section
variable {Val : Type} [Inhabited Val]

/-- Zobowiązanie w semantyce: warunek prawdziwy — kontynuacja; fałszywy — zależnie od trybu. -/
def oblR (m : Mode) (c : Bool) (k : Outcome Val) : Outcome Val :=
  if c then k else
    match m with
    | .proved => .fail
    | .checked => .trap
    | .erased => k

/-- Stan początkowy procedury: parametry i parametry `inout` z wartościami argumentów. -/
def entry (p : Proc Val) (args : List (State Val → Val)) (outs : List Var) (σ : State Val) :
    State Val :=
  updMany (fun _ => default) (p.params ++ p.inouts) (args.map (· σ) ++ outs.map σ)

/-- Stan wywołującego po powrocie: cele `inout` dostają końcowe wartości parametrów,
`x` — wynik. Pozostałe zmienne są niezmienione (własność ramki, lemat 8.3). -/
def afterCall (p : Proc Val) (outs : List Var) (x : Var) (σ σf' : State Val) (v : Val) :
    State Val :=
  upd (updMany σ outs (p.inouts.map σf')) x v

/-- Semantyka z paliwem: paliwo maleje przy każdym obrocie pętli i każdym wywołaniu. -/
def exec (P : Procs Val) : Nat → Stmt Val → State Val → Outcome Val
  | 0, _, _ => .timeout
  | _ + 1, .skip, σ => .normal σ
  | _ + 1, .assign x e, σ => .normal (upd σ x (e σ))
  | n + 1, .seq s t, σ =>
      match exec P (n + 1) s σ with
      | .normal σ' => exec P (n + 1) t σ'
      | o => o
  | n + 1, .ite b s t, σ => if b σ then exec P (n + 1) s σ else exec P (n + 1) t σ
  | _ + 1, .brk, σ => .brk σ
  | _ + 1, .cont, σ => .cont σ
  | _ + 1, .ret e, σ => .ret (e σ) σ
  | _ + 1, .obl m φ, σ => oblR m (φ σ) (.normal σ)
  | n + 1, .loop first b inv mI mP var mV body, σ =>
      oblR (if first then mI else mP) (inv σ) <|
        if b σ then
          oblR mV (decide (0 ≤ var σ)) <|
            match exec P (n + 1) body σ with
            | .normal σ' => oblR mV (decide (var σ' < var σ))
                (exec P n (.loop false b inv mI mP var mV body) σ')
            | .cont σ' => oblR mV (decide (var σ' < var σ))
                (exec P n (.loop false b inv mI mP var mV body) σ')
            | .brk σ' => .normal σ'
            | o => o
        else .normal σ
  | n + 1, .call m x f args outs, σ =>
      let p := P f
      let σf := entry p args outs σ
      oblR m (p.pre σf) <|
        match exec P n p.body σf with
        | .ret v σf' => oblR p.mPost (p.post σf σf' v) (.normal (afterCall p outs x σ σf' v))
        | .normal _ => .fail
        | .brk _ => .fail
        | .cont _ => .fail
        | o => o
termination_by n s => (n, sizeOf s)

/-- Zmienne zapisywane przez instrukcję (analiza syntaktyczna `ws`, §6.4). -/
def writes : Stmt Val → List Var
  | .assign x _ => [x]
  | .seq s t => writes s ++ writes t
  | .ite _ s t => writes s ++ writes t
  | .loop _ _ _ _ _ _ _ body => writes body
  | .call _ x _ _ outs => x :: outs
  | _ => []

/-- `τ` zgadza się z `σ` poza zbiorem `ws`. -/
def agree (ws : List Var) (σ τ : State Val) : Prop := ∀ y, y ∉ ws → τ y = σ y

/-- Poprawność strukturalna: prawo wyłączności dla wywołań — cele `inout` są parami różne
i różne od zmiennej wyniku (§5.4). -/
def WF (P : Procs Val) : Stmt Val → Prop
  | .seq s t => WF P s ∧ WF P t
  | .ite _ s t => WF P s ∧ WF P t
  | .loop _ _ _ _ _ _ _ body => WF P body
  | .call _ x _ _ outs => (x :: outs).Nodup
  | _ => True

def WFProcs (P : Procs Val) : Prop := ∀ f, WF P (P f).body

end

end Rdzen
