"""
Export Manager Module

Provides export functionality for the trading dashboard.
Supports exporting to CSV and generating PDF reports.
"""

import pandas as pd
import io
from datetime import datetime
from typing import Optional, List, Dict, Any
import base64


class ExportManager:
    """
    Manages export functionality for trading data.
    
    Supports:
    - CSV export for trade history and positions
    - PDF report generation (basic format)
    - P&L statement generation
    
    Attributes:
        None
    """
    
    @staticmethod
    def export_to_csv(data: pd.DataFrame, filename: str = "export.csv") -> bytes:
        """
        Export DataFrame to CSV format.
        
        Args:
            data: DataFrame to export
            filename: Output filename (used for content disposition)
        
        Returns:
            CSV data as bytes
        """
        csv_buffer = io.StringIO()
        data.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue().encode('utf-8')
    
    @staticmethod
    def export_positions_csv(positions: List[Dict[str, Any]]) -> bytes:
        """
        Export positions to CSV format.
        
        Args:
            positions: List of position dictionaries
        
        Returns:
            CSV data as bytes
        """
        if not positions:
            return b"No positions to export"
        
        df = pd.DataFrame([{
            "Symbol": p.symbol if hasattr(p, 'symbol') else p.get('symbol', ''),
            "Underlying": p.underlying if hasattr(p, 'underlying') else p.get('underlying', ''),
            "Type": p.position_type if hasattr(p, 'position_type') else p.get('position_type', ''),
            "Quantity": p.quantity if hasattr(p, 'quantity') else p.get('quantity', 0),
            "Entry Price": p.entry_price if hasattr(p, 'entry_price') else p.get('entry_price', 0),
            "Current Price": p.current_price if hasattr(p, 'current_price') else p.get('current_price', 0),
            "Unrealized P&L": p.unrealized_pnl if hasattr(p, 'unrealized_pnl') else p.get('unrealized_pnl', 0),
            "Delta": p.delta if hasattr(p, 'delta') else p.get('delta', 0),
            "Gamma": p.gamma if hasattr(p, 'gamma') else p.get('gamma', 0),
            "Theta": p.theta if hasattr(p, 'theta') else p.get('theta', 0),
            "Vega": p.vega if hasattr(p, 'vega') else p.get('vega', 0),
            "Entry Date": p.entry_date if hasattr(p, 'entry_date') else p.get('entry_date', ''),
            "Expiry": p.expiry if hasattr(p, 'expiry') else p.get('expiry', ''),
        } for p in positions])
        
        return ExportManager.export_to_csv(df)
    
    @staticmethod
    def export_orders_csv(orders: List[Dict[str, Any]]) -> bytes:
        """
        Export order history to CSV format.
        
        Args:
            orders: List of order dictionaries
        
        Returns:
            CSV data as bytes
        """
        if not orders:
            return b"No orders to export"
        
        df = pd.DataFrame([{
            "Order ID": o.get("order_id", ""),
            "Timestamp": o.get("timestamp", ""),
            "Symbol": o.get("symbol", ""),
            "Underlying": o.get("underlying", ""),
            "Side": o.get("side", ""),
            "Quantity": o.get("quantity", 0),
            "Order Type": o.get("order_type", ""),
            "Price": o.get("price", 0),
            "Status": o.get("status", ""),
        } for o in orders])
        
        return ExportManager.export_to_csv(df)
    
    @staticmethod
    def export_pnl_csv(pnl_data: pd.DataFrame) -> bytes:
        """
        Export P&L history to CSV format.
        
        Args:
            pnl_data: DataFrame with P&L history
        
        Returns:
            CSV data as bytes
        """
        if pnl_data.empty:
            return b"No P&L data to export"
        
        # Format the data
        export_df = pnl_data.copy()
        if 'date' in export_df.columns:
            export_df['date'] = pd.to_datetime(export_df['date']).dt.strftime('%Y-%m-%d')
        
        # Round numeric columns
        numeric_cols = ['daily_pnl', 'cumulative_pnl', 'equity']
        for col in numeric_cols:
            if col in export_df.columns:
                export_df[col] = export_df[col].round(2)
        
        return ExportManager.export_to_csv(export_df)
    
    @staticmethod
    def generate_pnl_report(
        pnl_data: pd.DataFrame,
        positions: List[Any],
        risk_metrics: Any,
        report_date: Optional[datetime] = None
    ) -> str:
        """
        Generate a P&L report in text format.
        
        Args:
            pnl_data: DataFrame with P&L history
            positions: List of current positions
            risk_metrics: RiskMetrics object
            report_date: Date for the report
        
        Returns:
            Report as formatted string
        """
        report_date = report_date or datetime.now()
        
        report = f"""
================================================================================
                           TRADING P&L REPORT
================================================================================
Report Date: {report_date.strftime('%Y-%m-%d %H:%M:%S')}
--------------------------------------------------------------------------------

SUMMARY
-------
Total P&L:          ₹{risk_metrics.total_pnl:,.2f}
Daily P&L:          ₹{risk_metrics.daily_pnl:,.2f}
Current Drawdown:   {risk_metrics.drawdown:.2f}%
Margin Used:        {risk_metrics.margin_used:.2f}%

RISK METRICS
------------
Value at Risk (95%): ₹{risk_metrics.var_95:,.2f}
Value at Risk (99%): ₹{risk_metrics.var_99:,.2f}
CVaR (95%):         ₹{risk_metrics.cvar_95:,.2f}

GREEKS EXPOSURE
---------------
Delta:  {risk_metrics.delta_exposure:,.4f}
Gamma:  {risk_metrics.gamma_exposure:,.6f}
Theta:  ₹{risk_metrics.theta_exposure:,.2f}
Vega:   {risk_metrics.vega_exposure:,.2f}

OPEN POSITIONS ({len(positions)} total)
----------------"""
        
        if positions:
            for pos in positions:
                symbol = pos.symbol if hasattr(pos, 'symbol') else pos.get('symbol', 'N/A')
                pnl = pos.unrealized_pnl if hasattr(pos, 'unrealized_pnl') else pos.get('unrealized_pnl', 0)
                report += f"\n  {symbol}: ₹{pnl:,.2f}"
        else:
            report += "\n  No open positions"
        
        report += f"""

--------------------------------------------------------------------------------
P&L HISTORY (Last 30 Days)
--------------------------"""
        
        if not pnl_data.empty:
            recent_data = pnl_data.tail(30)
            for _, row in recent_data.iterrows():
                date = row.get('date', 'N/A')
                if hasattr(date, 'strftime'):
                    date = date.strftime('%Y-%m-%d')
                daily = row.get('daily_pnl', 0)
                cumulative = row.get('cumulative_pnl', 0)
                report += f"\n  {date}:  Daily: ₹{daily:>10,.2f}  Cumulative: ₹{cumulative:>12,.2f}"
        else:
            report += "\n  No P&L history available"
        
        report += """

================================================================================
                              END OF REPORT
================================================================================
"""
        return report
    
    @staticmethod
    def get_download_link(data: bytes, filename: str, link_text: str) -> str:
        """
        Generate an HTML download link for binary data.
        
        Args:
            data: Binary data to download
            filename: Suggested filename
            link_text: Text to display for the link
        
        Returns:
            HTML link string
        """
        b64 = base64.b64encode(data).decode()
        
        # Determine MIME type
        if filename.endswith('.csv'):
            mime_type = 'text/csv'
        elif filename.endswith('.txt'):
            mime_type = 'text/plain'
        elif filename.endswith('.pdf'):
            mime_type = 'application/pdf'
        else:
            mime_type = 'application/octet-stream'
        
        href = f'<a href="data:{mime_type};base64,{b64}" download="{filename}">{link_text}</a>'
        return href
