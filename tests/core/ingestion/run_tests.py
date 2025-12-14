#!/usr/bin/env python3
"""
测试运行脚本 - 摄取图管道测试套件

使用方法:
    python run_tests.py [选项]

选项:
    --all       运行所有测试（包括可能卡住的测试）
    --safe      只运行安全的测试（默认）
    --router    只运行路由测试
    --graph     只运行图测试
    --verbose   详细输出
    --coverage  生成覆盖率报告
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """运行命令并处理结果"""
    print(f"\n{'='*60}")
    if description:
        print(f"运行: {description}")
    print(f"命令: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.stdout:
            print("输出:")
            print(result.stdout)
        
        if result.stderr:
            print("错误:")
            print(result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {description or '命令'} 成功完成")
        else:
            print(f"❌ {description or '命令'} 失败 (退出码: {result.returncode})")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"⏰ {description or '命令'} 超时 (5分钟)")
        return False
    except Exception as e:
        print(f"💥 {description or '命令'} 异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="摄取图管道测试运行器")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    parser.add_argument("--safe", action="store_true", default=True, help="只运行安全测试")
    parser.add_argument("--router", action="store_true", help="只运行路由测试")
    parser.add_argument("--graph", action="store_true", help="只运行图测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--coverage", action="store_true", help="生成覆盖率报告")
    
    args = parser.parse_args()
    
    # 确定测试目录
    test_dir = Path(__file__).parent
    
    # 构建基础命令
    base_cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        base_cmd.append("-v")
    
    if args.coverage:
        base_cmd.extend(["--cov=core.ingestion", "--cov-report=html", "--cov-report=term"])
    
    success_count = 0
    total_count = 0
    
    # 根据参数选择测试
    if args.router:
        total_count += 1
        cmd = base_cmd + [str(test_dir / "test_router.py")]
        if run_command(cmd, "路由测试"):
            success_count += 1
    
    elif args.graph:
        total_count += 1
        cmd = base_cmd + [str(test_dir / "test_graph_simple.py")]
        if run_command(cmd, "图管道测试（简化版）"):
            success_count += 1
    
    elif args.all:
        # 运行所有测试，包括可能有问题的
        tests = [
            ("test_router.py", "路由测试"),
            ("test_graph_simple.py", "图管道测试（简化版）"),
            ("test_graph.py", "图管道测试（完整版）- 可能卡住"),
        ]
        
        for test_file, description in tests:
            total_count += 1
            cmd = base_cmd + [str(test_dir / test_file)]
            if run_command(cmd, description):
                success_count += 1
    
    else:  # 默认安全模式
        tests = [
            ("test_router.py", "路由测试"),
            ("test_graph_simple.py", "图管道测试（简化版）"),
        ]
        
        for test_file, description in tests:
            total_count += 1
            cmd = base_cmd + [str(test_dir / test_file)]
            if run_command(cmd, description):
                success_count += 1
    
    # 如果没有指定特定测试，运行组合测试
    if not any([args.router, args.graph, args.all]):
        total_count += 1
        cmd = base_cmd + [
            str(test_dir / "test_router.py"),
            str(test_dir / "test_graph_simple.py")
        ]
        if run_command(cmd, "组合测试（路由 + 图管道简化版）"):
            success_count += 1
    
    # 输出总结
    print(f"\n{'='*60}")
    print("测试总结")
    print('='*60)
    print(f"总测试套件: {total_count}")
    print(f"成功: {success_count}")
    print(f"失败: {total_count - success_count}")
    
    if success_count == total_count:
        print("🎉 所有测试都成功通过！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查上面的输出")
        return 1


if __name__ == "__main__":
    sys.exit(main())