/-
SPDX-License-Identifier: MIT OR Apache-2.0

Własność ramki (lemat 8.3) i lematy o aktualizacjach stanu.
-/
import Rdzen.Core

set_option linter.unusedSectionVars false

namespace Rdzen

section
variable {Val : Type}

@[simp] theorem upd_same (σ : State Val) (x : Var) (v : Val) : upd σ x v x = v := by
  simp [upd]

theorem upd_ne {σ : State Val} {x y : Var} (v : Val) (h : y ≠ x) : upd σ x v y = σ y := by
  simp [upd, h]

theorem updMany_not_mem (σ : State Val) (xs : List Var) (vs : List Val) (y : Var)
    (h : y ∉ xs) : updMany σ xs vs y = σ y := by
  induction xs generalizing σ vs with
  | nil => cases vs <;> rfl
  | cons x xs ih =>
    cases vs with
    | nil => rfl
    | cons v vs =>
      simp only [List.mem_cons, not_or] at h
      simp only [updMany]
      rw [ih _ _ h.2, upd_ne _ h.1]

/-- Prawo wyłączności w działaniu: przy parami różnych celach każdy cel dostaje swoją wartość. -/
theorem updMany_zip (σ : State Val) (xs : List Var) (vs : List Val) (y : Var) (v : Val)
    (hnd : xs.Nodup) (hm : (y, v) ∈ xs.zip vs) : updMany σ xs vs y = v := by
  induction xs generalizing σ vs with
  | nil => simp at hm
  | cons x xs ih =>
    cases vs with
    | nil => simp at hm
    | cons w vs =>
      simp only [List.zip_cons_cons, List.mem_cons, Prod.mk.injEq] at hm
      have hnd' := List.nodup_cons.mp hnd
      simp only [updMany]
      rcases hm with ⟨rfl, rfl⟩ | hm
      · rw [updMany_not_mem _ _ _ _ hnd'.1, upd_same]
      · exact ih _ _ hnd'.2 hm

theorem agree_refl (ws : List Var) (σ : State Val) : agree ws σ σ := fun _ _ => rfl

theorem agree_trans {ws : List Var} {σ τ ρ : State Val} (h1 : agree ws σ τ) (h2 : agree ws τ ρ) :
    agree ws σ ρ := fun y hy => (h2 y hy).trans (h1 y hy)

theorem agree_mono {ws ws' : List Var} {σ τ : State Val} (h : agree ws σ τ)
    (hsub : ∀ y, y ∈ ws → y ∈ ws') : agree ws' σ τ :=
  fun y hy => h y (fun hm => hy (hsub y hm))

end

/-- Stan końcowy wyniku (jeśli wykonanie zakończyło się normalnie lub skokiem). -/
def Outcome.state? {Val : Type} : Outcome Val → Option (State Val)
  | .normal σ => some σ
  | .brk σ => some σ
  | .cont σ => some σ
  | .ret _ σ => some σ
  | _ => none

section
variable {Val : Type} [Inhabited Val]

theorem oblR_state {m : Mode} {c : Bool} {k : Outcome Val} {τ : State Val}
    (h : (oblR m c k).state? = some τ) : k.state? = some τ := by
  unfold oblR at h
  split at h
  · exact h
  · cases m <;> simp_all [Outcome.state?]

theorem agree_afterCall (p : Proc Val) (outs : List Var) (x : Var) (σ σf' : State Val) (v : Val) :
    agree (x :: outs) σ (afterCall p outs x σ σf' v) := by
  intro y hy
  simp only [List.mem_cons, not_or] at hy
  simp only [afterCall]
  rw [upd_ne _ hy.1, updMany_not_mem _ _ _ _ hy.2]

/-- Lemat 8.3 (ramka zapisu): wykonanie instrukcji zmienia tylko zmienne z `writes s`. -/
theorem exec_frame (P : Procs Val) :
    ∀ n (s : Stmt Val) σ τ, (exec P n s σ).state? = some τ → agree (writes s) σ τ := by
  intro n
  induction n with
  | zero => intro s σ τ h; simp [exec, Outcome.state?] at h
  | succ n ihn =>
    intro s
    induction s with
    | skip => intro σ τ h; simp [exec, Outcome.state?] at h; subst h; exact agree_refl _ _
    | assign x e =>
      intro σ τ h
      simp [exec, Outcome.state?] at h; subst h
      intro y hy
      simp only [writes, List.mem_singleton] at hy
      exact upd_ne _ hy
    | seq s t ihs iht =>
      intro σ τ h
      simp only [exec] at h
      split at h
      · rename_i σ' hs
        have h1 := ihs σ σ' (by rw [hs]; rfl)
        have h2 := iht σ' τ h
        exact agree_trans (agree_mono h1 (fun y hy => by simp [writes, hy]))
          (agree_mono h2 (fun y hy => by simp [writes, hy]))
      · rename_i o hs _
        exact agree_mono (ihs σ τ h) (fun y hy => by simp [writes, hy])
    | ite b s t ihs iht =>
      intro σ τ h
      simp only [exec] at h
      split at h
      · exact agree_mono (ihs σ τ h) (fun y hy => by simp [writes, hy])
      · exact agree_mono (iht σ τ h) (fun y hy => by simp [writes, hy])
    | loop first b inv mI mP var mV body ihb =>
      intro σ τ h
      simp only [exec] at h
      have h := oblR_state h
      split at h
      · have h := oblR_state h
        split at h
        · rename_i σ' hb
          have h := oblR_state h
          have h2 := ihn _ σ' τ h
          exact agree_trans (ihb σ σ' (by rw [hb]; rfl)) h2
        · rename_i σ' hb
          have h := oblR_state h
          have h2 := ihn _ σ' τ h
          exact agree_trans (ihb σ σ' (by rw [hb]; rfl)) h2
        · rename_i σ' hb
          simp [Outcome.state?] at h; subst h
          exact ihb σ _ (by rw [hb]; rfl)
        · exact ihb σ τ h
      · simp [Outcome.state?] at h; subst h; exact agree_refl _ _
    | brk => intro σ τ h; simp [exec, Outcome.state?] at h; subst h; exact agree_refl _ _
    | cont => intro σ τ h; simp [exec, Outcome.state?] at h; subst h; exact agree_refl _ _
    | ret e => intro σ τ h; simp [exec, Outcome.state?] at h; subst h; exact agree_refl _ _
    | obl m φ =>
      intro σ τ h
      simp only [exec] at h
      have h := oblR_state h
      simp [Outcome.state?] at h; subst h; exact agree_refl _ _
    | call m x f args outs =>
      intro σ τ h
      simp only [exec] at h
      have h := oblR_state h
      split at h
      · have h := oblR_state h
        simp [Outcome.state?] at h; subst h
        exact agree_afterCall _ _ _ _ _ _
      all_goals simp_all [Outcome.state?]

end

end Rdzen
