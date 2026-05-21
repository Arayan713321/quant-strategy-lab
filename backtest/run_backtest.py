import os
import logging
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import backtrader as bt
from strategy.strategy import MomentumSwingStrategy

logger = logging.getLogger(__name__)

class PortfolioMetricsAnalyzer(bt.Analyzer):
    """
    Custom Backtrader Analyzer to record daily portfolio value, peaks, 
    and drawdowns, allowing us to generate precise timeseries logs 
    and custom publication-grade plots.
    """
    def __init__(self):
        super(PortfolioMetricsAnalyzer, self).__init__()
        self.dates = []
        self.values = []

    def next(self):
        # Retrieve current date from data feed
        self.dates.append(self.strategy.data.datetime.date(0))
        # Retrieve current portfolio value from broker
        self.values.append(self.strategy.broker.get_value())

    def get_analysis(self):
        # Compile lists into a structured Pandas DataFrame
        df = pd.DataFrame(index=pd.to_datetime(self.dates), data={'PortfolioValue': self.values})
        df.index.name = 'Date'
        # Compute peak values and percentage drawdowns
        df['Peak'] = df['PortfolioValue'].cummax()
        df['Drawdown'] = (df['PortfolioValue'] - df['Peak']) / df['Peak'] * 100
        return df

def run_backtest(df: pd.DataFrame, params: dict = None, initial_capital: float = 100000.0, commission: float = 0.001) -> tuple:
    """
    Configures and runs a single Backtrader backtest using the MomentumSwingStrategy.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Pandas DataFrame containing daily stock data.
    params : dict
        Strategy parameters (e.g. {'sma_fast': 20, 'sma_slow': 50}).
    initial_capital : float
        Starting portfolio cash balance. Default is 100,000.
    commission : float
        Transaction fee commission rate (e.g., 0.001 = 0.1%).
        
    Returns:
    --------
    tuple (metrics, trade_records, timeseries_df)
        - metrics : dict of calculated metrics (Sharpe, Return, Drawdown, CAGR, etc.)
        - trade_records : list of dicts, details of closed trades
        - timeseries_df : pd.DataFrame, daily equity and drawdown tracking
    """
    # Initialize Backtrader's central engine
    cerebro = bt.Cerebro()

    # Pass strategy with parameters
    if params:
        cerebro.addstrategy(MomentumSwingStrategy, **params)
    else:
        cerebro.addstrategy(MomentumSwingStrategy)

    # Convert incoming Pandas DataFrame to Backtrader-compatible feed
    # Open, High, Low, Close, Volume, OpenInterest are standard
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    # Configure broker capital and commission structure
    cerebro.broker.setcash(initial_capital)
    cerebro.broker.setcommission(commission=commission)
    
    # Configure realistic slippage (e.g. 0.05% of the price)
    cerebro.broker.set_slippage_perc(0.0005)

    # Register standard and custom analyzers
    # riskfreerate is set to 0.0 (risk-free asset rate is 0.0 for direct excess return).
    # We will manually annualize the returned daily Sharpe ratio by multiplying by sqrt(252).
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.0, timeframe=bt.TimeFrame.Days, factor=252)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(PortfolioMetricsAnalyzer, _name='metrics_timeseries')

    # Execute backtest
    strategies = cerebro.run()
    strat = strategies[0]

    # --- Metrics Extraction ---
    final_val = cerebro.broker.get_value()
    total_return = (final_val - initial_capital) / initial_capital * 100
    
    # Analyze core metrics safely using analyzers
    sharpe_anal = strat.analyzers.sharpe.get_analysis()
    sharpe_ratio = sharpe_anal.get('sharperatio', 0.0)
    # If Sharpe is None or NaN, default to 0.0
    if sharpe_ratio is None or np.isnan(sharpe_ratio):
        sharpe_ratio = 0.0
    else:
        # Backtrader's SharpeRatio analyzer returns the daily period Sharpe ratio.
        # Annualize the daily Sharpe ratio by multiplying by the square root of 252.
        sharpe_ratio = sharpe_ratio * np.sqrt(252)

    dd_anal = strat.analyzers.drawdown.get_analysis()
    max_dd = dd_anal.get('max', {}).get('drawdown', 0.0)

    # CAGR Calculation
    start_date = df.index.min()
    end_date = df.index.max()
    years = (end_date - start_date).days / 365.25
    if years > 0 and final_val > 0:
        cagr = ((final_val / initial_capital) ** (1 / years) - 1) * 100
    else:
        cagr = 0.0

    # Trade Analyzer Metrics
    trade_anal = strat.analyzers.trade_analyzer.get_analysis()
    total_trades = trade_anal.get('total', {}).get('total', 0)
    
    win_rate = 0.0
    profit_factor = 0.0
    
    if total_trades > 0:
        won = trade_anal.get('won', {}).get('total', 0)
        win_rate = (won / total_trades) * 100
        
        gross_profit = trade_anal.get('won', {}).get('pnl', {}).get('gross', 0.0)
        gross_loss = abs(trade_anal.get('lost', {}).get('pnl', {}).get('gross', 0.0))
        
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = float('inf') if gross_profit > 0 else 1.0

    metrics = {
        'initial_capital': initial_capital,
        'final_value': final_val,
        'total_return_pct': total_return,
        'cagr_pct': cagr,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown_pct': max_dd,
        'total_trades': total_trades,
        'win_rate_pct': win_rate,
        'profit_factor': profit_factor
    }

    # Extract custom timeseries and trade logs
    timeseries_df = strat.analyzers.metrics_timeseries.get_analysis()
    trade_records = strat.trade_records

    return metrics, trade_records, timeseries_df

