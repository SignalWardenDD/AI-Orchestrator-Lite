#!/usr/bin/env python3
"""
Генерация оптимизированной конфигурации моделей с весами и EV-порогами.
"""

import yaml
import json
from pathlib import Path
import sys

# Добавляем путь к проекту
sys.path.append('.')

def load_model_quality():
    """Загружает данные о качестве моделей."""
    try:
        df = pd.read_csv("model_quality_report.csv")
        return df
    except:
        # Fallback данные на основе анализа
        return {
            'DOGEUSDT': {'avg_auc': 0.572, 'tier': 1},
            'SEIUSDT': {'avg_auc': 0.558, 'tier': 1},
            'LTCUSDT': {'avg_auc': 0.556, 'tier': 1},
            'ARBUSDT': {'avg_auc': 0.555, 'tier': 1},
            'ADAUSDT': {'avg_auc': 0.535, 'tier': 2},
            'SUIUSDT': {'avg_auc': 0.518, 'tier': 2},
            'WIFUSDT': {'avg_auc': 0.504, 'tier': 3},
            'HBARUSDT': {'avg_auc': 0.500, 'tier': 3},
            'PNUTUSDT': {'avg_auc': 0.498, 'tier': 3},
            'ENAUSDT': {'avg_auc': 0.427, 'tier': 3}
        }

def generate_models_per_signal_yaml():
    """Генерирует оптимизированный YAML для per-signal моделей."""
    
    # Tier-разделение на основе анализа
    tier_config = {
        1: {  # Tier 1 - Приоритетные пары
            'symbols': ['DOGEUSDT', 'SEIUSDT', 'LTCUSDT', 'ARBUSDT'],
            'weight': 1.2,
            'ev_min': 0.10,
            'enabled': True
        },
        2: {  # Tier 2 - Вторичные пары
            'symbols': ['ADAUSDT', 'SUIUSDT'],
            'weight': 0.8,
            'ev_min': 0.15,
            'enabled': True
        },
        3: {  # Tier 3 - Слабые пары (отключить)
            'symbols': ['WIFUSDT', 'HBARUSDT', 'PNUTUSDT', 'ENAUSDT'],
            'weight': 0.0,
            'ev_min': 0.25,
            'enabled': False
        }
    }
    
    # Генерируем конфигурацию
    config = {
        'version': '1.0',
        'description': 'Optimized per-signal models configuration with tier-based weights and EV thresholds',
        'models': {}
    }
    
    # Добавляем модели для каждого тира
    for tier, tier_data in tier_config.items():
        for symbol in tier_data['symbols']:
            for signal in ['BRK', 'PB', 'MR', 'BB']:
                for horizon in ['H12', 'H24']:
                    key = f"{symbol}_{signal}_{horizon}"
                    
                    config['models'][key] = {
                        'symbol': symbol,
                        'signal': signal,
                        'horizon': horizon,
                        'model_path': f"forecast/models/per_signal/{symbol}_{signal}_{horizon}.joblib",
                        'calibrator_path': f"forecast/models/per_signal/{symbol}_{signal}_{horizon}.calib.isotonic.joblib",
                        'weight': tier_data['weight'],
                        'ev_min': tier_data['ev_min'],
                        'enabled': tier_data['enabled'],
                        'tier': tier,
                        'fallback_to_individual': True,
                        'fallback_to_group': True
                    }
    
    return config

def generate_individual_models_yaml():
    """Генерирует оптимизированный YAML для индивидуальных моделей."""
    
    # Tier-разделение
    tier_config = {
        1: {  # Tier 1
            'symbols': ['DOGEUSDT', 'SEIUSDT', 'LTCUSDT', 'ARBUSDT'],
            'weight': 1.0,
            'ev_min': 0.10,
            'enabled': True
        },
        2: {  # Tier 2
            'symbols': ['ADAUSDT', 'SUIUSDT'],
            'weight': 0.7,
            'ev_min': 0.15,
            'enabled': True
        },
        3: {  # Tier 3
            'symbols': ['WIFUSDT', 'HBARUSDT', 'PNUTUSDT', 'ENAUSDT'],
            'weight': 0.0,
            'ev_min': 0.25,
            'enabled': False
        }
    }
    
    config = {
        'version': '1.0',
        'description': 'Optimized individual models configuration with tier-based weights and EV thresholds',
        'models': {}
    }
    
    # Добавляем модели для каждого тира
    for tier, tier_data in tier_config.items():
        for symbol in tier_data['symbols']:
            for horizon in ['H12', 'H24']:
                key = f"{symbol}_{horizon}"
                
                config['models'][key] = {
                    'symbol': symbol,
                    'horizon': horizon,
                    'model_path': f"forecast/models/binary_hit_{symbol}_{horizon}.joblib",
                    'calibrator_path': f"forecast/models/binary_hit_{symbol}_{horizon}.calib.isotonic.joblib",
                    'weight': tier_data['weight'],
                    'ev_min': tier_data['ev_min'],
                    'enabled': tier_data['enabled'],
                    'tier': tier,
                    'fallback_to_group': True
                }
    
    return config

