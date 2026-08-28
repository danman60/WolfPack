"""
Drop-in replacement for Kronos's finetune/config.py — tailored to our crypto-perp 1h dataset.

Used by patched copies of train_tokenizer.py / train_predictor.py via:
    cp idea6_finetune_config.py ~/projects/Kronos/finetune/config.py
"""

from pathlib import Path

CRYPTO_DATASET_PATH = Path("/home/danman60/projects/WolfPack/docs/research/2026-05-15-kronos-edge/finetune")
SAVE_PATH = Path("/mnt/firmament/hf-cache/kronos-finetune-crypto")  # save large checkpoints to SMB


class Config:
    def __init__(self):
        # Data & feature parameters
        self.qlib_data_path = ""  # unused — we pre-build pickles
        self.instrument = "crypto_perp_top3"

        # Hourly crypto window — 480 candles in, 24 candles out (matches our serving window)
        self.dataset_begin_time = "2017-01-01"
        self.dataset_end_time = "2030-01-01"
        self.lookback_window = 480
        self.predict_window = 24
        self.max_context = 512

        self.feature_list = ["open", "high", "low", "close", "vol", "amt"]
        self.time_feature_list = ["minute", "hour", "weekday", "day", "month"]

        # Splits already baked into the pickle files — these are placeholders
        self.train_time_range = ["2017-01-01", "2025-11-15"]
        self.val_time_range   = ["2025-11-15", "2026-02-14"]
        self.test_time_range  = ["2026-02-14", "2030-01-01"]
        self.backtest_time_range = ["2026-02-14", "2030-01-01"]

        self.dataset_path = str(CRYPTO_DATASET_PATH)

        # Training hyperparameters
        self.clip = 5.0
        self.epochs = 5             # SMALL — scaled down from 30 to fit one GPU overnight
        self.log_interval = 25
        self.batch_size = 32        # 3060 12GB headroom

        # We're fine-tuning, not training from scratch. Cap iterations per epoch.
        self.n_train_iter = 400 * self.batch_size      # 12,800 samples / epoch
        self.n_val_iter   = 80 * self.batch_size

        self.tokenizer_learning_rate = 5e-5   # gentler than 2e-4 default — we're fine-tuning
        self.predictor_learning_rate = 1e-5   # gentler than 4e-5 default

        self.accumulation_steps = 2

        self.adam_beta1 = 0.9
        self.adam_beta2 = 0.95
        self.adam_weight_decay = 0.1

        self.seed = 100

        # No Comet — keep it local
        self.use_comet = False
        self.comet_config = {"api_key": "", "project_name": "", "workspace": ""}
        self.comet_tag = "crypto"
        self.comet_name = "crypto"

        # Checkpoints to SMB so we don't fill the 31 GB-free system disk
        self.save_path = str(SAVE_PATH)
        self.tokenizer_save_folder_name = "tokenizer"
        self.predictor_save_folder_name = "predictor"
        self.backtest_save_folder_name = "backtest"

        self.backtest_result_path = str(SAVE_PATH / "backtest_results")

        # Pretrained — point at the HF-cached snapshots so we don't re-download
        self.pretrained_tokenizer_path = "NeoQuasar/Kronos-Tokenizer-base"
        self.pretrained_predictor_path = "NeoQuasar/Kronos-small"

        self.finetuned_tokenizer_path = f"{self.save_path}/{self.tokenizer_save_folder_name}/checkpoints/best_model"
        self.finetuned_predictor_path = f"{self.save_path}/{self.predictor_save_folder_name}/checkpoints/best_model"

        # Backtest params (we won't use Kronos's built-in qlib backtest — out of scope)
        self.backtest_n_symbol_hold = 1
        self.backtest_n_symbol_drop = 0
        self.backtest_hold_thresh = 1
        self.inference_T = 1.0
        self.inference_top_p = 0.9
        self.inference_top_k = 0
        self.inference_sample_count = 4
        self.backtest_batch_size = 64
        self.backtest_benchmark = "BTCUSDT"  # unused for our flow
