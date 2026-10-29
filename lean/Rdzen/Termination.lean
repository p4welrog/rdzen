/-
SPDX-License-Identifier: MIT OR Apache-2.0

Twierdzenie 8.7 (część 2: terminacja) dla fragmentu jądra.

Pętle z wariantem kończą się niezależnie od tego, czy zobowiązania `var-nn`/`var-dec` są
udowodnione (wtedy wynika to z VC), czy sprawdzane dynamicznie (wtedy naruszenie kończy
wykonanie pułapką). Wywołania są traktowane modularnie: zakładamy terminację wywoływanych
procedur dla argumentów spełniających warunek wstępny; dla acyklicznego grafu wywołań
założenie wynika z indukcji po porządku topologicznym, a dla rekursji — z miary `decreases`
(poza zakresem tej mechanizacji).
-/
import Rdzen.Gradual

set_option linter.unusedSectionVars false

namespace Rdzen

section
variable {Val : Type} [Inhabited Val]

theorem oblR_congr (m : Mode) (c : Bool) (k k' : Outcome Val)
    (h : oblR m c k ≠ .timeout) (hk : k ≠ .timeout → k' = k) : oblR m c k' = oblR m c k := by
  unfold oblR at h ⊢
  cases c with
  | true => simp only [if_true] at h ⊢; exact hk h
  | false => cases m <;> simp_all

theorem oblR_ne_timeout {m : Mode} {c : Bool} {k : Outcome Val} (hk : k ≠ .timeout) :
    oblR m c k ≠ .timeout := by
  unfold oblR; cases c <;> cases m <;> simp_all

/-- Więcej paliwa nie zmienia wyniku wykonania, które się zakończyło. -/
theorem exec_succ (P : Procs Val) :
    ∀ n (s : Stmt Val) σ, exec P n s σ ≠ .timeout → exec P (n + 1) s σ = exec P n s σ := by
  intro n
  induction n with
  | zero => intro s σ h; simp [exec] at h
  | succ n ihn =>
    intro s
    induction s with
    | skip => intro σ _; simp [exec]
    | assign x e => intro σ _; simp [exec]
    | brk => intro σ _; simp [exec]
    | cont => intro σ _; simp [exec]
    | ret e => intro σ _; simp [exec]
    | obl m φ => intro σ _; simp [exec]
    | seq s t ihs iht =>
      intro σ h
      simp only [exec] at h ⊢
      cases hr : exec P (n + 1) s σ with
      | normal σ' =>
        rw [hr] at h
        rw [ihs σ (by rw [hr]; simp), hr]
        exact iht σ' h
      | timeout => rw [hr] at h; exact absurd rfl h
      | _ => rw [ihs σ (by rw [hr]; simp), hr]
    | ite b s t ihs iht =>
      intro σ h
      simp only [exec] at h ⊢
      cases hb : b σ with
      | true => simp only [hb, if_true] at h ⊢; exact ihs σ h
      | false => simp only [hb] at h ⊢; exact iht σ h
    | loop fl b inv mI mP var mV body ihb =>
      intro σ h
      simp only [exec] at h ⊢
      apply oblR_congr _ _ _ _ h
      intro h1
      cases hb : b σ with
      | false => simp
      | true =>
        simp only [hb, if_true] at h1 ⊢
        apply oblR_congr _ _ _ _ h1
        intro h2
        cases hr : exec P (n + 1) body σ with
        | normal σ' =>
          rw [hr] at h2
          rw [ihb σ (by rw [hr]; simp), hr]
          exact oblR_congr _ _ _ _ h2 (fun h3 => by simpa only [exec] using ihn _ σ' h3)
        | cont σ' =>
          rw [hr] at h2
          rw [ihb σ (by rw [hr]; simp), hr]
          exact oblR_congr _ _ _ _ h2 (fun h3 => by simpa only [exec] using ihn _ σ' h3)
        | timeout => rw [hr] at h2; exact absurd rfl h2
        | _ => rw [ihb σ (by rw [hr]; simp), hr]
    | call m x f args outs =>
      intro σ h
      simp only [exec] at h ⊢
      apply oblR_congr _ _ _ _ h
      intro h1
      cases hr : exec P n (P f).body (entry (P f) args outs σ) with
      | timeout => rw [hr] at h1; exact absurd rfl h1
      | _ => rw [ihn _ _ (by rw [hr]; simp), hr]

theorem exec_mono (P : Procs Val) (n : Nat) (s : Stmt Val) (σ : State Val)
    (h : exec P n s σ ≠ .timeout) : ∀ k, exec P (n + k) s σ = exec P n s σ := by
  intro k
  induction k with
  | zero => rfl
  | succ k ih =>
    rw [← Nat.add_assoc, exec_succ P _ s σ (by rw [ih]; exact h), ih]

theorem exec_le (P : Procs Val) {n m : Nat} (hle : n ≤ m) (s : Stmt Val) (σ : State Val)
    (h : exec P n s σ ≠ .timeout) : exec P m s σ = exec P n s σ := by
  obtain ⟨k, rfl⟩ := Nat.exists_eq_add_of_le hle
  exact exec_mono P n s σ h k

theorem exec_pos {P : Procs Val} {n : Nat} {s : Stmt Val} {σ : State Val}
    (h : exec P n s σ ≠ .timeout) : ∃ m, n = m + 1 := by
  cases n with
  | zero => simp [exec] at h
  | succ m => exact ⟨m, rfl⟩

/-- Terminacja wywoływanych procedur (dla argumentów spełniających warunek wstępny). -/
def ProcsTerminate (P : Procs Val) : Prop :=
  ∀ f σf, (P f).pre σf = true → ∃ n, exec P n (P f).body σf ≠ .timeout

/-- **Twierdzenie 8.7 (2)**: przy poprawnym VC każde wykonanie instrukcji jest skończone
(kończy się wynikiem albo pułapką) dla dostatecznie dużego paliwa. -/
theorem terminates (P : Procs Val) (hP : ProcOK P) (hW : WFProcs P) (hT : ProcsTerminate P) :
    ∀ (s : Stmt Val) σ Q, WF P s → wp P s Q σ → ∃ n, exec P n s σ ≠ .timeout := by
  intro s
  induction s with
  | skip => intro σ Q _ _; exact ⟨1, by simp [exec]⟩
  | assign x e => intro σ Q _ _; exact ⟨1, by simp [exec]⟩
  | brk => intro σ Q _ _; exact ⟨1, by simp [exec]⟩
  | cont => intro σ Q _ _; exact ⟨1, by simp [exec]⟩
  | ret e => intro σ Q _ _; exact ⟨1, by simp [exec]⟩
  | obl m φ => intro σ Q _ _; exact ⟨1, by simp only [exec]; exact oblR_ne_timeout (by simp)⟩
  | ite b s t ihs iht =>
    intro σ Q hwf h
    simp only [WF] at hwf
    simp only [wp] at h
    cases hb : b σ with
    | true =>
      obtain ⟨n, hn⟩ := ihs σ Q hwf.1 (h.1 hb)
      obtain ⟨m, rfl⟩ := exec_pos hn
      exact ⟨m + 1, by simp only [exec, hb, if_true]; exact hn⟩
    | false =>
      obtain ⟨n, hn⟩ := iht σ Q hwf.2 (h.2 hb)
      obtain ⟨m, rfl⟩ := exec_pos hn
      exact ⟨m + 1, by simp only [exec, hb]; exact hn⟩
  | seq s t ihs iht =>
    intro σ Q hwf h
    simp only [WF] at hwf
    simp only [wp] at h
    obtain ⟨n1, h1⟩ := ihs σ _ hwf.1 h
    obtain ⟨m1, rfl⟩ := exec_pos h1
    have hsafe := soundness P hP hW (m1 + 1) s σ _ hwf.1 h
    cases hr : exec P (m1 + 1) s σ with
    | normal σ' =>
      simp only [hr, Safe] at hsafe
      obtain ⟨n2, h2⟩ := iht σ' Q hwf.2 hsafe
      refine ⟨m1 + n2 + 1, ?_⟩
      simp only [exec]
      rw [exec_le P (by omega : m1 + 1 ≤ m1 + n2 + 1) s σ h1, hr]
      dsimp only
      rw [exec_le P (by omega : n2 ≤ m1 + n2 + 1) t σ' h2]
      exact h2
    | timeout => exact absurd hr h1
    | _ => exact ⟨m1 + 1, by simp only [exec, hr]; simp⟩
  | loop fl b inv mI mP var mV body ihb =>
    intro σ Q hwf h0
    simp only [WF] at hwf
    -- indukcja po ograniczeniu górnym wariantu
    have main : ∀ k : Nat, ∀ (fl' : Bool) τ, var τ < (k : Int) →
        wp P (.loop fl' b inv mI mP var mV body) Q τ →
        ∃ n, exec P n (.loop fl' b inv mI mP var mV body) τ ≠ .timeout := by
      intro k
      induction k with
      | zero =>
        intro fl' τ hk h
        simp only [wp] at h
        cases hi : inv τ with
        | false =>
          cases hm : (if fl' = true then mI else mP) with
          | checked => exact ⟨1, by simp only [exec, hm, hi]; simp [oblR]⟩
          | proved => rw [hm] at h; simp [oblW, hi] at h
          | erased => rw [hm] at h; simp [oblW, hi] at h
        | true =>
          have hL := oblW_cond h hi
          have hτ := hL τ (agree_refl _ _) hi
          cases hb : b τ with
          | false => exact ⟨1, by simp only [exec, hi, hb]; simp [oblR]⟩
          | true =>
            cases hnn : decide (0 ≤ var τ) with
            | true => simp at hnn; omega
            | false =>
              cases hmv : mV with
              | checked => exact ⟨1, by simp only [exec, hi, hb, hnn, hmv]; simp [oblR]⟩
              | proved => have := hτ.1 hb; rw [hmv] at this; simp [oblW, hnn] at this
              | erased => have := hτ.1 hb; rw [hmv] at this; simp [oblW, hnn] at this
      | succ k ihk =>
        intro fl' τ hk h
        simp only [wp] at h
        cases hi : inv τ with
        | false =>
          cases hm : (if fl' = true then mI else mP) with
          | checked => exact ⟨1, by simp only [exec, hm, hi]; simp [oblR]⟩
          | proved => rw [hm] at h; simp [oblW, hi] at h
          | erased => rw [hm] at h; simp [oblW, hi] at h
        | true =>
          have hL := oblW_cond h hi
          have hτ := hL τ (agree_refl _ _) hi
          cases hb : b τ with
          | false => exact ⟨1, by simp only [exec, hi, hb]; simp [oblR]⟩
          | true =>
            have hv := hτ.1 hb
            cases hnn : decide (0 ≤ var τ) with
            | false =>
              cases hmv : mV with
              | checked => exact ⟨1, by simp only [exec, hi, hb, hnn, hmv]; simp [oblR]⟩
              | proved => rw [hmv] at hv; simp [oblW, hnn] at hv
              | erased => rw [hmv] at hv; simp [oblW, hnn] at hv
            | true =>
              have hbody := oblW_cond hv hnn
              obtain ⟨nb, hnb⟩ := ihb τ _ hwf hbody
              obtain ⟨mb, rfl⟩ := exec_pos hnb
              have hsafe := soundness P hP hW (mb + 1) body τ _ hwf hbody
              -- obrót zakończony normalnie lub przez `continue`: ponowne wejście
              have again : ∀ σ', (exec P (mb + 1) body τ = .normal σ' ∨
                  exec P (mb + 1) body τ = .cont σ') →
                  oblW mV (decide (var σ' < var τ) = true) (oblW mP (inv σ' = true) True) →
                  ∃ n, exec P n (.loop fl' b inv mI mP var mV body) τ ≠ .timeout := by
                intro σ' hex hpost
                cases hdec : decide (var σ' < var τ) with
                | false =>
                  cases hmv : mV with
                  | checked =>
                    refine ⟨mb + 1, ?_⟩
                    simp only [exec, hi, hb, hnn, if_true]
                    rcases hex with hex | hex <;> simp [hex, hdec, hmv, oblR]
                  | proved => rw [hmv] at hpost; simp [oblW, hdec] at hpost
                  | erased => rw [hmv] at hpost; simp [oblW, hdec] at hpost
                | true =>
                  have hag : agree (writes body) τ σ' := by
                    apply exec_frame P (mb + 1) body τ σ'
                    rcases hex with hex | hex <;> rw [hex] <;> rfl
                  have hlt : var σ' < (k : Int) := by simp at hdec; omega
                  have hre : wp P (.loop false b inv mI mP var mV body) Q σ' := by
                    simp only [wp, if_neg (by decide : ¬ (false = true))]
                    apply oblW_weaken (oblW_cond hpost hdec)
                    intro τ' hτ' hinvτ'
                    exact hL τ' (agree_trans hag hτ') hinvτ'
                  obtain ⟨nr, hnr⟩ := ihk false σ' hlt hre
                  refine ⟨mb + nr + 1, ?_⟩
                  simp only [exec, hi, hb, hnn, if_true]
                  rw [exec_le P (by omega) body τ hnb]
                  rcases hex with hex | hex <;> simp only [hex, hdec, oblR, if_true] <;>
                    rw [exec_le P (by omega) _ σ' hnr] <;> exact hnr
              cases hr : exec P (mb + 1) body τ with
              | normal σ' =>
                simp only [hr, Safe, iterPost] at hsafe
                exact again σ' (Or.inl hr) hsafe
              | cont σ' =>
                simp only [hr, Safe, iterPost] at hsafe
                exact again σ' (Or.inr hr) hsafe
              | timeout => exact absurd hr hnb
              | _ =>
                refine ⟨mb + 1, ?_⟩
                simp only [exec, hi, hb, hnn, if_true, hr, oblR]
                simp
    exact main ((var σ).toNat + 1) fl σ (by have := Int.self_le_toNat (var σ); omega) h0
  | call m x f args outs =>
    intro σ Q hwf h
    simp only [wp] at h
    cases hpre : (P f).pre (entry (P f) args outs σ) with
    | false =>
      cases hm : m with
      | checked => exact ⟨1, by simp only [exec, hpre, hm]; simp [oblR]⟩
      | proved => rw [hm] at h; simp [oblW, hpre] at h
      | erased => rw [hm] at h; simp [oblW, hpre] at h
    | true =>
      obtain ⟨nf, hnf⟩ := hT f _ hpre
      refine ⟨nf + 1, ?_⟩
      simp only [exec, hpre, oblR, if_true]
      cases hr : exec P nf (P f).body (entry (P f) args outs σ) with
      | ret v σf' => exact oblR_ne_timeout (by simp)
      | timeout => exact absurd hr hnf
      | _ => simp

end

end Rdzen
