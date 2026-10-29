/-
SPDX-License-Identifier: MIT OR Apache-2.0

Warunki weryfikacji (§6.4): najsłabszy warunek wstępny względem czwórki warunków końcowych
(wyjście normalne, `break`, `continue`, `return`).

* Zobowiązanie w trybie `proved` (i `erased`) jest koniunkcją — musi być dowiedzione;
  w trybie `checked` jest założeniem po sprawdzeniu (sprawdzenie dynamiczne kończy wykonanie
  pułapką, jeśli warunek nie zachodzi).
* Pętla: niezmiennik i wariant są obowiązkami dla każdego stanu `τ` zgodnego ze stanem wejścia
  poza zmiennymi zapisywanymi w ciele (havoc tylko `writes body`, §6.4).
* Wywołanie: kontrakt wywoływanej procedury; cele `inout` i wynik są wartościowane niezależnie
  (podstawienie), co jest poprawne dzięki prawu wyłączności.
-/
import Rdzen.Frame

set_option linter.unusedSectionVars false

namespace Rdzen

structure Post (Val : Type) where
  normal : State Val → Prop
  brk : State Val → Prop
  cont : State Val → Prop
  ret : Val → State Val → Prop

def oblW (m : Mode) (c k : Prop) : Prop :=
  match m with
  | .checked => c → k
  | _ => c ∧ k

section
variable {Val : Type} [Inhabited Val]

/-- Warunek końcowy ciała pętli w obrocie rozpoczętym w stanie `τ`. -/
def iterPost (inv : State Val → Bool) (mP : Mode) (var : State Val → Int) (mV : Mode)
    (Q : Post Val) (τ : State Val) : Post Val where
  normal := fun τ' => oblW mV (decide (var τ' < var τ) = true) (oblW mP (inv τ' = true) True)
  cont := fun τ' => oblW mV (decide (var τ' < var τ) = true) (oblW mP (inv τ' = true) True)
  brk := Q.normal
  ret := Q.ret

def wp (P : Procs Val) : Stmt Val → Post Val → State Val → Prop
  | .skip, Q, σ => Q.normal σ
  | .assign x e, Q, σ => Q.normal (upd σ x (e σ))
  | .seq s t, Q, σ => wp P s { Q with normal := fun σ' => wp P t Q σ' } σ
  | .ite b s t, Q, σ => (b σ = true → wp P s Q σ) ∧ (b σ = false → wp P t Q σ)
  | .brk, Q, σ => Q.brk σ
  | .cont, Q, σ => Q.cont σ
  | .ret e, Q, σ => Q.ret (e σ) σ
  | .obl m φ, Q, σ => oblW m (φ σ = true) (Q.normal σ)
  | .loop first b inv mI mP var mV body, Q, σ =>
      oblW (if first then mI else mP) (inv σ = true)
        (∀ τ, agree (writes body) σ τ → inv τ = true →
          (b τ = true → oblW mV (decide (0 ≤ var τ) = true)
              (wp P body (iterPost inv mP var mV Q τ) τ)) ∧
          (b τ = false → Q.normal τ))
  | .call m x f args outs, Q, σ =>
      oblW m ((P f).pre (entry (P f) args outs σ) = true)
        (∀ v σf' τ, (P f).post (entry (P f) args outs σ) σf' v = true →
          (∀ y q, (y, q) ∈ outs.zip (P f).inouts → τ y = σf' q) → τ x = v →
          agree (x :: outs) σ τ → Q.normal τ)

/-- Kontrakt ciała procedury: ciało kończy się wyłącznie przez `return`, a wynik spełnia `post`. -/
def procPost (p : Proc Val) (σ₀ : State Val) : Post Val where
  normal := fun _ => False
  brk := fun _ => False
  cont := fun _ => False
  ret := fun v σ' => oblW p.mPost (p.post σ₀ σ' v = true) True

/-- Wszystkie procedury spełniają swoje warunki weryfikacji. -/
def ProcOK (P : Procs Val) : Prop :=
  ∀ f σf, (P f).pre σf = true → wp P (P f).body (procPost (P f) σf) σf

/-- Wynik zgodny z czwórką warunków końcowych; `fail` (naruszenie udowodnionego zobowiązania)
nigdy nie jest bezpieczny, pułapka i brak paliwa są dopuszczalne. -/
def Safe : Outcome Val → Post Val → Prop
  | .normal σ, Q => Q.normal σ
  | .brk σ, Q => Q.brk σ
  | .cont σ, Q => Q.cont σ
  | .ret v σ, Q => Q.ret v σ
  | .fail, _ => False
  | .trap, _ => True
  | .timeout, _ => True

theorem oblR_safe {m : Mode} {c : Bool} {K : Prop} {k : Outcome Val} {Q : Post Val}
    (hw : oblW m (c = true) K) (hk : c = true → K → Safe k Q) : Safe (oblR m c k) Q := by
  unfold oblR
  cases c with
  | true => cases m <;> simp only [oblW] at hw <;> simp_all
  | false =>
    cases m with
    | proved => simp [oblW] at hw
    | checked => simp [Safe]
    | erased => simp [oblW] at hw

theorem oblW_weaken {m : Mode} {c K : Prop} (h : oblW m c True) (hk : K) : oblW m c K := by
  cases m <;> simp_all [oblW]

theorem oblW_cond {m : Mode} {c K : Prop} (h : oblW m c K) (hc : c) : K := by
  cases m <;> simp_all [oblW]

end

end Rdzen
