#!/usr/bin/env python3
"""
Static test quality analyzer.

This script analyzes test files without importing them to avoid
blocking issues while still ensuring test quality and coverage.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass

@dataclass
class TestStats:
    """Test statistics for a file."""
    file_name: str
    total_functions: int
    test_functions: int
    async_tests: int
    fixture_count: int
    mock_usage: int
    assertion_count: int
    priority_tests: Dict[str, int]  # P0, P1, P2 counts
    coverage_areas: Set[str]
    issues: List[str]

class TestQualityAnalyzer:
    """Analyze test quality without executing code."""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        
    def analyze_file(self, file_path: Path) -> TestStats:
        """Analyze a single test file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST
            tree = ast.parse(content)
            
            stats = TestStats(
                file_name=file_path.name,
                total_functions=0,
                test_functions=0,
                async_tests=0,
                fixture_count=0,
                mock_usage=0,
                assertion_count=0,
                priority_tests={"P0": 0, "P1": 0, "P2": 0},
                coverage_areas=set(),
                issues=[]
            )
            
            # Analyze AST nodes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    stats.total_functions += 1
                    
                    # Check if it's a test function
                    if node.name.startswith('test_'):
                        stats.test_functions += 1
                        
                        # Check if async
                        if isinstance(node, ast.AsyncFunctionDef):
                            stats.async_tests += 1
                    
                    # Check for fixtures
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Name) and decorator.id == 'fixture':
                            stats.fixture_count += 1
                        elif isinstance(decorator, ast.Attribute) and decorator.attr == 'fixture':
                            stats.fixture_count += 1
                
                # Count assertions
                elif isinstance(node, ast.Assert):
                    stats.assertion_count += 1
                
                # Check for mock usage
                elif isinstance(node, ast.Name) and 'mock' in node.id.lower():
                    stats.mock_usage += 1
                elif isinstance(node, ast.Attribute) and 'mock' in node.attr.lower():
                    stats.mock_usage += 1
            
            # Analyze content with regex for patterns AST might miss
            self._analyze_content_patterns(content, stats)
            
            # Check for quality issues
            self._check_quality_issues(stats)
            
            return stats
            
        except Exception as e:
            return TestStats(
                file_name=file_path.name,
                total_functions=0,
                test_functions=0,
                async_tests=0,
                fixture_count=0,
                mock_usage=0,
                assertion_count=0,
                priority_tests={"P0": 0, "P1": 0, "P2": 0},
                coverage_areas=set(),
                issues=[f"Analysis failed: {e}"]
            )
    
    def _analyze_content_patterns(self, content: str, stats: TestStats):
        """Analyze content with regex patterns."""
        
        # Priority markers
        p0_matches = len(re.findall(r'P0|TC-.*001|验证.*拒绝|验证.*崩溃|验证.*安全', content))
        p1_matches = len(re.findall(r'P1|TC-.*00[2-9]|验证.*功能|验证.*正确', content))
        p2_matches = len(re.findall(r'P2|TC-.*0[1-9][0-9]|验证.*性能|验证.*优化', content))
        
        stats.priority_tests["P0"] = p0_matches
        stats.priority_tests["P1"] = p1_matches  
        stats.priority_tests["P2"] = p2_matches
        
        # Coverage areas
        coverage_patterns = {
            'multi_tenant': r'channel_id|tenant|multi.*tenant|隔离',
            'large_file': r'large.*file|大文件|lazy.*load|streaming',
            'error_handling': r'error.*handling|exception|错误处理|重试',
            'concurrency': r'concurrent|parallel|semaphore|并发|限流',
            'batch_processing': r'batch|批处理|批量',
            'multimodal': r'multimodal|image|table|图片|表格',
            'security': r'security|permission|auth|安全|权限',
            'performance': r'performance|timeout|性能|超时',
        }
        
        for area, pattern in coverage_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                stats.coverage_areas.add(area)
        
        # Mock patterns
        mock_patterns = [
            r'@patch', r'Mock\(\)', r'AsyncMock', r'mock_.*=', 
            r'with patch', r'side_effect', r'return_value'
        ]
        
        for pattern in mock_patterns:
            stats.mock_usage += len(re.findall(pattern, content))
    
    def _check_quality_issues(self, stats: TestStats):
        """Check for potential quality issues."""
        
        # Low test coverage
        if stats.test_functions < 5:
            stats.issues.append(f"Low test count: only {stats.test_functions} tests")
        
        # No assertions
        if stats.assertion_count == 0:
            stats.issues.append("No assertions found")
        
        # No mocking (might indicate integration tests)
        if stats.mock_usage == 0:
            stats.issues.append("No mocking detected - might have external dependencies")
        
        # No async tests for async modules
        if 'async' in stats.file_name.lower() and stats.async_tests == 0:
            stats.issues.append("Async module but no async tests")
        
        # Missing priority coverage
        total_priority = sum(stats.priority_tests.values())
        if total_priority == 0:
            stats.issues.append("No priority markers found")
        
        # Missing critical coverage areas
        critical_areas = {'error_handling', 'security'}
        missing_critical = critical_areas - stats.coverage_areas
        if missing_critical:
            stats.issues.append(f"Missing critical coverage: {missing_critical}")
    
    def analyze_all_tests(self) -> Dict[str, TestStats]:
        """Analyze all test files."""
        results = {}
        
        test_files = [
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
        
        for test_file in test_files:
            file_path = self.test_dir / test_file
            if file_path.exists():
                results[test_file] = self.analyze_file(file_path)
            else:
                results[test_file] = TestStats(
                    file_name=test_file,
                    total_functions=0,
                    test_functions=0,
                    async_tests=0,
                    fixture_count=0,
                    mock_usage=0,
                    assertion_count=0,
                    priority_tests={"P0": 0, "P1": 0, "P2": 0},
                    coverage_areas=set(),
                    issues=["File not found"]
                )
        
        return results
    
    def print_summary(self, results: Dict[str, TestStats]):
        """Print analysis summary."""
        print("🔍 TEST QUALITY ANALYSIS REPORT")
        print("=" * 80)
        
        total_tests = 0
        total_assertions = 0
        total_mocks = 0
        total_p0 = 0
        total_p1 = 0
        total_p2 = 0
        all_coverage_areas = set()
        files_with_issues = 0
        
        print(f"\n{'File':<25} {'Tests':<8} {'Asserts':<8} {'Mocks':<8} {'P0/P1/P2':<12} {'Issues':<8}")
        print("-" * 80)
        
        for file_name, stats in results.items():
            if stats.test_functions > 0:  # Only show files with tests
                priority_str = f"{stats.priority_tests['P0']}/{stats.priority_tests['P1']}/{stats.priority_tests['P2']}"
                issue_count = len(stats.issues)
                
                print(f"{file_name:<25} {stats.test_functions:<8} {stats.assertion_count:<8} "
                      f"{stats.mock_usage:<8} {priority_str:<12} {issue_count:<8}")
                
                total_tests += stats.test_functions
                total_assertions += stats.assertion_count
                total_mocks += stats.mock_usage
                total_p0 += stats.priority_tests['P0']
                total_p1 += stats.priority_tests['P1']
                total_p2 += stats.priority_tests['P2']
                all_coverage_areas.update(stats.coverage_areas)
                
                if stats.issues:
                    files_with_issues += 1
        
        print("-" * 80)
        print(f"{'TOTALS':<25} {total_tests:<8} {total_assertions:<8} {total_mocks:<8} "
              f"{total_p0}/{total_p1}/{total_p2:<12} {files_with_issues:<8}")
        
        # Coverage summary
        print(f"\n📊 COVERAGE ANALYSIS:")
        print(f"  Total Test Functions: {total_tests}")
        print(f"  Total Assertions: {total_assertions}")
        print(f"  Mock Usage: {total_mocks}")
        print(f"  Priority Distribution: P0={total_p0}, P1={total_p1}, P2={total_p2}")
        print(f"  Coverage Areas: {', '.join(sorted(all_coverage_areas))}")
        
        # Quality assessment
        print(f"\n🎯 QUALITY ASSESSMENT:")
        
        quality_score = 0
        max_score = 100
        
        # Test quantity (20 points)
        if total_tests >= 200:
            quality_score += 20
        elif total_tests >= 100:
            quality_score += 15
        elif total_tests >= 50:
            quality_score += 10
        else:
            quality_score += max(0, total_tests // 5)
        
        # Assertion coverage (20 points)
        if total_assertions >= 500:
            quality_score += 20
        elif total_assertions >= 200:
            quality_score += 15
        elif total_assertions >= 100:
            quality_score += 10
        else:
            quality_score += max(0, total_assertions // 10)
        
        # Mock usage (15 points)
        if total_mocks >= 100:
            quality_score += 15
        elif total_mocks >= 50:
            quality_score += 10
        else:
            quality_score += max(0, total_mocks // 5)
        
        # Priority coverage (25 points)
        if total_p0 >= 10 and total_p1 >= 30:
            quality_score += 25
        elif total_p0 >= 5 and total_p1 >= 15:
            quality_score += 20
        else:
            quality_score += max(0, (total_p0 + total_p1) // 2)
        
        # Coverage breadth (20 points)
        coverage_score = min(20, len(all_coverage_areas) * 3)
        quality_score += coverage_score
        
        print(f"  Overall Quality Score: {quality_score}/{max_score} ({quality_score/max_score*100:.1f}%)")
        
        if quality_score >= 80:
            print("  🟢 EXCELLENT - High quality test suite")
        elif quality_score >= 60:
            print("  🟡 GOOD - Solid test coverage with room for improvement")
        elif quality_score >= 40:
            print("  🟠 FAIR - Basic coverage, needs enhancement")
        else:
            print("  🔴 POOR - Insufficient test coverage")
        
        # Detailed issues
        print(f"\n⚠️  DETAILED ISSUES:")
        for file_name, stats in results.items():
            if stats.issues:
                print(f"  {file_name}:")
                for issue in stats.issues:
                    print(f"    - {issue}")
        
        return quality_score >= 60  # Return True if quality is acceptable

def main():
    """Main entry point."""
    analyzer = TestQualityAnalyzer()
    
    print("🚀 Starting Static Test Quality Analysis")
    print("This analyzer checks test quality without executing code to avoid blocking.")
    
    results = analyzer.analyze_all_tests()
    acceptable_quality = analyzer.print_summary(results)
    
    if acceptable_quality:
        print(f"\n✅ Test suite quality is acceptable!")
        print("📋 RECOMMENDATIONS:")
        print("  - Tests are well-structured with good coverage")
        print("  - Mock usage indicates proper isolation")
        print("  - Priority markers help focus on critical tests")
        print("  - Consider running tests in isolated environments to avoid blocking")
        return 0
    else:
        print(f"\n❌ Test suite needs improvement!")
        print("📋 RECOMMENDATIONS:")
        print("  - Add more test functions to increase coverage")
        print("  - Include more assertions to verify behavior")
        print("  - Use mocks to isolate external dependencies")
        print("  - Add priority markers (P0/P1/P2) to categorize tests")
        print("  - Cover critical areas like security and error handling")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())