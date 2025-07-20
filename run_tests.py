#!/usr/bin/env python3
"""
Test runner script for the cryptocurrency trading bot.
Provides different test execution modes and reporting.
"""

import subprocess
import sys
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle output."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {description} failed!")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Run trading bot tests")
    parser.add_argument(
        '--mode', 
        choices=['unit', 'integration', 'all', 'fast', 'coverage'],
        default='all',
        help='Test mode to run'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--module', '-m',
        help='Run tests for specific module (e.g., config, signal_processor)'
    )
    parser.add_argument(
        '--coverage-report',
        action='store_true',
        help='Generate HTML coverage report'
    )
    
    args = parser.parse_args()
    
    # Ensure we're in the right directory
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    success = True
    
    if args.mode == 'unit':
        # Run only unit tests (exclude integration and slow tests)
        cmd = [
            'python', '-m', 'pytest', 
            'tests/', 
            '-m', 'not integration and not slow',
            '--tb=short'
        ]
        if args.verbose:
            cmd.append('-v')
        
        success = run_command(cmd, "Unit Tests")
    
    elif args.mode == 'integration':
        # Run only integration tests
        cmd = [
            'python', '-m', 'pytest', 
            'tests/', 
            '-m', 'integration',
            '--tb=short'
        ]
        if args.verbose:
            cmd.append('-v')
        
        success = run_command(cmd, "Integration Tests")
    
    elif args.mode == 'fast':
        # Run all tests except slow ones
        cmd = [
            'python', '-m', 'pytest', 
            'tests/', 
            '-m', 'not slow',
            '--tb=short'
        ]
        if args.verbose:
            cmd.append('-v')
        
        success = run_command(cmd, "Fast Tests")
    
    elif args.mode == 'coverage':
        # Run tests with coverage
        cmd = [
            'python', '-m', 'pytest', 
            'tests/', 
            '--cov=src',
            '--cov-report=term-missing',
            '--tb=short'
        ]
        if args.coverage_report:
            cmd.extend(['--cov-report=html'])
        if args.verbose:
            cmd.append('-v')
        
        success = run_command(cmd, "Coverage Tests")
        
        if args.coverage_report:
            print("\nHTML coverage report generated in htmlcov/")
    
    elif args.mode == 'all':
        # Run all tests
        cmd = [
            'python', '-m', 'pytest', 
            'tests/', 
            '--tb=short'
        ]
        if args.verbose:
            cmd.append('-v')
        
        success = run_command(cmd, "All Tests")
    
    # Run specific module tests
    if args.module:
        cmd = [
            'python', '-m', 'pytest', 
            f'tests/test_{args.module}.py',
            '--tb=short'
        ]
        if args.verbose:
            cmd.append('-v')
        
        success = run_command(cmd, f"Tests for {args.module}")
    
    # Code quality checks
    if args.mode in ['all', 'coverage']:
        print(f"\n{'='*60}")
        print("Running code quality checks...")
        print(f"{'='*60}")
        
        # Check if flake8 is available
        try:
            result = subprocess.run(['flake8', '--version'], capture_output=True)
            if result.returncode == 0:
                flake8_cmd = ['flake8', 'src/', 'tests/', '--max-line-length=100', '--ignore=E203,W503']
                run_command(flake8_cmd, "Code Style Check (flake8)")
        except FileNotFoundError:
            print("flake8 not found, skipping code style check")
        
        # Check if mypy is available
        try:
            result = subprocess.run(['mypy', '--version'], capture_output=True)
            if result.returncode == 0:
                mypy_cmd = ['mypy', 'src/', '--ignore-missing-imports']
                run_command(mypy_cmd, "Type Check (mypy)")
        except FileNotFoundError:
            print("mypy not found, skipping type check")
    
    if success:
        print(f"\n{'='*60}")
        print("✅ All tests passed successfully!")
        print(f"{'='*60}")
        sys.exit(0)
    else:
        print(f"\n{'='*60}")
        print("❌ Some tests failed!")
        print(f"{'='*60}")
        sys.exit(1)


if __name__ == "__main__":
    main()