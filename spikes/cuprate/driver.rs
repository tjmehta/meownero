// Local stream adapter. Inputs contain post-genesis samples, oldest first.
// Every row: count, then count pairs of (u64 timestamp, u128 cumulative work).
// Only HardFork::V16 (120 seconds), with unmodified main_net config, is exercised.
fn main() {
    use std::io::{self, BufRead};
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let mut fields = line.split_whitespace();
        let count: usize = fields.next().unwrap().parse().unwrap();
        assert!(count <= 735);
        let mut timestamps = VecDeque::new();
        let mut work = VecDeque::new();
        for _ in 0..count {
            timestamps.push_back(fields.next().unwrap().parse::<u64>().unwrap());
            work.push_back(fields.next().unwrap().parse::<u128>().unwrap());
        }
        assert!(fields.next().is_none());
        assert!(work.iter().zip(work.iter().skip(1)).all(|(a, b)| a < b));
        println!("{}", next_difficulty(&DifficultyCacheConfig::main_net(),
                                      &timestamps, &work, HardFork::V16));
    }
}
