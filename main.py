# ==============================================================================
#            COLLECTIONS MONKEY PATCH FOR PYTHON 3.10+ / 3.13 COMPATIBILITY
# ==============================================================================
import collections
try:
    collections.Iterable = collections.abc.Iterable
except AttributeError:
    pass
# ==============================================================================

import os
import sys
import logging
import pandas as pd
from data.downloader import download_stock_data
from backtest.run_backtest import run_backtest, plot_performance
from walkforward.walk_forward import run_wfa, plot_wfa_results
from optimization.parameter_sensitivity import run_sensitivity_analysis, save_sensitivity_report
from robustness.robustness_score import calculate_robustness_score

# Set up logging format
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def print_banner():
    banner = """
========================================================================
   ____                   _     ____  _             _                  
  / __ \                 | |   / ___|| |_ _ __ __ _| |_ ___  __ _ _  _ 
 | |  | |  _   _   __ _  | |_  \___ \| __| '__/ _` | __/ _ \/ _` | || |
 | |__| | | |_| | / _` | |  _|  ___) | |_| | | (_| | ||  __/ (_| | || |
  \___\_\  \__,_| \__,_|  \_|  |____/ \__|_|  \__,_|\__\___|\__, |\_,_|
                                                            |___/      
                QUANTITATIVE STRATEGY RESEARCH LAB
========================================================================
Architect: Senior Quantitative Developer / Python Architect
Asset    : RELIANCE.NS (Yahoo Finance)
Date Range: 2018-01-01 to 2024-12-31 (7 Years, Daily Bars)
========================================================================
"""
    print(banner)

