from typing import List, Dict, Any, Optional
import json
import re
from models import llm
from config import RECURSION_LIMIT, DIALECT
from langgraph.prebuilt import create_react_agent
from tools import get_sql_tools, create_chart_configuration_prompt
from langchain_core.messages import AIMessage
from .chart_processor import ChartProcessor

class InsightGenerator:
    """Generates enhanced insights and visualizations from data analysis results."""
    
    def __init__(self, db=None):
        """Initialize the insight generator."""
        self.db = db
        self.chart_processor = ChartProcessor()
    
    def generate_enhanced_insights_with_charts(
        self,
        original_question: str,
        sql_query: str,
        data: List[Dict[str, Any]],
        previous_description: Optional[str] = None,
        previous_context: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Generate enhanced insights and chart configurations from analysis results."""
        try:
            if not data or not sql_query:
                return {"description": "", "charts": []}
            
            print(f"DEBUG: Enhanced insights - Previous description length: {len(previous_description) if previous_description else 0}")
            
            # If we already have a substantial previous description, only generate charts
            if previous_description and len(previous_description) > 1000:
                print("DEBUG: Substantial previous description exists, generating charts only")
                chart_result = self._generate_charts_only(original_question, sql_query, data, previous_description)
                # Return empty description to preserve the original
                return {
                    "description": "",
                    "charts": chart_result.get("charts", [])
                }
            
            # If previous description is minimal, generate both insights and charts
            return self._generate_full_insights_and_charts(
                original_question, sql_query, data, previous_description, previous_context
            )
            
        except Exception as e:
            print(f"Error in generate_enhanced_insights_with_charts: {e}")
            return {
                "description": "",
                "charts": []
            }
    
    def _generate_charts_only(
        self,
        original_question: str,
        sql_query: str,
        data: List[Dict[str, Any]],
        previous_description: str
    ) -> Dict[str, Any]:
        """Generate only chart configurations when we already have good analysis."""
        try:
            print("DEBUG: Generating charts only, preserving existing description")
            
            # Create data summary
            data_summary = data[:5] if len(data) > 5 else data
            
            chart_prompt = f"""
You are a data visualization expert. Create Chart.js chart configurations using the ACTUAL DATA provided.

Question: {original_question}
SQL Query: {sql_query}
Complete Data: {json.dumps(data_summary, indent=2)}
Data Columns: {list(data_summary[0].keys()) if data_summary else []}

**CRITICAL**: Use the ACTUAL values from the data above. Extract real labels and values from the Complete Data.


{create_chart_configuration_prompt()}

**Chart Creation Instructions**:
1. Look at the data columns and values
2. Choose appropriate columns for labels (usually first column or names)
3. Choose appropriate columns for data values (usually numeric columns)
4. Use REAL data values, not placeholders
5. Create meaningful chart titles based on the actual data

**Output Format**: Return ONLY a JSON array in ```json``` blocks.

CRITICAL: Use ACTUAL data values, not placeholders. Extract real labels and numbers from the Complete Data above.
"""
            
            response = llm.invoke(chart_prompt)
            
            if hasattr(response, 'content'):
                full_response = response.content.strip()
            else:
                full_response = str(response).strip()
            
            print(f"DEBUG: Charts-only response length: {len(full_response)}")
            
            # Extract charts only
            charts = self.chart_processor.extract_charts_from_response(full_response)
            
            print(f"DEBUG: Extracted {len(charts)} charts from charts-only generation")
            
            return {
                "description": "",  # Explicitly empty to preserve existing description
                "charts": charts
            }
            
        except Exception as e:
            print(f"Error in _generate_charts_only: {e}")
            return {"description": "", "charts": []}
    
    def _generate_full_insights_and_charts(
        self,
        original_question: str,
        sql_query: str,
        data: List[Dict[str, Any]],
        previous_description: Optional[str] = None,
        previous_context: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Generate full business insights and charts when no substantial previous description exists."""
        try:
            # Create a summary of the data for context
            data_summary = []
            if len(data) <= 5:
                data_summary = data
            else:
                data_summary = data[:3] + [{"...": f"and {len(data) - 3} more rows"}]
            
            # Build the context
            context_parts = [
                f"Original Question: {original_question}",
                f"SQL Query Used: {sql_query}",
                f"Query Results: {json.dumps(data_summary, indent=2)}"
            ]
            
            if previous_description and previous_description.strip():
                context_parts.append(f"Initial Analysis: {previous_description}")
            
            context_string = "\n".join(context_parts)
            
            # STEP 1: Generate detailed insights with inferences (separate LLM call)
            insight_prompt = f"""
You are a senior data analyst providing comprehensive insights. Your task is to analyze the data and provide valuable business context, inferences, and actionable insights.

**Your Analysis Should Include:**

1. **Data Context & Background**: What this data represents and why it matters
2. **Key Insights**: What the data reveals about patterns, trends, or performance
3. **Industry Context**: Relevant industry knowledge or benchmarks
4. **Inferences**: What can be inferred from the results using common knowledge
5. **Business Implications**: What this means for decision-making

**Guidelines:**
- Provide 2-4 concise paragraphs of analysis
- Use specific data points to support your insights
- Include relevant industry context or common knowledge
- Make meaningful inferences beyond just stating the numbers
- Focus on actionable insights and business value
- You can reference general industry knowledge or trends
- Avoid repetitive data listing - synthesize and interpret instead

**Context and Data:**
{context_string}

Provide a comprehensive analysis that goes beyond the raw data to deliver valuable business insights and context.
"""
            
            # Use the LLM for detailed insights
            insight_response = llm.invoke(insight_prompt)
            
            if hasattr(insight_response, 'content'):
                business_insights = insight_response.content.strip()
            else:
                business_insights = str(insight_response).strip()
            
            print(f"DEBUG: Generated detailed insights with {len(business_insights)} characters")
            
            # STEP 2: Generate ONLY charts (separate LLM call)
            # Use complete data for charts, not just sample
            complete_data = data if len(data) <= 20 else data[:20]  # Use more data for charts
            
            chart_prompt = f"""
You are a data visualization expert. Create Chart.js chart configurations using the ACTUAL DATA provided.

Question: {original_question}
SQL Query: {sql_query}
Complete Data: {json.dumps(complete_data, indent=2)}
Data Columns: {list(complete_data[0].keys()) if complete_data else []}

**CRITICAL**: Use the ACTUAL values from the data above. Extract real labels and values from the Complete Data.

{create_chart_configuration_prompt()}

**Chart Creation Instructions**:
1. Look at the data columns and values
2. Choose appropriate columns for labels (usually first column or names)
3. Choose appropriate columns for data values (usually numeric columns)
4. Use REAL data values, not placeholders
5. Create meaningful chart titles based on the actual data


CRITICAL: Use ACTUAL data values, not placeholders. Extract real labels and numbers from the Complete Data above.
"""
            
            # Use the LLM for charts only
            chart_response = llm.invoke(chart_prompt)
            
            if hasattr(chart_response, 'content'):
                chart_content = chart_response.content.strip()
            else:
                chart_content = str(chart_response).strip()
            
            # Extract charts from the chart response
            charts = self.chart_processor.extract_charts_from_response(chart_content)
            
            return {
                "description": business_insights,
                "charts": charts
            }
            
        except Exception as e:
            print(f"Error in _generate_full_insights_and_charts: {e}")
            return {"description": "", "charts": []}
    
    def _extract_business_insights(self, response_text: str) -> str:
        """Extract business insights from response, excluding chart configurations."""
        if not response_text:
            return ""
        
        # Split response into lines
        lines = response_text.split('\n')
        insight_lines = []
        in_json_block = False
        
        for line in lines:
            # Check for start/end of JSON blocks
            if '```json' in line.lower():
                in_json_block = True
                continue
            elif '```' in line and in_json_block:
                in_json_block = False
                continue
            
            # Skip lines inside JSON blocks
            if in_json_block:
                continue
            
            # Skip lines that look like chart metadata
            if any(phrase in line.lower() for phrase in [
                'chart.js', 'chart configuration', 'visualization', 
                'here\'s an analysis', 'chart configs', 'json'
            ]):
                continue
            
            # Keep meaningful content
            if line.strip():
                insight_lines.append(line)
        
        insights = '\n'.join(insight_lines).strip()
        
        # Clean up any remaining artifacts
        insights = re.sub(r'```.*?```', '', insights, flags=re.DOTALL)
        insights = re.sub(r'\n\s*\n', '\n\n', insights)
        
        return insights.strip()
    
    def generate_contextual_summary(
        self,
        current_analysis: Dict[str, Any],
        previous_context: Optional[List[Dict[str, Any]]] = None,
        original_question: Optional[str] = None
    ) -> str:
        """Generate a comprehensive summary combining current and previous analysis."""
        try:
            # Prepare the context for the summary prompt
            context_parts = []
            
            if original_question:
                context_parts.append(f"Original Question: {original_question}")
            
            # Add previous context if available
            if previous_context:
                context_parts.append("\n=== Previous Context ===")
                if isinstance(previous_context, list):
                    for i, context_item in enumerate(previous_context, 1):
                        if isinstance(context_item, dict):
                            context_parts.append(f"\nPrevious Analysis {i}:")
                            if context_item.get('question'):
                                context_parts.append(f"Question: {context_item['question']}")
                            if context_item.get('description'):
                                context_parts.append(f"Findings: {context_item['description']}")
                            if context_item.get('sql'):
                                context_parts.append(f"Query Used: {context_item['sql']}")
                        elif isinstance(context_item, str):
                            context_parts.append(f"\nPrevious Context {i}: {context_item}")
                else:
                    context_parts.append(f"\nPrevious Context: {previous_context}")
            
            # Add current analysis
            context_parts.append("\n=== Current Analysis ===")
            if current_analysis.get('description'):
                context_parts.append(f"Current Findings: {current_analysis['description']}")
            if current_analysis.get('sql'):
                context_parts.append(f"Current Query: {current_analysis['sql']}")
            
            # Create data summary for context
            current_data = current_analysis.get('data', [])
            if current_data:
                if len(current_data) <= 3:
                    data_summary = current_data
                else:
                    data_summary = current_data[:2] + [{"...": f"and {len(current_data) - 2} more rows"}]
                context_parts.append(f"Current Data Sample: {json.dumps(data_summary, indent=2)}")
            
            context_string = "\n".join(context_parts)
            
            # NUCLEAR BRIEF SUMMARY TOO!
            summary_prompt = f"""
You are a senior data analyst providing comprehensive insights. Your task is to analyze the data and provide valuable business context, inferences, and actionable insights.

**Your Analysis Should Include:**

1. **Data Context & Background**: What this data represents and why it matters
2. **Key Insights**: What the data reveals about patterns, trends, or performance
3. **Industry Context**: Relevant industry knowledge or benchmarks
4. **Inferences**: What can be inferred from the results using common knowledge or web search
5. **Business Implications**: What this means for decision-making

**Guidelines:**
- Provide bullet points of insights under headers.
- Try not to make paragraphs.
- Use specific data points to support your insights
- Include relevant industry context or common knowledge
- Make meaningful inferences beyond just stating the numbers (using numbers occasionally is fina as well)
- Focus on actionable insights and business value
- You can reference general industry knowledge or trends

**Context and Data:**
{context_string}

Provide a comprehensive analysis that goes beyond the raw data to deliver valuable business insights and context.
"""
            
            # Use the LLM to generate the summary
            response = llm.invoke(summary_prompt)
            
            if hasattr(response, 'content'):
                summary = response.content.strip()
            else:
                summary = str(response).strip()
            
            # Clean up the summary
            summary = self._clean_description(summary)
            
            return summary if summary else "Analysis completed successfully."
            
        except Exception as e:
            print(f"Error generating contextual summary: {e}")
            return f"Unable to generate contextual summary: {str(e)}"
    
    def _clean_description(self, text: str) -> str:
        """Clean up description text by removing code blocks and tool calls."""
        if not text:
            return ""
        
        # Remove code blocks
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'Calling tool:.*?(?=\n)', '', text, flags=re.DOTALL)
        text = re.sub(r'Tool.*?returned:.*?(?=\n)', '', text, flags=re.DOTALL)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()