import os
import logging
import pandas as pd
import numpy as np
from backtest.run_backtest import run_backtest

logger = logging.getLogger(__name__)

def run_sensitivity_analysis(df: pd.DataFrame) -> dict:
    """
    Evaluates the trading strategy over the entire historical data using
    three nearby parameter combinations to test stability and overfitting.
    
    Parameter sets tested:
    1. Set A (Aggressive): SMA 15 / SMA 45
    2. Set B (Baseline): SMA 20 / SMA 50
    3. Set C (Conservative): SMA 25 / SMA 60
    
    All sets keep RSI period at 14 and RSI trigger at 55.
    
    Returns:
    --------
    dict
        Dictionary containing the compiled comparison DataFrame and individual run metrics.
    """
    parameter_sets = {
        'SMA 15/45 (Aggressive)': {
            'sma_fast': 15,
            'sma_slow': 45,
            'rsi_period': 14,
            'rsi_trigger': 55,
            'verbose': False
        },
        'SMA 20/50 (Baseline)': {
            'sma_fast': 20,
            'sma_slow': 50,
            'rsi_period': 14,
            'rsi_trigger': 55,
            'verbose': False
        },
        'SMA 25/60 (Conservative)': {
            'sma_fast': 25,
            'sma_slow': 60,
            'rsi_period': 14,
            'rsi_trigger': 55,
            'verbose': False
        }
    }
    
    logger.info("Beginning Parameter Sensitivity Analysis across 3 configuration sets...")
    
    results = {}
    
    for set_name, params in parameter_sets.items():
        try:
            logger.info(f"Running backtest for: {set_name}...")
            metrics, trades, ts = run_backtest(df, params=params)
            results[set_name] = {
                'metrics': metrics,
                'trades': trades,
                'timeseries': ts
            }
            logger.info(f"Backtest for {set_name} COMPLETE | Return: {metrics['total_return_pct']:.2f}% | Sharpe: {metrics['sharpe_ratio']:.2f} | Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        except Exception as e:
            logger.error(f"Failed running sensitivity backtest for {set_name}: {e}")
            
    # Compile a beautiful comparison table
    comparison_rows = []
    
    metrics_to_compare = [
        ('Initial Capital', 'initial_capital', 'INR {:,.2f}'),
        ('Final Portfolio Value', 'final_value', 'INR {:,.2f}'),
        ('Total Return (%)', 'total_return_pct', '{:.2f}%'),
        ('CAGR (%)', 'cagr_pct', '{:.2f}%'),
        ('Sharpe Ratio', 'sharpe_ratio', '{:.2f}'),
        ('Maximum Drawdown (%)', 'max_drawdown_pct', '{:.2f}%'),
        ('Win Rate (%)', 'win_rate_pct', '{:.2f}%'),
        ('Profit Factor', 'profit_factor', '{:.2f}'),
        ('Number of Trades', 'total_trades', '{:d}')
    ]
    
    for label, key, fmt in metrics_to_compare:
        row = {'Metric': label}
        for set_name in parameter_sets.keys():
            if set_name in results:
                val = results[set_name]['metrics'][key]
                # Format infinity/floats nicely
                if val == float('inf'):
                    row[set_name] = 'N/A (No Losses)'
                elif isinstance(val, (int, float, np.integer, np.floating)):
                    row[set_name] = fmt.format(val)
                else:
                    row[set_name] = str(val)
            else:
                row[set_name] = 'Failed'
        comparison_rows.append(row)
        
    comparison_df = pd.DataFrame(comparison_rows)
    
    return {
        'comparison_df': comparison_df,
        'results': results
    }

def save_sensitivity_report(comparison_df: pd.DataFrame, results_dir: str = 'results'):
    """
    Saves the parameter sensitivity comparison to a CSV file and logs a summary text report.
    """
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
        
    file_path = os.path.join(results_dir, 'parameter_sensitivity.csv')
    comparison_df.to_csv(file_path, index=False)
    logger.info(f"Parameter sensitivity comparison table successfully saved to '{file_path}'")
