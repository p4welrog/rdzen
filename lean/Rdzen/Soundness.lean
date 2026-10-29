/-
SPDX-License-Identifier: MIT OR Apache-2.0

Twierdzenie 8.5 (poprawność warunków weryfikacji) dla fragmentu jądra:
jeśli wszystkie procedury spełniają swoje VC, a stan spełnia `wp s Q`, to żadne wykonanie `s`
(dla dowolnego paliwa) nie narusza udowodnionego zobowiązania, a wynik spełnia odpowiednią
składową czwórki `Q`. Dowód: indukcja po paliwie (długości wykonania — przypadek wywołań
i kolejnych obrotów pętli) i po strukturze instrukcji.
-/
import Rdzen.Wp

set_option linter.unusedSectionVars false

namespace Rdzen

theorem mem_zip_map {α β γ : Type} (f : β → γ) :
    ∀ (xs : List α) (qs : List β) (y : α) (q : β), (y, q) ∈ xs.zip qs → (y, f q) ∈ xs.zip (qs.map f)
  | [], _, _, _, h => by simp at h
  | _ :: _, [], _, _, h => by simp at h
  | x :: xs, q' :: qs, y, q, h => by
    simp only [List.zip_cons_cons, List.mem_cons, Prod.mk.injEq, List.map_cons] at h ⊢
    rcases h with ⟨rfl, rfl⟩ | h
    · exact Or.inl ⟨rfl, rfl⟩
    · exact Or.inr (mem_zip_map f xs qs y q h)

theorem mem_zip_left {α β : Type} :
    ∀ (xs : List α) (qs : List β) (y : α) (q : β), (y, q) ∈ xs.zip qs → y ∈ xs
  | [], _, _, _, h => by simp at h
  | _ :: _, [], _, _, h => by simp at h
  | x :: xs, q' :: qs, y, q, h => by
    simp only [List.zip_cons_cons, List.mem_cons, Prod.mk.injEq] at h
    rcases h with ⟨rfl, rfl⟩ | h
    · exact List.mem_cons_self _ _
    · exact List.mem_cons_of_mem _ (mem_zip_left xs qs y q h)

section
variable {Val : Type} [Inhabited Val]

/-- Po powrocie z wywołania każdy cel `inout` ma końcową wartość swojego parametru —
wymaga prawa wyłączności (`Nodup`). -/
theorem afterCall_out (p : Proc Val) (outs : List Var) (x : Var) (σ σf' : State Val) (v : Val)
    (hnd : (x :: outs).Nodup) (y : Var) (q : Var) (hm : (y, q) ∈ outs.zip p.inouts) :
    afterCall p outs x σ σf' v y = σf' q := by
  have hnd' := List.nodup_cons.mp hnd
  have hy : y ∈ outs := mem_zip_left _ _ _ _ hm
  have hyx : y ≠ x := fun h => hnd'.1 (h ▸ hy)
  simp only [afterCall]
  rw [upd_ne _ hyx]
  exact updMany_zip _ _ _ _ _ hnd'.2 (mem_zip_map σf' _ _ _ _ hm)

