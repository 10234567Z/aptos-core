// Copyright (c) Aptos Foundation
// Licensed pursuant to the Innovation-Enabling Source Code License, available at https://github.com/aptos-labs/aptos-core/blob/main/LICENSE

//! General utilities shared across the crate.

use std::path::Path;

/// Find the Move package root by walking up from the given directory.
pub fn find_package_root(start: &Path) -> Option<std::path::PathBuf> {
    let mut dir = start;
    loop {
        let manifest = dir.join("Move.toml");
        if manifest.is_file() {
            return Some(dir.to_path_buf());
        }
        match dir.parent() {
            Some(parent) => dir = parent,
            None => return None,
        }
    }
}
