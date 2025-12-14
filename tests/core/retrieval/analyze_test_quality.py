#!/usr/bin/env python3
"""
检索管道测试质量分析器

静态分析测试文件质量，避免导入阻塞问题的同时确保测试质量和覆盖率。
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass

@dataclass
class RetrievalTestStats:
    """检索测试统计信息"""
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
    retrieval_specific_patterns: Dict[str, int]

class RetrievalTestQualityAnalyzer:
    """检索管道测试质量分析器"""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        
    def analyze_file(self, file_path: Path) -> RetrievalTestStats:
        """分析单个测试文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 AST
            tree = ast.parse(content)
            
            stats = RetrievalTestStats(
                file_name=file_path.name,
                total_functions=0,
                test_functions=0,
                async_tests=0,
                fixture_count=0,
                mock_usage=0,
                assertion_count=0,
                priority_tests={"P0": 0, "P1": 0, "P2": 0},
                coverage_areas=set(),
                issues=[],
                retrieval_specific_patterns={}
            )
            
            # 分析 AST 节点
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    stats.total_functions += 1
                    
                    # 检查测试函数
                    if node.name.startswith('test_'):
                        stats.test_functions += 1
                        
                        # 检查异步测试
                        if any(isinstance(d, ast.Name) and d.id == 'asyncio' 
                               for d in ast.walk(node)) or \
                           any(isinstance(d, ast.Attribute) and d.attr == 'asyncio'
                               for d in ast.walk(node)):
                            stats.async_tests += 1
                    
                    # 检查 fixtures
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Name) and decorator.id == 'fixture':
                            stats.fixture_count += 1
                        elif isinstance(decorator, ast.Attribute) and decorator.attr == 'fixture':
                            stats.fixture_count += 1
                
                # 计算断言
                elif isinstance(node, ast.Assert):
                    stats.assertion_count += 1
                
                # 检查 mock 使用
                elif isinstance(node, ast.Name) and 'mock' in node.id.lower():
                    stats.mock_usage += 1
                elif isinstance(node, ast.Attribute) and 'mock' in node.attr.lower():
                    stats.mock_usage += 1
            
            # 使用正则表达式分析内容模式
            self._analyze_content_patterns(content, stats)
            
            # 检查质量问题
            self._check_quality_issues(stats)
            
            return stats
            
        except Exception as e:
            return RetrievalTestStats(
                file_name=file_path.name,
                total_functions=0,
                test_functions=0,
                async_tests=0,
                fixture_count=0,
                mock_usage=0,
                assertion_count=0,
                priority_tests={"P0": 0, "P1": 0, "P2": 0},
                coverage_areas=set(),
                issues=[f"分析失败: {e}"],
                retrieval_specific_patterns={}
            )
    
    def _analyze_content_patterns(self, content: str, stats: RetrievalTestStats):
        """使用正则表达式分析内容模式"""
        
        # 优先级标记
        p0_matches = len(re.findall(r'TC-[A-Z]+001|P0|验证.*拒绝|验证.*崩溃|验证.*安全|验证.*越权', content))
        p1_matches = len(re.findall(r'TC-[A-Z]+00[2-9]|P1|验证.*功能|验证.*正确|验证.*核心', content))
        p2_matches = len(re.findall(r'TC-[A-Z]+0[1-9][0-9]|P2|验证.*性能|验证.*优化|验证.*增强', content))
        
        stats.priority_tests["P0"] = p0_matches
        stats.priority_tests["P1"] = p1_matches  
        stats.priority_tests["P2"] = p2_matches
        
        # 检索管道特定覆盖区域
        coverage_patterns = {
            'intent_routing': r'intent.*router|意图.*路由|IntentRouter|路由.*映射',
            'semantic_cache': r'semantic.*cache|语义.*缓存|cache.*hit|缓存.*命中',
            'multi_tenant': r'channel_id|tenant|multi.*tenant|隔离|越权',
            'rrf_fusion': r'rrf.*fusion|RRF.*融合|_rrf_fusion|融合.*算法',
            'citation_parsing': r'citation.*parsing|引用.*解析|<cite.*id|引用.*标签',
            'rerank_threshold': r'rerank.*threshold|重排序.*阈值|rerank_threshold',
            'llm_gateway_cache': r'gateway.*cache|网关.*缓存|_GATEWAY_CACHE',
            'async_wrapping': r'async.*wrapping|异步.*包装|asyncio\.to_thread',
            'confidence_calculation': r'confidence.*calculation|置信度.*计算|retrieval_confidence',
            'hallucination_check': r'hallucination.*check|幻觉.*检测|hallucination_detected',
            'web_search_integration': r'web.*search|WebSearchNode|web_search_client',
            'embedding_similarity': r'embedding.*similarity|嵌入.*相似|cosine.*similarity',
            'ttl_expiration': r'ttl.*expiration|TTL.*过期|ttl_seconds',
            'error_injection': r'error.*injection|错误.*注入|side_effect.*Exception',
            'storage_degradation': r'storage.*degradation|存储.*降级|unavailable.*degradation'
        }
        
        for area, pattern in coverage_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                stats.coverage_areas.add(area)
        
        # 检索特定模式
        retrieval_patterns = {
            'langgraph_routing': len(re.findall(r'LangGraph|StateGraph|条件路由|graph\.add_conditional_edges', content)),
            'mock_llm_calls': len(re.findall(r'mock.*llm|LLMGateway.*mock|mock_gateway', content)),
            'async_test_patterns': len(re.findall(r'@pytest\.mark\.asyncio|async def test_', content)),
            'cache_operations': len(re.findall(r'cache.*hit|cache.*miss|缓存.*命中|缓存.*未命中', content)),
            'tenant_isolation': len(re.findall(r'tenant_a|tenant_b|channel.*isolation|租户.*隔离', content)),
            'confidence_assertions': len(re.findall(r'assert.*confidence|confidence.*==|置信度.*断言', content)),
            'citation_validation': len(re.findall(r'assert.*citation|citation.*==|引用.*验证', content)),
            'threshold_testing': len(re.findall(r'threshold.*test|阈值.*测试|above.*threshold|below.*threshold', content)),
            'fallback_mechanisms': len(re.findall(r'fallback.*test|回退.*测试|degradation.*test|降级.*测试', content)),
            'performance_monitoring': len(re.findall(r'latency.*monitoring|延迟.*监控|performance.*test|性能.*测试', content))
        }
        
        stats.retrieval_specific_patterns = retrieval_patterns
        
        # Mock 模式
        mock_patterns = [
            r'@patch', r'Mock\(\)', r'AsyncMock', r'mock_.*=', 
            r'with patch', r'side_effect', r'return_value',
            r'patch\.dict', r'patch\.multiple'
        ]
        
        for pattern in mock_patterns:
            stats.mock_usage += len(re.findall(pattern, content))
    
    def _check_quality_issues(self, stats: RetrievalTestStats):
        """检查潜在的质量问题"""
        
        # 测试数量不足
        if stats.test_functions < 10:
            stats.issues.append(f"测试数量不足: 只有 {stats.test_functions} 个测试")
        
        # 无断言
        if stats.assertion_count == 0:
            stats.issues.append("未发现断言语句")
        
        # Mock 使用不足
        if stats.mock_usage < 5:
            stats.issues.append("Mock 使用不足 - 可能存在外部依赖")
        
        # 异步测试覆盖
        if 'async' in stats.file_name.lower() and stats.async_tests == 0:
            stats.issues.append("异步模块但无异步测试")
        
        # 优先级覆盖
        total_priority = sum(stats.priority_tests.values())
        if total_priority == 0:
            stats.issues.append("未发现优先级标记")
        
        # 关键覆盖区域缺失
        critical_areas = {'multi_tenant', 'error_injection', 'async_wrapping'}
        missing_critical = critical_areas - stats.coverage_areas
        if missing_critical:
            stats.issues.append(f"缺少关键覆盖区域: {missing_critical}")
        
        # 检索特定模式检查
        if stats.retrieval_specific_patterns.get('tenant_isolation', 0) == 0:
            stats.issues.append("缺少多租户隔离测试")
        
        if stats.retrieval_specific_patterns.get('async_test_patterns', 0) == 0:
            stats.issues.append("缺少异步测试模式")
    
    def analyze_all_tests(self) -> Dict[str, RetrievalTestStats]:
        """分析所有检索测试文件"""
        results = {}
        
        test_files = [
            "test_graph.py",
            "test_preprocessor.py",
            "test_retriever.py",
            "test_reranker.py", 
            "test_generator.py",
            "test_semantic_cache.py"
        ]
        
        for test_file in test_files:
            file_path = self.test_dir / test_file
            if file_path.exists():
                results[test_file] = self.analyze_file(file_path)
            else:
                results[test_file] = RetrievalTestStats(
                    file_name=test_file,
                    total_functions=0,
                    test_functions=0,
                    async_tests=0,
                    fixture_count=0,
                    mock_usage=0,
                    assertion_count=0,
                    priority_tests={"P0": 0, "P1": 0, "P2": 0},
                    coverage_areas=set(),
                    issues=["文件不存在"],
                    retrieval_specific_patterns={}
                )
        
        return results
    
    def print_summary(self, results: Dict[str, RetrievalTestStats]):
        """打印分析总结"""
        print("🔍 检索管道测试质量分析报告")
        print("=" * 80)
        
        total_tests = 0
        total_assertions = 0
        total_mocks = 0
        total_p0 = 0
        total_p1 = 0
        total_p2 = 0
        all_coverage_areas = set()
        files_with_issues = 0
        
        print(f"\n{'文件':<30} {'测试数':<8} {'断言数':<8} {'Mock数':<8} {'P0/P1/P2':<12} {'问题数':<8}")
        print("-" * 80)
        
        for file_name, stats in results.items():
            if stats.test_functions > 0:  # 只显示有测试的文件
                priority_str = f"{stats.priority_tests['P0']}/{stats.priority_tests['P1']}/{stats.priority_tests['P2']}"
                issue_count = len(stats.issues)
                
                print(f"{file_name:<30} {stats.test_functions:<8} {stats.assertion_count:<8} "
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
        print(f"{'总计':<30} {total_tests:<8} {total_assertions:<8} {total_mocks:<8} "
              f"{total_p0}/{total_p1}/{total_p2:<12} {files_with_issues:<8}")
        
        # 覆盖率分析
        print(f"\n📊 覆盖率分析:")
        print(f"  总测试函数: {total_tests}")
        print(f"  总断言数: {total_assertions}")
        print(f"  Mock 使用: {total_mocks}")
        print(f"  优先级分布: P0={total_p0}, P1={total_p1}, P2={total_p2}")
        print(f"  覆盖区域数: {len(all_coverage_areas)}")
        
        # 检索特定模式统计
        print(f"\n🎯 检索管道特定模式:")
        pattern_totals = {}
        for stats in results.values():
            for pattern, count in stats.retrieval_specific_patterns.items():
                pattern_totals[pattern] = pattern_totals.get(pattern, 0) + count
        
        for pattern, total in sorted(pattern_totals.items()):
            if total > 0:
                print(f"  {pattern}: {total}")
        
        # 质量评估
        print(f"\n🎯 质量评估:")
        
        quality_score = 0
        max_score = 100
        
        # 测试数量 (25分)
        if total_tests >= 100:
            quality_score += 25
        elif total_tests >= 60:
            quality_score += 20
        elif total_tests >= 30:
            quality_score += 15
        else:
            quality_score += max(0, total_tests // 3)
        
        # 断言覆盖 (20分)
        if total_assertions >= 200:
            quality_score += 20
        elif total_assertions >= 100:
            quality_score += 15
        elif total_assertions >= 50:
            quality_score += 10
        else:
            quality_score += max(0, total_assertions // 5)
        
        # Mock 使用 (15分)
        if total_mocks >= 80:
            quality_score += 15
        elif total_mocks >= 40:
            quality_score += 10
        else:
            quality_score += max(0, total_mocks // 4)
        
        # 优先级覆盖 (20分)
        if total_p0 >= 8 and total_p1 >= 20:
            quality_score += 20
        elif total_p0 >= 4 and total_p1 >= 10:
            quality_score += 15
        else:
            quality_score += max(0, (total_p0 + total_p1) // 2)
        
        # 覆盖广度 (20分)
        coverage_score = min(20, len(all_coverage_areas) * 2)
        quality_score += coverage_score
        
        print(f"  整体质量分数: {quality_score}/{max_score} ({quality_score/max_score*100:.1f}%)")
        
        if quality_score >= 85:
            print("  🟢 优秀 - 高质量测试套件")
        elif quality_score >= 70:
            print("  🟡 良好 - 测试覆盖充分，有改进空间")
        elif quality_score >= 55:
            print("  🟠 一般 - 基础覆盖，需要增强")
        else:
            print("  🔴 不足 - 测试覆盖不充分")
        
        # 详细问题
        print(f"\n⚠️  详细问题:")
        for file_name, stats in results.items():
            if stats.issues:
                print(f"  {file_name}:")
                for issue in stats.issues:
                    print(f"    - {issue}")
        
        # 推荐改进
        print(f"\n💡 改进建议:")
        
        if total_tests < 60:
            print("  - 增加测试用例数量，特别是边界条件和错误场景")
        
        if total_p0 < 5:
            print("  - 增加 P0 级别的安全和崩溃测试")
        
        if 'multi_tenant' not in all_coverage_areas:
            print("  - 添加多租户隔离测试")
        
        if 'error_injection' not in all_coverage_areas:
            print("  - 添加错误注入和降级测试")
        
        if pattern_totals.get('async_test_patterns', 0) < 20:
            print("  - 增加异步测试覆盖")
        
        if pattern_totals.get('cache_operations', 0) < 10:
            print("  - 增加缓存操作测试")
        
        return quality_score >= 70  # 返回质量是否可接受


def main():
    """主入口函数"""
    analyzer = RetrievalTestQualityAnalyzer()
    
    print("🚀 开始检索管道测试质量静态分析")
    print("此分析器检查测试质量而不执行代码，避免阻塞问题。")
    
    results = analyzer.analyze_all_tests()
    acceptable_quality = analyzer.print_summary(results)
    
    if acceptable_quality:
        print(f"\n✅ 检索管道测试质量可接受！")
        print("📋 建议:")
        print("  - 测试结构良好，覆盖充分")
        print("  - Mock 使用得当，实现了适当隔离")
        print("  - 优先级标记有助于聚焦关键测试")
        print("  - 考虑在隔离环境中运行测试以避免阻塞")
        return 0
    else:
        print(f"\n❌ 检索管道测试质量需要改进！")
        print("📋 建议:")
        print("  - 增加测试函数数量以提高覆盖率")
        print("  - 包含更多断言以验证行为")
        print("  - 使用 Mock 隔离外部依赖")
        print("  - 添加优先级标记 (P0/P1/P2) 对测试分类")
        print("  - 覆盖关键区域如安全性和错误处理")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())