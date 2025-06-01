# Improved chart_processor.py with better validation and structure handling

import json
import re
from typing import List, Dict, Any

class ChartProcessor:
    """Handles chart extraction and processing from LLM responses."""
    
    def extract_charts_from_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Extract charts from LLM response that can be either individual chart objects or arrays of charts.
        Handles the new structure with relevancy and chart_config.
        """
        charts = []
        
        print(f"DEBUG: Looking for charts in response text (length: {len(response_text)})")
        
        # Look for JSON blocks in the response
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        json_blocks = re.findall(json_pattern, response_text, re.IGNORECASE)
        
        print(f"DEBUG: Found {len(json_blocks)} JSON blocks")
        
        for i, json_block in enumerate(json_blocks):
            try:
                # Clean the JSON block
                cleaned_json = json_block.strip()
                print(f"DEBUG: Processing JSON block {i} (length: {len(cleaned_json)})")
                
                # Parse the JSON
                parsed_json = json.loads(cleaned_json)
                
                print(f"DEBUG: Successfully parsed JSON block {i}, type: {type(parsed_json)}")
                
                # Handle different structures
                if isinstance(parsed_json, list):
                    # This is an array of charts
                    print(f"DEBUG: Processing array of {len(parsed_json)} charts")
                    for j, chart_item in enumerate(parsed_json):
                        if isinstance(chart_item, dict):
                            processed_chart = self._process_chart_item(chart_item, f"block_{i}_array[{j}]")
                            if processed_chart:
                                charts.append(processed_chart)
                        else:
                            print(f"DEBUG: Chart {j} in array is not a dict: {type(chart_item)}")
                            
                elif isinstance(parsed_json, dict):
                    # Single chart object
                    print(f"DEBUG: Processing single chart object")
                    processed_chart = self._process_chart_item(parsed_json, f"block_{i}_single")
                    if processed_chart:
                        charts.append(processed_chart)
                else:
                    print(f"DEBUG: Parsed JSON is neither list nor dict: {type(parsed_json)}")
                    
            except json.JSONDecodeError as e:
                print(f"DEBUG: Failed to parse JSON block {i}: {e}")
                print(f"DEBUG: Problematic JSON start: {json_block[:200]}...")
                
                # Try to extract charts from broken JSON using fallback method
                fallback_charts = self._extract_charts_fallback(json_block)
                charts.extend(fallback_charts)
                continue
            except Exception as e:
                print(f"DEBUG: Unexpected error processing JSON block {i}: {e}")
                continue
        
        print(f"DEBUG: Total charts extracted: {len(charts)}")
        
        # Log chart details and validate
        validated_charts = []
        for i, chart in enumerate(charts):
            if self._validate_chart_structure(chart, f"chart_{i}"):
                validated_charts.append(chart)
            else:
                print(f"DEBUG: Chart {i} failed validation, excluding from results")
        
        print(f"DEBUG: Charts after validation: {len(validated_charts)}")
        return validated_charts
    
    def _process_chart_item(self, chart_item: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        """Process a single chart item and validate its structure."""
        
        # Check if this is the new structure with relevancy and chart_config
        if 'relevancy' in chart_item and 'chart_config' in chart_item:
            relevancy = chart_item['relevancy']
            chart_config = chart_item['chart_config']
            user_input = chart_item.get('user_input', '')
            
            if self._is_valid_chart_config(chart_config):
                print(f"DEBUG: {context} - Valid chart with relevancy '{relevancy}' and type '{chart_config.get('type')}'")
                # Return the full structure for proper handling
                result = {
                    'relevancy': relevancy,
                    'chart_config': chart_config
                }
                if user_input:
                    result['user_input'] = user_input
                return result
            else:
                print(f"DEBUG: {context} - Invalid chart_config in relevancy structure")
                return None
        
        # Check if this is a direct chart config with relevancy field
        elif 'relevancy' in chart_item and 'type' in chart_item and 'data' in chart_item:
            relevancy = chart_item['relevancy']
            chart_type = chart_item['type']
            user_input = chart_item.get('user_input', '')
            
            if self._is_valid_chart_config(chart_item):
                print(f"DEBUG: {context} - Valid direct chart config with relevancy '{relevancy}' and type '{chart_type}'")
                # Keep the structure but mark it properly
                result = chart_item.copy()
                return result
            else:
                print(f"DEBUG: {context} - Invalid direct chart config with relevancy")
                return None
        
        # Check if this is a standard chart config without relevancy
        elif 'type' in chart_item and 'data' in chart_item:
            chart_type = chart_item['type']
            
            if self._is_valid_chart_config(chart_item):
                print(f"DEBUG: {context} - Valid standard chart config with type '{chart_type}'")
                # Add default relevancy if missing
                result = chart_item.copy()
                if 'relevancy' not in result:
                    result['relevancy'] = 'main'  # Default to main
                return result
            else:
                print(f"DEBUG: {context} - Invalid standard chart config")
                return None
        
        else:
            print(f"DEBUG: {context} - Chart doesn't match any expected structure")
            print(f"DEBUG: {context} - Available keys: {list(chart_item.keys())}")
            return None
    
    def _validate_chart_structure(self, chart: Dict[str, Any], context: str = "") -> bool:
        """Validate the overall chart structure."""
        if not isinstance(chart, dict):
            print(f"DEBUG: {context} - Chart is not a dict")
            return False
        
        # Extract the actual chart config
        chart_config = chart
        if 'chart_config' in chart:
            chart_config = chart['chart_config']
        
        # Validate the chart config
        if not self._is_valid_chart_config(chart_config):
            print(f"DEBUG: {context} - Chart config validation failed")
            return False
        
        # Check for required fields in the overall structure
        if 'relevancy' not in chart:
            print(f"DEBUG: {context} - Missing relevancy field")
            return False
        
        relevancy = chart['relevancy']
        if relevancy not in ['main', 'secondary']:
            print(f"DEBUG: {context} - Invalid relevancy value: {relevancy}")
            return False
        
        print(f"DEBUG: {context} - Chart structure validation passed")
        return True
    
    def _is_valid_chart_config(self, chart_config: Dict[str, Any]) -> bool:
        """Validate that a chart config has the required structure."""
        if not isinstance(chart_config, dict):
            return False
        
        # Must have type and data
        if 'type' not in chart_config or 'data' not in chart_config:
            return False
        
        # Validate chart type
        valid_types = ['bar', 'line', 'pie', 'doughnut', 'scatter', 'radar', 'polarArea', 'bubble']
        if chart_config['type'] not in valid_types:
            print(f"DEBUG: Invalid chart type: {chart_config['type']}")
            return False
        
        # Data must be a dict
        if not isinstance(chart_config['data'], dict):
            return False
        
        # Data should have datasets (for most chart types)
        data = chart_config['data']
        if 'datasets' not in data:
            return False
        
        # Datasets should be a list with at least one dataset
        if not isinstance(data['datasets'], list) or len(data['datasets']) == 0:
            return False
        
        # Validate each dataset
        for i, dataset in enumerate(data['datasets']):
            if not isinstance(dataset, dict):
                print(f"DEBUG: Dataset {i} is not a dict")
                return False
            
            if 'data' not in dataset:
                print(f"DEBUG: Dataset {i} missing data field")
                return False
            
            if not isinstance(dataset['data'], list):
                print(f"DEBUG: Dataset {i} data is not a list")
                return False
        
        # For non-pie charts, labels should be present
        if chart_config['type'] not in ['pie', 'doughnut'] and 'labels' not in data:
            print(f"DEBUG: Chart type {chart_config['type']} missing labels")
            return False
        
        return True
    
    def _extract_charts_fallback(self, broken_json: str) -> List[Dict[str, Any]]:
        """Fallback method to extract basic chart info from broken JSON."""
        charts = []
        
        print("DEBUG: Attempting fallback chart extraction from broken JSON")
        
        # Try to find chart type
        type_match = re.search(r'"type"\s*:\s*"([^"]+)"', broken_json)
        if not type_match:
            print("DEBUG: No chart type found in broken JSON")
            return charts
        
        chart_type = type_match.group(1)
        
        # Try to find labels
        labels_match = re.search(r'"labels"\s*:\s*\[(.*?)\]', broken_json, re.DOTALL)
        labels = []
        if labels_match:
            labels_text = labels_match.group(1)
            # Extract quoted strings
            label_matches = re.findall(r'"([^"]+)"', labels_text)
            labels = label_matches
        
        # Try to find data values
        data_match = re.search(r'"data"\s*:\s*\[([\d.,\s]+)\]', broken_json)
        data_values = []
        if data_match:
            data_text = data_match.group(1)
            # Extract numbers
            numbers = re.findall(r'[\d.]+', data_text)
            data_values = [float(num) for num in numbers]
        
        if labels and data_values and len(labels) == len(data_values):
            basic_chart = {
                "relevancy": "main",  # Default fallback charts to main
                "type": chart_type,
                "data": {
                    "labels": labels,
                    "datasets": [{
                        "label": "Data",
                        "data": data_values,
                        "backgroundColor": ["#3498db", "#e74c3c", "#f39c12", "#27ae60", "#9b59b6", "#1abc9c"][:len(data_values)]
                    }]
                },
                "options": {
                    "responsive": True,
                    "maintainAspectRatio": False,
                    "plugins": {
                        "title": {
                            "display": True,
                            "text": f"Fallback {chart_type.title()} Chart"
                        }
                    }
                }
            }
            charts.append(basic_chart)
            print(f"DEBUG: Created basic fallback chart with {len(labels)} labels and {len(data_values)} data points")
        
        return charts