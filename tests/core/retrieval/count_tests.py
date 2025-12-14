#!/usr/bin/env python3
"""
检索管道测试计数器

准确统计测试函数数量和相关指标。
"""

import re
from pathlib import Path
from typing import Dict, List

def count_tests_in_file(file_path: Path) -> Dict[str, int]:
    """统计单个文件中的测试"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 统计测试函数
        async_test_pattern = r'async def test_\w+'
        sync_test_pattern = r'def test_\w+'
        
        async_tests = len(re.findall(async_test_pattern, content))
        sync_tests = len(re.findall(sync_test_pattern, content))
        total_tests = async_tests + sync_tests
        
        # 统计其他指标
        mock_patterns = len(re.findall(r'@patch|with patch|Mock\(|AsyncMock\(', content))
        assertions = len(re.findall(r'assert ', content))
        
        # 统计优先级标记
        p0_count = len(re.findall(r'TC-[A-Z]+001|P0|验证.*拒绝|验证.*崩溃|验证.*安全|验证.*越权', content))
        p1_count = len(re.findall(r'TC-[A-Z]+00[2-9]|P1|验证.*功能|验证.*正确|验证.*核心', content))
        p2_count = len(re.findall(r'TC-[A-Z]+0[1-9][0-9]|P2|验证.*性能|验证.*优化|验证.*增强', content))
        
        return {
            'total_tests': total_tests,
            'async_tests': async_tests,
            'sync_tests': sync_tests,
            'mock_patterns': mock_patterns,
            'assertions': assertions,
            'p0_count': p0_count,
            'p1_count': p1_count,
            'p2_count': p2_count
        }
        
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return {
            'total_tests': 0,
            'async_tests': 0,
            'sync_tests': 0,
            'mock_patterns': 0,
            'assertions': 0,
            'p0_count': 0,
            'p1_count': 0,
            'p2_count': 0
        }

def main():
    """主函数"""
    test_dir = Path(__file__).parent
    test_files = [
        "test_graph.py",
        "test_preprocessor.py", 
        "test_retriever.py",
        "test_reranker.py",
        "test_generator.py",
        "test_semantic_cache.py"
    ]
    
    print("📊 检索管道测试统计报告")
    print("=" * 80)
    
    total_stats = {
        'total_tests': 0,
        'async_tests': 0,
        'sync_tests': 0,
        'mock_patterns': 0,
        'assertions': 0,
        'p0_count': 0,
        'p1_count': 0,
        'p2_count': 0
    }
    
    print(f"\n{'文件':<30} {'总测试':<8} {'异步':<6} {'同步':<6} {'Mock':<6} {'断言':<6} {'P0/P1/P2':<12}")
    print("-" * 80)
    
    for test_file in test_files:
        file_path = test_dir / test_file
        if file_path.exists():
            stats = count_tests_in_file(file_path)
            
            priority_str = f"{stats['p0_count']}/{stats['p1_count']}/{stats['p2_count']}"
            
            print(f"{test_file:<30} {stats['total_tests']:<8} {stats['async_tests']:<6} "
                  f"{stats['sync_tests']:<6} {stats['mock_patterns']:<6} "
                  f"{stats['assertions']:<6} {priority_str:<12}")
            
            # 累加到总计
            for key in total_stats:
                total_stats[key] += stats[key]
        else:
            print(f"{test_file:<30} {'不存在':<8}")
    
    print("-" * 80)
    priority_total = f"{total_stats['p0_count']}/{total_stats['p1_count']}/{total_stats['p2_count']}"
    print(f"{'总计':<30} {total_stats['total_tests']:<8} {total_stats['async_tests']:<6} "
          f"{total_stats['sync_tests']:<6} {total_stats['mock_patterns']:<6} "
          f"{total_stats['assertions']:<6} {priority_total:<12}")
    
    print(f"\n📈 统计摘要:")
    print(f"  总测试函数: {total_stats['total_tests']} 个")
    print(f"  异步测试: {total_stats['async_tests']} 个 ({total_stats['async_tests']/total_stats['total_tests']*100:.1f}%)")
    print(f"  同步测试: {total_stats['sync_tests']} 个 ({total_stats['sync_tests']/total_stats['total_tests']*100:.1f}%)")
    print(f"  Mock 模式: {total_stats['mock_patterns']} 个")
    print(f"  断言语句: {total_stats['assertions']} 个")
    print(f"  优先级分布: P0={total_stats['p0_count']}, P1={total_stats['p1_count']}, P2={total_stats['p2_count']}")
    
    # 质量评估
    avg_tests_per_file = total_stats['total_tests'] / len(test_files)
    avg_assertions_per_test = total_stats['assertions'] / total_stats['total_tests'] if total_stats['total_tests'] > 0 else 0
    
    print(f"\n🎯 质量指标:")
    print(f"  平均测试数/文件: {avg_tests_per_file:.1f}")
    print(f"  平均断言数/测试: {avg_assertions_per_test:.1f}")
    
    if total_stats['total_tests'] >= 80 and avg_assertions_per_test >= 2:
        print("  🟢 测试覆盖: 优秀")
    elif total_stats['total_tests'] >= 60 and avg_assertions_per_test >= 1.5:
        print("  🟡 测试覆盖: 良好")
    else:
        print("  🟠 测试覆盖: 需要改进")

if __name__ == "__main__":
    main()