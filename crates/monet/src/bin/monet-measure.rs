//! Offline calculator for measurement expressions from the desktop Command Bar.
use std::time::{Duration, Instant};

struct Deadline(Instant);

impl fend_core::Interrupt for Deadline {
    fn should_interrupt(&self) -> bool {
        Instant::now() >= self.0
    }
}

fn main() {
    let mut args = std::env::args().skip(1);
    let Some(expression) = args.next() else {
        return;
    };
    if args.next().is_some() || expression.len() > 768 {
        return;
    }
    if expression == "--license" {
        print!("{}", include_str!("../../fend-LICENSE.md"));
        return;
    }
    let mut context = fend_core::Context::new();
    context.disable_rng();
    let deadline = Deadline(Instant::now() + Duration::from_millis(70));
    if let Ok(value) = fend_core::evaluate_with_interrupt(&expression, &mut context, &deadline) {
        let text = value.get_main_result();
        if text.len() <= 160 && !text.chars().any(char::is_control) {
            println!("{text}");
        }
    }
}
