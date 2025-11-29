"""
Angel One Account Management Module.

Handles account information, margin, and RMS limits.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AngelOneAccount:
    """
    Handles account management with Angel One SmartAPI.
    
    Supports:
    - Account profile retrieval
    - Margin/funds information
    - RMS limits
    - Margin calculator
    """
    
    def __init__(self, smart_api, config: Optional[Dict[str, Any]] = None):
        """
        Initialize account handler.
        
        Args:
            smart_api: Authenticated SmartAPI instance
            config: Optional configuration
        """
        self._smart_api = smart_api
        self._config = config or {}
        
        logger.info("Initialized AngelOneAccount")
    
    def get_profile(self) -> Dict[str, Any]:
        """
        Get user profile information.
        
        Returns:
            Dictionary with profile details
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            response = self._smart_api.getProfile(self._config.get('refresh_token', ''))
            
            if response.get('status'):
                data = response.get('data', {})
                return {
                    'status': True,
                    'profile': {
                        'client_id': data.get('clientcode', ''),
                        'name': data.get('name', ''),
                        'email': data.get('email', ''),
                        'phone': data.get('mobileno', ''),
                        'broker': 'Angel One',
                        'exchanges': data.get('exchanges', []),
                        'products': data.get('products', []),
                        'order_types': data.get('ordertypes', []),
                    }
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Failed to get profile')
                }
                
        except Exception as e:
            logger.exception(f"Get profile exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_margin(self) -> Dict[str, Any]:
        """
        Get margin/funds information.
        
        Returns:
            Dictionary with margin details
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            response = self._smart_api.rmsLimit()
            
            if response.get('status'):
                data = response.get('data', {})
                
                # Extract margin components
                net = float(data.get('net', 0))
                utilized = float(data.get('utilised', {}).get('debits', 0))
                available_margin = float(data.get('availablecash', 0))
                collateral = float(data.get('collateral', 0))
                
                return {
                    'status': True,
                    'margin': {
                        'available_cash': available_margin,
                        'available_margin': available_margin,
                        'used_margin': utilized,
                        'total_margin': net,
                        'collateral': collateral,
                        'opening_balance': float(data.get('availableintradaypayin', 0)),
                        'payin': float(data.get('payin', 0)),
                        'payout': float(data.get('payout', 0)),
                        'span': float(data.get('utilisedspan', 0)) if 'utilisedspan' in data else 0,
                        'exposure': float(data.get('utilisedexposure', 0)) if 'utilisedexposure' in data else 0,
                        'option_premium': float(data.get('utilisedoptionpremium', 0)) if 'utilisedoptionpremium' in data else 0,
                        'm2m': float(data.get('m2mrealized', 0)) + float(data.get('m2munrealized', 0)),
                        'realized_m2m': float(data.get('m2mrealized', 0)),
                        'unrealized_m2m': float(data.get('m2munrealized', 0)),
                    }
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Failed to get margin')
                }
                
        except Exception as e:
            logger.exception(f"Get margin exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_rms_limits(self) -> Dict[str, Any]:
        """
        Get RMS (Risk Management) limits.
        
        Returns:
            Dictionary with RMS limit details
        """
        if not self._smart_api:
            return {'status': False, 'message': 'API not initialized'}
        
        try:
            response = self._smart_api.rmsLimit()
            
            if response.get('status'):
                data = response.get('data', {})
                return {
                    'status': True,
                    'rms_limits': {
                        'net': float(data.get('net', 0)),
                        'available_cash': float(data.get('availablecash', 0)),
                        'available_intraday': float(data.get('availableintradaypayin', 0)),
                        'collateral': float(data.get('collateral', 0)),
                        'utilised': data.get('utilised', {}),
                        'm2m_realized': float(data.get('m2mrealized', 0)),
                        'm2m_unrealized': float(data.get('m2munrealized', 0)),
                    }
                }
            else:
                return {
                    'status': False,
                    'message': response.get('message', 'Failed to get RMS limits')
                }
                
        except Exception as e:
            logger.exception(f"Get RMS limits exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def calculate_margin_required(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        price: float,
        product_type: str = "INTRADAY",
        symbol_token: str = ""
    ) -> Dict[str, Any]:
        """
        Calculate margin required for a trade.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
            transaction_type: BUY or SELL
            quantity: Order quantity
            price: Expected price
            product_type: Product type
            symbol_token: Symbol token
            
        Returns:
            Dictionary with margin calculation
            
        Note:
            Angel One API doesn't provide direct margin calculator.
            This returns an estimate based on standard margin requirements.
        """
        try:
            # Standard margin percentages (approximate)
            margin_rates = {
                'INTRADAY': {
                    'NFO': 0.15,  # ~15% for F&O intraday
                    'NSE': 0.20,  # ~20% for equity intraday
                    'BSE': 0.20,
                },
                'DELIVERY': {
                    'NFO': 1.0,   # Full margin for F&O delivery
                    'NSE': 1.0,  # Full amount for equity delivery
                    'BSE': 1.0,
                },
                'CARRYFORWARD': {
                    'NFO': 0.15,  # SPAN + Exposure margin
                    'NSE': 1.0,
                    'BSE': 1.0,
                }
            }
            
            exchange = exchange.upper()
            product_type = product_type.upper()
            
            # Get margin rate
            margin_rate = margin_rates.get(product_type, {}).get(exchange, 0.20)
            
            # Calculate notional value and margin
            notional_value = price * quantity
            margin_required = notional_value * margin_rate
            
            # For options, premium is paid upfront for buyers
            is_option = 'CE' in symbol or 'PE' in symbol
            if is_option and transaction_type.upper() == 'BUY':
                margin_required = notional_value  # Full premium
            
            return {
                'status': True,
                'margin_calculation': {
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': price,
                    'notional_value': notional_value,
                    'margin_required': margin_required,
                    'margin_rate': margin_rate,
                    'product_type': product_type,
                    'exchange': exchange,
                    'note': 'Estimated margin. Actual may vary.'
                }
            }
            
        except Exception as e:
            logger.exception(f"Calculate margin exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_fund_summary(self) -> Dict[str, Any]:
        """
        Get a summary of funds and utilization.
        
        Returns:
            Dictionary with fund summary
        """
        margin_result = self.get_margin()
        if not margin_result.get('status'):
            return margin_result
        
        margin = margin_result.get('margin', {})
        
        available = margin.get('available_margin', 0)
        used = margin.get('used_margin', 0)
        total = margin.get('total_margin', 0)
        
        utilization_pct = (used / total * 100) if total > 0 else 0
        
        return {
            'status': True,
            'fund_summary': {
                'total_funds': total,
                'available_funds': available,
                'utilized_funds': used,
                'utilization_percentage': utilization_pct,
                'collateral': margin.get('collateral', 0),
                'm2m': margin.get('m2m', 0),
                'can_trade': available > 0,
            }
        }
    
    def check_margin_availability(
        self,
        required_margin: float
    ) -> Dict[str, Any]:
        """
        Check if required margin is available.
        
        Args:
            required_margin: Margin required for the trade
            
        Returns:
            Dictionary with availability status
        """
        margin_result = self.get_margin()
        if not margin_result.get('status'):
            return margin_result
        
        available = margin_result.get('margin', {}).get('available_margin', 0)
        
        return {
            'status': True,
            'is_available': available >= required_margin,
            'available_margin': available,
            'required_margin': required_margin,
            'shortfall': max(0, required_margin - available)
        }
