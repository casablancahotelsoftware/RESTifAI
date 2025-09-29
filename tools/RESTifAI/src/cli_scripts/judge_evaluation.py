#!/usr/bin/env python3
"""
Test Case Judge Evaluation Tool

This script evaluates the performance of the TestCaseJudge against gold labels.

The script ONLY accepts an Excel file with the following REQUIRED columns:
- test_result: JSON string containing the test case data/results
- classification: Golden label classification ('TP' or 'FP')

Features:
1. Process Excel files with gold-labeled test cases
2. Run the TestCaseJudge on each entry and compare against gold labels
3. Calculate accuracy, precision, recall, F1 score and other metrics
4. Generate detailed reports and visualizations
5. Store everything in an organized analysis folder structure

Usage:
    python scripts/judge_evaluation.py path/to/excel_file.xlsx

Environment Variables Required:
- JUDGE_AZURE_OPENAI_API_KEY
- JUDGE_AZURE_OPENAI_ENDPOINT  
- JUDGE_AZURE_OPENAI_API_VERSION
- JUDGE_AZURE_OPENAI_DEPLOYMENT_NAME
"""

import os
import sys
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, List, Any, Tuple
import argparse
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


def create_analysis_folder(label: str = "evaluation") -> Tuple[Path, str]:
    """
    Create a dedicated analysis folder for this run
    
    Args:
        label: Base name for the analysis folder
        
    Returns:
        Tuple of (path to analysis folder, analysis_id)
    """
    # Create unique analysis ID based on timestamp and label
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    analysis_id = f"{label}_{timestamp}"
    
    # Create folder structure
    analysis_folder = ANALYSIS_ROOT / analysis_id
    analysis_folder.mkdir(exist_ok=True)
    
    # Create subfolders
    (analysis_folder / "csv").mkdir(exist_ok=True)
    (analysis_folder / "results").mkdir(exist_ok=True)
    (analysis_folder / "visualizations").mkdir(exist_ok=True)
    
    return analysis_folder, analysis_id