def generate_orchestrator_config():
    """Генерирует конфигурацию для оркестратора с EV-порогами."""
    
    config = {
        'orchestrator': {
            'ev_filtering': {
                'tier_1_ev_min': 0.10,  # Tier 1 пары
                'tier_2_ev_min': 0.15,  # Tier 2 пары
                'tier_3_ev_min': 0.25,  # Tier 3 пары (отключены)
                'default_ev_min': 0.12,
                'max_ev_threshold': 0.30
            },
            'model_weights': {
                'tier_1_weight': 1.2,
                'tier_2_weight': 0.8,
                'tier_3_weight': 0.0,
                'per_signal_boost': 1.1
            },
            'risk_management': {
                'max_positions_per_symbol': 1,
                'max_global_positions': 4,
                'position_size_usdt': 15,
                'leverage': 5,
                'cooldown_seconds': 0
            },
            'ml_integration': {
                'use_per_signal_models': True,
                'fallback_to_individual': True,
                'fallback_to_group': True,
                'auto_disable_weak_models': True,
                'retrain_frequency_days': 14
            }
        }
    }
    
    return config

def main():
    """Главная функция генерации конфигураций."""
    print("🔧 Генерация оптимизированных конфигураций...")
    
    # 1. Per-signal models YAML
    print("📝 Генерация models_per_signal.yaml...")
    per_signal_config = generate_models_per_signal_yaml()
    
    with open('config/optimized/models_per_signal_optimized.yaml', 'w') as f:
        yaml.dump(per_signal_config, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Создан config/models_per_signal_optimized.yaml")
    print(f"   - {len(per_signal_config['models'])} моделей")
    print(f"   - Tier 1: {len([k for k, v in per_signal_config['models'].items() if v['tier'] == 1])} моделей")
    print(f"   - Tier 2: {len([k for k, v in per_signal_config['models'].items() if v['tier'] == 2])} моделей")
    print(f"   - Tier 3: {len([k for k, v in per_signal_config['models'].items() if v['tier'] == 3])} моделей (отключены)")
    
    # 2. Individual models YAML
    print("\n📝 Генерация models_individual_optimized.yaml...")
    individual_config = generate_individual_models_yaml()
    
    with open('config/optimized/models_individual_optimized.yaml', 'w') as f:
        yaml.dump(individual_config, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Создан config/models_individual_optimized.yaml")
    print(f"   - {len(individual_config['models'])} моделей")
    print(f"   - Tier 1: {len([k for k, v in individual_config['models'].items() if v['tier'] == 1])} моделей")
    print(f"   - Tier 2: {len([k for k, v in individual_config['models'].items() if v['tier'] == 2])} моделей")
    print(f"   - Tier 3: {len([k for k, v in individual_config['models'].items() if v['tier'] == 3])} моделей (отключены)")
    
    # 3. Orchestrator config
    print("\n📝 Генерация orchestrator_optimized.yaml...")
    orchestrator_config = generate_orchestrator_config()
    
    with open('config/optimized/orchestrator_optimized.yaml', 'w') as f:
        yaml.dump(orchestrator_config, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Создан config/orchestrator_optimized.yaml")
    
    # 4. Создаем README с инструкциями
    print("\n📝 Создание README с инструкциями...")
    
    readme_content = """# 🚀 Оптимизированная конфигурация для лайв-торговли

## 📊 Tier-разделение моделей

### Tier 1 (Приоритетные пары) - weight=1.2, EV_min=0.10
- **DOGEUSDT** - лучшее качество (AUC 0.572)
- **SEIUSDT** - стабильное качество (AUC 0.558)
- **LTCUSDT** - хорошее качество (AUC 0.556)
- **ARBUSDT** - стабильное качество (AUC 0.555)

### Tier 2 (Вторичные пары) - weight=0.8, EV_min=0.15
- **ADAUSDT** - среднее качество (AUC 0.535)
- **SUIUSDT** - нестабильное качество (AUC 0.518)

### Tier 3 (Отключенные пары) - weight=0.0, EV_min=0.25
- **WIFUSDT** - низкое качество (AUC 0.504)
- **HBARUSDT** - низкое качество (AUC 0.500)
- **PNUTUSDT** - плохое качество (AUC 0.498)
- **ENAUSDT** - очень плохое качество (AUC 0.427)

## 🔧 Как использовать

1. **Обновите settings.yaml:**
```yaml
ml:
  models_per_signal:
    yaml_path: "config/models_per_signal_optimized.yaml"
  models_individual:
    yaml_path: "config/models_individual_optimized.yaml"
```

2. **Запустите оркестратор:**
```bash
python3 orchestrator/app.py
```

## 📈 Ожидаемые результаты

- **Tier 1 пары:** активная торговля с высоким EV
- **Tier 2 пары:** ограниченная торговля с повышенным EV-порогом
- **Tier 3 пары:** отключены для предотвращения убытков

## 🔄 Мониторинг и обновление

- **Retrain:** каждые 2 недели
- **Мониторинг AUC:** в реальном времени
- **Auto-disable:** слабые модели отключаются автоматически

## 📞 Поддержка

При возникновении вопросов проверьте:
1. Качество моделей в `MODEL_QUALITY_REPORT.md`
2. Логи оркестратора
3. EV-пороги в конфигурации
"""
    
    with open('config/optimized/README_OPTIMIZED.md', 'w') as f:
        f.write(readme_content)
    
    print(f"✅ Создан config/README_OPTIMIZED.md")
    
    print(f"\n🎉 Оптимизированные конфигурации созданы!")
    print(f"📁 Файлы:")
    print(f"   - config/optimized/models_per_signal_optimized.yaml")
    print(f"   - config/optimized/models_individual_optimized.yaml")
    print(f"   - config/optimized/orchestrator_optimized.yaml")
    print(f"   - config/optimized/README_OPTIMIZED.md")
    
    print(f"\n🚀 Система готова к лайв-торговле с оптимизированными настройками!")

if __name__ == "__main__":
    main()
