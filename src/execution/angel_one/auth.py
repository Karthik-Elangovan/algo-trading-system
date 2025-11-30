"""
Angel One Authentication Module.

Handles SmartAPI authentication including TOTP generation,
session management, and token refresh.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AngelOneAuth:
    """
    Handles authentication with Angel One SmartAPI.
    
    Supports:
    - Login with API key, client ID, and password
    - TOTP generation for 2FA
    - Session token management
    - Automatic session refresh
    - Logout and cleanup
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize authentication handler.
        
        Args:
            config: Configuration dictionary with:
                - api_key: Angel One API key
                - client_id: Trading account client ID
                - password: Account password
                - totp_secret: TOTP secret for 2FA (optional if using app TOTP)
        """
        self.api_key = config.get('api_key', '')
        self.client_id = config.get('client_id', '')
        self.password = config.get('password', '')
        self.totp_secret = config.get('totp_secret', '')
        
        self._smart_api = None
        self._session_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._feed_token: Optional[str] = None
        self._jwt_token: Optional[str] = None
        self._session_expiry: Optional[datetime] = None
        self._is_authenticated = False
        
        logger.info(f"Initialized AngelOneAuth for client: {self.client_id}")
    
    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self._is_authenticated and self._session_token is not None
    
    @property
    def session_token(self) -> Optional[str]:
        """Get current session token."""
        return self._session_token
    
    @property
    def feed_token(self) -> Optional[str]:
        """Get feed token for WebSocket."""
        return self._feed_token
    
    @property
    def jwt_token(self) -> Optional[str]:
        """Get JWT token."""
        return self._jwt_token
    
    @property
    def smart_api(self):
        """Get SmartAPI instance."""
        return self._smart_api
    
    def generate_totp(self) -> str:
        """
        Generate TOTP code for 2FA.
        
        Returns:
            6-digit TOTP code
            
        Raises:
            ValueError: If TOTP secret is not configured
        """
        if not self.totp_secret:
            raise ValueError("TOTP secret not configured")
        
        try:
            import pyotp
            totp = pyotp.TOTP(self.totp_secret)
            code = totp.now()
            logger.debug("Generated TOTP code successfully")
            return code
        except Exception as e:
            logger.error(f"Failed to generate TOTP: {e}")
            raise
    
    def login(self, totp: Optional[str] = None) -> Dict[str, Any]:
        """
        Authenticate with Angel One SmartAPI.
        
        Args:
            totp: TOTP code (auto-generated if not provided and secret configured)
            
        Returns:
            Login response dictionary with tokens
            
        Raises:
            AuthenticationError: If login fails
        """
        try:
            from SmartApi import SmartConnect
        except ImportError:
            logger.error("SmartApi package not installed. Install with: pip install smartapi-python")
            raise ImportError("smartapi-python package required")
        
        try:
            # Initialize SmartAPI
            self._smart_api = SmartConnect(api_key=self.api_key)
            
            # Generate TOTP if not provided
            if not totp and self.totp_secret:
                totp = self.generate_totp()
            
            # Perform login
            logger.info(f"Attempting login for client: {self.client_id}")
            response = self._smart_api.generateSession(
                clientCode=self.client_id,
                password=self.password,
                totp=totp
            )
            
            if response.get('status'):
                data = response.get('data', {})
                self._session_token = data.get('jwtToken')
                self._refresh_token = data.get('refreshToken')
                self._feed_token = data.get('feedToken')
                self._jwt_token = self._session_token
                self._session_expiry = datetime.now() + timedelta(hours=24)
                self._is_authenticated = True
                
                logger.info(f"Login successful for client: {self.client_id}")
                return {
                    'status': True,
                    'session_token': self._session_token,
                    'feed_token': self._feed_token,
                    'refresh_token': self._refresh_token,
                    'message': 'Login successful'
                }
            else:
                error_msg = response.get('message', 'Login failed')
                logger.error(f"Login failed: {error_msg}")
                self._is_authenticated = False
                return {
                    'status': False,
                    'message': error_msg
                }
                
        except Exception as e:
            logger.exception(f"Login exception: {e}")
            self._is_authenticated = False
            return {
                'status': False,
                'message': str(e)
            }
    
    def logout(self) -> Dict[str, Any]:
        """
        Logout from Angel One SmartAPI.
        
        Returns:
            Logout response dictionary
        """
        if not self._smart_api or not self._is_authenticated:
            logger.warning("Not authenticated, nothing to logout")
            return {'status': True, 'message': 'Not authenticated'}
        
        try:
            response = self._smart_api.terminateSession(self.client_id)
            
            # Clear tokens
            self._session_token = None
            self._refresh_token = None
            self._feed_token = None
            self._jwt_token = None
            self._session_expiry = None
            self._is_authenticated = False
            
            if response.get('status'):
                logger.info(f"Logout successful for client: {self.client_id}")
                return {'status': True, 'message': 'Logout successful'}
            else:
                logger.warning(f"Logout response: {response}")
                return {'status': True, 'message': 'Session cleared'}
                
        except Exception as e:
            # Even on error, clear local tokens
            self._session_token = None
            self._refresh_token = None
            self._feed_token = None
            self._is_authenticated = False
            
            logger.exception(f"Logout exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def refresh_session(self) -> Dict[str, Any]:
        """
        Refresh the session token.
        
        Returns:
            Refresh response dictionary
        """
        if not self._smart_api or not self._refresh_token:
            logger.warning("Cannot refresh - no refresh token available")
            return {'status': False, 'message': 'No refresh token'}
        
        try:
            response = self._smart_api.generateToken(self._refresh_token)
            
            if response.get('status'):
                data = response.get('data', {})
                self._session_token = data.get('jwtToken')
                self._feed_token = data.get('feedToken')
                self._jwt_token = self._session_token
                self._session_expiry = datetime.now() + timedelta(hours=24)
                
                logger.info("Session refreshed successfully")
                return {'status': True, 'message': 'Session refreshed'}
            else:
                logger.error(f"Session refresh failed: {response}")
                return {'status': False, 'message': response.get('message')}
                
        except Exception as e:
            logger.exception(f"Session refresh exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def is_session_valid(self) -> bool:
        """
        Check if current session is valid.
        
        Returns:
            True if session is valid and not expired
        """
        if not self._is_authenticated or not self._session_token:
            return False
        
        if self._session_expiry and datetime.now() >= self._session_expiry:
            logger.warning("Session expired")
            return False
        
        return True
    
    def ensure_session(self) -> bool:
        """
        Ensure session is valid, refresh if needed.
        
        Returns:
            True if session is valid (after refresh if needed)
        """
        if self.is_session_valid():
            return True
        
        # Try to refresh
        result = self.refresh_session()
        return result.get('status', False)
    
    def get_profile(self) -> Dict[str, Any]:
        """
        Get user profile information.
        
        Returns:
            Profile data dictionary
        """
        if not self._smart_api or not self._is_authenticated:
            return {'status': False, 'message': 'Not authenticated'}
        
        try:
            response = self._smart_api.getProfile(self._refresh_token)
            
            if response.get('status'):
                logger.info("Profile retrieved successfully")
                return {
                    'status': True,
                    'data': response.get('data', {})
                }
            else:
                return {'status': False, 'message': response.get('message')}
                
        except Exception as e:
            logger.exception(f"Get profile exception: {e}")
            return {'status': False, 'message': str(e)}
    
    def get_tokens(self) -> Dict[str, Optional[str]]:
        """
        Get all authentication tokens.
        
        Returns:
            Dictionary with all tokens
        """
        return {
            'session_token': self._session_token,
            'refresh_token': self._refresh_token,
            'feed_token': self._feed_token,
            'jwt_token': self._jwt_token,
        }
