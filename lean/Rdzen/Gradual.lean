/-
SPDX-License-Identifier: MIT OR Apache-2.0

Twierdzenie 8.6 (poprawność weryfikacji stopniowanej) i przekształcenie R (§6.6).

`erase` usuwa z programu zobowiązania udowodnione (tryb `proved` → `erased`); sprawdzenia
dynamiczne (`checked`) zostają. Pokazujemy:
* `erase_exec`: dopóki program instrumentowany nie narusza udowodnionego zobowiązania,
  program po usunięciu zobowiązań zachowuje się identycznie;
* `gradual`: przy poprawnym VC program wykonywalny (po R) kończy się zgodnie z kontraktem,
  pułapką sprawdzenia dynamicznego albo nie kończy się w danym paliwie;
* `no_trap`: program, w którym wszystkie zobowiązania są udowodnione, nie kończy się pułapką
  (część 1 tw. 8.5).
-/
import Rdzen.Soundness

set_option linter.unusedSectionVars false

namespace Rdzen

def em : Mode → Mode
  | .proved => .erased
  | m => m

section
variable {Val : Type} [Inhabited Val]

def erase : Stmt Val → Stmt Val
  | .seq s t => .seq (erase s) (erase t)
  | .ite b s t => .ite b (erase s) (erase t)
  | .loop fl b inv mI mP var mV body => .loop fl b inv (em mI) (em mP) var (em mV) (erase body)
  | .obl m φ => .obl (em m) φ
  | .call m x f args outs => .call (em m) x f args outs
  | s => s

def eraseP (P : Procs Val) : Procs Val :=
  fun f => { P f with mPost := em (P f).mPost, body := erase (P f).body }

