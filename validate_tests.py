#!/usr/bin/env python3
"""
Test validation script to verify test setup and dependencies.
"""

import sys
import importlib
from pathlib import Path


def check_imports():
    """Check if all required modules can be imported."""
    required_modules = [
        'pytest',
        'pandas',
        'numpy',
        'ta',
        'asyncio',
    ]
    
    print("Checking required modules...")
    missing_modules = []
    
    for module in required_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module}")
            missing_modules.append(module)
    
    if missing_modules:
        print(f"\nMissing modules: {', '.join(missing_modules)}")
        print("Please install missing modules with: pip install -r requirements.txt")
        return False
    
    return True


def check_project_structure():
    """Check if project structure is correct."""
    print("\nChecking project structure...")
    
    required_paths = [
        'src/',
        'src/config.py',
        'src/data/',
        'src/data/collector.py',
        'src/strategies/',
        'src/strategies/signal_processor.py',
        'src/risk/',
        'src/risk/manager.py',
        'src/execution/',
        'src/execution/engine.py',
        'src/utils/',
        'src/utils/logger.py',
        'tests/',
        'tests/conftest.py',
        'tests/test_config.py',
        'tests/test_signal_processor.py',
        'tests/test_risk_manager.py',
        'tests/test_data_collector.py',
        'tests/test_execution_engine.py',
        'tests/test_integration.py',
        'pytest.ini',
        '.env.example',
        '.env.test',
    ]
    
    missing_paths = []
    
    for path in required_paths:
        if Path(path).exists():
            print(f"✅ {path}")
        else:
            print(f"❌ {path}")
            missing_paths.append(path)
    
    if missing_paths:
        print(f"\nMissing paths: {', '.join(missing_paths)}")
        return False
    
    return True


def check_test_imports():
    """Check if test modules can import source modules."""
    print("\nChecking test imports...")
    
    test_imports = [
        ('src.config', 'Config module'),
        ('src.strategies.signal_processor', 'Signal processor'),
        ('src.risk.manager', 'Risk manager'),
        ('src.data.collector', 'Data collector'),
        ('src.execution.engine', 'Execution engine'),
        ('src.utils.logger', 'Logger'),
    ]
    
    import_errors = []
    
    for module_name, description in test_imports:
        try:
            importlib.import_module(module_name)
            print(f"✅ {description}")
        except ImportError as e:
            print(f"❌ {description}: {e}")
            import_errors.append((module_name, str(e)))
    
    if import_errors:
        print("\nImport errors found. Please check module structure.")
        return False
    
    return True


def validate_pytest_config():
    """Validate pytest configuration."""
    print("\nValidating pytest configuration...")
    
    try:
        with open('pytest.ini', 'r') as f:
            content = f.read()
            
        required_config = [
            'testpaths = tests',
            'python_files = test_*.py',
            'asyncio-mode=auto'
        ]
        
        for config in required_config:
            if config in content:
                print(f"✅ {config}")
            else:
                print(f"❌ {config}")
                return False
        
        return True
        
    except FileNotFoundError:
        print("❌ pytest.ini not found")
        return False


def main():
    """Main validation function."""
    print("🔍 Validating test setup for cryptocurrency trading bot\n")
    
    checks = [
        ("Module imports", check_imports),
        ("Project structure", check_project_structure),
        ("Test imports", check_test_imports),
        ("Pytest configuration", validate_pytest_config),
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        print(f"\n{'='*50}")
        print(f"Checking: {check_name}")
        print(f"{'='*50}")
        
        if not check_func():
            all_passed = False
    
    print(f"\n{'='*50}")
    if all_passed:
        print("✅ All validation checks passed!")
        print("You can now run tests with: python run_tests.py")
        print("Or run pytest directly: pytest tests/")
    else:
        print("❌ Some validation checks failed!")
        print("Please fix the issues above before running tests.")
    print(f"{'='*50}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())