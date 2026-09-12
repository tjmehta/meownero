// Generated from hash-verified upstream; see extract.py.

use std::{collections::VecDeque, time::Duration};

const DIFFICULTY_WINDOW: usize = 720;

const DIFFICULTY_CUT: usize = 60;

const DIFFICULTY_LAG: usize = 15;

const BLOCK_TIME_V1: Duration = Duration::from_secs(60);

const BLOCK_TIME_V2: Duration = Duration::from_secs(120);

#[derive(Default, Clone, Copy)]

pub enum HardFork {
    #[default]
    V1 = 1,
    V2,
    V3,
    V4,
    V5,
    V6,
    V7,
    V8,
    V9,
    V10,
    V11,
    V12,
    V13,
    V14,
    V15,
    V16,
}

impl HardFork {

pub const fn block_time(self) -> Duration {
        match self {
            Self::V1 => BLOCK_TIME_V1,
            Self::V2
            | Self::V3
            | Self::V4
            | Self::V5
            | Self::V6
            | Self::V7
            | Self::V8
            | Self::V9
            | Self::V10
            | Self::V11
            | Self::V12
            | Self::V13
            | Self::V14
            | Self::V15
            | Self::V16 => BLOCK_TIME_V2,
        }
    }

}

pub struct DifficultyCacheConfig {
    pub window: usize,
    pub cut: usize,
    pub lag: usize,
    /// If [`Some`] the difficulty cache will always return this value as the current difficulty.
    pub fixed_difficulty: Option<u128>,
}

impl DifficultyCacheConfig {
    /// Returns the total amount of blocks we need to track to calculate difficulty
    pub const fn total_block_count(&self) -> usize {
        self.window + self.lag
    }

    /// The amount of blocks we account for after removing the outliers.
    pub const fn accounted_window_len(&self) -> usize {
        self.window - 2 * self.cut
    }

    /// Returns the config needed for [`Mainnet`](cuprate_helper::network::Network::Mainnet). This is also the
    /// config for all other current networks.
    pub const fn main_net() -> Self {
        Self {
            window: DIFFICULTY_WINDOW,
            cut: DIFFICULTY_CUT,
            lag: DIFFICULTY_LAG,
            fixed_difficulty: None,
        }
    }
}

fn next_difficulty(
    config: &DifficultyCacheConfig,
    timestamps: &VecDeque<u64>,
    cumulative_difficulties: &VecDeque<u128>,
    hf: HardFork,
) -> u128 {
    if let Some(fixed_difficulty) = config.fixed_difficulty {
        return fixed_difficulty;
    }

    if timestamps.len() <= 1 {
        return 1;
    }

    let mut timestamps = timestamps.clone();

    if timestamps.len() > config.window {
        // remove the lag.
        timestamps.drain(config.window..);
    }
    let timestamps_slice = timestamps.make_contiguous();

    let (window_start, window_end) = get_window_start_and_end(
        timestamps_slice.len(),
        config.accounted_window_len(),
        config.window,
    );

    // We don't sort the whole timestamp list
    let mut time_span = u128::from(
        *timestamps_slice.select_nth_unstable(window_end - 1).1
            - *timestamps_slice.select_nth_unstable(window_start).1,
    );

    let windowed_work =
        cumulative_difficulties[window_end - 1] - cumulative_difficulties[window_start];

    if time_span == 0 {
        time_span = 1;
    }

    // TODO: do `checked_mul` here and unwrap so we don't silently overflow?
    (windowed_work * u128::from(hf.block_time().as_secs())).div_ceil(time_span)
}

fn get_window_start_and_end(
    window_len: usize,
    accounted_window: usize,
    window: usize,
) -> (usize, usize) {
    debug_assert!(window > accounted_window);

    let window_len = if window_len > window {
        window
    } else {
        window_len
    };

    if window_len <= accounted_window {
        (0, window_len)
    } else {
        let start = (window_len - (accounted_window)).div_ceil(2);
        (start, start + accounted_window)
    }
}

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