def convert_excel_to_csv(excel_path: str, analysis_folder: Path) -> str:
    """
    Convert Excel file to CSV and store in analysis folder
    
    Args:
        excel_path: Path to Excel file
        analysis_folder: Path to analysis folder
        
    Returns:
        Path to converted CSV file
    """
    # Read Excel file
    print(f"📊 Reading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)
    
    # Define CSV output path
    base_name = Path(excel_path).stem
    csv_dir = analysis_folder / "csv"
    csv_path = str(csv_dir / f"{base_name}.csv")
    
    # Save as CSV
    df.to_csv(csv_path, index=False)
    print(f"✅ Converted to CSV: {csv_path}")
    
    # Also copy the original Excel file to the analysis folder
    excel_copy = str(analysis_folder / Path(excel_path).name)
    shutil.copy2(excel_path, excel_copy)
    print(f"✅ Copied original Excel file to: {excel_copy}")
    
    return csv_path


def judge_csv_entries(csv_path: str, analysis_folder: Path) -> Dict[str, Any]:
    """
    Judge all entries in a CSV file
    
    Args:
        csv_path: Path to CSV file
        analysis_folder: Path to analysis folder
        
    Returns:
        Dictionary with judging results
    """
    print(f"🏛️ Initializing TestCaseJudge...")
    judge = TestCaseJudge()
    
    # Test connection
    if not judge.is_running():
        print("❌ Judge LLM connection failed")
        return {}
        
    print(f"🔍 Evaluating entries from CSV: {csv_path}")
    
    # Create results directory path using the analysis folder
    results_dir = analysis_folder / "results"
    
    # Perform evaluation
    try:
        results = judge.evaluate_from_csv(csv_path)
        print(f"✅ Evaluation complete. Accuracy: {results.get('metrics', {}).get('accuracy', 0):.2f}")
        
        # Save raw results to JSON in the analysis folder
        results_path = results_dir / "evaluation_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"✅ Saved raw evaluation results to: {results_path}")
        
        return results
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        return {}


def analyze_results(results: Dict[str, Any], analysis_folder: Path, analysis_id: str) -> None:
    """
    Analyze and visualize evaluation results
    
    Args:
        results: Dictionary with evaluation results
        analysis_folder: Path to analysis folder
        analysis_id: Unique identifier for this analysis run
    """
    if not results or 'metrics' not in results:
        print("❌ No results to analyze")
        return
        
    metrics = results.get('metrics', {})
    print("\n📊 Analysis Results:")
    print(f"   Accuracy:  {metrics.get('accuracy', 0):.4f}")
    print(f"   Precision: {metrics.get('precision', 0):.4f}")
    print(f"   Recall:    {metrics.get('recall', 0):.4f}")
    print(f"   F1 Score:  {metrics.get('f1_score', 0):.4f}")
    
    # Get detailed results
    detailed = results.get('detailed_results', [])
    if not detailed:
        return
        
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(detailed)
    
    # Save detailed results to CSV
    results_dir = analysis_folder / "results"
    details_csv = results_dir / "detailed_results.csv"
    df.to_csv(details_csv, index=False)
    
    # Also save as Excel for better formatting
    excel_path = results_dir / "detailed_results.xlsx"
    writer = pd.ExcelWriter(excel_path, engine='openpyxl')
    df.to_excel(writer, sheet_name='Detailed Results', index=False)
    
    # Format the Excel file
    workbook = writer.book
    worksheet = writer.sheets['Detailed Results']
    
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
    
    writer.close()
    
    print(f"✅ Saved detailed results to:")
    print(f"   CSV:  {details_csv}")
    print(f"   Excel: {excel_path}")
    
    # Generate summary report
    summary_path = results_dir / "summary_report.txt"
    with open(summary_path, 'w') as f:
        f.write(f"Analysis ID: {analysis_id}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("Summary Metrics:\n")
        f.write(f"  Total Entries: {len(detailed)}\n")
        f.write(f"  Accuracy:      {metrics.get('accuracy', 0):.4f}\n")
        f.write(f"  Precision:     {metrics.get('precision', 0):.4f}\n")
        f.write(f"  Recall:        {metrics.get('recall', 0):.4f}\n")
        f.write(f"  F1 Score:      {metrics.get('f1_score', 0):.4f}\n\n")
        
        # Add classification distribution
        if 'classification' in df.columns:
            f.write("Classification Distribution:\n")
            class_counts = df['classification'].value_counts()
            for cls, count in class_counts.items():
                f.write(f"  {cls}: {count} ({count/len(df)*100:.1f}%)\n")
    
    print(f"✅ Saved summary report: {summary_path}")
    
    # Generate visualizations
    try:
        generate_visualizations(df, analysis_folder, analysis_id)
    except Exception as e:
        print(f"❌ Error generating visualizations: {e}")
        import traceback
        traceback.print_exc()


def generate_visualizations(df: pd.DataFrame, analysis_folder: Path, analysis_id: str) -> None:
    """
    Generate visualizations from the detailed results
    
    Args:
        df: DataFrame with detailed results
        analysis_folder: Path to analysis folder
        analysis_id: Unique identifier for this analysis run
    """
    """
    Generate visualizations from the detailed results
    
    Args:
        df: DataFrame with detailed results
        analysis_folder: Path to analysis folder
        analysis_id: Unique identifier for this analysis run
    """
    # Create visualization directory
    viz_dir = analysis_folder / "visualizations"
    
    # Set plot style
    plt.style.use('ggplot')
    sns.set_theme(style="whitegrid")
    
    # Ensure consistent colors
    colors = {
        'TP': '#4CAF50',  # Green
        'FP': '#F44336',  # Red
        'TN': '#2196F3',  # Blue
        'FN': '#FF9800',  # Orange
        'correct': '#4CAF50',
        'incorrect': '#F44336'
    }
      # 1. Confusion Matrix Heatmap
    if 'gold_label' in df.columns and 'predicted_label' in df.columns:
        plt.figure(figsize=(10, 8))
        
        # Create a crosstab with fillna to ensure all combinations are present
        confusion = pd.crosstab(df['gold_label'], df['predicted_label'], 
                              rownames=['Actual'], colnames=['Predicted'])
        
        # Make sure both 'TP' and 'FP' are in the index and columns
        for label in ['TP', 'FP']:
            if label not in confusion.index:
                confusion.loc[label] = 0
            if label not in confusion.columns:
                confusion[label] = 0
                
        # Sort to ensure consistent ordering
        confusion = confusion.reindex(['TP', 'FP']).reindex(columns=['TP', 'FP'])
        
        # Create the heatmap
        ax = sns.heatmap(confusion, annot=True, fmt='d', cmap='Blues',
                    linewidths=.5, cbar=False)
        
        plt.title('Confusion Matrix', fontsize=16)
        plt.xlabel('Predicted Label', fontsize=14)
        plt.ylabel('Actual Label', fontsize=14)
        
        plt.tight_layout()
        plt.savefig(viz_dir / "confusion_matrix.png", dpi=300, bbox_inches='tight')
        plt.close()
      # 2. Classification Distribution
    if 'predicted_label' in df.columns:
        plt.figure(figsize=(10, 6))
        
        # Create a complete series with both TP and FP
        counts = df['predicted_label'].value_counts()
        complete_counts = pd.Series(0, index=['TP', 'FP'])
        for idx in counts.index:
            if idx in complete_counts.index:  # Only count valid labels
                complete_counts[idx] = counts[idx]
        
        # Create the bar chart
        bars = plt.bar(complete_counts.index, complete_counts.values, 
                     color=[colors.get('TP', '#4CAF50'), colors.get('FP', '#F44336')])
        
        plt.title('Predicted Classification Distribution', fontsize=16)
        plt.xlabel('Classification', fontsize=14)
        plt.ylabel('Count', fontsize=14)
        
        # Add count labels
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height}', ha='center', fontsize=12)
        
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.savefig(viz_dir / "classification_distribution.png", dpi=300, bbox_inches='tight')
        plt.close()
      # 3. Correct vs. Incorrect Predictions
    if 'correct' in df.columns:
        plt.figure(figsize=(8, 8))
        
        # Ensure we have both True and False values for correct/incorrect
        correct_counts = df['correct'].value_counts()
        
        # Create a complete series with both True and False, filling missing values with 0
        complete_counts = pd.Series([0, 0], index=[True, False])
        for idx in correct_counts.index:
            complete_counts[idx] = correct_counts[idx]
        
        # Now we always have 2 values (correct and incorrect)
        explode = (0.1, 0)  # Explode the first slice (correct)
        labels = ['Correct', 'Incorrect']
        
        plt.pie(complete_counts, explode=explode, labels=labels, 
                autopct='%1.1f%%', shadow=True, startangle=90,
                colors=[colors['correct'], colors['incorrect']])
        
        plt.axis('equal')
        plt.title('Prediction Accuracy', fontsize=16)
        plt.tight_layout()
        plt.savefig(viz_dir / "prediction_accuracy_pie.png", dpi=300, bbox_inches='tight')
        plt.close()
      # 4. Confidence Distribution by Correctness
    if 'confidence' in df.columns and 'correct' in df.columns:
        try:
            plt.figure(figsize=(12, 6))
            
            # Map confidence string values to numeric if needed
            if df['confidence'].dtype == 'object':
                # Try to map common confidence levels to numeric values
                confidence_map = {
                    'HIGH': 3,
                    'MEDIUM': 2, 
                    'LOW': 1,
                    'VERY HIGH': 4,
                    'VERY LOW': 0
                }
                
                # Check if we can convert confidence values
                if df['confidence'].isin(confidence_map.keys()).any():
                    # Create a safe copy to avoid modifying the original dataframe
                    plot_df = df.copy()
                    plot_df['confidence_numeric'] = plot_df['confidence'].map(confidence_map)
                    
                    # Handle any values that weren't in the map
                    unknown_values = plot_df[plot_df['confidence_numeric'].isna()]['confidence'].unique()
                    if len(unknown_values) > 0:
                        print(f"Warning: Unknown confidence values: {unknown_values}")
                    
                    # Fill NAs with a default value
                    plot_df['confidence_numeric'].fillna(-1, inplace=True)
                    
                    # Create a simpler visualization - just the counts of each confidence level
                    conf_counts = plot_df['confidence'].value_counts().sort_index()
                    
                    plt.bar(conf_counts.index, conf_counts.values, 
                           color=[colors.get(label, '#999999') for label in conf_counts.index])
                    
                    plt.title('Confidence Level Distribution', fontsize=16)
                    plt.xlabel('Confidence Level', fontsize=14)
                    plt.ylabel('Count', fontsize=14)
                    plt.grid(True, linestyle='--', alpha=0.7)
                    plt.tight_layout()
                    plt.savefig(viz_dir / "confidence_distribution.png", dpi=300, bbox_inches='tight')
                    
                    # If we have enough data, try to create the grouped bar chart
                    try:
                        # Group by confidence and correctness
                        grouped = plot_df.groupby(['confidence', 'correct']).size().unstack().fillna(0)
                        
                        # Create new figure for the grouped chart
                        plt.figure(figsize=(12, 6))
                        
                        # Sort by confidence level if possible
                        if grouped.index.isin(confidence_map.keys()).all():
                            conf_order = sorted(grouped.index, key=lambda x: confidence_map.get(x, -1))
                            grouped = grouped.reindex(conf_order)
                        
                        # Create grouped bar chart
                        if True in grouped.columns and False in grouped.columns:
                            grouped.plot(kind='bar', stacked=False, ax=plt.gca(),
                                      color=[colors['correct'], colors['incorrect']])
                            plt.title('Confidence Levels by Prediction Correctness', fontsize=16)
                            plt.xlabel('Confidence Level', fontsize=14)
                            plt.ylabel('Count', fontsize=14)
                            plt.legend(['Correct', 'Incorrect'])
                            plt.tight_layout()
                            plt.savefig(viz_dir / "confidence_by_correctness.png", dpi=300, bbox_inches='tight')
                    except Exception as e:
                        print(f"Notice: Could not create grouped confidence chart: {e}")
            
            plt.close()
        except Exception as e:
            print(f"Notice: Skipping confidence visualization: {e}")
            plt.close('all')
    
    # Create an index.html file that displays all visualizations
    html_path = viz_dir / "index.html"
    with open(html_path, 'w') as f:
        f.write(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Analysis Results: {analysis_id}</title>
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
                <h1>Analysis Results: {analysis_id}</h1>
                <div class="nav">
                    <a href="../results/summary_report.txt">Summary Report</a>
                    <a href="../results/detailed_results.xlsx">Detailed Results (Excel)</a>
                    <a href="../results/detailed_results.csv">Detailed Results (CSV)</a>
                    <a href="../results/evaluation_results.json">Raw Evaluation Data</a>
                </div>
                
                <h2>Visualizations</h2>
                <div class="viz-container">
                    <div class="viz-item">
                        <h3>Confusion Matrix</h3>
                        <img src="confusion_matrix.png" alt="Confusion Matrix">
                    </div>
                    <div class="viz-item">
                        <h3>Classification Distribution</h3>
                        <img src="classification_distribution.png" alt="Classification Distribution">
                    </div>
                    <div class="viz-item">
                        <h3>Prediction Accuracy</h3>
                        <img src="prediction_accuracy_pie.png" alt="Prediction Accuracy">
                    </div>
                    <div class="viz-item">
                        <h3>Confidence by Correctness</h3>
                        <img src="confidence_by_correctness.png" alt="Confidence by Correctness">
                    </div>
                </div>
            </div>
        </body>
        </html>
        """)
    
    print(f"✅ Generated visualizations dashboard: {html_path}")
    

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


def judge_all_test_suites(analysis_folder: Path) -> Dict[str, Any]:
    """
    Judge all test files in the test_data directory
    
    Args:
        analysis_folder: Path to analysis folder
        
    Returns:
        Dictionary with results for each test file
    """
    test_data_dir = Paths.get_test_data_str()
    
    if not os.path.exists(test_data_dir):
        print(f"❌ Test directory {test_data_dir} does not exist")
        return {}
        
    # Initialize TestCaseJudge
    print(f"🏛️ Initializing TestCaseJudge...")
    judge = TestCaseJudge()
    
    # Test connection
    if not judge.is_running():
        print("❌ Judge LLM connection failed")
        return {}
    
    # Get all test suite directories
    test_suites = [d for d in os.listdir(test_data_dir) 
                  if os.path.isdir(os.path.join(test_data_dir, d))]
    
    if not test_suites:
        print(f"❌ No test suites found in {test_data_dir}")
        return {}
    
    print(f"📁 Found {len(test_suites)} test suites: {', '.join(test_suites)}")
    
    # Process each test suite
    all_suite_results = {}
    for test_suite in test_suites:
        suite_results = judge_test_suite(judge, test_suite)
        if suite_results:
            all_suite_results[test_suite] = suite_results
    
    # Count total judgments
    total_judgments = sum(len(results) for results in all_suite_results.values())
    
    if total_judgments > 0:
        print(f"\n📊 Total judgments: {total_judgments} across {len(all_suite_results)} test suites")
        
        # Save all_suite_results to JSON
        results_dir = analysis_folder / "results"
        results_path = results_dir / "all_test_judgments.json"
        with open(results_path, 'w') as f:
            json.dump(all_suite_results, f, indent=2)
        
        # Convert to DataFrame for analysis
        consolidated_data = []
        for test_suite, suite_results in all_suite_results.items():
            for result in suite_results:
                consolidated_data.append({
                    "test_suite": test_suite,
                    "test_case_name": result.get("test_case_name", "Unknown"),
                    "classification": result.get("classification", "Unknown"),
                    "confidence": result.get("confidence", 0),
                    "reasoning": result.get("reasoning", ""),
                    "recommendation": result.get("recommendation", "")
                })
        
        # Save to CSV and Excel
        df = pd.DataFrame(consolidated_data)
        csv_path = results_dir / "all_test_judgments.csv"
        df.to_csv(csv_path, index=False)
        
        # Create Excel with formatting
        excel_path = results_dir / "all_test_judgments.xlsx"
        writer = pd.ExcelWriter(excel_path, engine='openpyxl')
        df.to_excel(writer, sheet_name='Test Judgments', index=False)
        
        # Format Excel
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
        
        writer.close()
        
        print(f"\n✅ Saved all test judgments to:")
        print(f"   JSON: {results_path}")
        print(f"   CSV:  {csv_path}")
        print(f"   Excel: {excel_path}")
        
        # Generate visualizations for test suite results
        try:
            generate_test_suite_visualizations(df, analysis_folder)
        except Exception as e:
            print(f"❌ Error generating test suite visualizations: {e}")
            import traceback
            traceback.print_exc()
        
        return df
    else:
        print("\nℹ️  No failed test cases found that require judgment")
        return None


def generate_test_suite_visualizations(df: pd.DataFrame, analysis_folder: Path) -> None:
    """
    Generate visualizations from test suite judgment data
    
    Args:
        df: DataFrame with test suite judgment data
        analysis_folder: Path to analysis folder
    """
    viz_dir = analysis_folder / "visualizations"
    
    # Set plot style
    plt.style.use('ggplot')
    sns.set_theme(style="whitegrid")
    
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
        
    # Update the index.html file to include the new visualizations
    html_path = viz_dir / "index.html"
    
    # If the HTML file exists, update it, otherwise create it
    if html_path.exists():
        with open(html_path, 'r') as f:
            html_content = f.read()
            
        if "Test Suite Analysis" not in html_content:
            # Add test suite visualizations to existing HTML
            insert_point = "</div>\n            </div>\n        </body>"
            new_content = """
                <h2>Test Suite Analysis</h2>
                <div class="viz-container">
                    <div class="viz-item">
                        <h3>Classification by Test Suite</h3>
                        <img src="classification_by_suite.png" alt="Classification by Test Suite">
                    </div>
                    <div class="viz-item">
                        <h3>Confidence Level Distribution</h3>
                        <img src="confidence_distribution.png" alt="Confidence Distribution">
                    </div>
                </div>
            </div>
        </body>"""
            
            html_content = html_content.replace(insert_point, new_content)
            
            with open(html_path, 'w') as f:
                f.write(html_content)
    else:
        # Create new HTML file
        with open(html_path, 'w') as f:
            f.write(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Test Suite Analysis</title>
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
                        <a href="../results/all_test_judgments.xlsx">Detailed Results (Excel)</a>
                        <a href="../results/all_test_judgments.csv">Detailed Results (CSV)</a>
                        <a href="../results/all_test_judgments.json">Raw Judgment Data</a>
                    </div>
                    
                    <h2>Test Suite Analysis</h2>
                    <div class="viz-container">
                        <div class="viz-item">
                            <h3>Classification by Test Suite</h3>
                            <img src="classification_by_suite.png" alt="Classification by Test Suite">
                        </div>
                        <div class="viz-item">
                            <h3>Confidence Level Distribution</h3>
                            <img src="confidence_distribution.png" alt="Confidence Distribution">
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """)


def evaluate_excel_file(excel_path: str, analysis_folder: Path) -> Dict[str, Any]:
    """
    Evaluate test cases from an Excel file with gold labels
    
    Args:
        excel_path: Path to Excel file
        analysis_folder: Path to analysis folder
        
    Returns:
        Dictionary with evaluation results
    """
    print(f"📊 Reading Excel file: {excel_path}")
    
    try:
        # Read the Excel file
        df = pd.read_excel(excel_path)
        
        # Check required columns
        required_columns = ['test_result', 'classification']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"❌ Excel file must contain the following required columns: {', '.join(required_columns)}")
            print(f"   Missing columns: {', '.join(missing_columns)}")
            return {}
        
        # Validate classification values
        invalid_classifications = df[~df['classification'].str.upper().isin(['TP', 'FP'])]['classification'].unique()
        if len(invalid_classifications) > 0:
            print(f"❌ Excel file contains invalid classification values: {invalid_classifications}")
            print("   Classification values must be either 'TP' or 'FP'")
            return {}
        
        # Initialize the judge
        print(f"🏛️ Initializing TestCaseJudge...")
        judge = TestCaseJudge()
        
        # Test connection
        if not judge.is_running():
            print("❌ Judge LLM connection failed")
            return {}
        
        # Save a copy of the Excel file to the analysis folder
        results_dir = analysis_folder / "results"
        excel_copy = results_dir / Path(excel_path).name
        shutil.copy2(excel_path, excel_copy)
        print(f"✅ Copied original Excel file to: {excel_copy}")
        
        # Convert Excel to CSV for processing
        csv_path = analysis_folder / "csv" / f"{Path(excel_path).stem}.csv"
        df.to_csv(csv_path, index=False)
        print(f"✅ Saved CSV version to: {csv_path}")
        
        # Prepare data for evaluation
        predictions = []
        gold_labels = []
        detailed_results = []
        
        print(f"\n� Evaluating {len(df)} test cases...")
          # Process each row
        for index, row in df.iterrows():
            try:
                # Get the test result data (can be JSON string or direct dictionary)
                test_data = row['test_result']
                
                # Convert to dictionary if it's a string
                if isinstance(test_data, str):
                    try:
                        test_data = json.loads(test_data)
                    except json.JSONDecodeError:
                        print(f"⚠️  Invalid JSON at row {index}, skipping")
                        print(f"    Error parsing: {test_data[:100]}...")
                        continue
                
                # Get the gold label from the classification column
                gold_label = str(row['classification']).strip().upper()
                
                # Validate gold label is either TP or FP
                if gold_label not in ['TP', 'FP']:
                    print(f"⚠️  Invalid gold label '{gold_label}' at row {index}, skipping")
                    print("    Gold label must be either 'TP' or 'FP'")
                    continue
                
                # Get judgment from LLM
                print(f"🔍 Judging test case {index + 1}/{len(df)}")
                judgment = judge.judge_test_case(test_data)
                
                if judgment and 'classification' in judgment:
                    predicted_label = judgment['classification'].strip().upper()
                    
                    predictions.append(predicted_label)
                    gold_labels.append(gold_label)
                    
                    # Create detailed result entry
                    result_entry = {
                        'row_index': index,
                        'test_name': test_data.get('test_name', f'test_{index}'),
                        'gold_label': gold_label,
                        'predicted_label': predicted_label,
                        'correct': predicted_label == gold_label,
                        'confidence': judgment.get('confidence', 'UNKNOWN'),
                        'reasoning': judgment.get('reasoning', ''),
                        'recommendation': judgment.get('recommendation', '')
                    }
                    
                    # Add any additional columns from the Excel file
                    for col in df.columns:
                        if col not in ['test_result', 'classification'] and col not in result_entry:
                            result_entry[col] = row[col]
                    
                    detailed_results.append(result_entry)
                    
                    status = "✅" if predicted_label == gold_label else "❌"
                    print(f"{status} Row {index}: Gold={gold_label}, Predicted={predicted_label}")
                else:
                    print(f"❌ Failed to get judgment for row {index}")
                    
            except Exception as e:
                print(f"❌ Error processing row {index}: {e}")
          # Calculate metrics
        if len(predictions) > 0:
            # Use TestCaseJudge's evaluation metrics calculation
            try:
                # First try to use sklearn metrics calculation if available
                evaluation_results = judge._calculate_sklearn_metrics(gold_labels, predictions, detailed_results)
            except AttributeError:
                try:
                    # Fall back to standard calculation method
                    evaluation_results = judge._calculate_evaluation_metrics(gold_labels, predictions, detailed_results)
                except AttributeError:
                    # If both fail, calculate our own metrics
                    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
                    
                    # Convert labels to binary for sklearn
                    gold_binary = [1 if label == 'TP' else 0 for label in gold_labels]
                    pred_binary = [1 if label == 'TP' else 0 for label in predictions]
                    
                    # Calculate metrics
                    accuracy = accuracy_score(gold_binary, pred_binary)
                    precision = precision_score(gold_binary, pred_binary, average='binary')
                    recall = recall_score(gold_binary, pred_binary, average='binary')
                    f1 = f1_score(gold_binary, pred_binary, average='binary')
                    
                    # Confusion matrix
                    cm = confusion_matrix(gold_binary, pred_binary)
                    tn, fp, fn, tp = cm.ravel()
                    
                    evaluation_results = {
                        'summary_metrics': {
                            'total_cases': len(gold_labels),
                            'accuracy': accuracy,
                            'precision': precision,
                            'recall': recall,
                            'f1_score': f1
                        },
                        'confusion_matrix': {
                            'true_negatives': int(tn),
                            'false_positives': int(fp),
                            'false_negatives': int(fn),
                            'true_positives': int(tp)
                        },
                        'detailed_results': detailed_results
                    }
            
            # Save results
            save_evaluation_results(evaluation_results, analysis_folder)
            
            return evaluation_results
        else:
            print("❌ No valid predictions were generated")
            return {}
            
    except Exception as e:
        print(f"❌ Error evaluating Excel file: {e}")
        import traceback
        traceback.print_exc()
        return {}

