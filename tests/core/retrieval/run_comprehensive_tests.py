#!/usr/bin/env python3
"""
检索管道综合测试运行器

提供多种测试运行模式：
- 全部测试
- 优先级测试 (P0/P1)
- 特定模块测试
- 性能测试
"""

import sys
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any
import argparse

class RetrievalTestRunner:
    """检索管道测试运行器"""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.test_files = [
            "test_graph.py",
            "test_preprocessor.py", 
            "test_retriever.py",
            "test_reranker.py",
            "test_generator.py",
            "test_semantic_cache.py"
        ]
        
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("🚀 运行检索管道全部测试")
        print("=" * 60)
        
        results = {}
        total_start = time.time()
        
        for test_file in self.test_files:
            print(f"\n📋 运行 {test_file}")
            print("-" * 40)
            
            start_time = time.time()
            result = self._run_single_test(test_file)
            duration = time.time() - start_time
            
            results[test_file] = {
                **result,
                "duration": duration
            }
            
            status = "✅ 通过" if result["success"] else "❌ 失败"
            print(f"{status} - {duration:.2f}秒")
        
        total_duration = time.time() - total_start
        
        # 生成总结报告
        self._print_summary(results, total_duration)
        
        return results
    
    def run_priority_tests(self, priorities: List[str] = None) -> Dict[str, Any]:
        """运行优先级测试"""
        if priorities is None:
            priorities = ["P0", "P1"]
        
        print(f"🎯 运行优先级测试: {', '.join(priorities)}")
        print("=" * 60)
        
        results = {}
        
        for test_file in self.test_files:
            print(f"\n📋 运行 {test_file} 优先级测试")
            
            # 使用 pytest 标记过滤
            priority_markers = " or ".join([f"TC_{p}" for p in priorities])
            
            start_time = time.time()
            result = self._run_single_test(test_file, extra_args=["-k", priority_markers])
            duration = time.time() - start_time
            
            results[test_file] = {
                **result,
                "duration": duration
            }
            
            status = "✅ 通过" if result["success"] else "❌ 失败"
            print(f"{status} - {duration:.2f}秒")
        
        return results
    
    def run_specific_tests(self, modules: List[str]) -> Dict[str, Any]:
        """运行特定模块测试"""
        print(f"🔍 运行特定模块测试: {', '.join(modules)}")
        print("=" * 60)
        
        module_map = {
            "graph": "test_graph.py",
            "preprocessor": "test_preprocessor.py",
            "retriever": "test_retriever.py", 
            "reranker": "test_reranker.py",
            "generator": "test_generator.py",
            "semantic_cache": "test_semantic_cache.py"
        }
        
        results = {}
        
        for module in modules:
            if module not in module_map:
                print(f"⚠️  未知模块: {module}")
                continue
                
            test_file = module_map[module]
            print(f"\n📋 运行 {test_file}")
            
            start_time = time.time()
            result = self._run_single_test(test_file)
            duration = time.time() - start_time
            
            results[test_file] = {
                **result,
                "duration": duration
            }
            
            status = "✅ 通过" if result["success"] else "❌ 失败"
            print(f"{status} - {duration:.2f}秒")
        
        return results
    
    def run_performance_tests(self) -> Dict[str, Any]:
        """运行性能测试"""
        print("⚡ 运行性能测试")
        print("=" * 60)
        
        results = {}
        
        # 性能测试配置
        perf_config = [
            "--benchmark-only",
            "--benchmark-sort=mean",
            "--benchmark-columns=min,max,mean,stddev"
        ]
        
        for test_file in self.test_files:
            print(f"\n📊 性能测试 {test_file}")
            
            start_time = time.time()
            result = self._run_single_test(test_file, extra_args=perf_config)
            duration = time.time() - start_time
            
            results[test_file] = {
                **result,
                "duration": duration
            }
        
        return results
    
    def _run_single_test(self, test_file: str, extra_args: List[str] = None) -> Dict[str, Any]:
        """运行单个测试文件"""
        test_path = self.test_dir / test_file
        
        if not test_path.exists():
            return {
                "success": False,
                "error": f"测试文件不存在: {test_file}",
                "output": "",
                "tests_run": 0,
                "failures": 0
            }
        
        # 构建 pytest 命令
        cmd = ["python", "-m", "pytest", str(test_path), "-v", "--tb=short"]
        
        if extra_args:
            cmd.extend(extra_args)
        
        try:
            # 运行测试
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                cwd=self.test_dir.parent.parent.parent  # 项目根目录
            )
            
            # 解析输出
            output = result.stdout + result.stderr
            success = result.returncode == 0
            
            # 提取测试统计
            tests_run, failures = self._parse_test_stats(output)
            
            return {
                "success": success,
                "output": output,
                "tests_run": tests_run,
                "failures": failures,
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "测试超时",
                "output": "",
                "tests_run": 0,
                "failures": 0
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "tests_run": 0,
                "failures": 0
            }
    
    def _parse_test_stats(self, output: str) -> tuple[int, int]:
        """解析测试统计信息"""
        import re
        
        # 查找 pytest 结果行
        # 例如: "= 25 passed, 2 failed in 10.5s ="
        pattern = r"= (\d+) passed(?:, (\d+) failed)?.*in [\d.]+s ="
        match = re.search(pattern, output)
        
        if match:
            passed = int(match.group(1))
            failed = int(match.group(2)) if match.group(2) else 0
            return passed + failed, failed
        
        # 备用解析
        if "passed" in output:
            return 1, 0
        elif "failed" in output:
            return 1, 1
        
        return 0, 0
    
    def _print_summary(self, results: Dict[str, Any], total_duration: float):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("📊 测试总结报告")
        print("=" * 60)
        
        total_tests = 0
        total_failures = 0
        successful_files = 0
        
        print(f"\n{'文件':<25} {'状态':<8} {'测试数':<8} {'失败数':<8} {'耗时':<8}")
        print("-" * 60)
        
        for test_file, result in results.items():
            status = "✅ 通过" if result["success"] else "❌ 失败"
            tests = result.get("tests_run", 0)
            failures = result.get("failures", 0)
            duration = result.get("duration", 0)
            
            print(f"{test_file:<25} {status:<8} {tests:<8} {failures:<8} {duration:.2f}s")
            
            total_tests += tests
            total_failures += failures
            if result["success"]:
                successful_files += 1
        
        print("-" * 60)
        print(f"{'总计':<25} {successful_files}/{len(results):<8} {total_tests:<8} {total_failures:<8} {total_duration:.2f}s")
        
        # 成功率计算
        success_rate = (total_tests - total_failures) / total_tests * 100 if total_tests > 0 else 0
        file_success_rate = successful_files / len(results) * 100 if results else 0
        
        print(f"\n📈 统计信息:")
        print(f"  测试成功率: {success_rate:.1f}% ({total_tests - total_failures}/{total_tests})")
        print(f"  文件成功率: {file_success_rate:.1f}% ({successful_files}/{len(results)})")
        print(f"  总耗时: {total_duration:.2f}秒")
        
        # 质量评估
        if success_rate >= 95 and file_success_rate >= 90:
            print("  🟢 质量评级: 优秀")
        elif success_rate >= 85 and file_success_rate >= 80:
            print("  🟡 质量评级: 良好")
        elif success_rate >= 70 and file_success_rate >= 60:
            print("  🟠 质量评级: 一般")
        else:
            print("  🔴 质量评级: 需要改进")
        
        # 失败详情
        if total_failures > 0:
            print(f"\n❌ 失败详情:")
            for test_file, result in results.items():
                if not result["success"]:
                    error = result.get("error", "未知错误")
                    print(f"  {test_file}: {error}")


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(description="检索管道测试运行器")
    parser.add_argument(
        "mode",
        choices=["all", "priority", "specific", "performance"],
        help="测试运行模式"
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="特定模式的目标 (specific模式: 模块名; priority模式: P0,P1,P2)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出"
    )
    
    args = parser.parse_args()
    
    runner = RetrievalTestRunner()
    
    try:
        if args.mode == "all":
            results = runner.run_all_tests()
        elif args.mode == "priority":
            priorities = args.targets if args.targets else ["P0", "P1"]
            results = runner.run_priority_tests(priorities)
        elif args.mode == "specific":
            if not args.targets:
                print("❌ specific 模式需要指定模块名")
                print("可用模块: graph, preprocessor, retriever, reranker, generator, semantic_cache")
                return 1
            results = runner.run_specific_tests(args.targets)
        elif args.mode == "performance":
            results = runner.run_performance_tests()
        
        # 检查整体成功状态
        overall_success = all(result["success"] for result in results.values())
        
        if args.verbose:
            print("\n🔍 详细输出:")
            for test_file, result in results.items():
                if result.get("output"):
                    print(f"\n--- {test_file} ---")
                    print(result["output"])
        
        return 0 if overall_success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        return 130
    except Exception as e:
        print(f"\n❌ 运行测试时发生错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())