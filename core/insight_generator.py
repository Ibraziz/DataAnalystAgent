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
                return {"description": "No data available for analysis.", "charts": []}
            
            # Create a summary of the data for context
            data_summary = []
            if len(data) <= 5:
                data_summary = data
            else:
                data_summary = data[:3] + [{"...": f"and {len(data) - 3} more rows"}]
            
            # Build the context with previous description if available
            context_parts = [
                f"Original Question: {original_question}",
                f"Original SQL Query: {sql_query}",
                f"Sample Results: {json.dumps(data_summary, indent=2)}"
            ]
            
            if previous_description and previous_description.strip():
                context_parts.insert(-1, f"Previous Analysis: {previous_description}")
            
            context_string = "\n".join(context_parts)
            
            # Create an agent for generating insights with chart requirements
            tools = get_sql_tools(self.db)
            chart_prompt = create_chart_configuration_prompt()
            insight_agent = create_react_agent(llm, tools, prompt=f"""
You are a data analyst expert. Given the original question and previous analysis,
your task is to explore the database and find additional interesting insights that complement the original query results.

Focus on:
1. Creating a syntactically correct {DIALECT} query to run
2. Look at the results of the query and provide a detailed answer
3. The query should retrieve interesting information like trends, patterns, statistical insights or anomalies in the data

{chart_prompt}

Use the previous analysis as context to build upon and provide complementary insights with appropriate visualizations.

{context_string}

Generate enhanced insights and chart configurations based on this information.
""")
            
            # Execute the insight generation
            insight_messages = []
            for step in insight_agent.stream(
                {"messages": [{"role": "user", "content": f"Analyze the results, provide enhanced insights, and create chart visualizations for: {original_question}"}]},
                stream_mode="values",
                config={"recursion_limit": RECURSION_LIMIT}
            ):
                if "messages" in step:
                    insight_messages.extend(step["messages"])
            
            # Extract the enhanced description and charts from the insight agent's response
            enhanced_description = ""
            all_response_text = ""
            
            for msg in insight_messages:
                if hasattr(msg, 'content') and msg.content and msg.content.strip():
                    all_response_text += msg.content + "\n"
            
            # Get the final response for description
            for msg in reversed(insight_messages):
                if hasattr(msg, 'content') and msg.content and msg.content.strip():
                    # Check if this is a final response (not just a tool call)
                    if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                        enhanced_description = msg.content.strip()
                        break
            
            # Extract charts from all response text
            charts = self.chart_processor.extract_charts_from_response(all_response_text)
            
            # Clean up the description
            if enhanced_description:
                # Remove code blocks from description
                enhanced_description = self._clean_description(enhanced_description)
            
            return {
                "description": enhanced_description if enhanced_description and len(enhanced_description) > 10 else "Analysis completed successfully with the provided data.",
                "charts": charts
            }
            
        except Exception as e:
            print(f"Error in generate_enhanced_insights_with_charts: {e}")
            return {
                "description": f"Unable to generate enhanced insights: {str(e)}",
                "charts": []
            }
    
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
            
            # Create summary prompt
            summary_prompt = f"""
You data analyst creating a comprehensive concise summary. 

Your task is to analyze all the provided information and create a cohesive, insightful summary that:
- start your words by explaining what the query do, then continue to other findings
- Focus on business value and actionable insights
- Highlight any contradictions or confirmations between previous and current findings
- Use specific data points and numbers to support your conclusions
- Keep the summary concise but comprehensive (aim for 2-3 paragraphs)
- Avoid repeating the same information - synthesize and add value

Context and Data:
{context_string}

Generate a comprehensive executive summary based on all the above information, provide the information in a clear form as a human.
"""
            
            # Use the LLM to generate the summary
            response = llm.invoke(summary_prompt)
            
            if hasattr(response, 'content'):
                summary = response.content.strip()
            else:
                summary = str(response).strip()
            
            # Clean up the summary
            summary = self._clean_description(summary)
            
            return summary if summary else "Summary generation completed successfully."
            
        except Exception as e:
            return f"Unable to generate contextual summary: {str(e)}"
    
    def _clean_description(self, text: str) -> str:
        """Clean up description text by removing code blocks and tool calls."""
        import re
        
        # Remove code blocks
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'Calling tool:.*?(?=\n)', '', text, flags=re.DOTALL)
        text = re.sub(r'Tool.*?returned:.*?(?=\n)', '', text, flags=re.DOTALL)
        text = re.sub(r'\n\s*\n', '\n', text)
        
        return text.strip() 