def save_evaluation_results(results: Dict[str, Any], analysis_folder: Path) -> None:
    """
    Save evaluation results to files
    
    Args:
        results: Dictionary with evaluation results
        analysis_folder: Path to analysis folder
    """
    if not results:
        return
        
    results_dir = analysis_folder / "results"
    
    # Save raw results to JSON
    with open(results_dir / "evaluation_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    # Create detailed results DataFrame
    if 'detailed_results' in results:
        df = pd.DataFrame(results['detailed_results'])
        
        # Save to CSV
        df.to_csv(results_dir / "detailed_results.csv", index=False)
        
        # Save to Excel with formatting
        excel_path = results_dir / "detailed_results.xlsx"
        writer = pd.ExcelWriter(excel_path, engine='openpyxl')
        df.to_excel(writer, sheet_name='Detailed Results', index=False)
        
        # Format Excel
        workbook = writer.book
        worksheet = writer.sheets['Detailed Results']
        
        # Auto-fit columns
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = min(len(str(cell.value)), 100)
                except:
                    pass
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Save Excel
        writer.close()
        
        # Create summary text file
        summary_path = results_dir / "summary_report.txt"
        with open(summary_path, 'w') as f:
            f.write(f"Judge Model Evaluation Summary\n")
            f.write(f"===========================\n\n")
            
            # Add metrics
            if 'summary_metrics' in results:
                metrics = results['summary_metrics']
                f.write("Performance Metrics:\n")
                f.write(f"  Total Test Cases: {metrics.get('total_cases', 0)}\n")
                f.write(f"  Accuracy:         {metrics.get('accuracy', 0):.4f}\n")
                f.write(f"  Precision:        {metrics.get('precision', 0):.4f}\n")
                f.write(f"  Recall:           {metrics.get('recall', 0):.4f}\n")
                f.write(f"  F1 Score:         {metrics.get('f1_score', 0):.4f}\n\n")
            
            # Add confusion matrix
            if 'confusion_matrix' in results:
                cm = results['confusion_matrix']
                f.write("Confusion Matrix:\n")
                f.write(f"  True Positives:  {cm.get('true_positives', 0)}\n")
                f.write(f"  False Positives: {cm.get('false_positives', 0)}\n")
                f.write(f"  False Negatives: {cm.get('false_negatives', 0)}\n")
                f.write(f"  True Negatives:  {cm.get('true_negatives', 0)}\n\n")
            
            # Add label distribution
            if 'detailed_results' in results:
                f.write("Label Distribution:\n")
                gold_labels = [r.get('gold_label') for r in results['detailed_results']]
                pred_labels = [r.get('predicted_label') for r in results['detailed_results']]
                
                f.write("  Gold Labels:\n")
                f.write(f"    TP: {gold_labels.count('TP')}\n")
                f.write(f"    FP: {gold_labels.count('FP')}\n\n")
                
                f.write("  Predicted Labels:\n")
                f.write(f"    TP: {pred_labels.count('TP')}\n")
                f.write(f"    FP: {pred_labels.count('FP')}\n")
        
        # Also save confusion matrix and metrics as separate CSV files
        if 'summary_metrics' in results:
            metrics_df = pd.DataFrame([results['summary_metrics']])
            metrics_df.to_csv(results_dir / "metrics_summary.csv", index=False)
            
        if 'confusion_matrix' in results:
            cm = results['confusion_matrix']
            cm_df = pd.DataFrame([
                [cm.get('true_positives', 0), cm.get('false_positives', 0)],
                [cm.get('false_negatives', 0), cm.get('true_negatives', 0)]
            ], index=['Actual TP', 'Actual FP'], columns=['Predicted TP', 'Predicted FP'])
            cm_df.to_csv(results_dir / "confusion_matrix.csv")
    
    print(f"\n✅ Saved evaluation results to:")
    print(f"   - JSON: {results_dir / 'evaluation_results.json'}")
    print(f"   - CSV: {results_dir / 'detailed_results.csv'}")
    print(f"   - Excel: {results_dir / 'detailed_results.xlsx'}")

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Test Case Judge Evaluation Tool")
    parser.add_argument("excel_file", help="Path to Excel file with test_result and classification columns")
    args = parser.parse_args()
    
    # Create analysis folder
    analysis_folder, analysis_id = create_analysis_folder()
    print(f"📊 Analysis ID: {analysis_id}")
    print(f"📁 Analysis folder: {analysis_folder}")
      # Verify Excel file exists and has a valid path
    excel_path = args.excel_file
    
    # Create an example template if needed
    def create_example_template():
        print("\n📝 Creating example evaluation template...")
        template_df = pd.DataFrame({
            'test_result': [
                '{"test_name":"example_test","request":{"method":"GET","path":"/api/users","query_params":{}},"response":{"status_code":404},"passed":false,"assertions":[{"message":"Expected status code 200 but got 404","passed":false}]}',
            ],
            'classification': ['TP']
        })
        
        template_path = analysis_folder / "results" / "example_template.xlsx"
        template_df.to_excel(template_path, index=False)
        print(f"📝 Example template created at: {template_path}")
        print("\n💡 Excel file must have the following columns:")
        print("   - test_result: JSON string containing the test case data")
        print("   - classification: Golden label (TP or FP)")
        print("\n   Then run: python scripts/judge_evaluation.py path/to/excel_file.xlsx")
    
    if not excel_path:
        print("❌ No Excel file provided.")
        parser.print_help()
        return
    
    if not os.path.exists(excel_path):
        print(f"❌ Excel file not found: {excel_path}")
        create_example_template()
        return
    
    # Validate file extension
    if not excel_path.lower().endswith(('.xlsx', '.xls')):
        print(f"❌ File must be an Excel file with .xlsx or .xls extension: {excel_path}")
        create_example_template()
        return
    
    # Create an example template if needed
    def create_example_template():
        print("\n📝 Creating example evaluation template...")
        template_df = pd.DataFrame({
            'test_result': [
                '{"test_name":"example_test","request":{"method":"GET","path":"/api/users","query_params":{}},"response":{"status_code":404},"passed":false,"assertions":[{"message":"Expected status code 200 but got 404","passed":false}]}',
            ],
            'classification': ['TP']
        })
        
        template_path = analysis_folder / "results" / "example_template.xlsx"
        template_df.to_excel(template_path, index=False)
        print(f"📝 Example template created at: {template_path}")
        print("\n💡 Excel file must have the following columns:")
        print("   - test_result: JSON string containing the test case data")
        print("   - classification: Golden label (TP or FP)")
        print("\n   Then run: python scripts/judge_evaluation.py path/to/excel_file.xlsx")
    
    if not os.path.exists(excel_path):
        print(f"❌ Excel file not found: {excel_path}")
        return
    
    # Evaluate Excel file
    results = evaluate_excel_file(excel_path, analysis_folder)
      # Generate visualizations if we have results
    if results and 'detailed_results' in results:
        try:
            # Create DataFrame and ensure it has the expected columns
            df = pd.DataFrame(results['detailed_results'])
            
            # Make sure we have at least some rows
            if len(df) > 0:
                # Try to create each visualization independently
                try:
                    generate_visualizations(df, analysis_folder, analysis_id)
                    print(f"\n✅ Generated visualizations in: {analysis_folder / 'visualizations'}")
                    print(f"   Dashboard: {analysis_folder / 'visualizations' / 'index.html'}")
                except Exception as e:
                    print(f"❌ Error generating visualizations: {e}")
                    # Generate basic HTML file anyway
                    try:
                        viz_dir = analysis_folder / "visualizations"
                        viz_dir.mkdir(exist_ok=True)
                        
                        with open(viz_dir / "index.html", 'w') as f:
                            f.write(f"""
                            <!DOCTYPE html>
                            <html>
                            <head>
                                <title>Analysis Results: {analysis_id}</title>
                                <style>
                                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                                    .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
                                    h1, h2 {{ color: #333; }}
                                    .nav {{ margin-bottom: 20px; }}
                                    .nav a {{ margin-right: 15px; }}
                                </style>
                            </head>
                            <body>
                                <div class="container">
                                    <h1>Analysis Results: {analysis_id}</h1>
                                    <div class="nav">
                                        <a href="../results/summary_report.txt">Summary Report</a>
                                        <a href="../results/detailed_results.xlsx">Detailed Results (Excel)</a>
                                        <a href="../results/detailed_results.csv">Detailed Results (CSV)</a>
                                        <a href="../results/evaluation_results.json">Raw Evaluation Data</a>
                                    </div>
                                    
                                    <h2>Visualizations</h2>
                                    <p>Error generating visualizations: {str(e)}</p>
                                </div>
                            </body>
                            </html>
                            """)
                        print(f"   Created basic dashboard: {viz_dir / 'index.html'}")
                    except Exception:
                        pass
            else:
                print("\n⚠️ No detailed results to visualize")
        except Exception as e:
            print(f"❌ Error preparing data for visualization: {e}")    # Check for metrics in different formats
    metrics = None
    if results:
        if 'summary_metrics' in results:
            metrics = results['summary_metrics']
        elif 'metrics' in results:
            metrics = results['metrics']
    
    if metrics:
        print("\n📊 Evaluation Results Summary:")
        print(f"   Total Cases: {metrics.get('total_cases', len(results.get('detailed_results', [])))}")
        print(f"   Accuracy:    {metrics.get('accuracy', 0):.4f}")
        print(f"   Precision:   {metrics.get('precision', 0):.4f}")
        print(f"   Recall:      {metrics.get('recall', 0):.4f}")
        print(f"   F1 Score:    {metrics.get('f1_score', 0):.4f}")
        
        # Check for confusion matrix
        cm = None
        if 'confusion_matrix' in results:
            cm = results['confusion_matrix']
            print("\n📊 Confusion Matrix:")
            print(f"   True Positives (TP correct):  {cm.get('true_positives', 0)}")
            print(f"   False Positives (FP as TP):   {cm.get('false_positives', 0)}")
            print(f"   False Negatives (TP as FP):   {cm.get('false_negatives', 0)}")
            print(f"   True Negatives (FP correct):  {cm.get('true_negatives', 0)}")
        
        print("\n🎉 Evaluation completed successfully!")
        print(f"📊 Results available in: {analysis_folder}")
    elif results and 'detailed_results' in results:
        print("\n⚠️ Evaluation completed but no metrics were calculated")
        print(f"📊 Results available in: {analysis_folder}")
    else:
        print("\n❌ Evaluation failed - no results to analyze")


if __name__ == "__main__":
    main()