def plot_performance(timeseries_df: pd.DataFrame, metrics: dict, ticker: str, save_path: str = None):
    """
    Generates a stunning, publication-grade visualization panel including the
    Equity Curve and the Drawdown Curve.
    """
    # Create charts directory if it doesn't exist
    if save_path:
        dir_name = os.path.dirname(save_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)

    # Configure style aesthetics (clean, high-contrast, modern layout)
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1]})

    # Royal blue equity color
    primary_color = '#1f77b4'
    fill_color = '#d6e4f0'
    coral_color = '#e24a33'
    soft_red_fill = '#fcdcd8'

    # --- Panel 1: Equity Curve ---
    ax1.plot(timeseries_df.index, timeseries_df['PortfolioValue'], color=primary_color, linewidth=2, label='Portfolio Value (Equity)')
    ax1.fill_between(timeseries_df.index, timeseries_df['PortfolioValue'], metrics['initial_capital'], color=fill_color, alpha=0.5)
    
    title_text = f"Algorithmic Trading Research Suite - {ticker} Performance"
    ax1.set_title(title_text, fontsize=14, fontweight='bold', pad=15)
    ax1.set_ylabel("Portfolio Value (₹)", fontsize=11, fontweight='semibold')
    
    # Annotate summary boxes inside the chart
    summary_text = (
        f"Starting Capital: ₹{metrics['initial_capital']:,.2f}\n"
        f"Final Value: ₹{metrics['final_value']:,.2f}\n"
        f"Total Return: {metrics['total_return_pct']:.2f}%\n"
        f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}"
    )
    ax1.text(0.02, 0.95, summary_text, transform=ax1.transAxes, fontsize=10,
             verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.85, edgecolor='#cccccc'))
    
    ax1.legend(loc='upper right', frameon=True)
    ax1.tick_params(axis='y', labelsize=10)

    # --- Panel 2: Drawdown Curve ---
    ax2.plot(timeseries_df.index, timeseries_df['Drawdown'], color=coral_color, linewidth=1.5, label='Drawdown %')
    ax2.fill_between(timeseries_df.index, timeseries_df['Drawdown'], 0, color=soft_red_fill, alpha=0.6)
    
    ax2.set_ylabel("Drawdown %", fontsize=11, fontweight='semibold')
    ax2.set_xlabel("Timeline", fontsize=11, fontweight='semibold')
    ax2.set_ylim(-max(25, metrics['max_drawdown_pct'] * 1.2), 1)
    
    # Annotate max drawdown
    max_dd_idx = timeseries_df['Drawdown'].idxmin()
    max_dd_val = timeseries_df['Drawdown'].min()
    ax2.annotate(f"Max Drawdown: {max_dd_val:.2f}%", 
                 xy=(max_dd_idx, max_dd_val), 
                 xytext=(max_dd_idx, max_dd_val - 5),
                 arrowprops=dict(facecolor='black', shrink=0.08, width=1, headwidth=6),
                 fontsize=9, fontweight='semibold', color='black')

    ax2.legend(loc='lower right', frameon=True)
    ax2.tick_params(axis='both', labelsize=10)

    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Performance chart successfully saved to '{save_path}'")
        plt.close()
    else:
        plt.show()
