#!/usr/bin/env python3
"""
Тест подключения к Binance и синхронизации данных
"""
import sys
import os
from datetime import datetime

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from orchestrator.exec.broker import Broker
from orchestrator.state.recon import reconcile_from_exchange
from orchestrator.state.store import StateStore
from orchestrator.utils.env import load_env

def test_binance_connection():
    """Тест подключения к Binance API"""
    print("🔗 Тестирование подключения к Binance...")
    
    try:
        # Загружаем конфигурацию
        env = load_env()
        print(f"✅ Конфигурация загружена")
        print(f"   API Key: {env.binance_key[:10]}..." if env.binance_key else "   API Key: НЕ НАЙДЕН")
        print(f"   Base URL: {env.base_url}")
        
        if not env.binance_key or not env.binance_secret:
            print("❌ ОШИБКА: API ключи не найдены в .env файле")
            return False
            
        # Создаем брокера
        broker = Broker(env.binance_key, env.binance_secret, env.base_url)
        print("✅ Брокер создан")
        
        # Тест 1: Получение информации о бирже
        print("\n📊 Тест 1: Информация о бирже...")
        try:
            exchange_info = broker.fetch_exchange_info()
            print(f"   ✅ Exchange info получена")
            print(f"   Серверное время: {datetime.fromtimestamp(exchange_info.get('serverTime', 0)/1000)}")
        except Exception as e:
            print(f"   ❌ Ошибка получения exchange info: {e}")
            return False
            
        # Тест 2: Получение цены
        print("\n💰 Тест 2: Получение цены BTCUSDT...")
        try:
            price = broker.fetch_price("BTCUSDT")
            print(f"   ✅ Цена BTCUSDT: ${price:,.2f}")
        except Exception as e:
            print(f"   ❌ Ошибка получения цены: {e}")
            return False
            
        # Тест 3: Получение исторических данных
        print("\n📈 Тест 3: Получение исторических данных ADAUSDT...")
        try:
            klines = broker.fetch_ohlcv("ADAUSDT", "1h", 5)
            print(f"   ✅ Получено {len(klines)} свечей")
            if klines:
                last_candle = klines[-1]
                print(f"   Последняя свеча: O={last_candle[1]}, H={last_candle[2]}, L={last_candle[3]}, C={last_candle[4]}")
        except Exception as e:
            print(f"   ❌ Ошибка получения исторических данных: {e}")
            return False
            
        # Тест 4: Проверка позиций
        print("\n📋 Тест 4: Проверка позиций...")
        try:
            positions = broker.position_info("ADAUSDT")
            if positions:
                print(f"   ✅ Позиция ADAUSDT найдена:")
                print(f"   Количество: {positions.get('positionAmt', 0)}")
                print(f"   Цена входа: {positions.get('entryPrice', 0)}")
                print(f"   PnL: {positions.get('unrealizedPnl', 0)}")
            else:
                print("   ℹ️  Позиций по ADAUSDT нет")
        except Exception as e:
            print(f"   ❌ Ошибка проверки позиций: {e}")
            return False
            
        # Тест 5: Синхронизация состояния
        print("\n🔄 Тест 5: Синхронизация состояния...")
        try:
            store = StateStore()
            reconcile_from_exchange(store, broker)
            print(f"   ✅ Синхронизация завершена")
            print(f"   Восстановлено позиций: {len(store.positions)}")
            for symbol, pos in store.positions.items():
                print(f"   - {symbol}: {pos.side} {pos.qty} @ {pos.entry_price}")
        except Exception as e:
            print(f"   ❌ Ошибка синхронизации: {e}")
            return False
            
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("✅ Подключение к Binance работает корректно")
        return True
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Тест подключения к Binance USDT-M")
    print("=" * 50)
    
    success = test_binance_connection()
    
    if success:
        print("\n✅ Готово! Оркестратор может работать с Binance")
        sys.exit(0)
    else:
        print("\n❌ Есть проблемы с подключением к Binance")
        sys.exit(1)
