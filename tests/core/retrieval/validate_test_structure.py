#!/usr/bin/env python3
"""
检索管道测试结构验证器

验证测试文件的结构、Mock使用、断言覆盖等质量指标。
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Any
from dataclasses import dataclass

@dataclass
class TestValidationResult:
    """测试验证结果"""
    file_name: str
    is_valid: bool
    test_count: int
    mock_patterns: List[str]
    assertion_patterns: List[str]
    async_tests: int
    priority_markers: Dict[str, int]
    issues: List[str]
    recommendations: List[str]

class RetrievalTestValidator:
    """检索管道测试验证器"""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        
    def validate_all_tests(self) -> Dict[str, TestValidationResult]:
        """验证所有测试文件"""
        test_files = [
            "test_graph.py",
            "test_preprocessor.py", 
            "test_retriever.py",
            "test_reranker.py",
            "test_generator.py",
            "test_semantic_cache.py"
        ]
        
        results = {}
        
        for test_file in test_files:
            file_path = self.test_dir / test_file
            if file_path.exists():
                results[test_file] = self.validate_test_file(file_path)
            else:
                results[test_file] = TestValidationResult(
                    file_name=test_file,
                    is_valid=False,
                    test_count=0,
                    mock_patterns=[],
                    assertion_patterns=[],
                    async_tests=0,
                    priority_markers={},
                    issues=["文件不存在"],
                    recommendations=["创建测试文件"]
                )
        
        return results
    
    def validate_test_file(self, file_path: Path) -> TestValidationResult:
        """验证单个测试文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析AST
            tree = ast.parse(content)
            
            result = TestValidationResult(
                file_name=file_path.name,
                is_valid=True,
                test_count=0,
                mock_patterns=[],
                assertion_patterns=[],
                async_tests=0,
                priority_markers={},
                issues=[],
                recommendations=[]
            )
            
            # 分析测试函数
            self._analyze_test_functions(tree, content, result)
            
            # 分析Mock使用
            self._analyze_mock_usage(content, result)
            
            # 分析断言模式
            self._analyze_assertions(tree, content, result)
            
            # 分析优先级标记
            self._analyze_priority_markers(content, result)
            
            # 检查质量问题
            self._check_quality_issues(result)
            
            return result
            
        except Exception as e:
            return TestValidationResult(
                file_name=file_path.name,
                is_valid=False,
                test_count=0,
                mock_patterns=[],
                assertion_patterns=[],
                async_tests=0,
                priority_markers={},
                issues=[f"验证失败: {e}"],
                recommendations=["检查文件语法"]
            )
    
    def _analyze_test_functions(self, tree: ast.AST, content: str, result: TestValidationResult):
        """分析测试函数"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                result.test_count += 1
                
                # 检查异步测试
                if any('@pytest.mark.asyncio' in line for line in content.split('\n')
                       if f'def {node.name}' in line or f'async def {node.name}' in line):
                    result.async_tests += 1
    
    def _analyze_mock_usage(self, content: str, result: TestValidationResult):
        """分析Mock使用模式"""
        mock_patterns = [
            (r'@patch\(', 'decorator_patch'),
            (r'with patch\(', 'context_patch'),
            (r'patch\.dict\(', 'patch_dict'),
            (r'patch\.multiple\(', 'patch_multiple'),
            (r'Mock\(\)', 'mock_instance'),
            (r'AsyncMock\(\)', 'async_mock'),
            (r'side_effect\s*=', 'side_effect'),
            (r'return_value\s*=', 'return_value'),
            (r'mock_.*=', 'mock_assignment'),
            (r'\.assert_called', 'assert_called'),
        ]
        
        for pattern, name in mock_patterns:
            matches = re.findall(pattern, content)
            if matches:
                result.mock_patterns.append(f"{name}: {len(matches)}")
    
    def _analyze_assertions(self, tree: ast.AST, content: str, result: TestValidationResult):
        """分析断言模式"""
        # AST断言计数
        assert_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                assert_count += 1
        
        if assert_count > 0:
            result.assertion_patterns.append(f"ast_assertions: {assert_count}")
        
        # 特定断言模式
        assertion_patterns = [
            (r'assert.*==', 'equality_assertions'),
            (r'assert.*in', 'membership_assertions'),
            (r'assert.*is True', 'boolean_true'),
            (r'assert.*is False', 'boolean_false'),
            (r'assert.*is None', 'none_assertions'),
            (r'assert.*len\(', 'length_assertions'),
            (r'assert.*all\(', 'all_assertions'),
            (r'assert.*any\(', 'any_assertions'),
        ]
        
        for pattern, name in assertion_patterns:
            matches = re.findall(pattern, content)
            if matches:
                result.assertion_patterns.append(f"{name}: {len(matches)}")
    
    def _analyze_priority_markers(self, content: str, result: TestValidationResult):
        """分析优先级标记"""
        priority_patterns = {
            'P0': r'TC-[A-Z]+001|P0|验证.*拒绝|验证.*崩溃|验证.*安全|验证.*越权',
            'P1': r'TC-[A-Z]+00[2-9]|P1|验证.*功能|验证.*正确|验证.*核心',
            'P2': r'TC-[A-Z]+0[1-9][0-9]|P2|验证.*性能|验证.*优化|验证.*增强'
        }
        
        for priority, pattern in priority_patterns.items():
            matches = len(re.findall(pattern, content))
            if matches > 0:
                result.priority_markers[priority] = matches
    
    def _check_quality_issues(self, result: TestValidationResult):
        """检查质量问题"""
        # 测试数量检查
        if result.test_count == 0:
            result.issues.append("没有发现测试函数")
            result.is_valid = False
        elif result.test_count < 5:
            result.issues.append(f"测试数量较少: {result.test_count}")
            result.recommendations.append("增加更多测试用例")
        
        # Mock使用检查
        if not result.mock_patterns:
            result.issues.append("没有发现Mock使用")
            result.recommendations.append("添加Mock来隔离外部依赖")
        
        # 断言检查
        if not result.assertion_patterns:
            result.issues.append("没有发现断言语句")
            result.is_valid = False
            result.recommendations.append("添加断言来验证测试结果")
        
        # 异步测试检查
        if result.async_tests == 0 and 'async' in result.file_name.lower():
            result.issues.append("异步模块但没有异步测试")
            result.recommendations.append("添加@pytest.mark.asyncio异步测试")
        
        # 优先级标记检查
        if not result.priority_markers:
            result.issues.append("没有发现优先级标记")
            result.recommendations.append("添加P0/P1/P2优先级标记")
    
    def print_validation_report(self, results: Dict[str, TestValidationResult]):
        """打印验证报告"""
        print("🔍 检索管道测试结构验证报告")
        print("=" * 80)
        
        total_tests = 0
        valid_files = 0
        total_issues = 0
        
        print(f"\n{'文件':<30} {'状态':<8} {'测试数':<8} {'异步':<6} {'Mock':<6} {'断言':<6}")
        print("-" * 80)
        
        for file_name, result in results.items():
            status = "✅ 有效" if result.is_valid else "❌ 无效"
            mock_count = len(result.mock_patterns)
            assertion_count = len(result.assertion_patterns)
            
            print(f"{file_name:<30} {status:<8} {result.test_count:<8} "
                  f"{result.async_tests:<6} {mock_count:<6} {assertion_count:<6}")
            
            total_tests += result.test_count
            total_issues += len(result.issues)
            if result.is_valid:
                valid_files += 1
        
        print("-" * 80)
        print(f"{'总计':<30} {valid_files}/{len(results):<8} {total_tests:<8} "
              f"{'':6} {'':6} {'':6}")
        
        # 详细分析
        print(f"\n📊 详细分析:")
        
        for file_name, result in results.items():
            if result.issues or result.recommendations:
                print(f"\n📁 {file_name}:")
                
                if result.mock_patterns:
                    print(f"  Mock模式: {', '.join(result.mock_patterns[:3])}...")
                
                if result.assertion_patterns:
                    print(f"  断言模式: {', '.join(result.assertion_patterns[:3])}...")
                
                if result.priority_markers:
                    markers = [f"{k}={v}" for k, v in result.priority_markers.items()]
                    print(f"  优先级: {', '.join(markers)}")
                
                if result.issues:
                    print(f"  ⚠️  问题: {'; '.join(result.issues)}")
                
                if result.recommendations:
                    print(f"  💡 建议: {'; '.join(result.recommendations)}")
        
        # 总体评估
        print(f"\n🎯 总体评估:")
        
        validity_rate = valid_files / len(results) * 100 if results else 0
        avg_tests_per_file = total_tests / len(results) if results else 0
        
        print(f"  文件有效率: {validity_rate:.1f}% ({valid_files}/{len(results)})")
        print(f"  平均测试数: {avg_tests_per_file:.1f} 个/文件")
        print(f"  总问题数: {total_issues}")
        
        if validity_rate >= 90 and avg_tests_per_file >= 10:
            print("  🟢 结构质量: 优秀")
        elif validity_rate >= 80 and avg_tests_per_file >= 8:
            print("  🟡 结构质量: 良好")
        elif validity_rate >= 60 and avg_tests_per_file >= 5:
            print("  🟠 结构质量: 一般")
        else:
            print("  🔴 结构质量: 需要改进")
        
        return validity_rate >= 80


def main():
    """主入口函数"""
    validator = RetrievalTestValidator()
    
    print("🚀 开始检索管道测试结构验证")
    
    results = validator.validate_all_tests()
    is_valid = validator.print_validation_report(results)
    
    if is_valid:
        print(f"\n✅ 检索管道测试结构验证通过！")
        return 0
    else:
        print(f"\n❌ 检索管道测试结构需要改进！")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())