#!/usr/bin/env python3
"""
Вычитка кода - проверка всех модулей на наличие функций и классов.
"""

import os
import ast
import sys
from pathlib import Path

def analyze_python_file(file_path):
    """Анализирует Python файл и возвращает информацию о функциях и классах."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        functions = []
        classes = []
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.append(f"{node.module}.{alias.name}" if node.module else alias.name)
        
        return {
            'functions': functions,
            'classes': classes,
            'imports': imports,
            'lines': len(content.splitlines())
        }
    except Exception as e:
        return {'error': str(e)}

def audit_module(module_path):
    """Аудирует модуль и его зависимости."""
    print(f"\n🔍 Аудит модуля: {module_path}")
    
    if not os.path.exists(module_path):
        print(f"❌ Файл не найден: {module_path}")
        return False
    
    analysis = analyze_python_file(module_path)
    
    if 'error' in analysis:
        print(f"❌ Ошибка анализа: {analysis['error']}")
        return False
    
    print(f"📊 Статистика:")
    print(f"   - Строк кода: {analysis['lines']}")
    print(f"   - Функций: {len(analysis['functions'])}")
    print(f"   - Классов: {len(analysis['classes'])}")
    print(f"   - Импортов: {len(analysis['imports'])}")
    
    if analysis['functions']:
        print(f"   - Функции: {', '.join(analysis['functions'][:5])}{'...' if len(analysis['functions']) > 5 else ''}")
    
    if analysis['classes']:
        print(f"   - Классы: {', '.join(analysis['classes'])}")
    
    return True

def check_missing_imports():
    """Проверяет отсутствующие импорты."""
    print("\n🔍 Проверка отсутствующих импортов...")
    
    missing_imports = []
    
    # Проверяем основные модули
    modules_to_check = [
        'orchestrator/app.py',
        'orchestrator/exec/sl_manager.py',
        'orchestrator/exec/planner.py',
        'orchestrator/signals/breakout.py',
        'orchestrator/risk/filters.py',
        'orchestrator/telemetry/logger.py',
        'orchestrator/api/healthcheck.py',
        'orchestrator/engine/pipeline.py'
    ]
    
    for module in modules_to_check:
        if not os.path.exists(module):
            missing_imports.append(f"Файл не найден: {module}")
            continue
        
        analysis = analyze_python_file(module)
        if 'error' in analysis:
            missing_imports.append(f"Ошибка в {module}: {analysis['error']}")
            continue
        
        # Проверяем, что файл не пустой
        if analysis['lines'] < 10:
            missing_imports.append(f"Файл слишком короткий: {module} ({analysis['lines']} строк)")
    
    if missing_imports:
        print("❌ Найдены проблемы:")
        for issue in missing_imports:
            print(f"   - {issue}")
        return False
    else:
        print("✅ Все модули в порядке")
        return True

def check_critical_functions():
    """Проверяет наличие критически важных функций."""
    print("\n🔍 Проверка критических функций...")
    
    critical_functions = {
        'orchestrator/exec/sl_manager.py': ['SLManager', 'maybe_adjust_sl'],
        'orchestrator/exec/planner.py': ['plan_entry', 'PlanBuilder'],
        'orchestrator/signals/breakout.py': ['compute_marks'],
        'orchestrator/risk/filters.py': ['check_daily_loss', 'check_position_limits'],
        'orchestrator/telemetry/logger.py': ['setup_logger'],
        'orchestrator/api/healthcheck.py': ['health_check'],
        'orchestrator/engine/pipeline.py': ['Pipeline', 'AnalyzePipeline']
    }
    
    missing_functions = []
    
    for module_path, expected_functions in critical_functions.items():
        if not os.path.exists(module_path):
            missing_functions.append(f"Модуль не найден: {module_path}")
            continue
        
        analysis = analyze_python_file(module_path)
        if 'error' in analysis:
            missing_functions.append(f"Ошибка в {module_path}: {analysis['error']}")
            continue
        
        for func in expected_functions:
            if func not in analysis['functions'] and func not in analysis['classes']:
                missing_functions.append(f"Отсутствует {func} в {module_path}")
    
    if missing_functions:
        print("❌ Найдены отсутствующие функции:")
        for issue in missing_functions:
            print(f"   - {issue}")
        return False
    else:
        print("✅ Все критические функции найдены")
        return True

def generate_missing_code_report():
    """Генерирует отчет о недостающем коде."""
    print("\n📝 Генерация отчета о недостающем коде...")
    
    report = {
        'missing_classes': [],
        'missing_functions': [],
        'empty_files': [],
        'broken_imports': []
    }
    
    # Проверяем каждый модуль
    modules = [
        'orchestrator/exec/sl_manager.py',
        'orchestrator/exec/planner.py',
        'orchestrator/signals/breakout.py',
        'orchestrator/risk/filters.py',
        'orchestrator/telemetry/logger.py',
        'orchestrator/api/healthcheck.py',
        'orchestrator/engine/pipeline.py'
    ]
    
    for module in modules:
        if not os.path.exists(module):
            report['broken_imports'].append(module)
            continue
        
        analysis = analyze_python_file(module)
        if 'error' in analysis:
            report['broken_imports'].append(f"{module}: {analysis['error']}")
            continue
        
        if analysis['lines'] < 10:
            report['empty_files'].append(module)
    
    # Сохраняем отчет
    with open('code_audit_report.json', 'w') as f:
        import json
        json.dump(report, f, indent=2)
    
    print(f"📄 Отчет сохранен: code_audit_report.json")
    return report

def main():
    """Главная функция аудита кода."""
    print("🔍 ВЫЧИТКА КОДА - АУДИТ СИСТЕМЫ")
    print("=" * 50)
    
    # Аудируем основные модули
    modules_to_audit = [
        'orchestrator/app.py',
        'orchestrator/exec/sl_manager.py',
        'orchestrator/exec/planner.py',
        'orchestrator/signals/breakout.py',
        'orchestrator/risk/filters.py',
        'orchestrator/telemetry/logger.py',
        'orchestrator/api/healthcheck.py',
        'orchestrator/engine/pipeline.py'
    ]
    
    for module in modules_to_audit:
        audit_module(module)
    
    # Проверяем отсутствующие импорты
    check_missing_imports()
    
    # Проверяем критические функции
    check_critical_functions()
    
    # Генерируем отчет
    report = generate_missing_code_report()
    
    print("\n" + "=" * 50)
    print("📊 ИТОГОВЫЙ ОТЧЕТ АУДИТА")
    print("=" * 50)
    
    total_issues = len(report['missing_classes']) + len(report['missing_functions']) + len(report['empty_files']) + len(report['broken_imports'])
    
    if total_issues == 0:
        print("✅ КОД В ПОРЯДКЕ - НЕТ КРИТИЧЕСКИХ ПРОБЛЕМ")
    else:
        print(f"⚠️ НАЙДЕНО {total_issues} ПРОБЛЕМ:")
        print(f"   - Отсутствующие классы: {len(report['missing_classes'])}")
        print(f"   - Отсутствующие функции: {len(report['missing_functions'])}")
        print(f"   - Пустые файлы: {len(report['empty_files'])}")
        print(f"   - Сломанные импорты: {len(report['broken_imports'])}")
    
    return total_issues == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
