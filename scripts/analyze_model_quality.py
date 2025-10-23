#!/usr/bin/env python3
"""
Анализ качества моделей и направлений.
"""

import json
import pandas as pd
from pathlib import Path
import sys

# Добавляем путь к проекту
sys.path.append('.')

def analyze_model_quality():
    """Анализирует качество всех моделей."""
    models_dir = Path("data/models")
    
    results = []
    
    # Сканируем все модели
    for model_file in models_dir.glob("binary_hit_*_H*.meta.json"):
        try:
            with open(model_file, 'r') as f:
                meta = json.load(f)
            
            # Извлекаем символ и горизонт из имени файла
            filename = model_file.stem
            parts = filename.split('_')
            symbol = parts[2] if len(parts) > 2 else 'UNKNOWN'
            horizon = parts[3] if len(parts) > 3 else 'UNKNOWN'
            
            auc = meta.get('val_auc', 0.0)
            n_train = meta.get('val_count', 0)
            
            results.append({
                'symbol': symbol,
                'horizon': horizon,
                'auc': auc,
                'n_train': n_train,
                'quality': 'Excellent' if auc >= 0.65 else 'Good' if auc >= 0.55 else 'Fair' if auc >= 0.50 else 'Poor'
            })
        except Exception as e:
            print(f"Error reading {model_file}: {e}")
    
    return results

def create_quality_report(results):
    """Создает отчет о качестве моделей."""
    df = pd.DataFrame(results)
    
    print("🎯 ОТЧЕТ О КАЧЕСТВЕ МОДЕЛЕЙ")
    print("=" * 80)
    
    # Общая статистика
    print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    print(f"  Всего моделей: {len(df)}")
    print(f"  Средний AUC: {df['auc'].mean():.3f}")
    print(f"  Медианный AUC: {df['auc'].median():.3f}")
    print(f"  Лучший AUC: {df['auc'].max():.3f}")
    print(f"  Худший AUC: {df['auc'].min():.3f}")
    
    # Качество по горизонтам
    print(f"\n📈 КАЧЕСТВО ПО ГОРИЗОНТАМ:")
    horizon_stats = df.groupby('horizon')['auc'].agg(['count', 'mean', 'std', 'min', 'max'])
    for horizon, stats in horizon_stats.iterrows():
        print(f"  {horizon}: {stats['count']} моделей, AUC {stats['mean']:.3f} ± {stats['std']:.3f}")
    
    # Качество по символам
    print(f"\n🏆 ТОП-10 ЛУЧШИХ МОДЕЛЕЙ:")
    top_models = df.nlargest(10, 'auc')[['symbol', 'horizon', 'auc', 'quality']]
    for _, row in top_models.iterrows():
        print(f"  {row['symbol']} {row['horizon']}: AUC={row['auc']:.3f} ({row['quality']})")
    
    # Качество по символам (среднее)
    print(f"\n📊 СРЕДНЕЕ КАЧЕСТВО ПО СИМВОЛАМ:")
    symbol_stats = df.groupby('symbol')['auc'].agg(['count', 'mean', 'std']).round(3)
    symbol_stats = symbol_stats.sort_values('mean', ascending=False)
    for symbol, stats in symbol_stats.iterrows():
        print(f"  {symbol}: {stats['count']} моделей, средний AUC {stats['mean']:.3f} ± {stats['std']:.3f}")
    
    # Распределение по качеству
    print(f"\n🎯 РАСПРЕДЕЛЕНИЕ ПО КАЧЕСТВУ:")
    quality_dist = df['quality'].value_counts()
    for quality, count in quality_dist.items():
        pct = count / len(df) * 100
        print(f"  {quality}: {count} моделей ({pct:.1f}%)")
    
    # Рекомендации
    print(f"\n💡 РЕКОМЕНДАЦИИ:")
    excellent_models = df[df['quality'] == 'Excellent']
    if len(excellent_models) > 0:
        print(f"  ✅ {len(excellent_models)} моделей с отличным качеством (AUC ≥ 0.65)")
    
    poor_models = df[df['quality'] == 'Poor']
    if len(poor_models) > 0:
        print(f"  ⚠️  {len(poor_models)} моделей с плохим качеством (AUC < 0.50)")
        print(f"     Рекомендуется отключить: {', '.join(poor_models['symbol'].unique())}")
    
    # Направления (LONG/SHORT)
    print(f"\n🔄 АНАЛИЗ НАПРАВЛЕНИЙ:")
    print(f"  Все модели обучены на бинарной классификации hit/miss")
    print(f"  Поддерживаются оба направления: LONG и SHORT")
    print(f"  Сторона определяется провайдером сигнала")
    
    return df

def main():
    """Главная функция анализа."""
    print("🔍 Анализ качества моделей...")
    
    results = analyze_model_quality()
    if not results:
        print("❌ Модели не найдены!")
        return
    
    df = create_quality_report(results)
    
    # Сохраняем детальный отчет
    report_file = Path("reports/model_quality_report.csv")
    df.to_csv(report_file, index=False)
    print(f"\n💾 Детальный отчет сохранен: {report_file}")
    
    print(f"\n🎉 Анализ завершен!")

if __name__ == "__main__":
    main()
