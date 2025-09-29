#!/usr/bin/env python3
"""
Script for judging test results from all test data folders.

This script:
1. Processes all test suites in the test_data directory
2. Judges all failed test cases using the TestCaseJudge
3. Creates a comprehensive report with test case judgments
4. Saves the report to the analysis directory

Environment Variables Required:
- JUDGE_AZURE_OPENAI_API_KEY
- JUDGE_AZURE_OPENAI_ENDPOINT  
- JUDGE_AZURE_OPENAI_API_VERSION
- JUDGE_AZURE_OPENAI_DEPLOYMENT_NAME

Usage:
    python scripts/judge_results.py [test_suite_name]

Arguments:
    test_suite_name - Optional: Process only the specified test suite.
                     If not provided, all test suites will be processed.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import shutil

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.test_case_judge.test_case_judge import TestCaseJudge
from config import Paths, PROJECT_ROOT

# Create dedicated analysis folder structure
ANALYSIS_ROOT = PROJECT_ROOT / "analysis"
ANALYSIS_ROOT.mkdir(exist_ok=True)

def create_analysis_folder(label: str = "judgments") -> Path:
    """
    Create a dedicated analysis folder for this run
    
    Args:
        label: Label for the analysis folder
        
    Returns:
        Path to analysis folder
    """
    # Create unique folder name with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    folder_name = f"{label}_{timestamp}"
    
    # Create folder structure
    analysis_folder = ANALYSIS_ROOT / folder_name
    analysis_folder.mkdir(exist_ok=True)
    
    # Create subfolders
    (analysis_folder / "results").mkdir(exist_ok=True)
    (analysis_folder / "visualizations").mkdir(exist_ok=True)
    
    return analysis_folder

def judge_test_suite(judge: TestCaseJudge, test_suite_name: str) -> List[Dict[str, Any]]:
    """
    Judge all failed test cases in a test suite
    
    Args:
        judge: TestCaseJudge instance
        test_suite_name: Name of the test suite
        
    Returns:
        List of judgment results
    """
    print(f"\n🔍 Processing test suite: {test_suite_name}")
    
    # Get test suite path
    test_data_dir = Paths.get_test_data_str()
    test_suite_path = os.path.join(test_data_dir, test_suite_name)
    
    if not os.path.exists(test_suite_path):
        print(f"❌ Test suite directory not found: {test_suite_path}")
        return []
    
    # Judge test cases from the suite
    results = judge.judge_test_cases_from_files(test_suite_name)
    
    # Print summary
    if results:
        print(f"✅ Judged {len(results)} failed test cases in '{test_suite_name}'")
        for result in results:
            print(f"   - {result.get('test_case_name', 'Unknown')}: {result.get('classification')} "
                  f"({result.get('confidence')})")
    else:
        print(f"ℹ️  No failed test cases found in '{test_suite_name}'")
        
    return results

def judge_all_test_suites() -> Dict[str, List[Dict[str, Any]]]:
    """
    Judge all test suites in the test_data directory
    
    Returns:
        Dictionary with test suite names as keys and lists of judgment results as values
    """
    print("🏛️  Initializing TestCaseJudge...")
    judge = TestCaseJudge()
    
    # Test connection
    if not judge.is_running():
        print("❌ Judge LLM connection failed")
        return {}
        
    # Get test data directory
    test_data_dir = Paths.get_test_data_str()
    
    if not os.path.exists(test_data_dir):
        print(f"❌ Test data directory not found: {test_data_dir}")
        return {}
        
    # Get all test suite directories
    test_suites = [d for d in os.listdir(test_data_dir) 
                   if os.path.isdir(os.path.join(test_data_dir, d))]
    
    if not test_suites:
        print("ℹ️  No test suites found")
        return {}
        
    print(f"📁 Found {len(test_suites)} test suites: {test_suites}")
    
    # Process each test suite
    all_results = {}
    for test_suite in test_suites:
        results = judge_test_suite(judge, test_suite)
        if results:
            all_results[test_suite] = results
            
    return all_results

def generate_visualizations(df: pd.DataFrame, analysis_folder: Path) -> None:
    """
    Generate visualizations from the consolidated data
    
    Args:
        df: DataFrame with judgment data
        analysis_folder: Path to analysis folder
    """
    viz_dir = analysis_folder / "visualizations"
    
    try:
        # 1. Classification Distribution by Test Suite
        plt.figure(figsize=(12, 8))
        if len(df['test_suite'].unique()) > 1:
            # Multiple test suites
            classification_by_suite = df.groupby(['test_suite', 'classification']).size().unstack(fill_value=0)
            classification_by_suite.plot(kind='bar', stacked=True, ax=plt.gca())
            
            plt.title('Test Case Classification by Test Suite', fontsize=16)
            plt.xlabel('Test Suite', fontsize=14)
            plt.ylabel('Number of Test Cases', fontsize=14)
        else:
            # Single test suite
            counts = df['classification'].value_counts()
            plt.bar(counts.index, counts.values)
            
            plt.title(f'Classification Distribution for {df["test_suite"].iloc[0]}', fontsize=16)
            plt.xlabel('Classification', fontsize=14)
            plt.ylabel('Count', fontsize=14)
        
        plt.tight_layout()
        plt.savefig(viz_dir / "classification_by_suite.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Confidence Level Distribution
        if 'confidence' in df.columns:
            plt.figure(figsize=(10, 6))
            
            # Try to extract confidence or use as is
            confidence_counts = df['confidence'].value_counts()
            confidence_counts.plot(kind='bar')
            
            plt.title('Confidence Level Distribution', fontsize=16)
            plt.xlabel('Confidence Level', fontsize=14)
            plt.ylabel('Count', fontsize=14)
            plt.grid(True, linestyle='--', alpha=0.7)
            
            plt.tight_layout()
            plt.savefig(viz_dir / "confidence_distribution.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            # 3. Confidence by Classification
            plt.figure(figsize=(12, 8))
            confidence_by_class = pd.crosstab(df['confidence'], df['classification'])
            confidence_by_class.plot(kind='bar', stacked=False)
            
            plt.title('Confidence Level by Classification', fontsize=16)
            plt.xlabel('Confidence Level', fontsize=14)
            plt.ylabel('Count', fontsize=14)
            plt.legend(title='Classification')
            
            plt.tight_layout()
            plt.savefig(viz_dir / "confidence_by_classification.png", dpi=300, bbox_inches='tight')
            plt.close()
    except Exception as e:
        print(f"❌ Error generating matplotlib visualizations: {e}")
        import traceback
        traceback.print_exc()
    
    # Create an index.html file that displays all visualizations
    html_path = viz_dir / "index.html"
    with open(html_path, 'w') as f:
        f.write(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Judgments Analysis</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
                h1, h2 {{ color: #333; }}
                .viz-container {{ display: flex; flex-wrap: wrap; justify-content: space-around; }}
                .viz-item {{ margin: 20px; text-align: center; }}
                img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 5px; box-shadow: 0 0 5px rgba(0,0,0,0.1); }}
                .nav {{ margin-bottom: 20px; }}
                .nav a {{ margin-right: 15px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Test Case Judgments Analysis</h1>
                <div class="nav">
                    <a href="../results/test_judgments_report.xlsx">Detailed Results (Excel)</a>
                    <a href="../results/test_judgments_report.csv">Detailed Results (CSV)</a>
                    <a href="../results/test_judgments_report.json">Raw Judgment Data</a>
                </div>
                
                <h2>Visualizations</h2>
                <div class="viz-container">
                    <div class="viz-item">
                        <h3>Classification by Test Suite</h3>
                        <img src="classification_by_suite.png" alt="Classification by Test Suite">
                    </div>
                    <div class="viz-item">
                        <h3>Confidence Level Distribution</h3>
                        <img src="confidence_distribution.png" alt="Confidence Distribution">
                    </div>
                    <div class="viz-item">
                        <h3>Confidence by Classification</h3>
                        <img src="confidence_by_classification.png" alt="Confidence by Classification">
                    </div>
                </div>
            </div>
        </body>
        </html>
        """)

