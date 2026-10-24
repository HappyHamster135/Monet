//! The window's words in Windows' display language, from Monet's own
//! translations (each crate's words_table.rs, written by tools/make-translations.py
//! from po/). English when Windows speaks a language Monet doesn't yet. Monet Bridge
//! uses this file too.

use std::sync::OnceLock;

use crate::words_table as table;

fn language() -> &'static str {
    static LANGUAGE: OnceLock<&'static str> = OnceLock::new();
    // MONET_LANGID (a Windows language id, 0x407 say) shows another language, for a look.
    let asked = std::env::var("MONET_LANGID").ok().and_then(|id| u16::from_str_radix(id.trim_start_matches("0x"), 16).ok());
    LANGUAGE.get_or_init(|| code(asked.unwrap_or_else(|| unsafe { windows_sys::Win32::Globalization::GetUserDefaultUILanguage() })))
}

/// Whether the words read right to left.
#[allow(dead_code)] // Make-USB-Stick's window is laid out one way
pub fn rtl() -> bool {
    matches!(language(), "ar" | "he")
}

/// Windows' language id (its primary language in the low 10 bits, the region's
/// variant above them) as one of Monet's language codes.
fn code(id: u16) -> &'static str {
    let (primary, sub) = (id & 0x3ff, id >> 10);
    match primary {
        0x01 => "ar",
        // Simplified for the mainland and Singapore, traditional for Taiwan, Hong Kong and Macau.
        0x04 if sub == 0x02 || sub == 0x04 => "zh_CN",
        0x04 => "zh_TW",
        0x05 => "cs",
        0x06 => "da",
        0x07 => "de",
        0x08 => "el",
        0x0a => "es",
        0x0b => "fi",
        0x0c => "fr",
        0x0d => "he",
        0x0e => "hu",
        0x10 => "it",
        0x11 => "ja",
        0x12 => "ko",
        0x13 => "nl",
        0x14 => "nb",
        0x15 => "pl",
        0x16 if sub == 0x01 => "pt_BR",
        0x16 => "pt",
        0x18 => "ro",
        0x19 => "ru",
        0x1d => "sv",
        0x1e => "th",
        0x1f => "tr",
        0x21 => "id",
        0x22 => "uk",
        0x2a => "vi",
        0x39 => "hi",
        _ => "en",
    }
}

/// text in Windows' language, or as it is.
pub fn tr(text: &str) -> String {
    let language = language();
    table::TABLE
        .iter()
        .find(|(code, _)| *code == language)
        .and_then(|(_, words)| words.iter().find(|(english, _)| *english == text))
        .map(|(_, said)| said.to_string())
        .unwrap_or_else(|| text.to_string())
}

/// The same, with %1, %2... filled in.
pub fn trf(text: &str, values: &[&str]) -> String {
    let mut said = tr(text);
    for (i, value) in values.iter().enumerate().rev() {
        said = said.replace(&format!("%{}", i + 1), value);
    }
    said
}
