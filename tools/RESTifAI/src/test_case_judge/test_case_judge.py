import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from langchain_openai import AzureChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report
from dataclasses import dataclass

from prompt_templates import TestFailureClassificationPrompt2
from config import Paths

load_dotenv()

@dataclass
class TestCaseJudgeInput:
    """
    Input data structure for test case judging.
    
    Attributes:
        test_suite_name: Name of the test suite
        test_case_name: Name of the test case
        test_case_description: Description of the test case
        test_case_results: Results of the test case execution
        open_api_specification: OpenAPI specification used for the test case
    """
    test_suite_name: str
    test_case_name: str
    test_case_description: str
    test_case_results: Dict[str, Any]
    open_api_specification: Optional[Dict[str, Any]]

class TestCaseJudge:
    """
    Standalone class for judging test cases using LLM to classify them as True Positive or False Positive.
    Uses separate environment variables for its own LLM model configuration.
    """
    
    def __init__(self):
        """Initialize the TestCaseJudge with its own LLM model configuration."""
        # Load judge-specific environment variables
        api_key = os.getenv("JUDGE_AZURE_OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("JUDGE_AZURE_OPENAI_API_KEY environment variable is not set.")
        endpoint = os.getenv("JUDGE_AZURE_OPENAI_ENDPOINT", "")
        if not endpoint:
            raise ValueError("JUDGE_AZURE_OPENAI_ENDPOINT environment variable is not set.")
        api_version = os.getenv("JUDGE_AZURE_OPENAI_API_VERSION", "")
        if not api_version:
            raise ValueError("JUDGE_AZURE_OPENAI_API_VERSION environment variable is not set.")
        model_name = os.getenv("JUDGE_AZURE_OPENAI_DEPLOYMENT_NAME", "")
        if not model_name:
            raise ValueError("JUDGE_AZURE_OPENAI_DEPLOYMENT_NAME environment variable is not set.")

        # Initialize LLM model for judging
        self.model = AzureChatOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            azure_deployment=model_name,
            temperature=0,
            max_tokens=None,
            max_retries=2,
        )
        
        self.str_output_parser = StrOutputParser()
        self.prompt_template = TestFailureClassificationPrompt2()
        
    def is_running(self) -> bool:
        """
        Check if the judge LLM is running by invoking a simple prompt.
        """
        try:
            response = self.model.invoke("Test connection")
            return True
        except Exception as e:
            print(f"Judge LLM connection test failed: {e}")
            return False
        
    @staticmethod
    def _get_json_block(text: str) -> dict:
        """
        Extracts a JSON block from the given text.
        """
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            json_str = text[start:end]
            data = json.loads(json_str)
        except (ValueError, json.JSONDecodeError):
            print("Error extracting JSON block from text.")
            raise json.JSONDecodeError("Invalid JSON format, cant apply json.loads() to output", text, 0)
        
        if not isinstance(data, dict):
            raise ValueError("Extracted JSON is not a dictionary.")
        return data
    
    def judge_test_case(self, test_case_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Judge a single test case and return the classification result.
        
        Args:
            test_case_data: Dictionary containing test case data from test_data JSON file
            
        Returns:
            Dictionary with classification results or None if error occurred
        """
        try:
            # Validate input data
            if not isinstance(test_case_data, dict):
                raise ValueError("test_case_data must be a dictionary")
            
            input = TestCaseJudgeInput(
                test_suite_name=test_case_data.get("test_suite", "Unknown Suite"),
                test_case_name=test_case_data.get("test_name", "Unknown Test Case"),
                test_case_description=test_case_data.get("description", "No description provided"),
                test_case_results=test_case_data.get("test_results", {}),
                open_api_specification=test_case_data.get("relevant_endpoints", None)
            )

            # Convert test case data to JSON string for the prompt
            test_case_json = json.dumps(input.__dict__, indent=2)
            
            input_data = {
                "test_case_data": test_case_json,
            }
            # Create the prompt
            prompt = self.prompt_template.generate_prompt(input_data)
            
            # Get LLM response
            chain = self.model | self.str_output_parser
            llm_output = chain.invoke(prompt)
            
            # Parse JSON response
            try:
                result = self._get_json_block(llm_output)
            except json.JSONDecodeError:
                print(f"Failed to parse JSON from response: {llm_output}")
                return None
            return result
                    
        except Exception as e:
            print(f"Error judging test case: {e}")
            return None
    
    def judge_test_cases_from_files(self, test_suite_name: str, test_case_names: List[str] = None) -> List[Dict[str, Any]]:
        """
        Judge multiple test cases from test_data files.
        
        Args:
            test_suite_name: Name of the test suite
            test_case_names: List of specific test case names to judge. If None, judges all test cases in the suite.
            
        Returns:
            List of judgment results
        """
        results = []
        test_data_dir = Paths.get_test_data_str()
        test_suite_dir = os.path.join(test_data_dir, test_suite_name)
        
        if not os.path.exists(test_suite_dir):
            print(f"❌ Test suite directory not found: {test_suite_dir}")
            return results
          # Get list of test case files
        if test_case_names:
            test_files = [f"{name}.json" for name in test_case_names]
        else:
            test_files = [f for f in os.listdir(test_suite_dir) if f.endswith('.json')]
        
        for test_file in test_files:
            test_file_path = os.path.join(test_suite_dir, test_file)
            
            if not os.path.exists(test_file_path):
                print(f"⚠️  Test case file not found: {test_file_path}")
                continue
                
            try:
                # Load test case data
                with open(test_file_path, 'r') as f:
                    test_case_data = json.load(f)
                
                # Only judge failed test cases
                if test_case_data.get("passed", True):
                    print(f"⏭️  Skipping passed test case: {test_file}")
                    continue
                
                print(f"🔍 Judging test case: {test_file}")
                judgment = self.judge_test_case(test_case_data)
                
                if judgment:
                    judgment["test_case_name"] = test_case_data.get("test_name", test_file.replace('.json', ''))
                    judgment["test_suite"] = test_suite_name
                    results.append(judgment)
                    print(f"✅ Judged {test_file}: {judgment.get('classification', 'Unknown')}")
                else:
                    print(f"❌ Failed to judge {test_file}")
                    
            except Exception as e:
                print(f"❌ Error processing {test_file}: {e}")
        
        return results
    
    def evaluate_from_csv(self, csv_file_path: str) -> Dict[str, Any]:
        """
        Evaluate test cases from a CSV file containing test data and golden labels.
        
        CSV format expected:
        - Column 'test_data': JSON string containing test case data
        - Column 'label': Golden labels ('TP' or 'FP')
        
        Args:
            csv_file_path: Path to the CSV evaluation file
            
        Returns:
            Dictionary containing evaluation metrics and analysis
        """
        try:
            # Load CSV file
            df = pd.read_csv(csv_file_path)
            
            # Validate required columns
            if 'test_data' not in df.columns or 'label' not in df.columns:
                raise ValueError("CSV file must contain 'test_data' and 'label' columns")
            
            predictions = []
            gold_labels = []
            detailed_results = []
            
            print(f"📊 Evaluating {len(df)} test cases from {csv_file_path}")
            
            for index, row in df.iterrows():
                try:
                    # Parse test data JSON
                    test_data = json.loads(row['test_data'])
                    gold_label = row['label'].strip().upper()
                    
                    # Validate gold label
                    if gold_label not in ['TP', 'FP']:
                        print(f"⚠️  Invalid gold label '{gold_label}' at row {index}, skipping")
                        continue
                    
                    # Get judgment from LLM
                    print(f"🔍 Judging test case {index + 1}/{len(df)}")
                    judgment = self.judge_test_case(test_data)
                    
                    if judgment and 'classification' in judgment:
                        predicted_label = judgment['classification'].strip().upper()
                        
                        predictions.append(predicted_label)
                        gold_labels.append(gold_label)
                        
                        detailed_results.append({
                            'row_index': index,
                            'test_name': test_data.get('test_name', f'test_{index}'),
                            'gold_label': gold_label,
                            'predicted_label': predicted_label,
                            'correct': predicted_label == gold_label,
                            'confidence': judgment.get('confidence', 'UNKNOWN'),
                            'reasoning': judgment.get('reasoning', ''),
                            'recommendation': judgment.get('recommendation', '')
                        })
                        
                        status = "✅" if predicted_label == gold_label else "❌"
                        print(f"{status} Row {index}: Gold={gold_label}, Predicted={predicted_label}")
                    else:
                        print(f"❌ Failed to get judgment for row {index}")
                        
                except Exception as e:
                    print(f"❌ Error processing row {index}: {e}")
            
            # Calculate metrics
            if len(predictions) > 0:
                evaluation_results = self._calculate_sklearn_metrics(gold_labels, predictions, detailed_results)
                  # Save detailed results
                self._save_evaluation_results(evaluation_results, csv_file_path)
                
                return evaluation_results
            else:
                return {"error": "No valid predictions were generated"}
        except Exception as e:
            print(f"❌ Error evaluating CSV file: {e}")
            return {"error": str(e)}
    
    def _calculate_sklearn_metrics(self, gold_labels: List[str], predictions: List[str], detailed_results: List[Dict]) -> Dict[str, Any]:
        """Calculate evaluation metrics using sklearn."""
        
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
        
        # Classification report
        class_report = classification_report(gold_binary, pred_binary, target_names=['FP', 'TP'], output_dict=True)
        
        # Confidence analysis
        confidence_counts = {}
        for result in detailed_results:
            conf = result['confidence']
            if conf not in confidence_counts:
                confidence_counts[conf] = {'total': 0, 'correct': 0}
            confidence_counts[conf]['total'] += 1
            confidence_counts[conf]['correct'] += 1 if result['correct'] else 0
        
        # Calculate confidence-based accuracy
        confidence_accuracy = {}
        for conf, data in confidence_counts.items():
            confidence_accuracy[conf] = data['correct'] / data['total'] if data['total'] > 0 else 0
        
        return {
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
            'classification_report': class_report,
            'confidence_analysis': {
                'confidence_counts': confidence_counts,
                'confidence_accuracy': confidence_accuracy
            },
            'detailed_results': detailed_results,
            'label_distribution': {
                'gold_labels': {
                    'TP': gold_labels.count('TP'),
                    'FP': gold_labels.count('FP')
                },
                'predictions': {
                    'TP': predictions.count('TP'),
                    'FP': predictions.count('FP')
                }
            }
        }
    
    def _save_evaluation_results(self, results: Dict[str, Any], original_csv_path: str):
        """Save evaluation results to JSON file."""
        try:
            # Create output filename
            base_name = os.path.splitext(os.path.basename(original_csv_path))[0]
            output_file = os.path.join(Paths.get_reports_str(), f"{base_name}_evaluation_results.json")
            
            # Save results
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            print(f"💾 Evaluation results saved to: {output_file}")
            
            # Print summary
            metrics = results['summary_metrics']
            print(f"\n📊 Evaluation Summary:")
            print(f"   Total Cases: {metrics['total_cases']}")
            print(f"   Accuracy: {metrics['accuracy']:.3f}")
            print(f"   Precision: {metrics['precision']:.3f}")
            print(f"   Recall: {metrics['recall']:.3f}")
            print(f"   F1 Score: {metrics['f1_score']:.3f}")
            
        except Exception as e:
            print(f"❌ Error saving evaluation results: {e}")