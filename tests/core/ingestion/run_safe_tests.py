#!/usr/bin/env python3
"""
Safe test runner that avoids heavy imports that might cause blocking.

This runner uses subprocess to isolate test execution and prevent
mutex blocking issues.
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple

class SafeTestRunner:
    """Safe test runner with timeout and isolation."""
    
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.test_dir = Path(__file__).parent
        
    def run_single_test_safe(self, test_file: str) -> Tuple[bool, str, float]:
        """Run a single test file safely with timeout."""
        print(f"\n🧪 Running: {test_file}")
        
        start_time = time.time()
        
        try:
            # Use subprocess to isolate the test execution
            cmd = [
                sys.executable, "-m", "pytest", 
                str(self.test_dir / test_file),
                "-v", "--tb=short", "-x"  # Stop on first failure
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.test_dir.parent.parent.parent  # Project root
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                print(f"✅ {test_file}: PASSED ({duration:.2f}s)")
                return True, result.stdout, duration
            else:
                print(f"❌ {test_file}: FAILED ({duration:.2f}s)")
                print("STDOUT:", result.stdout[-500:] if result.stdout else "None")
                print("STDERR:", result.stderr[-500:] if result.stderr else "None")
                return False, result.stderr, duration
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"⏰ {test_file}: TIMEOUT after {duration:.2f}s")
            return False, f"Test timed out after {self.timeout}s", duration
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"💥 {test_file}: ERROR - {e}")
            return False, str(e), duration
    
    def run_priority_tests(self) -> Dict:
        """Run high priority tests first."""
        # Start with the simplest tests that are most likely to work
        priority_tests = [
            "test_graph_simple.py",  # Simplest graph test
            "test_error_handler.py", # Pure logic, no heavy deps
            "test_finalizer.py",     # Mostly file operations
        ]
        
        results = {}
        total_passed = 0
        total_failed = 0
        
        print("🎯 Running Priority Tests (P0/P1)")
        print("=" * 50)
        
        for test_file in priority_tests:
            if (self.test_dir / test_file).exists():
                success, output, duration = self.run_single_test_safe(test_file)
                results[test_file] = {
                    "success": success,
                    "output": output,
                    "duration": duration
                }
                
                if success:
                    total_passed += 1
                else:
                    total_failed += 1
            else:
                print(f"⚠️  {test_file}: FILE NOT FOUND")
                results[test_file] = {
                    "success": False,
                    "output": "File not found",
                    "duration": 0
                }
                total_failed += 1
        
        print(f"\n📊 Priority Test Results: {total_passed} passed, {total_failed} failed")
        return results
    
    def run_core_functionality_tests(self) -> Dict:
        """Run core functionality tests."""
        core_tests = [
            "test_router.py",
            "test_chunker.py", 
            "test_embedder.py",
            "test_indexer.py",
        ]
        
        results = {}
        total_passed = 0
        total_failed = 0
        
        print("\n🔧 Running Core Functionality Tests")
        print("=" * 50)
        
        for test_file in core_tests:
            if (self.test_dir / test_file).exists():
                success, output, duration = self.run_single_test_safe(test_file)
                results[test_file] = {
                    "success": success,
                    "output": output,
                    "duration": duration
                }
                
                if success:
                    total_passed += 1
                else:
                    total_failed += 1
                    # If a core test fails, we might want to continue or stop
                    print(f"⚠️  Core test {test_file} failed, continuing...")
            else:
                print(f"⚠️  {test_file}: FILE NOT FOUND")
                results[test_file] = {
                    "success": False,
                    "output": "File not found", 
                    "duration": 0
                }
                total_failed += 1
        
        print(f"\n📊 Core Test Results: {total_passed} passed, {total_failed} failed")
        return results
    
    def run_integration_tests(self) -> Dict:
        """Run integration tests that might have heavier dependencies."""
        integration_tests = [
            "test_loader.py",
            "test_cpu_parser.py",
            "test_gpu_parser.py",
            "test_graph.py",
        ]
        
        results = {}
        total_passed = 0
        total_failed = 0
        
        print("\n🔗 Running Integration Tests")
        print("=" * 50)
        
        for test_file in integration_tests:
            if (self.test_dir / test_file).exists():
                success, output, duration = self.run_single_test_safe(test_file)
                results[test_file] = {
                    "success": success,
                    "output": output,
                    "duration": duration
                }
                
                if success:
                    total_passed += 1
                else:
                    total_failed += 1
            else:
                print(f"⚠️  {test_file}: FILE NOT FOUND")
                results[test_file] = {
                    "success": False,
                    "output": "File not found",
                    "duration": 0
                }
                total_failed += 1
        
        print(f"\n📊 Integration Test Results: {total_passed} passed, {total_failed} failed")
        return results
    
    def print_final_summary(self, all_results: Dict):
        """Print final test summary."""
        print("\n" + "=" * 80)
        print("🏁 FINAL TEST SUMMARY")
        print("=" * 80)
        
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_duration = 0
        
        for category, results in all_results.items():
            print(f"\n📂 {category.upper()}:")
            for test_file, result in results.items():
                status = "✅ PASS" if result["success"] else "❌ FAIL"
                duration = result["duration"]
                print(f"  {test_file:<30} {status} ({duration:.2f}s)")
                
                total_tests += 1
                total_duration += duration
                if result["success"]:
                    total_passed += 1
                else:
                    total_failed += 1
        
        print(f"\n📈 OVERALL RESULTS:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {total_passed}")
        print(f"  Failed: {total_failed}")
        print(f"  Success Rate: {(total_passed/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
        print(f"  Total Duration: {total_duration:.2f}s")
        
        return total_failed == 0

def main():
    """Main entry point."""
    runner = SafeTestRunner(timeout=120)  # 2 minute timeout per test
    
    print("🚀 Starting Safe Test Execution")
    print("This runner uses subprocess isolation to prevent blocking issues.")
    
    all_results = {}
    
    # Run tests in order of increasing complexity/dependency
    all_results["priority"] = runner.run_priority_tests()
    all_results["core"] = runner.run_core_functionality_tests()
    all_results["integration"] = runner.run_integration_tests()
    
    # Print final summary
    success = runner.print_final_summary(all_results)
    
    if success:
        print("\n🎉 All tests passed! System is stable.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())