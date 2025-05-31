# 🤖 SQL Data Analytics Agent

**DataAnalystAgent** is an autonomous AI agent that leverages the power of Google models to analyze datasets, generate summaries, and answer questions about your data. With a natural language interface, it empowers users to gain insights from a database without writing a single line of code.

## ✨ Features

- 📊 Upload and analyze your own SQL databases
- 🗣️ Ask natural language questions about your data
- 📝 Generates SQL queries and natural language summaries
- 📈 Automatically creates data visualizations (bar, pie, line, scatter, etc.)
- ⚙️ Built with LangChain, Google Generative AI, and Flask
- 🧩 Modular agent and tool architecture

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/DataAnalystAgent.git
cd DataAnalystAgent
```
![step1](C:\Users\pinku\Downloads\Hackathon\DataAnalystAgent\images\step1.png)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

![step2](C:\Users\pinku\Downloads\Hackathon\DataAnalystAgent\images\step2.png)

### 3. Prepare your database

- Place your SQLite database file in the `database/` folder.
- Example databases: `Chinook_Sqlite.sql`,`Northwind_Sqlitesql`

![step3](C:\Users\pinku\Downloads\Hackathon\DataAnalystAgent\images\step3.png)

### 4. Run the agent

```bash
python app.py
```

![step5](C:\Users\pinku\Downloads\Hackathon\DataAnalystAgent\images\step5.png)

- The agent will prompt you for a question or run the existing example in `app.py`.
- Visualizations will be displayed using HTML & CSS.

![step6](C:\Users\pinku\Downloads\Hackathon\DataAnalystAgent\images\step1.png)
---

## 🗂️ Project Structure

```
DataAnalystAgent/
│
├── core/                   # Core logic for agent orchestration, SQL execution, and insight generation
├── database/               # Example and user-uploaded databases
|── utils/                  # Utility functions and helpers used across the project
├── templates/              # HTML templates for web interface (if used)
├── __init__.py             # Marks the directory as a Python package
├── agent_types.py          # Defines different agent types and their configurations
├── app.py                  # Flask web application entry point (for web interface)
├── config.py               # Configuration settings (database, dialect, etc.)
├── main.py                 # Command-line entry point for running the agent
├── models.py               # LLM model configuration and setup
├── prompts.py              # System and tool prompts for the agent
├── requirements.txt        # Python dependencies
├── schemas.py              # Database schema definitions and helpers
├── tools.py                # Tool definitions (SQL, visualization, etc.)
├── README.md               # This file
└── ...
```

---

## 🧑‍💻 Usage Example

Ask a question like:

> "What is the average value of an order for each customer segment over the past year? don't limit the query result"

The agent will:
1. Generate and execute the SQL query.
2. Return a summary and a visualization (e.g., bar chart).

---

![step9]((C:\Users\pinku\Downloads\Hackathon\DataAnalystAgent\images\step9.png))
![step8]((C:\Users\pinku\Downloads\Hackathon\DataAnalystAgent\images\step8.png))
![step7]((C:\Users\pinku\Downloads\Hackathon\DataAnalystAgent\images\step7.png))

## 🛠️ Customization

- **Add new tools:** Extend `tools.py` for more capabilities.
- **Change prompts:** Edit `prompts.py` for different agent behaviors.
- **Web interface:** Use `app.py` and `templates/` for a Flask-based UI.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Pull requests and issues are welcome!

---

## 📬 Contact

For questions or support, open an issue or contact the maintainer.
