#!/usr/bin/env python3
"""
Comprehensive test runner for core/ingestion/** modules.

This script runs all test suites for the ingestion pipeline and provides
detailed reporting on test coverage, performance, and results.
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pytest


class TestRunner:
    """Comprehensive test runner for ingestion modules."""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.results: Dict[str, Dict] = {}
        
    def discover_test_files(self) -> List[Path]:
        """Discover all test files in the ingestion test directory."""
        test_files = []
        
        # Core test files
        test_patterns = [
            "test_graph.py",
            "test_graph_simple.py", 
            "test_router.py",
            "test_loader.py",
            "test_cpu_parser.py",
            "test_gpu_parser.py",
            "test_chunker.py",
            "test_embedder.py",
            "test_indexer.py",
            "test_error_handler.py",
            "test_finalizer.py",
        ]
        
        for pattern in test_patterns:
            test_file = self.test_dir / pattern
            if test_file.exists():
                test_files.append(test_file)
            else:
                print(f"Warning: Test file {pattern} not found")
        
        return test_files
    
    def run_test_file(self, test_file: Path) -> Dict:
        """Run a single test file and collect results."""
        print(f"\n{'='*60}")
        print(f"Running tests: {test_file.name}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        # Run pytest with detailed output
        args = [
            str(test_file),
            "-v",                    # Verbose output
            "--tb=short",           # Short traceback format
            "--durations=10",       # Show 10 slowest tests
            "--strict-markers",     # Strict marker checking
            "-x",                   # Stop on first failure (optional)
        ]
        
        # Capture results
        result_code = pytest.main(args)
        
        duration = time.time() - start_time
        
        return {
            "file": test_file.name,
            "result_code": result_code,
            "duration": duration,
            "status": "PASSED" if result_code == 0 else "FAILED",
        }
    
    def run_all_tests(self) -> Dict:
        """Run all discovered test files."""
        test_files = self.discover_test_files()
        
        print(f"Discovered {len(test_files)} test files")
        print(f"Test directory: {self.test_dir}")
        
        overall_start = time.time()
        total_passed = 0
        total_failed = 0
        
        for test_file in test_files:
            try:
                result = self.run_test_file(test_file)
                self.results[test_file.name] = result
                
                if result["status"] == "PASSED":
                    total_passed += 1
                else:
                    total_failed += 1
                    
            except Exception as e:
                print(f"Error running {test_file.name}: {e}")
                self.results[test_file.name] = {
                    "file": test_file.name,
                    "result_code": -1,
                    "duration": 0,
                    "status": "ERROR",
                    "error": str(e),
                }
                total_failed += 1
        
        overall_duration = time.time() - overall_start
        
        return {
            "total_files": len(test_files),
            "passed": total_passed,
            "failed": total_failed,
            "duration": overall_duration,
            "results": self.results,
        }
    
    def print_summary(self, summary: Dict):
        """Print test execution summary."""
        print(f"\n{'='*80}")
        print("TEST EXECUTION SUMMARY")
        print(f"{'='*80}")
        
        print(f"Total test files: {summary['total_files']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Total duration: {summary['duration']:.2f}s")
        
        print(f"\n{'File':<30} {'Status':<10} {'Duration':<10}")
        print("-" * 50)
        
        for file_name, result in summary["results"].items():
            status = result["status"]
            duration = f"{result['duration']:.2f}s"
            print(f"{file_name:<30} {status:<10} {duration:<10}")
        
        # Show failed tests
        failed_tests = [r for r in summary["results"].values() if r["status"] != "PASSED"]
        if failed_tests:
            print(f"\n{'='*40}")
            print("FAILED TESTS")
            print(f"{'='*40}")
            for test in failed_tests:
                print(f"❌ {test['file']}")
                if "error" in test:
                    print(f"   Error: {test['error']}")
        
        # Success rate
        if summary['total_files'] > 0:
            success_rate = (summary['passed'] / summary['total_files']) * 100
            print(f"\nSuccess rate: {success_rate:.1f}%")
        
        return summary['failed'] == 0


def run_specific_tests(test_names: List[str]):
    """Run specific test files by name."""
    runner = TestRunner()
    test_dir = runner.test_dir
    
    for test_name in test_names:
        if not test_name.startswith("test_"):
            test_name = f"test_{test_name}"
        if not test_name.endswith(".py"):
            test_name = f"{test_name}.py"
        
        test_file = test_dir / test_name
        if test_file.exists():
            result = runner.run_test_file(test_file)
            print(f"\nResult for {test_name}: {result['status']}")
        else:
            print(f"Test file not found: {test_name}")


def run_priority_tests():
    """Run only P0 and P1 priority tests."""
    print("Running P0 and P1 priority tests...")
    
    # Use pytest markers to run only high priority tests
    args = [
        str(Path(__file__).parent),
        "-v",
        "-m", "not P2",  # Exclude P2 tests
        "--tb=short",
    ]
    
    result_code = pytest.main(args)
    return result_code == 0


def run_performance_tests():
    """Run performance-focused tests."""
    print("Running performance tests...")
    
    args = [
        str(Path(__file__).parent),
        "-v",
        "-k", "performance or concurrency or batch",
        "--tb=short",
        "--durations=0",  # Show all test durations
    ]
    
    result_code = pytest.main(args)
    return result_code == 0


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "all":
            # Run all tests
            runner = TestRunner()
            summary = runner.run_all_tests()
            success = runner.print_summary(summary)
            sys.exit(0 if success else 1)
            
        elif command == "priority":
            # Run P0/P1 tests only
            success = run_priority_tests()
            sys.exit(0 if success else 1)
            
        elif command == "performance":
            # Run performance tests
            success = run_performance_tests()
            sys.exit(0 if success else 1)
            
        elif command == "specific":
            # Run specific tests
            if len(sys.argv) > 2:
                test_names = sys.argv[2:]
                run_specific_tests(test_names)
            else:
                print("Usage: python run_comprehensive_tests.py specific <test_name1> <test_name2> ...")
            
        else:
            print(f"Unknown command: {command}")
            print("Available commands: all, priority, performance, specific")
            sys.exit(1)
    else:
        # Default: run all tests
        runner = TestRunner()
        summary = runner.run_all_tests()
        success = runner.print_summary(summary)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()