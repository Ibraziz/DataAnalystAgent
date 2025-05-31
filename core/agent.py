from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import llm, get_database_connection
from prompts import SYSTEM_MESSAGE
from tools import get_sql_tools, create_chart_configuration_prompt
from config import RECURSION_LIMIT
from .sql_executor import SQLExecutor
from .message_processor import MessageProcessor
from .insight_generator import InsightGenerator
from .chart_processor import ChartProcessor

class DataAnalystAgent:
    """Main agent class that coordinates data analysis tasks."""
    
    def __init__(self, database_name=None):
        """Initialize the agent with optional configuration."""
        self.db = get_database_connection(database_name) if database_name else None
        self.sql_executor = SQLExecutor(self.db)
        self.message_processor = MessageProcessor()
        self.insight_generator = InsightGenerator(self.db)
        self.chart_processor = ChartProcessor()
        self.agent = self._create_agent()
    
    def _create_agent(self):
        """Create the underlying agent with the specified configuration."""
        tools = get_sql_tools(self.db)
        
        # Add visualization instructions to the system prompt
        chart_prompt = create_chart_configuration_prompt()
        system_prompt = f"{SYSTEM_MESSAGE}\n\n{chart_prompt}"
        
        return create_react_agent(llm, tools, prompt=system_prompt)
    
    def execute(self, question: str, recursion_limit: Optional[int] = None) -> List[Any]:
        """Execute the agent with a given question and return messages."""
        if recursion_limit is None:
            recursion_limit = RECURSION_LIMIT
        
        messages = []
        
        # Collect all messages from the stream
        for step in self.agent.stream(
            {"messages": [{"role": "user", "content": question}]},
            stream_mode="values",
            config={"recursion_limit": recursion_limit}
        ):
            if "messages" in step:
                messages.extend(step["messages"])
                # Print for debugging (optional)
                if step["messages"]:
                    step["messages"][-1].pretty_print()
        
        return messages
    
    def execute_with_results(
        self,
        question: str,
        recursion_limit: Optional[int] = None,
        previous_context: Optional[List[Dict[str, Any]]] = None,
        generate_summary: bool = False
    ) -> Dict[str, Any]:
        """Execute agent and return clean structured results with SQL, description, data, and charts."""
        try:
            # First, let the agent explore the database and generate the query
            messages = self.execute(question, recursion_limit)
            
            # Extract SQL query from the agent's messages
            sql_query = self.message_processor.extract_sql_query(messages)
            
            # Execute the query
            data = []
            if sql_query:
                data = self.sql_executor.execute_query(sql_query)
            
            # Extract the initial description and look for charts
            initial_description = ""
            all_response_text = ""
            
            # Collect all AI message content for chart extraction
            for msg in messages:
                if hasattr(msg, 'content') and msg.content and msg.content.strip():
                    all_response_text += msg.content + "\n"
            
            # Get the final response for description
            final_response = self.message_processor.get_final_response(messages)
            if final_response:
                initial_description = self.message_processor.extract_description(final_response)
            
            # Extract charts from all response text
            initial_charts = self.chart_processor.extract_charts_from_response(all_response_text)
            
            # Create initial analysis result
            initial_analysis = {
                'sql': sql_query,
                'description': initial_description,
                'data': data,
                'question': question,
                'charts': initial_charts
            }
            
            # Generate enhanced insights with charts
            enhanced_result = self.insight_generator.generate_enhanced_insights_with_charts(
                original_question=question,
                sql_query=sql_query,
                data=data,
                previous_description=initial_description,
                previous_context=previous_context
            )
            
            # Merge charts from both initial and enhanced analysis, avoiding duplicates
            all_charts = []
            seen_charts = set()  # Track unique charts
            def chart_to_key(chart: Dict[str, Any]) -> str:
                """Convert a chart config to a unique string key."""
                try:
                    # Create a key based on chart type and data
                    chart_type = chart.get('type', '')
                    data = chart.get('data', {})
                    labels = tuple(data.get('labels', []))
                    
                    datasets = []
                    for dataset in data.get('datasets', []):
                        dataset_data = tuple(dataset.get('data', []))
                        dataset_label = dataset.get('label', '')
                        datasets.append((dataset_label, dataset_data))
                        
                        return f"{chart_type}:{labels}:{tuple(datasets)}"
                except Exception:
                    # If any error occurs, fall back to string representation
                    return str(chart)
            
            # Add initial charts
            for chart in initial_charts:
                chart_key = chart_to_key(chart)
                if chart_key not in seen_charts:
                    seen_charts.add(chart_key)
                    all_charts.append(chart)
            
            # Add enhanced charts, avoiding duplicates
            enhanced_charts = enhanced_result.get('charts', [])
            for chart in enhanced_charts:
                chart_key = chart_to_key(chart)
                if chart_key not in seen_charts:
                    seen_charts.add(chart_key)
                    all_charts.append(chart)
            
            # Create enhanced analysis result
            enhanced_analysis = {
                'sql': sql_query,
                'description': enhanced_result.get('description', initial_description),
                'data': data,
                'question': question,
                'charts': all_charts
            }
            
            # Prepare context for summary generation
            summary_context = []
            if previous_context:
                summary_context.extend(previous_context)
            summary_context.extend([initial_analysis, enhanced_analysis])
            
            # Generate contextual summary
            summary = self.insight_generator.generate_contextual_summary(
                current_analysis=enhanced_analysis,
                previous_context=summary_context,
                original_question=question
            )
            
            # Prepare the final result dictionary
            result = {
                'sql': sql_query,
                'description': summary,  # Use the contextual summary as the main description
                'data': data,
                'question': question,
                'charts': all_charts,  # Include all unique charts
                'initial_analysis': initial_description,  # Keep initial analysis for reference
                'enhanced_analysis': enhanced_result.get('description', ''),  # Keep enhanced analysis for reference
                'summary': summary  # Include summary separately as well
            }
            
            return result
            
        except Exception as e:
            result = {
                'sql': '',
                'description': f'Error occurred: {str(e)}',
                'data': [],
                'question': question,
                'charts': [],
                'initial_analysis': '',
                'enhanced_analysis': '',
                'summary': f'Unable to generate summary due to error: {str(e)}'
            }
            return result

# Factory functions for backward compatibility
def create_agent(database_name=None):
    """Create an agent with the specified configuration."""
    return DataAnalystAgent(database_name)

def execute_agent(agent, question, recursion_limit=None):
    """Execute the agent with a given question and return messages."""
    if isinstance(agent, DataAnalystAgent):
        return agent.execute(question, recursion_limit)
    else:
        # Handle legacy agent type
        if recursion_limit is None:
            recursion_limit = RECURSION_LIMIT
        
        messages = []
        for step in agent.stream(
            {"messages": [{"role": "user", "content": question}]},
            stream_mode="values",
            config={"recursion_limit": recursion_limit}
        ):
            if "messages" in step:
                messages.extend(step["messages"])
                if step["messages"]:
                    step["messages"][-1].pretty_print()
        return messages

def execute_agent_with_results(agent, question, database_connection=None, recursion_limit=None, previous_context=None, generate_summary=False):
    """Execute agent and return clean structured results."""
    if isinstance(agent, DataAnalystAgent):
        return agent.execute_with_results(
            question,
            recursion_limit,
            previous_context,
            generate_summary
        )
    else:
        # Handle legacy agent type
        agent_instance = DataAnalystAgent(database_name=database_connection)
        return agent_instance.execute_with_results(
            question,
            recursion_limit,
            previous_context,
            generate_summary
        ) 