def save_results_report(all_results: Dict[str, List[Dict[str, Any]]], analysis_folder: Path) -> str:
    """
    Save judgment results to a comprehensive report
    
    Args:
        all_results: Dictionary with test suite names as keys and lists of judgment results as values
        analysis_folder: Path to analysis folder
        
    Returns:
        Path to saved report
    """
    if not all_results:
        print("ℹ️  No results to save")
        return ""
        
    # Create consolidated data structure
    consolidated_data = []
    for test_suite, results in all_results.items():
        for result in results:
            consolidated_data.append({
                "test_suite": test_suite,
                "test_case_name": result.get("test_case_name", "Unknown"),
                "classification": result.get("classification", "Unknown"),
                "confidence": result.get("confidence", 0),
                "reasoning": result.get("reasoning", ""),
                "recommendation": result.get("recommendation", "")
            })
    
    # Convert to DataFrame
    df = pd.DataFrame(consolidated_data)
    
    # Save to JSON
    results_dir = analysis_folder / "results"
    json_path = results_dir / "test_judgments_report.json"
    with open(json_path, 'w') as f:
        json.dump(consolidated_data, f, indent=2)
    
    # Save to CSV
    csv_path = results_dir / "test_judgments_report.csv"
    df.to_csv(csv_path, index=False)
    
    # Also save as Excel for better formatting
    excel_path = results_dir / "test_judgments_report.xlsx"
    writer = pd.ExcelWriter(excel_path, engine='openpyxl')
    
    # Write data
    df.to_excel(writer, sheet_name='Test Judgments', index=False)
    
    # Format the Excel file
    workbook = writer.book
    worksheet = writer.sheets['Test Judgments']
    
    # Auto-fit columns
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = min(len(str(cell.value)), 100)  # Cap at 100 characters
            except:
                pass
        adjusted_width = (max_length + 2)
        worksheet.column_dimensions[column_letter].width = adjusted_width
    
    # Save Excel
    writer.close()
    
    print(f"\n✅ Saved judgment report to:")
    print(f"   JSON: {json_path}")
    print(f"   CSV:  {csv_path}")
    print(f"   Excel: {excel_path}")
    
    # Generate visualizations from the DataFrame
    try:
        generate_visualizations(df, analysis_folder)
        print(f"✅ Generated visualizations in: {analysis_folder / 'visualizations'}")
        print(f"   Dashboard: {analysis_folder / 'visualizations' / 'index.html'}")
    except Exception as e:
        print(f"❌ Error generating visualizations: {e}")
        import traceback
        traceback.print_exc()
    
    return excel_path

