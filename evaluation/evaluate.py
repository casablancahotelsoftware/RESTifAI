#!/usr/bin/env python3

import os
import json
import csv
import argparse
from pathlib import Path
import re
from datetime import datetime

def parse_jacoco_coverage(jacoco_dir):
    """Parse JaCoCo HTML report to extract coverage percentages"""
    coverage_data = {
        'instruction_coverage': '',
        'branch_coverage': '',
        'line_coverage': '',
        'method_coverage': '',
        'overall_coverage': ''
    }
    
    # Look for index.html in jacoco directory
    index_file = jacoco_dir / "index.html"
    if not index_file.exists():
        return coverage_data
    
    try:
        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse HTML using regex to extract coverage data from tfoot
        tfoot_match = re.search(r'<tfoot>.*?</tfoot>', content, re.DOTALL)
        if tfoot_match:
            tfoot_content = tfoot_match.group()
            
            # Find all td elements with coverage data
            td_elements = re.findall(r'<td[^>]*>(.*?)</td>', tfoot_content)
            
            if len(td_elements) >= 13:
                # Extract coverage percentages from specific positions
                # Based on JaCoCo table structure:
                # 0: Total, 1: Missed Instructions bar, 2: Instruction Cov%, 
                # 3: Missed Branches bar, 4: Branch Cov%, 5: Missed Cxty, 6: Total Cxty,
                # 7: Missed Lines, 8: Total Lines, 9: Missed Methods, 10: Total Methods, 
                # 11: Missed Classes, 12: Total Classes
                
                # Parse instruction coverage (position 2)
                inst_match = re.search(r'(\d+)%', td_elements[2])
                if inst_match:
                    coverage_data['instruction_coverage'] = inst_match.group(1) + '%'
                
                # Parse branch coverage (position 4)
                branch_match = re.search(r'(\d+)%', td_elements[4])
                if branch_match:
                    coverage_data['branch_coverage'] = branch_match.group(1) + '%'
                
                # Calculate line coverage from missed lines and total lines
                try:
                    missed_lines = int(td_elements[7].replace(',', ''))
                    total_lines = int(td_elements[8].replace(',', ''))
                    if total_lines > 0:
                        line_coverage = ((total_lines - missed_lines) / total_lines) * 100
                        coverage_data['line_coverage'] = f"{line_coverage:.0f}%"
                except (ValueError, IndexError):
                    pass
                
                # Calculate method coverage from missed methods and total methods
                try:
                    missed_methods = int(td_elements[9].replace(',', ''))
                    total_methods = int(td_elements[10].replace(',', ''))
                    if total_methods > 0:
                        method_coverage = ((total_methods - missed_methods) / total_methods) * 100
                        coverage_data['method_coverage'] = f"{method_coverage:.0f}%"
                except (ValueError, IndexError):
                    pass
                
                # Calculate overall coverage (average of instruction, branch, line, and method)
                try:
                    coverages = []
                    for cov_key in ['instruction_coverage', 'branch_coverage', 'line_coverage', 'method_coverage']:
                        if coverage_data[cov_key]:
                            pct = float(coverage_data[cov_key].replace('%', ''))
                            coverages.append(pct)
                    
                    if coverages:
                        overall_cov = sum(coverages) / len(coverages)
                        coverage_data['overall_coverage'] = f"{overall_cov:.1f}%"
                except ValueError:
                    pass
    
    except Exception as e:
        print(f"Error parsing JaCoCo report {index_file}: {e}")
    
    return coverage_data

def find_result_files(results_dir):
    """Find all results.json files in the results directory structure"""
    result_files = []
    results_path = Path(results_dir)
    
    if not results_path.exists():
        print(f"Results directory {results_dir} does not exist")
        return result_files
    
    # Walk through the directory structure: results/service/tool/
    for service_dir in results_path.iterdir():
        if service_dir.is_dir():
            service_name = service_dir.name
            for tool_dir in service_dir.iterdir():
                if tool_dir.is_dir():
                    tool_name = tool_dir.name
                    # Look for results.json files in subdirectories
                    for result_file in tool_dir.rglob("results.json"):
                        # Look for jacoco coverage reports - updated pattern
                        jacoco_dir = None
                        
                        # Look for pattern: tool_dir/jacoco/timestamp/jacoco/index.html
                        jacoco_pattern = tool_dir / "jacoco"
                        if jacoco_pattern.exists():
                            for timestamp_dir in jacoco_pattern.iterdir():
                                if timestamp_dir.is_dir():
                                    jacoco_index = timestamp_dir / "jacoco" / "index.html"
                                    if jacoco_index.exists():
                                        jacoco_dir = jacoco_index.parent
                                        break
                        
                        # Also check for alternative pattern: tool_dir/jacoco/timestamp/index.html
                        if not jacoco_dir and jacoco_pattern.exists():
                            for timestamp_dir in jacoco_pattern.iterdir():
                                if timestamp_dir.is_dir():
                                    jacoco_index = timestamp_dir / "index.html"
                                    if jacoco_index.exists():
                                        jacoco_dir = jacoco_index.parent
                                        break

                        print(f"Found JaCoCo dir for {service_name}/{tool_name}: {jacoco_dir}")
                        
                        result_files.append({
                            'service': service_name,
                            'tool': tool_name,
                            'file_path': result_file,
                            'jacoco_dir': jacoco_dir
                        })
    
    return result_files

