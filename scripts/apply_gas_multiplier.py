#!/usr/bin/env python3
"""
Apply gas/fee multipliers to Aptos gas parameter definitions.

Gas types receive --gas-multiplier:
  Gas, InternalGas, InternalGasPerAbstractValueUnit, InternalGasPerArg, InternalGasPerByte, InternalGasPerTypeNode

Storage fee types receive --storage-fee-multiplier:
  Fee, FeePerByte, FeePerSlot

All other types are left unchanged.

Values that are not pure integer literals (e.g. constants, expressions like
`64 * 1024`) are skipped with a warning -- update those manually if needed.

Usage:
    # Apply to all gas schedule files (run from repo root):
    python3 scripts/apply_gas_multiplier.py --gas-multiplier 2 --storage-fee-multiplier 4

    # Dry-run to preview changes:
    python3 scripts/apply_gas_multiplier.py --gas-multiplier 2 --storage-fee-multiplier 4 --dry-run

    # Apply to specific files:
    python3 scripts/apply_gas_multiplier.py --gas-multiplier 2 --storage-fee-multiplier 4 path/to/file.rs
"""

import argparse
import re
import sys
from pathlib import Path

GAS_TYPES = {
    "Gas",
    "InternalGas",
    "InternalGasPerAbstractValueUnit",
    "InternalGasPerArg",
    "InternalGasPerByte",
    "InternalGasPerTypeNode",
}

STORAGE_FEE_TYPES = {
    "Fee",
    "FeePerByte",
    "FeePerSlot",
}

DEFAULT_FILES = [
    "aptos-move/aptos-gas-schedule/src/gas_schedule/aptos_framework.rs",
    "aptos-move/aptos-gas-schedule/src/gas_schedule/instr.rs",
    "aptos-move/aptos-gas-schedule/src/gas_schedule/misc.rs",
    "aptos-move/aptos-gas-schedule/src/gas_schedule/move_stdlib.rs",
    "aptos-move/aptos-gas-schedule/src/gas_schedule/table.rs",
    "aptos-move/aptos-gas-schedule/src/gas_schedule/transaction.rs",
]


def strip_comments(text):
    """
    Return a copy of text with // and /* */ comments blanked out (replaced by
    spaces, preserving newlines and character positions).  String literals are
    left untouched so that quoted keys such as "load_data.base" are preserved.
    """
    result = list(text)
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '"':
            # Skip over string literal.
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    i += 1
                i += 1
            i += 1  # closing "
        elif text[i : i + 2] == "//":
            # Blank to end of line, keep newline.
            while i < n and text[i] != "\n":
                result[i] = " "
                i += 1
        elif text[i : i + 2] == "/*":
            # Blank block comment, keep newlines.
            while i < n and text[i : i + 2] != "*/":
                if text[i] != "\n":
                    result[i] = " "
                i += 1
            if i < n:
                result[i] = " "
                result[i + 1] = " "
                i += 2
        else:
            i += 1
    return "".join(result)


def find_bracket_end(text, start):
    """
    Return the index of the ] that matches the [ at `start`, skipping over
    nested brackets, brace blocks {…}, and string literals.
    Returns -1 if not found.
    """
    assert text[start] == "[", f"Expected '[' at position {start}, got {text[start]!r}"
    depth = 1
    i = start + 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i
        elif c == "{":
            brace = 1
            i += 1
            while i < n and brace > 0:
                if text[i] == "{":
                    brace += 1
                elif text[i] == "}":
                    brace -= 1
                i += 1
            continue
        elif c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    i += 1
                i += 1
        i += 1
    return -1


def top_level_commas(text):
    """
    Return the positions of commas in `text` that are not inside (), [], {},
    or string literals (depth 0).
    """
    positions = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    i += 1
                i += 1
        elif c == "," and depth == 0:
            positions.append(i)
        i += 1
    return positions


def find_macro_bounds(text):
    """
    Find the character range [start, end) of the body inside
    define_gas_parameters!(...).  `start` is the position just after the
    opening '(' and `end` is the position of the matching ')'.
    Returns (start, end) or (-1, -1) if not found.
    """
    idx = text.find("define_gas_parameters!")
    if idx == -1:
        return -1, -1
    # Advance to the opening '('
    i = idx + len("define_gas_parameters!")
    n = len(text)
    while i < n and text[i] != "(":
        i += 1
    if i >= n:
        return -1, -1
    open_paren = i + 1  # body starts after '('
    depth = 1
    i += 1
    while i < n and depth > 0:
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return open_paren, i
        elif c == "{":
            brace = 1
            i += 1
            while i < n and brace > 0:
                if text[i] == "{":
                    brace += 1
                elif text[i] == "}":
                    brace -= 1
                i += 1
            continue
        elif c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    i += 1
                i += 1
        i += 1
    return -1, -1


def format_int(value, use_underscores):
    """
    Format an integer as a string, inserting _ separators every 3 digits from
    the right when `use_underscores` is True.
    """
    s = str(value)
    if not use_underscores or len(s) <= 3:
        return s
    # Group digits from the right in chunks of 3.
    chunks = []
    while s:
        chunks.append(s[-3:])
        s = s[:-3]
    return "_".join(reversed(chunks))