def main():
    """Main function."""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Judge test results")
    parser.add_argument("test_suite", nargs="?", help="Optional: Name of specific test suite to process")
    args = parser.parse_args()
    
    print("🏛️  Test Case Judge - Processing All Test Data")
    print("=" * 60)
    
    # Create analysis folder
    analysis_folder = create_analysis_folder()
    print(f"📁 Analysis folder: {analysis_folder}")
    
    try:
        # Process specific test suite if provided
        if args.test_suite:
            print(f"📁 Processing only test suite: {args.test_suite}")
            judge = TestCaseJudge()
            
            # Test connection
            if not judge.is_running():
                print("❌ Judge LLM connection failed")
                return
                
            results = judge_test_suite(judge, args.test_suite)
            all_results = {args.test_suite: results} if results else {}
        else:
            # Process all test suites
            all_results = judge_all_test_suites()
        
        # Count total judgments
        total_judgments = sum(len(results) for results in all_results.values())
        
        if total_judgments > 0:
            print(f"\n📊 Total judgments: {total_judgments} across {len(all_results)} test suites")
            
            # Save results report
            report_path = save_results_report(all_results, analysis_folder)
            
            print("\n🎉 Judgment process completed successfully!")
            print(f"📊 Total test suites processed: {len(all_results)}")
            print(f"📊 Total test cases judged: {total_judgments}")
            
            # Add link to Excel analysis tool
            print("\n💡 To perform further analysis, run:")
            print(f"   python scripts/excel_to_judge.py {report_path}")
        else:
            print("\nℹ️  No failed test cases found that require judgment")
            print("\n💡 To create template for evaluation:")
            judge = TestCaseJudge()
            template_path = judge.create_evaluation_csv_template()
            
            # Copy template to analysis folder
            if template_path and os.path.exists(template_path):
                template_copy = analysis_folder / "results" / "evaluation_template.csv"
                shutil.copy2(template_path, template_copy)
                print(f"📝 Template copied to: {template_copy}")
        
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\n💡 Make sure you have set the judge-specific environment variables:")
        print("   - JUDGE_AZURE_OPENAI_API_KEY")
        print("   - JUDGE_AZURE_OPENAI_ENDPOINT")
        print("   - JUDGE_AZURE_OPENAI_API_VERSION")
        print("   - JUDGE_AZURE_OPENAI_DEPLOYMENT_NAME")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
