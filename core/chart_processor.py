import json
import re
from typing import List, Dict, Any, Optional

class ChartProcessor:
    """Handles all chart-related processing and extraction."""
    
    def __init__(self):
        """Initialize the chart processor."""
        self.valid_chart_types = ['bar', 'line', 'pie', 'doughnut', 'radar', 'polarArea', 'scatter', 'bubble']
    
    def extract_charts_from_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Extract Chart.js configuration objects from LLM response text."""
        charts = []
        
        try:
            print(f"DEBUG: Looking for charts in response text (length: {len(response_text)})")
            
            # Pattern 1: Look for ```json blocks
            json_pattern = r'```json\s*(.*?)\s*```'
            json_blocks = re.findall(json_pattern, response_text, re.DOTALL | re.IGNORECASE)
            
            print(f"DEBUG: Found {len(json_blocks)} JSON blocks")
            
            for i, block in enumerate(json_blocks):
                try:
                    print(f"DEBUG: Processing JSON block {i}")
                    cleaned_block = self.clean_json_for_parsing(block.strip())
                    parsed = json.loads(cleaned_block)
                    
                    if self.is_valid_chart_config(parsed):
                        print(f"DEBUG: Valid chart config found in block {i}")
                        charts.append(parsed)
                    else:
                        print(f"DEBUG: Invalid chart config in block {i}")
                        
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"DEBUG: Failed to parse JSON block {i}: {e}")
                    try:
                        fixed_block = self.fix_common_json_issues(block.strip())
                        parsed = json.loads(fixed_block)
                        if self.is_valid_chart_config(parsed):
                            print(f"DEBUG: Fixed and parsed JSON block {i}")
                            charts.append(parsed)
                    except Exception as fix_error:
                        print(f"DEBUG: Could not fix JSON block {i}: {fix_error}")
                        try:
                            basic_chart = self.extract_basic_chart_from_broken_json(block.strip())
                            if basic_chart:
                                print(f"DEBUG: Created basic chart from broken JSON block {i}")
                                charts.append(basic_chart)
                        except:
                            print(f"DEBUG: Could not create basic chart from block {i}")
                        continue
            
            # Pattern 2: Look for chart objects without json tags
            chart_patterns = [
                r'{\s*["\']?type["\']?\s*:\s*["\'](?:bar|line|pie|doughnut|radar|polarArea|scatter|bubble)["\'].*?(?=\n\n|\n```|\n#|$)',
            ]
            
            for pattern in chart_patterns:
                matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
                print(f"DEBUG: Found {len(matches)} pattern matches")
                
                for match in matches:
                    try:
                        cleaned_match = self.clean_json_for_parsing(match)
                        parsed = json.loads(cleaned_match)
                        if self.is_valid_chart_config(parsed):
                            charts.append(parsed)
                            print(f"DEBUG: Added chart from pattern match")
                    except:
                        continue
            
            print(f"DEBUG: Total charts extracted: {len(charts)}")
            
        except Exception as e:
            print(f"DEBUG: Error extracting charts from response: {e}")
        
        return charts
    
    def clean_json_for_parsing(self, json_str: str) -> str:
        """Clean JSON string to make it parseable by removing JavaScript functions."""
        try:
            print(f"DEBUG: Original JSON length: {len(json_str)}")
            
            # Remove tooltip section with JavaScript functions
            json_str = re.sub(r'"tooltip"\s*:\s*{[^}]*"callbacks"[^}]*function[^}]*}[^}]*}', '"tooltip": {}', json_str, flags=re.DOTALL)
            
            # Remove function definitions
            json_str = re.sub(r'"callbacks"\s*:\s*{[^}]*}', '{}', json_str, flags=re.DOTALL)
            json_str = re.sub(r'function\s*\([^)]*\)\s*{[^}]*}', 'null', json_str, flags=re.DOTALL)
            json_str = re.sub(r'"[^"]*"\s*:\s*function[^,}]*[,}]', '', json_str, flags=re.DOTALL)
            
            # Clean up JSON structure
            json_str = re.sub(r',\s*,', ',', json_str)
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
            json_str = re.sub(r'{\s*,', '{', json_str)
            json_str = re.sub(r':\s*,', ': null,', json_str)
            
            print(f"DEBUG: Cleaned JSON length: {len(json_str)}")
            return json_str
            
        except Exception as e:
            print(f"DEBUG: Error cleaning JSON: {e}")
            return json_str
    
    def fix_common_json_issues(self, json_str: str) -> str:
        """Try to fix common JSON parsing issues more aggressively."""
        try:
            print("DEBUG: Attempting to fix JSON issues...")
            
            # Remove problematic sections
            json_str = re.sub(r',?\s*"tooltip"\s*:\s*{[^{]*{[^}]*}[^}]*}', '', json_str, flags=re.DOTALL)
            json_str = re.sub(r',?\s*"callbacks"\s*:\s*{[^}]*}', '', json_str, flags=re.DOTALL)
            json_str = re.sub(r'function\s*\([^)]*\)\s*{[^}]*}', 'null', json_str, flags=re.DOTALL)
            
            # Remove lines containing 'function'
            lines = json_str.split('\n')
            cleaned_lines = []
            in_function = False
            brace_count = 0
            
            for line in lines:
                if 'function' in line:
                    in_function = True
                    brace_count = line.count('{') - line.count('}')
                    continue
                elif in_function:
                    brace_count += line.count('{') - line.count('}')
                    if brace_count <= 0:
                        in_function = False
                    continue
                else:
                    cleaned_lines.append(line)
            
            json_str = '\n'.join(cleaned_lines)
            
            # Clean up JSON structure
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
            json_str = re.sub(r'([}\]]),(\s*[}\]])', r'\1\2', json_str)
            json_str = re.sub(r'{\s*,', '{', json_str)
            json_str = re.sub(r',\s*}', '}', json_str)
            
            return json_str
            
        except Exception as e:
            print(f"DEBUG: Error fixing JSON: {e}")
            return json_str
    
    def is_valid_chart_config(self, config: Dict[str, Any]) -> bool:
        """Check if a parsed object is a valid Chart.js configuration."""
        try:
            if not isinstance(config, dict):
                print("DEBUG: Chart config is not a dict")
                return False
            
            if 'type' not in config:
                print("DEBUG: Chart config missing 'type' field")
                return False
            
            if config['type'] not in self.valid_chart_types:
                print(f"DEBUG: Invalid chart type: {config['type']}")
                return False
            
            if 'data' not in config:
                print("DEBUG: Chart config missing 'data' field")
                return False
            
            if not isinstance(config['data'], dict):
                print("DEBUG: Chart config 'data' is not a dict")
                return False
            
            print(f"DEBUG: Valid chart config found - type: {config['type']}")
            return True
            
        except Exception as e:
            print(f"DEBUG: Error validating chart config: {e}")
            return False
    
    def extract_basic_chart_from_broken_json(self, broken_json: str) -> Optional[Dict[str, Any]]:
        """Extract basic chart information from broken JSON and create a simplified chart."""
        try:
            print("DEBUG: Attempting to extract basic chart from broken JSON")
            
            # Extract chart type
            type_match = re.search(r'"type"\s*:\s*"([^"]*)"', broken_json)
            chart_type = type_match.group(1) if type_match else "bar"
            
            # Extract labels
            labels_match = re.search(r'"labels"\s*:\s*\[(.*?)\]', broken_json, re.DOTALL)
            labels = []
            if labels_match:
                labels_str = labels_match.group(1)
                labels = re.findall(r'"([^"]*)"', labels_str)
            
            # Extract data arrays
            data_matches = re.findall(r'"data"\s*:\s*\[([\d\s,.-]+)\]', broken_json)
            datasets = []
            
            # Extract dataset labels and colors
            dataset_labels = re.findall(r'"label"\s*:\s*"([^"]*)"', broken_json)
            color_matches = re.findall(r'"backgroundColor"\s*:\s*"([^"]*)"', broken_json)
            
            for i, data_match in enumerate(data_matches):
                try:
                    numbers = re.findall(r'[\d.-]+', data_match)
                    data_values = [float(num) for num in numbers]
                    
                    if data_values:
                        dataset = {
                            "label": dataset_labels[i] if i < len(dataset_labels) else f"Dataset {i+1}",
                            "data": data_values,
                            "backgroundColor": color_matches[i] if i < len(color_matches) else self.generate_color()
                        }
                        datasets.append(dataset)
                except:
                    continue
            
            # Create basic chart if we have minimum required data
            if chart_type and (labels or datasets):
                if not labels and datasets and datasets[0]['data']:
                    labels = [f"Item {i+1}" for i in range(len(datasets[0]['data']))]
                
                basic_chart = {
                    "type": chart_type,
                    "data": {
                        "labels": labels,
                        "datasets": datasets
                    },
                    "options": {
                        "responsive": True,
                        "maintainAspectRatio": False,
                        "plugins": {
                            "title": {
                                "display": True,
                                "text": f"{chart_type.title()} Chart"
                            }
                        }
                    }
                }
                
                print(f"DEBUG: Created basic chart with {len(labels)} labels and {len(datasets)} datasets")
                return basic_chart
            
        except Exception as e:
            print(f"DEBUG: Error extracting basic chart: {e}")
        
        return None
    
    def generate_color(self) -> str:
        """Generate a single color."""
        base_colors = [
            "#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6",
            "#1abc9c", "#34495e", "#e67e22", "#95a5a6", "#f1c40f"
        ]
        return base_colors[0]  # Return first color as default 