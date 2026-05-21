import os
import logging
import pandas as pd
import yfinance as yf

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def download_stock_data(ticker: str, start_date: str, end_date: str, data_dir: str = "data") -> pd.DataFrame:
    """
    Downloads historical daily stock data from Yahoo Finance via yfinance, 
    caches it to a local CSV file, and returns it as a pandas DataFrame.
    
    Parameters:
    -----------
    ticker : str
        The Yahoo Finance ticker symbol (e.g., 'RELIANCE.NS', 'AAPL').
    start_date : str
        Start date in 'YYYY-MM-DD' format.
    end_date : str
        End date in 'YYYY-MM-DD' format.
    data_dir : str
        Directory to store the cached CSV file. Default is 'data'.
        
    Returns:
    --------
    pd.DataFrame
        Pandas DataFrame containing daily Open, High, Low, Close, Adj Close, Volume.
    """
    # Create the directory if it doesn't exist
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"Created data directory at '{data_dir}'")
        
    # Clean ticker name for file safety
    safe_ticker = ticker.replace(".", "_")
    file_path = os.path.join(data_dir, f"{safe_ticker}.csv")
    
    # Check if cached file exists
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path, parse_dates=True, index_col=0)
            # Verify if cached data covers the requested date range
            cached_start = df.index.min().strftime("%Y-%m-%d")
            cached_end = df.index.max().strftime("%Y-%m-%d")
            
            if cached_start <= start_date and cached_end >= end_date:
                logger.info(f"Loaded {ticker} data from cache ({file_path}). Range: {cached_start} to {cached_end}")
                # Filter to the requested range and return
                return df.loc[start_date:end_date]
            else:
                logger.info(f"Cache range ({cached_start} to {cached_end}) insufficient for requested range ({start_date} to {end_date}). Re-downloading...")
        except Exception as e:
            logger.warning(f"Error reading cache file {file_path}: {e}. Proceeding with fresh download.")
            
    # Perform fresh download
    logger.info(f"Downloading historical data for {ticker} from {start_date} to {end_date} via yfinance...")
    try:
        df = yf.download(ticker, start=start_date, end=end_date)
        if df.empty:
            raise ValueError(f"No data returned for ticker {ticker} from Yahoo Finance.")
            
        # yfinance return column indices could be multi-index depending on version, normalize them
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Clean index name and sort
        df.index.name = "Date"
        df = df.sort_index()
        
        # Save to CSV cache
        df.to_csv(file_path)
        logger.info(f"Successfully downloaded {len(df)} rows of data and cached to '{file_path}'")
        return df
        
    except Exception as e:
        logger.error(f"Failed to download data for {ticker}: {e}")
        raise
