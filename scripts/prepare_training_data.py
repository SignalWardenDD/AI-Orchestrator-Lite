# scripts/prepare_training_data.py
from __future__ import annotations
import argparse, os, sys
from datetime import datetime, timezone
from typing import List, Dict, Any
import pandas as pd
import numpy as np

def load_csv_data(data_dir: str, interval: str) -> Dict[str, pd.DataFrame]:
    """Load all CSV files from data directory for given interval."""
    interval_dir = os.path.join(data_dir, interval)
    if not os.path.exists(interval_dir):
        print(f"Directory not found: {interval_dir}")
        return {}
    
    data = {}
    for filename in os.listdir(interval_dir):
        if filename.endswith('.csv'):
            symbol = filename.split('_')[0]
            filepath = os.path.join(interval_dir, filename)
            try:
                df = pd.read_csv(filepath, parse_dates=['timestamp'], index_col='timestamp')
                data[symbol] = df
                print(f"Loaded {symbol}: {len(df)} bars")
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    
    return data

def prepare_features(ohlc: pd.DataFrame) -> pd.DataFrame:
    """Prepare features for ML training."""
    close = ohlc['close']
    high, low = ohlc['high'], ohlc['low']
    
    feat = pd.DataFrame(index=ohlc.index)
    
    # Returns
    feat['ret_1'] = close.pct_change(1)
    feat['ret_3'] = close.pct_change(3)
    feat['ret_6'] = close.pct_change(6)
    
    # EMAs
    feat['ema20'] = close.ewm(span=20).mean()
    feat['ema50'] = close.ewm(span=50).mean()
    feat['ema200'] = close.ewm(span=200).mean()
    feat['ema20_slope'] = feat['ema20'].pct_change(1)
    
    # Volatility
    feat['natr14'] = ((high - low) / close * 100).ewm(span=14).mean()
    feat['rng_1'] = (high - low) / close
    feat['rng_3'] = feat['rng_1'].rolling(3).mean()
    
    # Z-score
    diff = close - feat['ema50']
    rolling_mean = diff.rolling(50).mean()
    rolling_std = diff.rolling(50).std()
    feat['z_close_50'] = (diff - rolling_mean) / rolling_std.replace(0, np.nan)
    
    # Lags
    for k in (1, 2, 3):
        feat[f'ret_1_lag{k}'] = feat['ret_1'].shift(k)
        feat[f'rng_1_lag{k}'] = feat['rng_1'].shift(k)
    
    # Clean up
    feat = feat.replace([np.inf, -np.inf], np.nan).dropna()
    return feat

def create_labels(ohlc: pd.DataFrame, horizon_bars: int = 24, tp_mult_atr: float = 2.0, sl_mult_atr: float = 2.0) -> pd.Series:
    """Create binary hit/miss labels for ML training."""
    close = ohlc['close']
    high, low = ohlc['high'], ohlc['low']
    
    # Calculate ATR
    tr = np.maximum(high - low, np.maximum(np.abs(high - close.shift(1)), np.abs(low - close.shift(1))))
    atr = tr.ewm(span=14).mean()
    
    labels = []
    for i in range(len(ohlc)):
        if i + horizon_bars >= len(ohlc):
            labels.append(0)  # Not enough future data
            continue
            
        current_price = close.iloc[i]
        current_atr = atr.iloc[i]
        
        # TP and SL levels
        tp_level = current_price * (1 + tp_mult_atr * current_atr / current_price)
        sl_level = current_price * (1 - sl_mult_atr * current_atr / current_price)
        
        # Check future bars
        future_high = high.iloc[i+1:i+horizon_bars+1].max()
        future_low = low.iloc[i+1:i+horizon_bars+1].min()
        
        # Binary hit: TP hit before SL
        if future_high >= tp_level and future_low > sl_level:
            labels.append(1)  # Hit TP
        elif future_low <= sl_level:
            labels.append(0)  # Hit SL
        else:
            labels.append(0)  # Neither hit
    
    return pd.Series(labels, index=ohlc.index)

