import os
import sys
from agent import create_agent, execute_agent

def main():
    # Create agent (without proper noun tool for this example)
    agent = create_agent(use_proper_noun_tool=False)
    
    # Example question
    question = "Which 10 products have generated the most revenue?"
    
    # Execute agent
    execute_agent(agent, question)

if __name__ == "__main__":
    main() 