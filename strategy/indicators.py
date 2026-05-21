import backtrader as bt

class NormalizedATR(bt.Indicator):
    """
    Normalized Average True Range (NATR).
    Expresses Average True Range (ATR) as a percentage of the asset's closing price.
    This provides a standardized, unitless metric of volatility that allows for 
    consistent volatility comparison across different assets and time periods.
    
    Formula:
    --------
    NATR = (ATR(period) / Close) * 100
    """
    lines = ('natr',)
    params = (('period', 14),)

    def __init__(self):
        # Validate parameter
        if self.params.period <= 0:
            raise ValueError("Period must be greater than zero.")
            
        # Depend on Backtrader's native Average True Range indicator
        self.atr = bt.indicators.AverageTrueRange(period=self.params.period)

    def next(self):
        if self.data.close[0] != 0:
            self.lines.natr[0] = (self.atr[0] / self.data.close[0]) * 100
        else:
            self.lines.natr[0] = 0.0
            
    def _plotlabel(self):
        # Define clean labels for Matplotlib plotting
        return [self.params.period]
