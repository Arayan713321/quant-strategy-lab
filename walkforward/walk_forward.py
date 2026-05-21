import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from backtest.run_backtest import run_backtest

logger = logging.getLogger(__name__)

def generate_wfa_windows(df: pd.DataFrame, train_years: int = 2, test_months: int = 6) -> list:
    """
    Generates chronological rolling windows with In-Sample (Train) and 
    Out-of-Sample (Test) boundaries using Pandas DateOffsets.
    """
    start_date = df.index.min()
    end_date = df.index.max()
    
    windows = []
    current_start = start_date
    
    while True:
        # Define In-Sample (IS) Training range
        is_start = current_start
        is_end = is_start + pd.DateOffset(years=train_years) - pd.Timedelta(days=1)
        
        # Define Out-of-Sample (OOS) Testing range
        oos_start = is_end + pd.Timedelta(days=1)
        oos_end = oos_start + pd.DateOffset(months=test_months) - pd.Timedelta(days=1)
        
        # Cease rolling if OOS window exceeds the dataset's tail
        if oos_end > end_date:
            break
            
        windows.append({
            'is_start': is_start,
            'is_end': is_end,
            'oos_start': oos_start,
            'oos_end': oos_end
        })
        
        # Shift anchor forward by test_months (standard rolling increment)
        current_start = current_start + pd.DateOffset(months=test_months)
        
    logger.info(f"Generated {len(windows)} rolling Walk-Forward windows from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    return windows

def run_wfa(df: pd.DataFrame) -> dict:
    """
    Executes rolling Walk-Forward Analysis (WFA) on the stock dataset.
    Optimizes parameters on IS (2 years) and evaluates on unseen OOS (6 months).
    
    Grid Search parameters:
    - sma_fast: [15, 20, 25]
    - sma_slow: [45, 50, 60]
    - rsi_trigger: [50, 55, 60]
    """
    windows = generate_wfa_windows(df, train_years=2, test_months=6)
    if not windows:
        raise ValueError("Insufficient data to generate WFA windows. Check dataset length.")
        
    wfa_records = []
    
    # Define hyperparameter grid
    sma_fast_grid = [15, 20, 25]
    sma_slow_grid = [45, 50, 60]
    rsi_trigger_grid = [50, 55, 60]
    
    logger.info("Beginning Walk-Forward Analysis grid-search optimization...")
    
    for idx, win in enumerate(windows, 1):
        is_start, is_end = win['is_start'], win['is_end']
        oos_start, oos_end = win['oos_start'], win['oos_end']
        
        df_is = df.loc[is_start:is_end]
        df_oos = df.loc[oos_start:oos_end]
        
        if len(df_is) < 100 or len(df_oos) < 20:
            logger.warning(f"Window {idx} skipped due to insufficient trading days.")
            continue
            
        # --- 1. Optimization Phase (In-Sample Grid Search) ---
        best_sharpe = -float('inf')
        best_params = None
        best_is_metrics = None
        
        for fast in sma_fast_grid:
            for slow in sma_slow_grid:
                # Ensure fast SMA is less than slow SMA
                if fast >= slow:
                    continue
                for rsi in rsi_trigger_grid:
                    params = {
                        'sma_fast': fast,
                        'sma_slow': slow,
                        'rsi_trigger': rsi,
                        'verbose': False  # Suppress individual grid-search prints
                    }
                    
                    try:
                        metrics, _, _ = run_backtest(df_is, params=params)
                        sh = metrics['sharpe_ratio']
                        
                        # Maximize Sharpe Ratio
                        if sh > best_sharpe:
                            best_sharpe = sh
                            best_params = params.copy()
                            best_is_metrics = metrics.copy()
                    except Exception as e:
                        # Fail-safe for individual parameter errors
                        continue
                        
        if best_params is None:
            logger.warning(f"Window {idx} failed to find optimal parameters. Skipping.")
            continue
            
        # --- 2. Evaluation Phase (Out-of-Sample Backtesting) ---
        try:
            # Force verbose=False for standard OOS evaluation
            best_params['verbose'] = False
            oos_metrics, oos_trades, oos_ts = run_backtest(df_oos, params=best_params)
            
            wfa_record = {
                'window': idx,
                'is_range': f"{is_start.strftime('%Y-%m-%d')} to {is_end.strftime('%Y-%m-%d')}",
                'oos_range': f"{oos_start.strftime('%Y-%m-%d')} to {oos_end.strftime('%Y-%m-%d')}",
                'opt_sma_fast': best_params['sma_fast'],
                'opt_sma_slow': best_params['sma_slow'],
                'opt_rsi_trigger': best_params['rsi_trigger'],
                'is_return_pct': best_is_metrics['total_return_pct'],
                'is_cagr_pct': best_is_metrics['cagr_pct'],
                'is_sharpe': best_is_metrics['sharpe_ratio'],
                'oos_return_pct': oos_metrics['total_return_pct'],
                'oos_cagr_pct': oos_metrics['cagr_pct'],
                'oos_sharpe': oos_metrics['sharpe_ratio'],
                'oos_max_dd_pct': oos_metrics['max_drawdown_pct'],
                'oos_trades_count': oos_metrics['total_trades']
            }
            
            wfa_records.append(wfa_record)
            logger.info(f"Window {idx}/{len(windows)} COMPLETE | OOS Period: {wfa_record['oos_range']} | Opt Params: SMA({wfa_record['opt_sma_fast']}/{wfa_record['opt_sma_slow']}), RSI({wfa_record['opt_rsi_trigger']}) | IS Sharpe: {wfa_record['is_sharpe']:.2f} | OOS Sharpe: {wfa_record['oos_sharpe']:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to evaluate OOS for window {idx}: {e}")
            continue
            
    # Compile records to DataFrame
    wfa_df = pd.DataFrame(wfa_records)
    
    # --- 3. WFA Aggregation & Summary ---
    avg_is_sharpe = wfa_df['is_sharpe'].mean()
    avg_oos_sharpe = wfa_df['oos_sharpe'].mean()
    avg_is_cagr = wfa_df['is_cagr_pct'].mean()
    avg_oos_cagr = wfa_df['oos_cagr_pct'].mean()
    
    # Walk-Forward Efficiency (WFE) ratios
    wfe_sharpe = (avg_oos_sharpe / avg_is_sharpe) if avg_is_sharpe > 0 else 0.0
    wfe_return = (avg_oos_cagr / avg_is_cagr) if avg_is_cagr > 0 else 0.0
    
    # Out-of-sample Consistency: profitable windows / total windows
    profitable_windows = sum(wfa_df['oos_return_pct'] > 0)
    consistency_pct = (profitable_windows / len(wfa_df)) * 100 if len(wfa_df) > 0 else 0.0
    
    summary = {
        'avg_is_sharpe': avg_is_sharpe,
        'avg_oos_sharpe': avg_oos_sharpe,
        'avg_is_cagr_pct': avg_is_cagr,
        'avg_oos_cagr_pct': avg_oos_cagr,
        'wfe_sharpe_pct': wfe_sharpe * 100,
        'wfe_return_pct': wfe_return * 100,
        'consistency_pct': consistency_pct,
        'total_oos_trades': wfa_df['oos_trades_count'].sum(),
        'average_oos_max_dd_pct': wfa_df['oos_max_dd_pct'].mean()
    }
    
    return {
        'results_df': wfa_df,
        'summary': summary
    }

def plot_wfa_results(wfa_df: pd.DataFrame, save_path: str = None):
    """
    Plots a highly polished, professional-grade comparison chart of In-Sample
    vs. Out-of-Sample Sharpe ratios for each Walk-Forward window.
    """
    if save_path:
        dir_name = os.path.dirname(save_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)

    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(10, 6))

    # Bar layout details
    indices = np.arange(len(wfa_df))
    bar_width = 0.35

    # Visual palettes
    is_color = '#4682b4'   # Steel blue
    oos_color = '#2e8b57'  # Sea green

    # Render side-by-side bar plots
    ax.bar(indices - bar_width/2, wfa_df['is_sharpe'], bar_width, label='In-Sample (Optimized)', color=is_color, alpha=0.9, edgecolor='grey')
    ax.bar(indices + bar_width/2, wfa_df['oos_sharpe'], bar_width, label='Out-of-Sample (Unseen)', color=oos_color, alpha=0.9, edgecolor='grey')

    # Formatting title & headers
    ax.set_title("Walk-Forward Validation: In-Sample vs. Out-of-Sample Sharpe Ratios", fontsize=13, fontweight='bold', pad=15)
    ax.set_xlabel("Walk-Forward Window Index", fontsize=11, fontweight='semibold')
    ax.set_ylabel("Annualized Sharpe Ratio", fontsize=11, fontweight='semibold')
    ax.set_xticks(indices)
    ax.set_xticklabels(wfa_df['window'], fontsize=10)
    ax.legend(loc='upper right', frameon=True)
    
    # Add baseline at 0
    ax.axhline(0, color='black', linewidth=0.8, linestyle='--')

    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Walk-Forward summary chart successfully saved to '{save_path}'")
        plt.close()
    else:
        plt.show()
