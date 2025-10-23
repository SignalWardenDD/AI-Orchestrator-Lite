#!/usr/bin/env python3
"""
Главный скрипт для запуска торговой системы.
Поддерживает graceful shutdown по Ctrl+C.
"""

import sys
import os
import signal
import time
import traceback
from typing import Optional

# Добавляем путь к проекту
sys.path.append('.')

class TradingSystem:
    """Главный класс торговой системы."""
    
    def __init__(self):
        self.running = False
        self.pipeline = None
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов для graceful shutdown."""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для остановки системы."""
        print(f"\n🛑 Получен сигнал {signum}. Останавливаем систему...")
        self.running = False
    
    def initialize_system(self) -> bool:
        """Инициализация всех компонентов системы."""
        try:
            print("🔧 Инициализация торговой системы...")
            
            # Импорты основных модулей
            from orchestrator.engine.pipeline import AnalyzePipeline
            from orchestrator.telemetry.logger import audit_line
            from orchestrator.state.store import StateStore
            from orchestrator.exec.broker import Broker
            from orchestrator.auction.scorer import IndividualMLManager, MLConfig
            import yaml
            
            # Загрузка конфигурации
            with open('config/settings.yaml', 'r') as f:
                settings = yaml.safe_load(f)
            
            with open('config/symbols.yaml', 'r') as f:
                symbols_config = yaml.safe_load(f)
            
            # Инициализация компонентов
            print("  📊 Загрузка символов...")
            symbols = list(symbols_config['A_group'].keys()) + list(symbols_config['B_group'].keys())
            print(f"  📊 Активных символов: {len(symbols)}")
            
            # Инициализация брокера (требует API ключи)
            print("  🔑 Инициализация брокера...")
            api_key = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_API_SECRET')
            
            if not api_key or not api_secret:
                print("  ⚠️  API ключи не найдены. Используем dummy брокер для тестирования.")
                from orchestrator.exec.dummy_broker import DummyBroker
                broker = DummyBroker()
            else:
                broker = Broker(api_key, api_secret)
            
            # Инициализация ML менеджера
            print("  🤖 Инициализация ML...")
            ml_manager = IndividualMLManager("config/models_individual_optimized.yaml")
            ml_config = MLConfig(
                enabled=True,
                config_path="config/models_individual_optimized.yaml",
                min_auc_threshold=0.45
            )
            
            # Инициализация хранилища состояния
            print("  💾 Инициализация хранилища...")
            store = StateStore()
            
            # Инициализация пайплайна
            print("  🔄 Инициализация пайплайна...")
            self.pipeline = AnalyzePipeline(
                symbols=symbols,
                settings=settings,
                broker=broker,
                store=store,
                ml_manager=ml_manager,
                ml_config=ml_config
            )
            
            print("✅ Система инициализирована успешно")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка инициализации: {e}")
            traceback.print_exc()
            return False
    
    def run(self):
        """Главный цикл работы системы."""
        if not self.initialize_system():
            print("❌ Не удалось инициализировать систему")
            return False
        
        self.running = True
        print("\n🚀 ТОРГОВАЯ СИСТЕМА ЗАПУЩЕНА")
        print("=" * 50)
        print("📊 Статус: АКТИВНА")
        print("🛑 Для остановки нажмите Ctrl+C")
        print("=" * 50)
        
        cycle_count = 0
        last_heartbeat = time.time()
        
        try:
            while self.running:
                cycle_start = time.time()
                cycle_count += 1
                
                try:
                    # Выполнение одного цикла анализа
                    self.pipeline.run_once()
                    
                    # Логирование каждые 10 циклов
                    if cycle_count % 10 == 0:
                        print(f"🔄 Цикл #{cycle_count} выполнен")
                    
                    # Heartbeat каждые 5 минут
                    if time.time() - last_heartbeat > 300:
                        print(f"💓 Heartbeat: {cycle_count} циклов выполнено")
                        last_heartbeat = time.time()
                    
                except Exception as e:
                    print(f"⚠️  Ошибка в цикле #{cycle_count}: {e}")
                    # Не останавливаем систему при ошибке в одном цикле
                    continue
                
                # Пауза между циклами
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, 120 - cycle_duration)  # 120 секунд между циклами
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("\n🛑 Получен сигнал остановки")
        except Exception as e:
            print(f"\n❌ Критическая ошибка: {e}")
            traceback.print_exc()
        finally:
            self.shutdown()
        
        return True
    
    def shutdown(self):
        """Корректное завершение работы системы."""
        print("\n🔄 Завершение работы системы...")
        
        try:
            # Закрытие всех открытых позиций (если нужно)
            if self.pipeline and hasattr(self.pipeline, 'close_all_positions'):
                self.pipeline.close_all_positions()
            
            # Сохранение состояния
            if self.pipeline and hasattr(self.pipeline, 'store'):
                self.pipeline.store.save_state()
            
            print("✅ Система корректно завершена")
            
        except Exception as e:
            print(f"⚠️  Ошибка при завершении: {e}")

def main():
    """Главная функция."""
    print("🚀 ORCHESTRATOR-ALPHA v1.0 - ТОРГОВАЯ СИСТЕМА")
    print("=" * 60)
    
    # Проверка окружения
    print("🔍 Проверка окружения...")
    
    # Проверка API ключей
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        print("⚠️  ВНИМАНИЕ: API ключи Binance не найдены!")
        print("   Установите переменные окружения:")
        print("   export BINANCE_API_KEY='your_key'")
        print("   export BINANCE_API_SECRET='your_secret'")
        print("   Система будет работать в тестовом режиме с dummy брокером")
        print()
    
    # Запуск системы
    system = TradingSystem()
    success = system.run()
    
    if success:
        print("🎉 Система завершила работу успешно")
        return 0
    else:
        print("❌ Система завершилась с ошибками")
        return 1

if __name__ == "__main__":
    sys.exit(main())