def main():
    print_banner()
    
    # Initialize output directories
    for directory in ['data', 'results', 'charts']:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created system directory: '{directory}/'")

    # Configuration constants
    TICKER = "AAPL"
    START_DATE = "2018-01-01"
    END_DATE = "2024-12-31"
    INITIAL_CAPITAL = 100000.0
    COMMISSION = 0.001  # 0.1% transaction cost
    
    # --- PHASE 1: DATA INGESTION ---
    print("\n[PHASE 1] DATA ACQUISITION & INTEGRITY CHECK")
    print("-" * 72)
    try:
        df = download_stock_data(TICKER, START_DATE, END_DATE)
        print(f"SUCCESS: Stock data loaded. Total trading days: {len(df)}")
    except Exception as e:
        logger.error(f"Failed to load market data: {e}")
        sys.exit(1)

    # --- PHASE 2: BASELINE RUN & DETAILED TRADE LOGGING ---
    print("\n[PHASE 2] BASELINE BACKTEST EXECUTION (Standard Crossover Parameters)")
    print("-" * 72)
    baseline_params = {
        'sma_fast': 20,
        'sma_slow': 50,
        'rsi_period': 14,
        'rsi_trigger': 55,
        'atr_period': 14,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.05,
        'risk_pct': 0.02,
        'verbose': True  # Enable console reporting for baseline trades
    }
    
    logger.info("Executing baseline backtest on full historical period...")
    metrics, trades, ts = run_backtest(df, params=baseline_params, initial_capital=INITIAL_CAPITAL, commission=COMMISSION)
    
    # Export baseline run timeseries & trade logs
    ts_file = os.path.join("results", "baseline_equity_curve.csv")
    ts.to_csv(ts_file)
    logger.info(f"Exported daily equity series to '{ts_file}'")
    
    trades_df = pd.DataFrame(trades)
    trades_file = os.path.join("results", "baseline_trade_log.csv")
    trades_df.to_csv(trades_file, index=False)
    logger.info(f"Exported detailed trade-by-trade logs ({len(trades)} trades) to '{trades_file}'")
    
    metrics_df = pd.DataFrame([metrics])
    metrics_file = os.path.join("results", "baseline_metrics.csv")
    metrics_df.to_csv(metrics_file, index=False)
    
    # Generate Baseline Performance Chart
    chart_file = os.path.join("charts", "baseline_performance.png")
    plot_performance(ts, metrics, TICKER, save_path=chart_file)
    print("SUCCESS: Baseline backtest execution complete.")

    # --- PHASE 3: ROLLING WALK-FORWARD ANALYSIS ---
    print("\n[PHASE 3] ROLLING WALK-FORWARD VALIDATION")
    print("-" * 72)
    logger.info("Initializing 2-year IS / 6-month OOS rolling walk-forward grid search...")
    wfa_out = run_wfa(df)
    wfa_df = wfa_out['results_df']
    wfa_summary = wfa_out['summary']
    
    # Save WFA results
    wfa_results_file = os.path.join("results", "walk_forward_results.csv")
    wfa_df.to_csv(wfa_results_file, index=False)
    logger.info(f"Walk-Forward rolling window details saved to '{wfa_results_file}'")
    
    # Save WFA summary chart
    wfa_chart_file = os.path.join("charts", "walk_forward_summary.png")
    plot_wfa_results(wfa_df, save_path=wfa_chart_file)
    print("SUCCESS: Walk-Forward Validation completed.")

    # --- PHASE 4: PARAMETER SENSITIVITY TESTING ---
    print("\n[PHASE 4] PARAMETER SENSITIVITY & STABILITY AUDIT")
    print("-" * 72)
    sensitivity_out = run_sensitivity_analysis(df)
    comp_df = sensitivity_out['comparison_df']
    save_sensitivity_report(comp_df)
    print("SUCCESS: Parameter stability analysis complete.")

    # --- PHASE 5: SYSTEM ROBUSTNESS AUDIT ---
    print("\n[PHASE 5] MULTI-FACTOR ROBUSTNESS SCORING ENGINE")
    print("-" * 72)
    robustness_data = calculate_robustness_score(wfa_summary, wfa_df, sensitivity_out['results'], metrics)
    final_score = robustness_data['overall_robustness_score']
    print(f"SUCCESS: Quantitative Robustness Audit Complete.")

    # --- FINAL CLI PERFORMANCE REPORT SUMMARY ---
    print("\n" + "=" * 72)
    print("                      STRATEGY RESEARCH SUMMARY                         ")
    print("=" * 72)
    print(f" Asset Symbol            : {TICKER}")
    print(f" Backtest period         : {START_DATE} to {END_DATE} ({years_diff(START_DATE, END_DATE):.1f} Years)")
    print(f" Starting Cash Balance   : INR {INITIAL_CAPITAL:,.2f}")
    print(f" Ending Cash Balance     : INR {metrics['final_value']:,.2f}")
    print(f" Total Net Return (%)    : {metrics['total_return_pct']:.2f}%")
    print(f" Compound Annual (CAGR)  : {metrics['cagr_pct']:.2f}%")
    print(f" Annualized Sharpe Ratio : {metrics['sharpe_ratio']:.2f}")
    print(f" Maximum Drawdown (%)    : {metrics['max_drawdown_pct']:.2f}%")
    print(f" Closed Trades Count     : {metrics['total_trades']}")
    print(f" Strategy Win Rate       : {metrics['win_rate_pct']:.2f}%")
    print(f" Profit Factor           : {metrics['profit_factor']:.2f}")
    print("-" * 72)
    print(f" WFA Avg. OOS Sharpe     : {wfa_summary['avg_oos_sharpe']:.2f}")
    print(f" WFA Avg. IS Sharpe      : {wfa_summary['avg_is_sharpe']:.2f}")
    print(f" WFA Sharpe Efficiency   : {wfa_summary['wfe_sharpe_pct']:.2f}%")
    print(f" WFA OOS Consistency     : {wfa_summary['consistency_pct']:.2f}% profitable windows")
    print("-" * 72)
    print(f" FINAL ROBUSTNESS SCORE  : {final_score:.2f} / 100.00")
    print(f" SYSTEM COMPLIANCE       : {'PASSED (>75)' if final_score >= 75.0 else 'FAILED (<75)'}")
    print("=" * 72)
    print("\nGenerated quantitative artifacts saved locally under:")
    print(" - Performance Plots: ./charts/")
    print(" - Structured Logs  : ./results/")
    print("========================================================================\n")

def years_diff(d1_str, d2_str):
    d1 = pd.to_datetime(d1_str)
    d2 = pd.to_datetime(d2_str)
    return (d2 - d1).days / 365.25

if __name__ == "__main__":
    main()