theorem oblR_erase (m : Mode) (c : Bool) (k k' : Outcome Val)
    (h : oblR m c k ≠ .fail) (hk : k ≠ .fail → k' = k) : oblR (em m) c k' = oblR m c k := by
  unfold oblR at h ⊢
  cases c with
  | true => simp only [if_true] at h ⊢; exact hk h
  | false =>
    cases m with
    | proved => simp at h
    | checked => simp [em]
    | erased => simp only [em] at h ⊢; exact hk h

theorem oblR_ne_fail {m : Mode} {c : Bool} {k : Outcome Val} (h : oblR m c k ≠ .fail)
    (hc : c = true) : k ≠ .fail := by
  simpa [oblR, hc] using h

/-- Usunięcie udowodnionych zobowiązań nie zmienia wykonania, które ich nie narusza. -/
theorem erase_exec (P : Procs Val) :
    ∀ n (s : Stmt Val) σ, exec P n s σ ≠ .fail → exec (eraseP P) n (erase s) σ = exec P n s σ := by
  intro n
  induction n with
  | zero => intro s σ _; simp [exec]
  | succ n ihn =>
    intro s
    induction s with
    | skip => intro σ _; simp [exec, erase]
    | assign x e => intro σ _; simp [exec, erase]
    | brk => intro σ _; simp [exec, erase]
    | cont => intro σ _; simp [exec, erase]
    | ret e => intro σ _; simp [exec, erase]
    | obl m φ =>
      intro σ h
      simp only [exec, erase] at h ⊢
      exact oblR_erase _ _ _ _ h (fun _ => rfl)
    | seq s t ihs iht =>
      intro σ h
      simp only [exec, erase] at h ⊢
      cases hr : exec P (n + 1) s σ with
      | normal σ' =>
        rw [hr] at h
        rw [ihs σ (by rw [hr]; simp), hr]
        exact iht σ' h
      | fail => rw [hr] at h; exact absurd rfl h
      | _ => rw [ihs σ (by rw [hr]; simp), hr]
    | ite b s t ihs iht =>
      intro σ h
      simp only [exec, erase] at h ⊢
      cases hb : b σ with
      | true => simp only [hb, if_true] at h ⊢; exact ihs σ h
      | false => simp only [hb] at h ⊢; exact iht σ h
    | loop fl b inv mI mP var mV body ihb =>
      intro σ h
      simp only [exec, erase] at h ⊢
      have hmode : (if fl = true then em mI else em mP) = em (if fl = true then mI else mP) := by
        cases fl <;> rfl
      rw [hmode]
      apply oblR_erase _ _ _ _ h
      intro h1
      cases hb : b σ with
      | false => simp
      | true =>
        simp only [hb, if_true] at h1 ⊢
        apply oblR_erase _ _ _ _ h1
        intro h2
        cases hr : exec P (n + 1) body σ with
        | normal σ' =>
          rw [hr] at h2
          rw [ihb σ (by rw [hr]; simp), hr]
          apply oblR_erase _ _ _ _ h2
          intro h3
          have := ihn (.loop false b inv mI mP var mV body) σ' h3
          simpa [erase] using this
        | cont σ' =>
          rw [hr] at h2
          rw [ihb σ (by rw [hr]; simp), hr]
          apply oblR_erase _ _ _ _ h2
          intro h3
          have := ihn (.loop false b inv mI mP var mV body) σ' h3
          simpa [erase] using this
        | fail => rw [hr] at h2; exact absurd rfl h2
        | _ => rw [ihb σ (by rw [hr]; simp), hr]
    | call m x f args outs =>
      intro σ h
      simp only [exec, erase] at h ⊢
      have hpre : (eraseP P f).pre = (P f).pre := rfl
      have hpost : (eraseP P f).post = (P f).post := rfl
      have hent : entry (eraseP P f) args outs σ = entry (P f) args outs σ := rfl
      have haft : ∀ σf' v, afterCall (eraseP P f) outs x σ σf' v = afterCall (P f) outs x σ σf' v :=
        fun _ _ => rfl
      rw [hent, hpre]
      apply oblR_erase _ _ _ _ h
      intro h1
      have hbody : (eraseP P f).body = erase (P f).body := rfl
      rw [hbody]
      cases hr : exec P n (P f).body (entry (P f) args outs σ) with
      | ret v σf' =>
        rw [hr] at h1
        rw [ihn _ _ (by rw [hr]; simp), hr]
        simp only [hpost, haft]
        exact oblR_erase _ _ _ _ h1 (fun _ => rfl)
      | fail => rw [hr] at h1; exact absurd rfl h1
      | _ => rw [ihn _ _ (by rw [hr]; simp), hr]

/-- **Twierdzenie 8.6** (poprawność weryfikacji stopniowanej): program wykonywalny `R(P)`
przy poprawnym VC kończy się zgodnie z kontraktem albo pułapką sprawdzenia dynamicznego. -/
theorem gradual (P : Procs Val) (hP : ProcOK P) (hW : WFProcs P) (n : Nat) (s : Stmt Val)
    (σ : State Val) (Q : Post Val) (hwf : WF P s) (h : wp P s Q σ) :
    Safe (exec (eraseP P) n (erase s) σ) Q := by
  rw [erase_exec P n s σ (no_fail P hP hW n s σ Q hwf h)]
  exact soundness P hP hW n s σ Q hwf h

/-- Wszystkie zobowiązania udowodnione (brak sprawdzeń dynamicznych). -/
def AllProved : Stmt Val → Prop
  | .seq s t => AllProved s ∧ AllProved t
  | .ite _ s t => AllProved s ∧ AllProved t
  | .loop _ _ _ mI mP _ mV body => mI ≠ .checked ∧ mP ≠ .checked ∧ mV ≠ .checked ∧ AllProved body
  | .obl m _ => m ≠ .checked
  | .call m _ _ _ _ => m ≠ .checked
  | _ => True

def AllProvedP (P : Procs Val) : Prop := ∀ f, (P f).mPost ≠ .checked ∧ AllProved (P f).body

theorem oblR_ne_trap {m : Mode} {c : Bool} {k : Outcome Val} (hm : m ≠ .checked)
    (hk : k ≠ .trap) : oblR m c k ≠ .trap := by
  unfold oblR
  cases c <;> cases m <;> simp_all

/-- Pułapki pochodzą wyłącznie ze sprawdzeń dynamicznych: program bez nich nie kończy się
pułapką (wraz z `no_fail` — część 1 tw. 8.5). -/
theorem no_trap (P : Procs Val) (hA : AllProvedP P) :
    ∀ n (s : Stmt Val) σ, AllProved s → exec P n s σ ≠ .trap := by
  intro n
  induction n with
  | zero => intro s σ _; simp [exec]
  | succ n ihn =>
    intro s
    induction s with
    | skip => intro σ _; simp [exec]
    | assign x e => intro σ _; simp [exec]
    | brk => intro σ _; simp [exec]
    | cont => intro σ _; simp [exec]
    | ret e => intro σ _; simp [exec]
    | obl m φ =>
      intro σ ha
      simp only [exec]
      exact oblR_ne_trap ha (by simp)
    | seq s t ihs iht =>
      intro σ ha
      simp only [AllProved] at ha
      simp only [exec]
      cases hr : exec P (n + 1) s σ with
      | normal σ' => exact iht σ' ha.2
      | trap => exact absurd hr (ihs σ ha.1)
      | _ => simp
    | ite b s t ihs iht =>
      intro σ ha
      simp only [AllProved] at ha
      simp only [exec]
      cases b σ <;> simp [ihs σ ha.1, iht σ ha.2]
    | loop fl b inv mI mP var mV body ihb =>
      intro σ ha
      simp only [AllProved] at ha
      obtain ⟨hI, hP', hV, hb⟩ := ha
      simp only [exec]
      apply oblR_ne_trap (by cases fl <;> simp [hI, hP'])
      split
      · apply oblR_ne_trap hV
        cases hr : exec P (n + 1) body σ with
        | normal σ' =>
          exact oblR_ne_trap hV (ihn _ σ' (by simp [AllProved, hI, hP', hV, hb]))
        | cont σ' =>
          exact oblR_ne_trap hV (ihn _ σ' (by simp [AllProved, hI, hP', hV, hb]))
        | trap => exact absurd hr (ihb σ hb)
        | _ => simp
      · simp
    | call m x f args outs =>
      intro σ ha
      simp only [AllProved] at ha
      simp only [exec]
      apply oblR_ne_trap ha
      cases hr : exec P n (P f).body (entry (P f) args outs σ) with
      | ret v σf' => exact oblR_ne_trap (hA f).1 (by simp)
      | trap => exact absurd hr (ihn _ _ (hA f).2)
      | _ => simp

end

end Rdzen
