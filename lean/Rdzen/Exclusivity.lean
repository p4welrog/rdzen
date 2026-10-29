/-
SPDX-License-Identifier: MIT OR Apache-2.0

Prawo wyłączności jest konieczne (§5.4): bez założenia `WF` (cele `inout` parami różne)
twierdzenie 8.5 nie zachodzi. Kontrprzykład: procedura ustawia `a := 1`, `b := 2`
i obiecuje `a = 1 ∧ b = 2`; wywołanie `f(&y, &y)` — warunek weryfikacji (który traktuje cele
niezależnie) jest spełniony dla dowolnego `Q`, a wykonanie kończy się stanem z `y = 2`.
-/
import Rdzen.Termination

namespace Rdzen.Exclusivity

open Rdzen

instance : Inhabited Int := ⟨0⟩

def pAlias : Proc Int where
  params := []
  inouts := ["a", "b"]
  pre := fun _ => true
  post := fun _ σ _ => σ "a" == 1 && σ "b" == 2
  mPost := .proved
  body := .seq (.assign "a" (fun _ => 1)) (.seq (.assign "b" (fun _ => 2)) (.ret (fun _ => 0)))

def PAlias : Procs Int := fun _ => pAlias

/-- Wywołanie łamiące prawo wyłączności: ta sama zmienna jako dwa cele `inout`. -/
def sAlias : Stmt Int := .call .proved "x" 0 [] ["y", "y"]

/-- Warunek końcowy niespełnialny: żadne wykonanie kończące się normalnie nie jest „bezpieczne”. -/
def QFalse : Post Int where
  normal := fun _ => False
  brk := fun _ => False
  cont := fun _ => False
  ret := fun _ _ => False

theorem alias_procOK : ProcOK PAlias := by
  intro f σf _
  simp [PAlias, pAlias, wp, procPost, oblW, upd]

theorem alias_vc : wp PAlias sAlias QFalse (fun _ => 0) := by
  simp only [sAlias, wp, PAlias, pAlias, oblW]
  refine ⟨trivial, ?_⟩
  intro v σf' τ hpost hout _ _
  have h1 := hout "y" "a" (by simp)
  have h2 := hout "y" "b" (by simp)
  simp at hpost
  omega

theorem alias_not_wf : ¬ WF PAlias sAlias := by
  simp [WF, sAlias]

theorem alias_unsafe : ¬ Safe (exec PAlias 2 sAlias (fun _ => 0)) QFalse := by
  simp [exec, sAlias, PAlias, pAlias, oblR, entry, afterCall, updMany, upd, Safe, QFalse]

/-- Bez prawa wyłączności warunek weryfikacji nie gwarantuje poprawności wykonania. -/
theorem exclusivity_necessary :
    ∃ (P : Procs Int) (s : Stmt Int) (σ : State Int) (Q : Post Int) (n : Nat),
      ProcOK P ∧ WFProcs P ∧ wp P s Q σ ∧ ¬ WF P s ∧ ¬ Safe (exec P n s σ) Q :=
  ⟨PAlias, sAlias, fun _ => 0, QFalse, 2, alias_procOK, fun _ => by simp [WF, PAlias, pAlias],
    alias_vc, alias_not_wf, alias_unsafe⟩

end Rdzen.Exclusivity
