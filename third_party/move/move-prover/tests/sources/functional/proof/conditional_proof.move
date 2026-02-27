// Copyright © Aptos Foundation
// SPDX-License-Identifier: Apache-2.0

// flag: --language-version=2.4

// E2E tests for conditional proofs with splits and case analysis.
module 0x42::proof_conditional {

    // ==================================================================
    // Simple if/else case split with tautological assertions.

    fun safe_div(x: u64, y: u64): u64 {
        if (y == 0) { 0 } else { x / y }
    }
    spec safe_div {
        ensures y == 0 ==> result == 0;
        ensures y != 0 ==> result == x / y;
    } proof {
        if (y == 0) {
            assert true;
        } else {
            assert y != 0;
        }
    }

    // ==================================================================
    // Conditional proof with lemma use.

    spec module {
        lemma mul_comm(a: u64, b: u64) {
            ensures a * b == b * a;
        } proof {
            assume [trusted] true;
        }
    }

    fun commute_mul(x: u64, y: u64): u64 {
        y * x
    }
    spec commute_mul {
        ensures result == x * y;
    } proof {
        apply mul_comm(x, y);
    }
}