theorem afterCall_res (p : Proc Val) (outs : List Var) (x : Var) (σ σf' : State Val) (v : Val) :
    afterCall p outs x σ σf' v x = v := by
  simp [afterCall]

/-- **Twierdzenie 8.5** (poprawność warunków weryfikacji). -/
theorem soundness (P : Procs Val) (hP : ProcOK P) (hW : WFProcs P) :
    ∀ n (s : Stmt Val) σ Q, WF P s → wp P s Q σ → Safe (exec P n s σ) Q := by
  intro n
  induction n with
  | zero => intro s σ Q _ _; simp [exec, Safe]
  | succ n ihn =>
    intro s
    induction s with
    | skip => intro σ Q _ h; simpa [exec, wp, Safe] using h
    | assign x e => intro σ Q _ h; simpa [exec, wp, Safe] using h
    | brk => intro σ Q _ h; simpa [exec, wp, Safe] using h
    | cont => intro σ Q _ h; simpa [exec, wp, Safe] using h
    | ret e => intro σ Q _ h; simpa [exec, wp, Safe] using h
    | obl m φ =>
      intro σ Q _ h
      simp only [exec, wp] at h ⊢
      exact oblR_safe h (fun _ hk => hk)
    | seq s t ihs iht =>
      intro σ Q hwf h
      simp only [WF] at hwf
      simp only [wp] at h
      have hs := ihs σ _ hwf.1 h
      simp only [exec]
      cases hr : exec P (n + 1) s σ with
      | normal σ' =>
        simp only [hr, Safe] at hs ⊢
        exact iht σ' Q hwf.2 hs
      | brk σ' => simpa [hr, Safe] using hs
      | cont σ' => simpa [hr, Safe] using hs
      | ret v σ' => simpa [hr, Safe] using hs
      | trap => simp [Safe]
      | fail => simp [hr, Safe] at hs
      | timeout => simp [Safe]
    | ite b s t ihs iht =>
      intro σ Q hwf h
      simp only [WF] at hwf
      simp only [wp] at h
      simp only [exec]
      cases hb : b σ with
      | true => simpa [hb] using ihs σ Q hwf.1 (h.1 hb)
      | false => simpa [hb] using iht σ Q hwf.2 (h.2 hb)
    | loop first b inv mI mP var mV body ihb =>
      intro σ Q hwf h
      simp only [WF] at hwf
      simp only [wp] at h
      simp only [exec]
      refine oblR_safe h (fun hinv hL => ?_)
      have hσ := hL σ (agree_refl _ _) hinv
      cases hb : b σ with
      | false => simpa [Safe] using hσ.2 hb
      | true =>
        simp only [if_pos hb]
        refine oblR_safe (hσ.1 hb) (fun _ hbody => ?_)
        have hres := ihb σ _ hwf hbody
        -- ponowne wejście do pętli w stanie σ' (zgodnym z σ poza `writes body`)
        have reenter : ∀ σ', exec P (n + 1) body σ = .normal σ' ∨ exec P (n + 1) body σ = .cont σ' →
            oblW mV (decide (var σ' < var σ) = true) (oblW mP (inv σ' = true) True) →
            Safe (oblR mV (decide (var σ' < var σ))
              (exec P n (.loop false b inv mI mP var mV body) σ')) Q := by
          intro σ' hex hpost
          have hag : agree (writes body) σ σ' := by
            apply exec_frame P (n + 1) body σ σ'
            rcases hex with hex | hex <;> rw [hex] <;> rfl
          refine oblR_safe hpost (fun _ hinvP => ?_)
          apply ihn (.loop false b inv mI mP var mV body) σ' Q (by simpa [WF] using hwf)
          simp only [wp, if_neg (by decide : ¬ (false = true))]
          apply oblW_weaken hinvP
          intro τ hτ hinvτ
          exact hL τ (agree_trans hag hτ) hinvτ
        cases hr : exec P (n + 1) body σ with
        | normal σ' =>
          simp only [hr, Safe, iterPost] at hres ⊢
          exact reenter σ' (Or.inl hr) hres
        | cont σ' =>
          simp only [hr, Safe, iterPost] at hres ⊢
          exact reenter σ' (Or.inr hr) hres
        | brk σ' => simpa [hr, Safe, iterPost] using hres
        | ret v σ' => simpa [hr, Safe, iterPost] using hres
        | trap => simp [Safe]
        | fail => simp [hr, Safe] at hres
        | timeout => simp [Safe]
    | call m x f args outs =>
      intro σ Q hwf h
      simp only [WF] at hwf
      simp only [wp] at h
      simp only [exec]
      refine oblR_safe h (fun hpre hQ => ?_)
      have hb := ihn _ _ (procPost (P f) (entry (P f) args outs σ)) (hW f) (hP f _ hpre)
      cases hr : exec P n (P f).body (entry (P f) args outs σ) with
      | ret v σf' =>
        simp only [hr, Safe, procPost] at hb ⊢
        cases hpost : (P f).post (entry (P f) args outs σ) σf' v with
        | true =>
          simp only [oblR, if_pos hpost, Safe]
          exact hQ v σf' _ hpost (afterCall_out _ _ _ _ _ _ hwf) (afterCall_res _ _ _ _ _ _)
            (agree_afterCall _ _ _ _ _ _)
        | false =>
          cases hm : (P f).mPost with
          | proved => simp [hpost, hm, oblW] at hb
          | erased => simp [hpost, hm, oblW] at hb
          | checked => simp [oblR, hpost, hm, Safe]
      | normal σ' => simp [hr, Safe, procPost] at hb
      | brk σ' => simp [hr, Safe, procPost] at hb
      | cont σ' => simp [hr, Safe, procPost] at hb
      | trap => simp [Safe]
      | fail => simp [hr, Safe] at hb
      | timeout => simp [Safe]

/-- Wniosek: przy poprawnym VC żadne wykonanie nie narusza udowodnionego zobowiązania. -/
theorem no_fail (P : Procs Val) (hP : ProcOK P) (hW : WFProcs P) (n : Nat) (s : Stmt Val)
    (σ : State Val) (Q : Post Val) (hwf : WF P s) (h : wp P s Q σ) : exec P n s σ ≠ .fail := by
  intro hf
  have := soundness P hP hW n s σ Q hwf h
  rw [hf] at this
  exact this

end

end Rdzen