def combine_data(data: Dict[str, pd.DataFrame], horizon_bars: int = 24) -> pd.DataFrame:
    """Combine data from all symbols into single training dataset."""
    all_features = []
    all_labels = []
    
    for symbol, ohlc in data.items():
        print(f"Processing {symbol}...")
        
        # Prepare features
        features = prepare_features(ohlc)
        if features.empty:
            continue
            
        # Create labels
        labels = create_labels(ohlc, horizon_bars)
        
        # Align features and labels
        common_idx = features.index.intersection(labels.index)
        if len(common_idx) < 100:  # Need minimum data
            print(f"  Skipping {symbol}: insufficient data ({len(common_idx)} bars)")
            continue
            
        features = features.loc[common_idx]
        labels = labels.loc[common_idx]
        
        # Add symbol one-hot
        features[f'sym__{symbol}'] = 1.0
        
        all_features.append(features)
        all_labels.append(labels)
        print(f"  {symbol}: {len(features)} samples")
    
    if not all_features:
        print("No data to combine!")
        return pd.DataFrame()
    
    # Combine all data
    combined_features = pd.concat(all_features, axis=0)
    combined_labels = pd.concat(all_labels, axis=0)
    
    # Align indices
    common_idx = combined_features.index.intersection(combined_labels.index)
    combined_features = combined_features.loc[common_idx]
    combined_labels = combined_labels.loc[common_idx]
    
    # Add labels to features
    combined_features['target'] = combined_labels
    
    return combined_features

def save_training_data(df: pd.DataFrame, output_dir: str, horizon_bars: int):
    """Save training data in multiple formats."""
    os.makedirs(output_dir, exist_ok=True)
    
    # CSV format
    csv_path = os.path.join(output_dir, f'training_data_H{horizon_bars}.csv')
    df.to_csv(csv_path)
    print(f"Saved CSV: {csv_path}")
    
    # Parquet format (more efficient)
    parquet_path = os.path.join(output_dir, f'training_data_H{horizon_bars}.parquet')
    df.to_parquet(parquet_path)
    print(f"Saved Parquet: {parquet_path}")
    
    # Train/Val split
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    val_df = df.iloc[split_idx:]
    
    train_path = os.path.join(output_dir, f'train_H{horizon_bars}.parquet')
    val_path = os.path.join(output_dir, f'val_H{horizon_bars}.parquet')
    
    train_df.to_parquet(train_path)
    val_df.to_parquet(val_path)
    
    print(f"Train/Val split: {len(train_df)} train, {len(val_df)} val")
    print(f"Train: {train_path}")
    print(f"Val: {val_path}")

def main():
    ap = argparse.ArgumentParser(description="Prepare training data from Binance OHLCV data.")
    ap.add_argument("--data_dir", type=str, default="data/raw/binance_futures",
                    help="Directory with downloaded CSV files")
    ap.add_argument("--interval", type=str, default="1h", help="Time interval to use")
    ap.add_argument("--horizon", type=int, default=24, help="Prediction horizon in bars")
    ap.add_argument("--output", type=str, default="data/processed",
                    help="Output directory for processed data")
    ap.add_argument("--tp_mult", type=float, default=2.0, help="TP multiplier for ATR")
    ap.add_argument("--sl_mult", type=float, default=2.0, help="SL multiplier for ATR")
    
    args = ap.parse_args()
    
    print(f"Loading data from {args.data_dir}/{args.interval}")
    data = load_csv_data(args.data_dir, args.interval)
    
    if not data:
        print("No data found!")
        sys.exit(1)
    
    print(f"Combining data from {len(data)} symbols...")
    combined = combine_data(data, args.horizon)
    
    if combined.empty:
        print("No combined data!")
        sys.exit(1)
    
    print(f"Combined dataset: {len(combined)} samples, {len(combined.columns)-1} features")
    print(f"Target distribution: {combined['target'].value_counts().to_dict()}")
    
    save_training_data(combined, args.output, args.horizon)
    print("Training data preparation complete!")

if __name__ == "__main__":
    main()
