"""
Tests for Real-Time Data Module

Tests for the real-time data manager, providers, and aggregator.
"""

import pytest
import time
import threading
from datetime import datetime
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.realtime_data import RealTimeDataManager
from src.data.realtime_aggregator import RealTimeAggregator
from src.data.providers.base_provider import DataProvider
from src.data.providers.mock_provider import MockDataProvider
from config.realtime_settings import (
    REALTIME_CONFIG,
    MOCK_PROVIDER_CONFIG,
    get_realtime_config,
    get_provider_config,
    get_token_for_symbol,
    get_symbol_for_token,
)


class TestMockDataProvider:
    """Tests for MockDataProvider."""
    
    @pytest.fixture
    def provider(self):
        """Create a mock data provider instance."""
        config = {
            'tick_interval_ms': 100,  # Fast ticks for testing
            'price_volatility': 0.001,
        }
        return MockDataProvider(config=config)
    
    def test_initialization(self, provider):
        """Test provider initializes correctly."""
        assert provider is not None
        assert not provider.is_connected
        assert isinstance(provider, DataProvider)
    
    def test_connect(self, provider):
        """Test provider connection."""
        assert provider.connect()
        assert provider.is_connected
        provider.disconnect()
    
    def test_disconnect(self, provider):
        """Test provider disconnection."""
        provider.connect()
        assert provider.disconnect()
        assert not provider.is_connected
    
    def test_subscribe(self, provider):
        """Test subscribing to tokens."""
        provider.connect()
        
        tokens = ['NIFTY', 'BANKNIFTY']
        assert provider.subscribe(tokens)
        
        subscribed = provider.get_subscribed_tokens()
        assert 'NIFTY' in subscribed
        assert 'BANKNIFTY' in subscribed
        
        provider.disconnect()
    
    def test_unsubscribe(self, provider):
        """Test unsubscribing from tokens."""
        provider.connect()
        provider.subscribe(['NIFTY', 'BANKNIFTY'])
        
        assert provider.unsubscribe(['NIFTY'])
        
        subscribed = provider.get_subscribed_tokens()
        assert 'NIFTY' not in subscribed
        assert 'BANKNIFTY' in subscribed
        
        provider.disconnect()
    
    def test_get_ltp(self, provider):
        """Test getting LTP."""
        provider.connect()
        provider.subscribe(['NIFTY'])
        
        # Wait for tick generation
        time.sleep(0.2)
        
        ltp = provider.get_ltp('NIFTY')
        assert ltp is not None
        assert ltp > 0
        
        provider.disconnect()
    
    def test_get_quote(self, provider):
        """Test getting quote."""
        provider.connect()
        provider.subscribe(['NIFTY'])
        
        # Wait for tick generation
        time.sleep(0.2)
        
        quote = provider.get_quote('NIFTY')
        assert quote is not None
        assert 'ltp' in quote
        assert 'high' in quote
        assert 'low' in quote
        assert 'volume' in quote
        
        provider.disconnect()
    
    def test_tick_callback(self, provider):
        """Test tick callback is called."""
        ticks_received: List[Dict[str, Any]] = []
        
        def on_tick(tick_data):
            ticks_received.append(tick_data)
        
        provider.register_tick_callback(on_tick)
        provider.connect()
        provider.subscribe(['NIFTY'])
        
        # Wait for ticks
        time.sleep(0.3)
        
        assert len(ticks_received) > 0
        
        tick = ticks_received[0]
        assert 'token' in tick
        assert 'ltp' in tick
        
        provider.disconnect()
    
    def test_set_price(self, provider):
        """Test manually setting price."""
        provider.connect()
        provider.subscribe(['TEST_TOKEN'])
        
        provider.set_price('TEST_TOKEN', 100.0)
        
        ltp = provider.get_ltp('TEST_TOKEN')
        assert ltp == 100.0
        
        provider.disconnect()
    
    def test_subscribe_without_connection(self, provider):
        """Test subscribing without connection fails."""
        assert not provider.subscribe(['NIFTY'])
    
    def test_get_ltp_unsubscribed(self, provider):
        """Test getting LTP for unsubscribed token."""
        provider.connect()
        
        ltp = provider.get_ltp('NOT_SUBSCRIBED')
        assert ltp is None
        
        provider.disconnect()


