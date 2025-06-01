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
            
            # Extract charts from initial response
            initial_charts = self.chart_processor.extract_charts_from_response(all_response_text)
            
            # Create initial analysis result
            initial_analysis = {
                'sql': sql_query,
                'description': initial_description,
                'data': data,
                'question': question
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
            seen_fingerprints = set()
            
            def create_chart_fingerprint(chart: Dict[str, Any]) -> str:
                """Create a unique fingerprint for a chart to detect duplicates."""
                try:
                    # Handle both structures
                    chart_config = chart
                    if 'chart_config' in chart:
                        chart_config = chart['chart_config']
                    
                    # Create fingerprint based on chart type and data
                    chart_type = chart_config.get('type', '')
                    data = chart_config.get('data', {})
                    labels = tuple(sorted(data.get('labels', [])))
                    
                    # Create fingerprint from datasets
                    datasets_fingerprint = []
                    for dataset in data.get('datasets', []):
                        dataset_data = tuple(sorted([str(x) for x in dataset.get('data', [])]))
                        dataset_label = dataset.get('label', '')
                        datasets_fingerprint.append((dataset_label, dataset_data))
                    
                    fingerprint = f"{chart_type}:{labels}:{tuple(sorted(datasets_fingerprint))}"
                    return fingerprint
                except Exception as e:
                    print(f"DEBUG: Error creating chart fingerprint: {e}")
                    # Fallback to string representation
                    return str(chart)
            
            def add_unique_chart(chart: Dict[str, Any], source: str):
                """Add a chart if it's not a duplicate."""
                fingerprint = create_chart_fingerprint(chart)
                if fingerprint not in seen_fingerprints:
                    seen_fingerprints.add(fingerprint)
                    all_charts.append(chart)
                    print(f"DEBUG: Added unique chart from {source}")
                    return True
                else:
                    print(f"DEBUG: Skipped duplicate chart from {source}")
                    return False
            
            # Add initial charts (typically fewer, more direct)
            print(f"DEBUG: Processing {len(initial_charts)} initial charts")
            for chart in initial_charts:
                add_unique_chart(chart, "initial")
            
            # Add enhanced charts (typically more analytical/secondary)
            enhanced_charts = enhanced_result.get('charts', [])
            print(f"DEBUG: Processing {len(enhanced_charts)} enhanced charts")
            for chart in enhanced_charts:
                add_unique_chart(chart, "enhanced")
            
            print(f"DEBUG: Total unique charts after merging: {len(all_charts)}")
            
            # Create enhanced analysis result
            enhanced_analysis = {
                'sql': sql_query,
                'description': enhanced_result.get('description', initial_description),
                'data': data,
                'question': question
            }
            
            # Generate contextual summary only if requested
            summary = ""
            if generate_summary:
                # Prepare context for summary generation
                summary_context = []
                if previous_context:
                    summary_context.extend(previous_context)
                summary_context.extend([initial_analysis, enhanced_analysis])
                
                summary = self.insight_generator.generate_contextual_summary(
                    current_analysis=enhanced_analysis,
                    previous_context=summary_context,
                    original_question=question
                )
            
            # Prioritize and preserve the initial detailed description
            final_description = initial_description
            enhanced_description = enhanced_result.get('description', '')
            
            print(f"DEBUG: Initial description length: {len(initial_description) if initial_description else 0}")
            print(f"DEBUG: Enhanced description length: {len(enhanced_description) if enhanced_description else 0}")
            print(f"DEBUG: Initial description preview: {initial_description[:100] if initial_description else 'None'}...")
            print(f"DEBUG: Enhanced description preview: {enhanced_description[:100] if enhanced_description else 'None'}...")
            
            # Strategy: Always preserve initial description, only supplement if enhanced adds real value
            if initial_description:
                # We have a good initial description, use it as the base
                final_description = initial_description
                
                # Only add enhanced if it's substantial and not metadata
                if (enhanced_description and 
                    len(enhanced_description.strip()) > 100 and 
                    not self._is_chart_metadata(enhanced_description) and
                    enhanced_description != initial_description):
                    
                    print("DEBUG: Adding enhanced description as supplement")
                    final_description = f"## Additional Insights\n{enhanced_description}"
                else:
                    print("DEBUG: Enhanced description not suitable for supplementing, keeping initial only")
                    
            elif enhanced_description and not self._is_chart_metadata(enhanced_description):
                # No initial description, but enhanced is good
                print("DEBUG: Using enhanced description as primary (no initial found)")
                final_description = enhanced_description
            else:
                # Fallback
                print("DEBUG: Using fallback description")
                final_description = "Analysis completed successfully."
            
            print(f"DEBUG: Final description length: {len(final_description)}")
            print(f"DEBUG: Using description source: {'initial' if final_description == initial_description else 'combined' if '## Additional Insights' in final_description else 'enhanced' if final_description == enhanced_description else 'fallback'}")
            
            # Prepare the final result dictionary
            result = {
                'sql': sql_query,
                'description': final_description,
                'data': data,
                'question': question,
                'charts': all_charts,  # Include all unique charts
            }
            
            # Add optional fields
            if summary:
                result['summary'] = summary
                
            if initial_description:
                result['initial_analysis'] = initial_description
                
            if enhanced_result.get('description'):
                result['enhanced_analysis'] = enhanced_result['description']
            
            print(f"DEBUG: Final result contains {len(all_charts)} charts")
            
            return result
            
        except Exception as e:
            print(f"ERROR in execute_with_results: {str(e)}")
            result = {
                'sql': '',
                'description': f'Error occurred: {str(e)}',
                'data': [],
                'question': question,
                'charts': [],
            }
            if generate_summary:
                result['summary'] = f'Unable to generate summary due to error: {str(e)}'
            return result
    
    def _is_chart_metadata(self, text: str) -> bool:
        """Check if text is just chart configuration metadata."""
        if not text or len(text.strip()) < 50:
            return True
        
        # Check for chart metadata indicators
        metadata_indicators = [
            "Chart.js configurations",
            "chart configurations", 
            "Here's an analysis",
            "presented with Chart.js",
            "visualization configurations",
            "```json",
            "chart.js format",
            "with Chart.js",
            "chart objects"
        ]
        
        # Check if text is mostly just a list without detailed analysis
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) <= 3 and any(indicator in text.lower() for indicator in metadata_indicators):
            return True
        
        # Check if text is just a simple list without business insights
        if (len(text) < 200 and 
            text.count(':') > 3 and 
            any(word in text.lower() for word in ['generated', 'revenue', 'products']) and
            'analysis' not in text.lower() and
            'insight' not in text.lower()):
            return True
        
        return any(indicator in text.lower() for indicator in metadata_indicators)

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