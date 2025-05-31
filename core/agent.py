from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent
from models import llm, get_database_connection
from prompts import SYSTEM_MESSAGE, PROPER_NOUN_SUFFIX
from tools import get_sql_tools, create_proper_noun_tool
from config import RECURSION_LIMIT
from .sql_executor import SQLExecutor
from .message_processor import MessageProcessor
from .insight_generator import InsightGenerator

class DataAnalystAgent:
    """Main agent class that coordinates data analysis tasks."""
    
    def __init__(self, use_proper_noun_tool=False, database_name=None):
        """Initialize the agent with optional configuration."""
        self.db = get_database_connection(database_name) if database_name else None
        self.use_proper_noun_tool = use_proper_noun_tool
        self.sql_executor = SQLExecutor(self.db)
        self.message_processor = MessageProcessor()
        self.insight_generator = InsightGenerator(self.db)
        self.agent = self._create_agent()
    
    def _create_agent(self):
        """Create the underlying agent with the specified configuration."""
        tools = get_sql_tools(self.db)
        system_prompt = SYSTEM_MESSAGE
        
        if self.use_proper_noun_tool:
            tools.append(create_proper_noun_tool(self.db))
            system_prompt = f"{SYSTEM_MESSAGE}\n\n{PROPER_NOUN_SUFFIX}"
        
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
        """Execute agent and return clean structured results with SQL, description, and data."""
        try:
            # First, let the agent explore the database and generate the query
            messages = self.execute(question, recursion_limit)
            
            # Extract SQL query from the agent's messages
            sql_query = self.message_processor.extract_sql_query(messages)
            
            # Execute the query
            data = []
            if sql_query:
                data = self.sql_executor.execute_query(sql_query)
            
            # Extract the initial description
            initial_description = ""
            final_response = self.message_processor.get_final_response(messages)
            if final_response:
                initial_description = self.message_processor.extract_description(final_response)
            
            # Create initial analysis result
            initial_analysis = {
                'sql': sql_query,
                'description': initial_description,
                'data': data,
                'question': question
            }
            
            # Generate enhanced insights
            enhanced_description = self.insight_generator.generate_enhanced_insights(
                original_question=question,
                sql_query=sql_query,
                data=data,
                previous_description=initial_description,
                previous_context=previous_context
            )
            
            # Create enhanced analysis result
            enhanced_analysis = {
                'sql': sql_query,
                'description': enhanced_description,
                'data': data,
                'question': question
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
                'initial_analysis': initial_description,  # Keep initial analysis for reference
                'enhanced_analysis': enhanced_description,  # Keep enhanced analysis for reference
                'summary': summary  # Include summary separately as well
            }
            
            return result
            
        except Exception as e:
            result = {
                'sql': '',
                'description': f'Error occurred: {str(e)}',
                'data': [],
                'question': question,
                'initial_analysis': '',
                'enhanced_analysis': '',
                'summary': f'Unable to generate summary due to error: {str(e)}'
            }
            return result

# Factory functions for backward compatibility
def create_agent(use_proper_noun_tool=False, database_name=None):
    """Create an agent with the specified configuration."""
    return DataAnalystAgent(use_proper_noun_tool, database_name)

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