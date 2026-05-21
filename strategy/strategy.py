import backtrader as bt
import logging
from strategy.indicators import NormalizedATR

logger = logging.getLogger(__name__)

class MomentumSwingStrategy(bt.Strategy):
    """
    A robust momentum-based swing trading strategy designed for daily historical data.
    
    Strategy Logic:
    ---------------
    Indicators:
    - Simple Moving Average (SMA) 20: Fast trend signal.
    - Simple Moving Average (SMA) 50: Slow trend signal.
    - Relative Strength Index (RSI) 14: Momentum filter.
    - Average True Range (ATR) 14: Volatility and risk benchmarking.
    
    Entry Rules (Long only):
    - SMA 20 crosses above SMA 50 (bullish crossover).
    - RSI 14 > 55 (confirming bullish momentum and strength).
    - No open position exists.
    
    Exit Rules:
    - SMA 20 crosses below SMA 50 (trend reversal).
    - Price falls below the 2% Stop Loss threshold from the entry price.
    - Price rises above the 5% Take Profit threshold from the entry price.
    
    Risk Management:
    - Capital allocation scaled dynamically to risk exactly 2% of total portfolio value
      per trade, based on the 2% stop loss distance.
    - Supports dynamic parameter configuration.
    """
    
    # Strategy parameters
    params = (
        ('sma_fast', 20),
        ('sma_slow', 50),
        ('rsi_period', 14),
        ('rsi_trigger', 55),
        ('atr_period', 14),
        ('stop_loss_pct', 0.02),     # 2% fixed stop loss
        ('take_profit_pct', 0.05),   # 5% fixed take profit
        ('risk_pct', 0.02),          # Risk 2% of portfolio value per trade
        ('verbose', False),          # Toggle console printing (highly recommended to disable during grid searches)
    )

    def log(self, txt, dt=None):
        """Logging utility method."""
        if self.params.verbose:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} - {txt}")

    def __init__(self):
        # Keep reference to core data feeds
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.dataopen = self.datas[0].open

        # Initialize indicators using standard Backtrader declarations
        self.sma_f = bt.indicators.SimpleMovingAverage(self.datas[0], period=self.params.sma_fast)
        self.sma_s = bt.indicators.SimpleMovingAverage(self.datas[0], period=self.params.sma_slow)
        self.rsi = bt.indicators.RSI(self.datas[0], period=self.params.rsi_period)
        self.atr = bt.indicators.AverageTrueRange(self.datas[0], period=self.params.atr_period)
        self.natr = NormalizedATR(self.datas[0], period=self.params.atr_period)

        # Crossover indicator (returns 1.0 for cross above, -1.0 for cross under, 0.0 otherwise)
        self.crossover = bt.indicators.CrossOver(self.sma_f, self.sma_s)

        # Operational state trackers
        self.order = None
        self.entry_price = None
        self.trade_records = []  # Detailed custom trade records

    def notify_order(self, order):
        """Handles order status updates from the Broker."""
        if order.status in [order.Submitted, order.Accepted]:
            # Order is pending; do not initiate other actions
            return

        # Check if an order has been completed
        if order.status == order.Completed:
            if order.isbuy():
                self.log(f"BUY EXECUTED | Price: {order.executed.price:.2f} | Size: {order.executed.size} | Value: {order.executed.value:.2f} | Comm: {order.executed.comm:.2f}")
                self.entry_price = order.executed.price
            elif order.issell():
                self.log(f"SELL EXECUTED | Price: {order.executed.price:.2f} | Size: {order.executed.size} | Value: {order.executed.value:.2f} | Comm: {order.executed.comm:.2f}")
                self.entry_price = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"ORDER INVALIDATED | Status: {order.getstatusname()}")

        # Clear pending order tracker
        self.order = None

    def notify_trade(self, trade):
        """Handles trade updates (position opened or closed)."""
        if not trade.isclosed:
            return

        self.log(f"TRADE CLOSED | Gross PnL: {trade.pnl:.2f} | Net PnL: {trade.pnlcomm:.2f} | Commission Paid: {trade.commission:.2f}")
        
        # Save structured trade history
        self.trade_records.append({
            'exit_date': self.datas[0].datetime.date(0).isoformat(),
            'pnl': trade.pnl,
            'pnlcomm': trade.pnlcomm,
            'barlen': trade.barlen,
            'commission': trade.commission,
            'entry_price': trade.price,
            'exit_price': self.dataclose[0]
        })

    def next(self):
        """Primary execution block evaluated at each data bar."""
        # If there is a pending order, wait for execution
        if self.order:
            return

        # Check if we are in an open market position
        if not self.position:
            # ENTRY SIGNAL: SMA(Fast) crosses above SMA(Slow) AND RSI > Trigger (55)
            if self.crossover[0] == 1.0 and self.rsi[0] > self.params.rsi_trigger:
                # Fractional Risk-based Position Sizing
                portfolio_value = self.broker.get_value()
                risk_amount = portfolio_value * self.params.risk_pct
                
                # Use today's close as a proxy for next day's open entry price
                est_entry_price = self.dataclose[0]
                
                # Risk in price points based on our stop loss percent
                risk_per_share = est_entry_price * self.params.stop_loss_pct
                
                # Dynamic share sizing
                if risk_per_share > 0:
                    size = int(risk_amount / risk_per_share)
                else:
                    size = 0
                
                # Enforce capital constraints (95% cap for safety margin and commission headroom)
                max_allowable_size = int((portfolio_value * 0.95) / est_entry_price)
                size = min(size, max_allowable_size)

                if size > 0:
                    self.log(f"BUY ORDER SENT | Est Price: {est_entry_price:.2f} | Targets Size: {size} | Portfolio Cash: {self.broker.get_cash():.2f}")
                    self.order = self.buy(size=size)
        else:
            # EXIT SIGNALS EVALUATION
            # Retrieve active entry price (fallback to position average price if notification lag occurs)
            entry_p = self.entry_price if self.entry_price is not None else self.position.price
            
            # Exit thresholds
            stop_loss_price = entry_p * (1.0 - self.params.stop_loss_pct)
            take_profit_price = entry_p * (1.0 + self.params.take_profit_pct)

            # Daily extremes check for intra-day price breaches
            sl_breached = self.datalow[0] <= stop_loss_price
            tp_breached = self.datahigh[0] >= take_profit_price
            trend_reversed = self.crossover[0] == -1.0  # SMA(Fast) crosses below SMA(Slow)

            exit_flag = False
            reason = ""

            # Check rules in order of priority (Stop Loss, Take Profit, Trend Reversal)
            if sl_breached:
                exit_flag = True
                reason = "STOP LOSS TRIGGERED"
            elif tp_breached:
                exit_flag = True
                reason = "TAKE PROFIT TRIGGERED"
            elif trend_reversed:
                exit_flag = True
                reason = "TREND REVERSAL (SMA CROSS-UNDER)"

            if exit_flag:
                self.log(f"SELL ORDER SENT ({reason}) | Close: {self.dataclose[0]:.2f} | Entry: {entry_p:.2f} | PnL%: {((self.dataclose[0] - entry_p)/entry_p)*100:.2f}%")
                self.order = self.close()