def process_file(filepath, gas_mult, fee_mult, dry_run=False):
    """
    Parse `filepath`, find all parameter entries in define_gas_parameters!,
    apply the appropriate multiplier to pure integer literal values, and write
    the result back (unless dry_run).

    Returns a list of (param_name, param_type, old_str, new_str) for each
    changed parameter.
    """
    content = Path(filepath).read_text()

    if "define_gas_parameters!" not in content:
        return []

    # Work on a comment-stripped copy that shares character positions with the
    # original so we can map any found integer back to the original file.
    stripped = strip_comments(content)

    changes = []  # (abs_start, abs_end, new_text, name, type_, old_str)

    # Restrict search to the body of the define_gas_parameters! macro.
    macro_start, macro_end = find_macro_bounds(stripped)
    if macro_start == -1:
        print(f"  WARNING: could not locate define_gas_parameters! body in {filepath}", file=sys.stderr)
        return []
    macro_body = stripped[macro_start:macro_end]

    # Each parameter entry begins with [<ident>: <Type>,
    param_re = re.compile(r"\[\s*(\w+)\s*:\s*(\w+)\s*,")

    for m in param_re.finditer(macro_body):
        bracket_pos = macro_start + m.start()
        param_name = m.group(1)
        param_type = m.group(2)

        if param_type in GAS_TYPES:
            multiplier = gas_mult
        elif param_type in STORAGE_FEE_TYPES:
            multiplier = fee_mult
        else:
            continue  # Not a type we care about.

        # Find the closing ] of this entry.
        end_pos = find_bracket_end(stripped, bracket_pos)
        if end_pos == -1:
            print(
                f"  WARNING: unmatched bracket for {param_name} in {filepath}",
                file=sys.stderr,
            )
            continue

        # Entry interior (without the outer brackets).
        entry = stripped[bracket_pos + 1 : end_pos]

        # Split on top-level commas: [name: Type] [key_spec] [value] [trailing?]
        commas = top_level_commas(entry)

        if len(commas) < 2:
            print(
                f"  WARNING: unexpected format for {param_name} (only {len(commas)} comma(s))",
                file=sys.stderr,
            )
            continue

        # Value is the segment between commas[1] and either commas[2] (trailing
        # comma style) or the end of the entry.
        val_start_in_entry = commas[1] + 1
        val_end_in_entry = commas[2] if len(commas) > 2 else len(entry)

        # Stripped version of the value text (comments already blanked).
        value_text = entry[val_start_in_entry:val_end_in_entry].strip()

        # Only handle pure integer literals (digits + underscores).
        if not re.match(r"^\d[\d_]*$", value_text):
            print(
                f"  SKIP {param_name} ({param_type}): non-literal value {value_text!r}",
                file=sys.stderr,
            )
            continue

        old_int = int(value_text.replace("_", ""))
        new_int = old_int * multiplier

        if new_int == old_int:
            continue

        use_underscores = "_" in value_text
        new_str = format_int(new_int, use_underscores)

        # Locate the integer literal using the comment-stripped region (which
        # shares character positions with the original content, since
        # strip_comments only replaces comment chars with spaces).
        region_start = bracket_pos + 1 + val_start_in_entry
        region_end = bracket_pos + 1 + val_end_in_entry
        stripped_region = stripped[region_start:region_end]

        # Find the first run of digits (possibly with underscores) in that region.
        int_match = re.search(r"\b(\d[\d_]*)\b", stripped_region)
        if not int_match:
            print(
                f"  WARNING: could not locate integer in stripped content for {param_name}",
                file=sys.stderr,
            )
            continue

        found_int = int(int_match.group(1).replace("_", ""))
        if found_int != old_int:
            print(
                f"  WARNING: value mismatch for {param_name}: "
                f"expected {old_int}, found {found_int}",
                file=sys.stderr,
            )
            continue

        abs_start = region_start + int_match.start()
        abs_end = region_start + int_match.end()

        changes.append((abs_start, abs_end, new_str, param_name, param_type, value_text))

    if not changes:
        return []

    # Apply changes from back to front to preserve absolute positions.
    results = []
    new_content = content
    for abs_start, abs_end, new_str, name, type_, old_str in sorted(
        changes, key=lambda x: x[0], reverse=True
    ):
        new_content = new_content[:abs_start] + new_str + new_content[abs_end:]
        results.append((name, type_, old_str, new_str))

    if not dry_run:
        Path(filepath).write_text(new_content)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Apply gas/fee multipliers to Aptos gas parameter definitions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--gas-multiplier",
        type=int,
        default=1,
        help="Multiplier for gas types (default: 1)",
    )
    parser.add_argument(
        "--storage-fee-multiplier",
        type=int,
        default=1,
        help="Multiplier for storage fee types (default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without modifying any files.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Files to process (default: all gas schedule files).",
    )
    args = parser.parse_args()

    files = args.files if args.files else DEFAULT_FILES

    total_params = 0
    total_files = 0

    for filepath in files:
        path = Path(filepath)
        if not path.exists():
            print(f"WARNING: {filepath} not found -- skipping", file=sys.stderr)
            continue

        prefix = "[DRY RUN] " if args.dry_run else ""
        print(f"\n{prefix}Processing {filepath} ...")

        results = process_file(filepath, args.gas_multiplier, args.storage_fee_multiplier, args.dry_run)

        if results:
            for name, type_, old, new in results:
                print(f"  {name} ({type_}): {old} -> {new}")
            total_params += len(results)
            total_files += 1
        else:
            print("  (no changes)")

    action = "Would change" if args.dry_run else "Changed"
    print(f"\n{action} {total_params} parameter(s) across {total_files} file(s).")


if __name__ == "__main__":
    main()