class TestRealTimeDataManager:
    """Tests for RealTimeDataManager."""
    
    @pytest.fixture
    def manager(self):
        """Create a real-time data manager instance."""
        provider = MockDataProvider(config={
            'tick_interval_ms': 100,
            'price_volatility': 0.001,
        })
        config = {
            'reconnect_attempts': 3,
            'reconnect_delay': 1,
            'tick_throttle_ms': 50,
        }
        return RealTimeDataManager(provider=provider, config=config)
    
    def test_initialization(self, manager):
        """Test manager initializes correctly."""
        assert manager is not None
        assert not manager.is_running
        assert not manager.is_connected
    
    def test_start(self, manager):
        """Test starting the manager."""
        assert manager.start()
        assert manager.is_running
        assert manager.is_connected
        manager.stop()
    
    def test_stop(self, manager):
        """Test stopping the manager."""
        manager.start()
        assert manager.stop()
        assert not manager.is_running
    
    def test_subscribe(self, manager):
        """Test subscribing to symbols."""
        manager.start()
        
        assert manager.subscribe(['NIFTY', 'BANKNIFTY'])
        
        subscriptions = manager.get_all_subscriptions()
        assert 'NIFTY' in subscriptions
        assert 'BANKNIFTY' in subscriptions
        
        manager.stop()
    
    def test_unsubscribe(self, manager):
        """Test unsubscribing from symbols."""
        manager.start()
        manager.subscribe(['NIFTY', 'BANKNIFTY'])
        
        assert manager.unsubscribe(['NIFTY'])
        
        subscriptions = manager.get_all_subscriptions()
        assert 'NIFTY' not in subscriptions
        assert 'BANKNIFTY' in subscriptions
        
        manager.stop()
    
    def test_get_ltp(self, manager):
        """Test getting LTP."""
        manager.start()
        manager.subscribe(['NIFTY'])
        
        # Wait for tick generation
        time.sleep(0.3)
        
        ltp = manager.get_ltp('NIFTY')
        assert ltp is not None
        assert ltp > 0
        
        manager.stop()
    
    def test_get_quote(self, manager):
        """Test getting quote."""
        manager.start()
        manager.subscribe(['NIFTY'])
        
        # Wait for tick generation
        time.sleep(0.3)
        
        quote = manager.get_quote('NIFTY')
        assert quote is not None
        assert 'ltp' in quote
        
        manager.stop()
    
    def test_register_callback(self, manager):
        """Test registering callbacks."""
        events_received: List[str] = []
        
        def on_connect(data):
            events_received.append('connect')
        
        def on_tick(data):
            events_received.append('tick')
        
        manager.register_callback('connect', on_connect)
        manager.register_callback('tick', on_tick)
        
        manager.start()
        manager.subscribe(['NIFTY'])
        
        # Wait for events
        time.sleep(0.3)
        
        assert 'connect' in events_received
        assert 'tick' in events_received
        
        manager.stop()
    
    def test_unregister_callback(self, manager):
        """Test unregistering callbacks."""
        call_count = [0]
        
        def on_tick(data):
            call_count[0] += 1
        
        manager.register_callback('tick', on_tick)
        manager.unregister_callback('tick', on_tick)
        
        manager.start()
        manager.subscribe(['NIFTY'])
        
        time.sleep(0.3)
        
        # Should not receive any ticks
        assert call_count[0] == 0
        
        manager.stop()
    
    def test_get_all_ltp(self, manager):
        """Test getting all LTP values."""
        manager.start()
        manager.subscribe(['NIFTY', 'BANKNIFTY'])
        
        time.sleep(0.3)
        
        all_ltp = manager.get_all_ltp()
        assert 'NIFTY' in all_ltp
        assert 'BANKNIFTY' in all_ltp
        
        manager.stop()
    
    def test_subscribe_modes(self, manager):
        """Test different subscription modes."""
        manager.start()
        
        # Test different modes
        assert manager.subscribe(['NIFTY'], mode='ltp')
        assert manager.subscribe(['BANKNIFTY'], mode='quote')
        assert manager.subscribe(['SENSEX'], mode='depth')
        
        manager.stop()
    
    def test_subscribe_without_start(self, manager):
        """Test subscribing without starting fails."""
        assert not manager.subscribe(['NIFTY'])