def extract_data_from_result(file_path, jacoco_dir=None):
    """Extract data from a results.json file and JaCoCo coverage"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Extract common fields that might exist
        result = {
            'successful_operations': data.get('successful_operations', ''),
            'server_errors': data.get('server_errors', ''),
            'total_tokens': data.get('total_tokens', ''),
            'total_cost': data.get('total_cost', ''),
            'total_tests': data.get('total_tests', ''),
            'failed_tests': data.get('failed_tests', ''),
            'passed_tests': data.get('passed_tests', ''),
            'execution_time': data.get('execution_time', ''),
            'instruction_coverage': '',
            'branch_coverage': '',
            'line_coverage': '',
            'method_coverage': '',
            'error_rate': '',
            'success_rate': ''
        }
        
        # Calculate passed tests if not provided
        if not result['passed_tests'] and result['total_tests'] and result['failed_tests']:
            try:
                total = int(result['total_tests'])
                failed = int(result['failed_tests'])
                result['passed_tests'] = total - failed
            except ValueError:
                pass
        
        # Parse JaCoCo coverage if available
        if jacoco_dir:
            coverage_data = parse_jacoco_coverage(jacoco_dir)
            result.update(coverage_data)
        
        # Calculate error rate if we have the data
        if result['total_tests'] and result['failed_tests']:
            try:
                error_rate = (float(result['failed_tests']) / float(result['total_tests'])) * 100
                result['error_rate'] = f"{error_rate:.2f}%"
                
                success_rate = 100 - error_rate
                result['success_rate'] = f"{success_rate:.2f}%"
            except (ValueError, ZeroDivisionError):
                pass
        
        return result
        
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading {file_path}: {e}")
        return None

def generate_csv(results_dir, output_file):
    """Generate CSV file from all results.json files and coverage reports"""
    
    result_files = find_result_files(results_dir)
    
    if not result_files:
        print(f"No results.json files found in {results_dir}")
        return
    
    # CSV headers
    headers = [
        'Service',
        'Tool',
        'Successful Operations',
        'Server Errors',
        'Total Tokens',
        'Total Cost',
        'Total Tests',
        'Failed Tests',
        'Passed Tests',
        'Error Rate',
        'Success Rate',
        'Execution Time',
        'Instruction Coverage',
        'Branch Coverage',
        'Line Coverage',
        'Method Coverage'
    ]
    
    rows = []
    
    for result_file in result_files:
        data = extract_data_from_result(result_file['file_path'], result_file['jacoco_dir'])
        if data:
            row = [
                result_file['service'],
                result_file['tool'],
                data['successful_operations'],
                data['server_errors'],
                data['total_tokens'],
                data['total_cost'],
                data['total_tests'],
                data['failed_tests'],
                data['passed_tests'],
                data['error_rate'],
                data['success_rate'],
                data['execution_time'],
                data['instruction_coverage'],
                data['branch_coverage'],
                data['line_coverage'],
                data['method_coverage']
            ]
            rows.append(row)
    
    # Write CSV file
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(rows)
    
    print(f"CSV file generated: {output_file}")
    print(f"Processed {len(rows)} result files")
    
    # Print summary statistics
    if rows:
        print("\n--- Summary Statistics ---")
        total_tests = sum(int(row[6]) for row in rows if row[6] and str(row[6]).isdigit())
        total_failed = sum(int(row[7]) for row in rows if row[7] and str(row[7]).isdigit())
        total_tokens = sum(int(row[4]) for row in rows if row[4] and str(row[4]).isdigit())
        total_cost = sum(float(row[5]) for row in rows if row[5] and str(row[5]).replace('.', '').isdigit())
        
        print(f"Total Tests Executed: {total_tests}")
        print(f"Total Failed Tests: {total_failed}")
        print(f"Total Tokens Used: {total_tokens:,}")
        print(f"Total Cost: ${total_cost:.4f}")
        
        if total_tests > 0:
            overall_success_rate = ((total_tests - total_failed) / total_tests) * 100
            print(f"Overall Success Rate: {overall_success_rate:.2f}%")

def main():
    parser = argparse.ArgumentParser(description='Generate CSV evaluation report from results.json files and JaCoCo coverage')
    parser.add_argument('--results-dir', '-r', default='/app/results', 
                       help='Directory containing results (default: /app/results)')
    parser.add_argument('--output', '-o', default='/app/output/evaluation_results.csv',
                       help='Output CSV file name (default: /app/output/evaluation_results.csv)')
    parser.add_argument('--timestamp', '-t', action='store_true',
                       help='Add timestamp to output filename')
    
    args = parser.parse_args()
    
    # Add timestamp to filename if requested
    if args.timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(args.output)
        args.output = str(output_path.parent / f"{output_path.stem}_{timestamp}{output_path.suffix}")
    
    # Create output directory if it doesn't exist
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not os.path.exists(args.results_dir):
        print(f"Results directory '{args.results_dir}' not found")
        return 1
    
    generate_csv(args.results_dir, args.output)
    return 0

if __name__ == "__main__":
    exit(main())