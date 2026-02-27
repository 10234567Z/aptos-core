// Copyright © Aptos Foundation
// SPDX-License-Identifier: Apache-2.0

// flag: --language-version=2.4

// E2E tests for lemma declarations: plain apply, preconditioned apply,
// and universally-quantified forall...apply with triggers.
module 0x42::proof_lemma {

    // ==================================================================
    // Lemma verified by prover (no proof body = VC).

    spec module {
        lemma add_zero_right(x: u64) {
            ensures x + 0 == x;
        }
    }

    fun identity_via_add(x: u64): u64 {
        x + 0
    }
    spec identity_via_add {
        ensures result == x;
    } proof {
        apply add_zero_right(x);
    }

    // ==================================================================
    // Trusted lemma with preconditions.

    spec module {
        lemma small_mul_bound(x: u64, y: u64) {
            requires x <= 1000;
            requires y <= 1000;
            ensures x * y <= 1000000;
        } proof {
            assume [trusted] true;
        }
    }

    fun small_product(x: u64, y: u64): u64 {
        x * y
    }
    spec small_product {
        requires x <= 1000;
        requires y <= 1000;
        ensures result <= 1000000;
    } proof {
        apply small_mul_bound(x, y);
    }

    // ==================================================================
    // Trusted commutativity lemma applied at a use site.

    spec module {
        lemma add_comm(a: u64, b: u64) {
            ensures a + b == b + a;
        } proof {
            assume [trusted] true;
        }
    }

    fun swap_add(a: u64, b: u64): u64 {
        b + a
    }
    spec swap_add {
        ensures result == a + b;
    } proof {
        apply add_comm(a, b);
    }

    // ==================================================================
    // forall...apply with triggers.
    //
    // Spec function sum(n) = 1 + 2 + ... + n.
    // Monotonicity lemma proved inductively: x <= y ==> sum(x) <= sum(y).
    // Parameters are `num` (mathematical integers) so the prover can
    // reason about subtraction without underflow concerns.

    spec fun sum(n: num): num {
        if (n == 0) { 0 } else { n + sum(n - 1) }
    }

    spec module {
        lemma monotonicity(x: num, y: num) {
            requires 0 <= x;
            requires x <= y;
            ensures sum(x) <= sum(y);
        } proof {
            if (x < y) {
                assert sum(y - 1) <= sum(y);
                apply monotonicity(x, y - 1);
            }
        }
    }

    fun sum_up_to(n: u64): u64 {
        if (n == 0) { 0 }
        else { n + sum_up_to(n - 1) }
    }
    spec sum_up_to {
        aborts_if sum(n) > MAX_U64;
        ensures result == sum(n);
    } proof {
        // The recursive call requires sum(n-1) <= MAX_U64 - n, which
        // follows from sum(n-1) <= sum(n) <= MAX_U64 via monotonicity.
        forall x: num, y: num {sum(x), sum(y)} apply monotonicity(x, y);
    }

    // ==================================================================
    // Mutually recursive lemmas.
    //
    // Two mutually recursive spec functions f and g (Fibonacci-like):
    //   f(n) = f(n-1) + g(n-1),  g(n) = f(n-1)
    // Lemma f_pos proves f(n) >= 1 using g_nonneg, and g_nonneg
    // proves g(n) >= 0 using f_pos — genuine mutual recursion.

    spec fun f(n: num): num {
        if (n <= 0) { 1 } else { f(n - 1) + g(n - 1) }
    }
    spec fun g(n: num): num {
        if (n <= 0) { 0 } else { f(n - 1) }
    }

    spec module {
        lemma f_pos(n: num) {
            requires 0 <= n;
            ensures f(n) >= 1;
        } proof {
            if (n > 0) {
                apply f_pos(n - 1);
                apply g_nonneg(n - 1);
            }
        }

        lemma g_nonneg(n: num) {
            requires 0 <= n;
            ensures g(n) >= 0;
        } proof {
            if (n > 0) {
                apply f_pos(n - 1);
            }
        }
    }
}
