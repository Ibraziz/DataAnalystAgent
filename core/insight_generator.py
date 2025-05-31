from typing import List, Dict, Any, Optional
import json
import re
from models import llm
from config import RECURSION_LIMIT, DIALECT
from langgraph.prebuilt import create_react_agent
from tools import get_sql_tools
from langchain_core.messages import AIMessage

class InsightGenerator:
    """Handles generation of insights and summaries from query results."""
    
    def __init__(self, database_connection=None):
        """Initialize with optional database connection."""
        self.db = database_connection
    
    def generate_enhanced_insights(
        self,
        original_question: str,
        sql_query: str,
        data: List[Dict[str, Any]],
        previous_description: Optional[str] = None,
        previous_context: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Generate enhanced insights from query results."""
        try:
            if not data or not sql_query:
                return "No data available for analysis."
            
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
            
            # Create an agent for generating insights
            tools = get_sql_tools(self.db)
            insight_agent = create_react_agent(llm, tools, prompt=f"""
You are a data analyst expert. Given the original question and previous analysis,
your task is to explore the database and find additional interesting insights that complement the original query results, just provide one more additional insight.

Focus on:
1. Creating a syntactically correct {DIALECT} query to run
2. Look at the results of the query and provide a detailed answer
3. the query should retrieve interesting information like Trends, patterns, statistical insights or anomalies in the data.

Provide a comprehensive analysis with specific findings. Execute additional queries as needed to gather supporting information, but focus on generating insights rather than just showing raw data.

Use the previous analysis as context to build upon and provide complementary insights.

{context_string}

Generate enhanced insights and analysis based on this information.
""")
            
            # Execute the insight generation
            from .agent import execute_agent
            insight_messages = execute_agent(
                insight_agent, 
                f"Analyze the results and provide enhanced insights for: {original_question}",
                recursion_limit=RECURSION_LIMIT
            )
            
            # Extract the enhanced description
            enhanced_description = ""
            for msg in reversed(insight_messages):
                if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                    if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                        enhanced_description = msg.content.strip()
                        break
            
            # Clean up the description
            if enhanced_description:
                enhanced_description = re.sub(r'```sql.*?```', '', enhanced_description, flags=re.DOTALL | re.IGNORECASE)
                enhanced_description = re.sub(r'```[a-zA-Z]*\n.*?```', '', enhanced_description, flags=re.DOTALL)
                enhanced_description = re.sub(r'Calling tool:.*?(?=\n)', '', enhanced_description, flags=re.DOTALL)
                enhanced_description = re.sub(r'Tool.*?returned:.*?(?=\n)', '', enhanced_description, flags=re.DOTALL)
                enhanced_description = re.sub(r'\n\s*\n', '\n', enhanced_description)
                enhanced_description = enhanced_description.strip()
                
                if len(enhanced_description) < 50:
                    for msg in reversed(insight_messages):
                        if isinstance(msg, AIMessage) and msg.content and len(msg.content.strip()) > 50:
                            backup_desc = re.sub(r'```sql.*?```', '', msg.content, flags=re.DOTALL | re.IGNORECASE)
                            backup_desc = backup_desc.strip()
                            if len(backup_desc) > 50:
                                enhanced_description = backup_desc
                                break
            
            return enhanced_description if enhanced_description and len(enhanced_description) > 10 else "Analysis completed successfully with the provided data."
            
        except Exception as e:
            return f"Unable to generate enhanced insights: {str(e)}"
    
    def generate_contextual_summary(
        self,
        current_analysis: Dict[str, Any],
        previous_context: Optional[List[Dict[str, Any]]] = None,
        original_question: Optional[str] = None
    ) -> str:
        """Generate a comprehensive summary combining current analysis with previous context."""
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
            summary = re.sub(r'\n\s*\n', '\n\n', summary)
            
            return summary if summary else "Summary generation completed successfully."
            
        except Exception as e:
            return f"Unable to generate contextual summary: {str(e)}" 