class TestRealTimeAggregator:
    """Tests for RealTimeAggregator."""
    
    @pytest.fixture
    def aggregator(self):
        """Create a real-time aggregator instance."""
        return RealTimeAggregator(
            intervals=['1m', '5m'],
            max_candles=100
        )
    
    def test_initialization(self, aggregator):
        """Test aggregator initializes correctly."""
        assert aggregator is not None
        stats = aggregator.get_stats()
        assert stats['intervals'] == ['1m', '5m']
        assert stats['max_candles_per_interval'] == 100
    
    def test_on_tick(self, aggregator):
        """Test processing ticks."""
        tick_data = {
            'token': 'NIFTY',
            'ltp': 19250.0,
            'volume': 1000,
        }
        
        aggregator.on_tick(tick_data)
        
        # Should have current candle
        current = aggregator.get_current_candle('NIFTY', '1m')
        assert current is not None
        assert current['close'] == 19250.0
    
    def test_candle_ohlc(self, aggregator):
        """Test OHLC values in candle."""
        ticks = [
            {'token': 'NIFTY', 'ltp': 100.0, 'volume': 100},
            {'token': 'NIFTY', 'ltp': 110.0, 'volume': 100},
            {'token': 'NIFTY', 'ltp': 95.0, 'volume': 100},
            {'token': 'NIFTY', 'ltp': 105.0, 'volume': 100},
        ]
        
        for tick in ticks:
            aggregator.on_tick(tick)
        
        current = aggregator.get_current_candle('NIFTY', '1m')
        assert current is not None
        assert current['open'] == 100.0
        assert current['high'] == 110.0
        assert current['low'] == 95.0
        assert current['close'] == 105.0
        assert current['volume'] == 400
        assert current['tick_count'] == 4
    
    def test_get_candles(self, aggregator):
        """Test getting completed candles."""
        # Initially no completed candles
        candles = aggregator.get_candles('NIFTY', '1m')
        assert len(candles) == 0
    
    def test_get_vwap(self, aggregator):
        """Test VWAP calculation."""
        ticks = [
            {'token': 'NIFTY', 'ltp': 100.0, 'volume': 1000},
            {'token': 'NIFTY', 'ltp': 110.0, 'volume': 2000},
        ]
        
        for tick in ticks:
            aggregator.on_tick(tick)
        
        vwap = aggregator.get_vwap('NIFTY')
        assert vwap is not None
        
        # VWAP = (100*1000 + 110*2000) / 3000 = 106.67
        expected_vwap = (100 * 1000 + 110 * 2000) / 3000
        assert abs(vwap - expected_vwap) < 0.01
    
    def test_get_vwap_no_volume(self, aggregator):
        """Test VWAP with no volume."""
        tick = {'token': 'NIFTY', 'ltp': 100.0, 'volume': 0}
        aggregator.on_tick(tick)
        
        vwap = aggregator.get_vwap('NIFTY')
        assert vwap is None
    
    def test_get_moving_average(self, aggregator):
        """Test moving average calculation."""
        # No candles, no MA
        ma = aggregator.get_moving_average('NIFTY', '1m', 5)
        assert ma is None
    
    def test_reset_symbol(self, aggregator):
        """Test resetting a symbol."""
        aggregator.on_tick({'token': 'NIFTY', 'ltp': 100.0, 'volume': 100})
        aggregator.on_tick({'token': 'BANKNIFTY', 'ltp': 200.0, 'volume': 100})
        
        aggregator.reset('NIFTY')
        
        assert aggregator.get_current_candle('NIFTY', '1m') is None
        assert aggregator.get_current_candle('BANKNIFTY', '1m') is not None
    
    def test_reset_all(self, aggregator):
        """Test resetting all symbols."""
        aggregator.on_tick({'token': 'NIFTY', 'ltp': 100.0, 'volume': 100})
        aggregator.on_tick({'token': 'BANKNIFTY', 'ltp': 200.0, 'volume': 100})
        
        aggregator.reset()
        
        stats = aggregator.get_stats()
        assert stats['total_symbols'] == 0
    
    def test_candle_callback(self, aggregator):
        """Test candle completion callback."""
        candles_received: List[Dict[str, Any]] = []
        
        def on_candle(symbol, interval, candle):
            candles_received.append({
                'symbol': symbol,
                'interval': interval,
                'candle': candle,
            })
        
        aggregator.register_candle_callback(on_candle)
        
        # Note: Candle callbacks only fire when a new candle starts
        # In real usage, this would happen when crossing minute boundaries
        aggregator.on_tick({'token': 'NIFTY', 'ltp': 100.0, 'volume': 100})
        
        # No callback yet since no candle completed
        assert len(candles_received) == 0
    
    def test_invalid_interval(self):
        """Test invalid interval raises error."""
        with pytest.raises(ValueError):
            RealTimeAggregator(intervals=['invalid'])
    
    def test_multiple_symbols(self, aggregator):
        """Test handling multiple symbols."""
        ticks = [
            {'token': 'NIFTY', 'ltp': 19250.0, 'volume': 100},
            {'token': 'BANKNIFTY', 'ltp': 43500.0, 'volume': 100},
            {'token': 'SENSEX', 'ltp': 64800.0, 'volume': 100},
        ]
        
        for tick in ticks:
            aggregator.on_tick(tick)
        
        stats = aggregator.get_stats()
        assert stats['total_symbols'] == 3


