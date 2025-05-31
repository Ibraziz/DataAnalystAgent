from core.agent import create_agent, execute_agent

def main():
    # Create agent
    agent = create_agent()
    
    # Example question
    question = "Which 10 products have generated the most revenue?"
    
    # Execute agent
    execute_agent(agent, question)

if __name__ == "__main__":
    main() 