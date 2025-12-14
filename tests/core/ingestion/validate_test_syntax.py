#!/usr/bin/env python3
"""
Test syntax validator.

Validates Python syntax and imports without executing code
to ensure tests are syntactically correct and importable.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple, Dict

class TestSyntaxValidator:
    """Validate test syntax without execution."""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        
    def validate_syntax(self, file_path: Path) -> Tuple[bool, List[str]]:
        """Validate Python syntax of a file."""
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST to check syntax
            ast.parse(content)
            return True, []
            
        except SyntaxError as e:
            errors.append(f"Syntax Error: {e.msg} at line {e.lineno}")
            return False, errors
        except Exception as e:
            errors.append(f"Parse Error: {e}")
            return False, errors
    
    def check_import_structure(self, file_path: Path) -> Tuple[bool, List[str]]:
        """Check import statements structure."""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
            
            # Check for common import issues
            if not any('pytest' in imp for imp in imports):
                issues.append("No pytest import found")
            
            if not any('mock' in imp.lower() for imp in imports):
                issues.append("No mock imports found - tests might not be isolated")
            
            # Check for relative imports that might cause issues
            problematic_imports = [imp for imp in imports if imp.startswith('core.') and 'test' not in file_path.name]
            if problematic_imports:
                issues.append(f"Potential import issues: {problematic_imports[:3]}")
            
            return len(issues) == 0, issues
            
        except Exception as e:
            return False, [f"Import analysis failed: {e}"]
    
    def validate_test_structure(self, file_path: Path) -> Tuple[bool, List[str]]:
        """Validate test function structure."""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            test_functions = []
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    test_functions.append(node.name)
                elif isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                    classes.append(node.name)
            
            if not test_functions and not classes:
                issues.append("No test functions or test classes found")
            
            # Check for async test patterns
            async_tests = [f for f in test_functions if 'async' in content]
            if async_tests and '@pytest.mark.asyncio' not in content:
                issues.append("Async tests found but no @pytest.mark.asyncio marker")
            
            return len(issues) == 0, issues
            
        except Exception as e:
            return False, [f"Structure analysis failed: {e}"]
    
    def validate_all_tests(self) -> Dict[str, Dict]:
        """Validate all test files."""
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
        
        results = {}
        
        for test_file in test_files:
            file_path = self.test_dir / test_file
            
            if not file_path.exists():
                results[test_file] = {
                    "exists": False,
                    "syntax_valid": False,
                    "imports_ok": False,
                    "structure_ok": False,
                    "issues": ["File not found"]
                }
                continue
            
            # Validate syntax
            syntax_valid, syntax_errors = self.validate_syntax(file_path)
            
            # Check imports
            imports_ok, import_issues = self.check_import_structure(file_path)
            
            # Check structure
            structure_ok, structure_issues = self.validate_test_structure(file_path)
            
            all_issues = syntax_errors + import_issues + structure_issues
            
            results[test_file] = {
                "exists": True,
                "syntax_valid": syntax_valid,
                "imports_ok": imports_ok,
                "structure_ok": structure_ok,
                "issues": all_issues
            }
        
        return results
    
    def print_validation_report(self, results: Dict[str, Dict]):
        """Print validation report."""
        print("🔍 TEST SYNTAX VALIDATION REPORT")
        print("=" * 80)
        
        total_files = len(results)
        valid_files = 0
        files_with_issues = 0
        
        print(f"\n{'File':<25} {'Exists':<8} {'Syntax':<8} {'Imports':<8} {'Structure':<10} {'Issues'}")
        print("-" * 80)
        
        for file_name, result in results.items():
            exists = "✅" if result["exists"] else "❌"
            syntax = "✅" if result["syntax_valid"] else "❌"
            imports = "✅" if result["imports_ok"] else "⚠️"
            structure = "✅" if result["structure_ok"] else "⚠️"
            issue_count = len(result["issues"])
            
            print(f"{file_name:<25} {exists:<8} {syntax:<8} {imports:<8} {structure:<10} {issue_count}")
            
            if result["exists"] and result["syntax_valid"] and result["imports_ok"] and result["structure_ok"]:
                valid_files += 1
            
            if result["issues"]:
                files_with_issues += 1
        
        print("-" * 80)
        print(f"Valid Files: {valid_files}/{total_files} ({valid_files/total_files*100:.1f}%)")
        
        # Detailed issues
        if files_with_issues > 0:
            print(f"\n⚠️  DETAILED ISSUES:")
            for file_name, result in results.items():
                if result["issues"]:
                    print(f"\n  📄 {file_name}:")
                    for issue in result["issues"]:
                        print(f"    - {issue}")
        
        # Summary
        print(f"\n📊 VALIDATION SUMMARY:")
        print(f"  Total Files: {total_files}")
        print(f"  Syntactically Valid: {sum(1 for r in results.values() if r['syntax_valid'])}")
        print(f"  Import Issues: {sum(1 for r in results.values() if not r['imports_ok'])}")
        print(f"  Structure Issues: {sum(1 for r in results.values() if not r['structure_ok'])}")
        
        if valid_files == total_files:
            print(f"\n✅ All test files are syntactically valid and well-structured!")
            return True
        else:
            print(f"\n⚠️  {total_files - valid_files} files have validation issues.")
            return False

def main():
    """Main entry point."""
    validator = TestSyntaxValidator()
    
    print("🚀 Starting Test Syntax Validation")
    print("This validator checks syntax and structure without executing code.")
    
    results = validator.validate_all_tests()
    all_valid = validator.print_validation_report(results)
    
    if all_valid:
        print(f"\n🎉 All tests pass syntax validation!")
        print("📋 NEXT STEPS:")
        print("  - Tests are syntactically correct")
        print("  - Import structure looks good")
        print("  - Test structure follows conventions")
        print("  - Ready for execution in isolated environment")
        return 0
    else:
        print(f"\n❌ Some tests have validation issues!")
        print("📋 RECOMMENDATIONS:")
        print("  - Fix syntax errors before running tests")
        print("  - Review import statements for potential blocking dependencies")
        print("  - Ensure test functions follow naming conventions")
        return 1

if __name__ == "__main__":
    sys.exit(main())