class TestRealtimeSettings:
    """Tests for real-time settings configuration."""
    
    def test_realtime_config(self):
        """Test REALTIME_CONFIG has expected keys."""
        assert 'provider' in REALTIME_CONFIG
        assert 'reconnect_attempts' in REALTIME_CONFIG
        assert 'tick_throttle_ms' in REALTIME_CONFIG
    
    def test_mock_provider_config(self):
        """Test MOCK_PROVIDER_CONFIG has expected keys."""
        assert 'tick_interval_ms' in MOCK_PROVIDER_CONFIG
        assert 'price_volatility' in MOCK_PROVIDER_CONFIG
        assert 'base_prices' in MOCK_PROVIDER_CONFIG
    
    def test_get_realtime_config(self):
        """Test get_realtime_config function."""
        config = get_realtime_config()
        assert 'provider' in config
        assert 'mock_provider' in config
        assert 'angel_one_provider' in config
    
    def test_get_provider_config(self):
        """Test get_provider_config function."""
        mock_config = get_provider_config('mock')
        assert 'tick_interval_ms' in mock_config
        
        angel_config = get_provider_config('angel_one')
        assert 'exchange_type' in angel_config
        
        unknown_config = get_provider_config('unknown')
        assert unknown_config == {}
    
    def test_get_token_for_symbol(self):
        """Test symbol to token mapping."""
        token = get_token_for_symbol('NIFTY')
        assert token == '99926000'
        
        # Unknown symbol returns itself
        unknown = get_token_for_symbol('UNKNOWN')
        assert unknown == 'UNKNOWN'
    
    def test_get_symbol_for_token(self):
        """Test token to symbol mapping."""
        symbol = get_symbol_for_token('99926000')
        assert symbol == 'NIFTY'
        
        # Unknown token returns itself
        unknown = get_symbol_for_token('12345')
        assert unknown == '12345'


class TestIntegration:
    """Integration tests for real-time data components."""
    
    def test_manager_with_aggregator(self):
        """Test manager integrated with aggregator."""
        provider = MockDataProvider(config={
            'tick_interval_ms': 50,
            'price_volatility': 0.001,
        })
        
        manager = RealTimeDataManager(
            provider=provider,
            config={'tick_throttle_ms': 20}
        )
        
        aggregator = RealTimeAggregator(intervals=['1m'])
        
        # Connect aggregator to manager
        manager.register_callback('tick', aggregator.on_tick)
        
        manager.start()
        manager.subscribe(['NIFTY'])
        
        # Wait for ticks
        time.sleep(0.3)
        
        # Check aggregator received data
        current = aggregator.get_current_candle('NIFTY', '1m')
        assert current is not None
        assert current['tick_count'] > 0
        
        manager.stop()
    
    def test_thread_safety(self):
        """Test thread safety of components."""
        provider = MockDataProvider(config={
            'tick_interval_ms': 10,
            'price_volatility': 0.001,
        })
        
        manager = RealTimeDataManager(
            provider=provider,
            config={'tick_throttle_ms': 5}
        )
        
        errors = []
        
        def subscriber():
            try:
                for _ in range(10):
                    manager.subscribe(['NIFTY'])
                    time.sleep(0.01)
                    manager.get_ltp('NIFTY')
            except Exception as e:
                errors.append(e)
        
        manager.start()
        
        threads = [threading.Thread(target=subscriber) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        
        manager.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
