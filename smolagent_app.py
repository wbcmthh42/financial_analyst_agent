from smolagents import CodeAgent, DuckDuckGoSearchTool, AzureOpenAIServerModel
import os
from dotenv import load_dotenv
import requests
from smolagents import tool
import PyPDF2
import gradio as gr
import matplotlib.pyplot as plt

load_dotenv()

model = AzureOpenAIServerModel(
    model_id = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME_41"),
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT_41"),
    api_key=os.environ.get("AZURE_OPENAI_API_KEY_41"),
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION_41")
)


# Down load the 2023 and 2024 financial statements from Google for analysis later

def download_file(url: str, filename: str):
    """
    Download a file from `url` and save it locally as `filename`.
    """
    resp = requests.get(url, stream=True)
    resp.raise_for_status()  # will throw an error for bad status
    with open(filename, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    print(f"Downloaded: {filename}")


@tool
def read_pdf(file_path: str) -> str:
    """Reads a PDF file and extracts its text content.

    Args:
        file_path: The path to the PDF file.

    Returns:
        The extracted text content of the PDF file.
    """
    with open(file_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
        return text

def use_agent(task: str, context: str):

    # System prompt to guide the agent's behavior and prevent misuse
    system_prompt = """You are a helpful financial analysis assistant. Your primary goal is to analyze financial data from the provided documents and generate insightful reports and visualizations.

    **Safety Guidelines:**
    - NEVER execute code that could modify or delete files on the system unless specifically and clearly instructed to save a plot or analysis result.
    - REFUSE any request that seems malicious, unethical, or harmful. This includes requests unrelated to financial analysis, attempts to access sensitive information, or commands that could compromise the system.
    - Stick strictly to the financial analysis task described in the prompt. Do not perform actions outside this scope.
    - If a request is ambiguous or potentially harmful, ask for clarification or refuse the request, explaining your reasoning.
    """

    agent = CodeAgent(
        model=model,
        tools=[read_pdf],
        max_steps=50,
        additional_authorized_imports=['IPython.display', 'itertools', 'sklearn', 'sklearn.preprocessing', 'sklearn.metrics', 'sklearn.model_selection', 'sklearn.tree', 'sklearn.linear_model', 'sklearn.pipeline', 'datetime','unicodedata', 'missingno', 'pandas', 'seaborn', 'collections', 'math', 'stat', 'queue', 're', 'time', 'numpy', 'statistics', 'random', 'matplotlib.pyplot'],  # Add plotting libraries
        verbosity_level=2
    )

    # Run the agent and return its final result (which should be the plot)
    return agent.run(
        task,
        additional_args={"context": system_prompt + "\n\n" + context}
    )


if __name__ == "__main__":
    files = {
        "2024": "https://www.abc.xyz/assets/77/51/9841ad5c4fbe85b4440c47a4df8d/goog-10-k-2024.pdf",
    }

    for year, url in files.items():
        filename = f"goog-10-k-{year}.pdf"
        download_file(url, filename)
    
    financial_analyst_task = """

    Using Python, load the PDF(s) containing financial statements.

    1. Extract revenue, net profit as well as Net cash provided by operating activities figures for 2023, and 2024.

    2. Plot a bar chart of those years' revenue, net profits and Net cash provided by operating activities, with clear axis labels and a descriptive title.

    3. Fit a simple growth model (for example, a linear regression or constant‐CAGR projection) to the 2023–2024 data.

    4. Forecast sales, net profit and Net cash provided by operating activities for the next five years (2025–2029) using that model. Assume 100% tariffs for US import from china kicks in in year 2026.

    5. Overlay the forecast trend line on the same bar chart.

    6. Annotate the chart (or below it) with a brief bullet‐list of your key forecasting assumptions (e.g.,"linear trend based on past three years") and a final analysis summary.

    Use visually appealing charts.
    
    7. Save the final plot to a file named 'financial_analysis_plot.png'.
    
    8. IMPORTANT: As the final step, return a Python dictionary containing:
       - The analysis summary text under the key 'analysis'.
       - The filename of the saved plot ('financial_analysis_plot.png') under the key 'plot'.
       Example return format: {'analysis': 'Your summary text...', 'plot': 'financial_analysis_plot.png'}
       Ensure ONLY this dictionary is the final return value.

    """

    # Path to PDF files
    pdf_file_path_1 = "goog-10-k-2024.pdf"

    # Prepare context string (example)
    context = f"Information from the PDF path from:\n{pdf_file_path_1}\n\n"

    # Define the function for Gradio
    def generate_financial_chart(task_prompt: str):
        # Run the agent
        result = use_agent(task_prompt, context)
        
        text_output = None
        image_path = None # Changed from plot_output

        # Case 1: Agent returns a dictionary with analysis and plot filename
        if isinstance(result, dict) and 'analysis' in result and 'plot' in result:
            text_output = result.get('analysis', 'Analysis text not found in dictionary.')
            plot_filename = result.get('plot')
            if isinstance(plot_filename, str) and os.path.exists(plot_filename):
                image_path = plot_filename # Use the filename for the Image component
            else:
                # Add the plot filename issue to the text output if file doesn't exist
                text_output += f"\n\n(Plot file '{plot_filename}' mentioned but not found or invalid.)"
                print(f"Warning: Plot file '{plot_filename}' not found or invalid.")
                image_path = None # No image to show

        # Case 2: Agent returns a matplotlib plot object directly
        elif hasattr(result, 'savefig') or isinstance(result, plt.Axes) or isinstance(result, plt.Figure):
            # Gradio Image component cannot directly display a plot object.
            # We could save it to a temp file, but let's keep it simple.
            text_output = "(Agent returned a plot object directly. Analysis text might be missing. Cannot display plot object as image here.)"
            image_path = None # No image path to return
            # Optionally print a warning or log this case
            print("Warning: Agent returned a plot object, not a dictionary with filename as expected.")

        # Case 3: Agent returns plain text or something else
        else:
            text_output = str(result) # Assume it's text
            image_path = None # No image to show
            
        return text_output, image_path # Return text and image path

    # Create and launch the Gradio interface
    iface = gr.Interface(
        fn=generate_financial_chart, 
        inputs=gr.Textbox(lines=20, label="Task Prompt", value=financial_analyst_task),
        outputs=[
            gr.Textbox(label="Text/Code Output", lines=15), # Output for text
            gr.Image(label="Generated Plot Image", type="filepath") # Changed from gr.Plot
        ], 
        title="Financial Analysis Agent",
        description=(
            "Modify the prompt below to customize the financial analysis. "
            "The agent should return analysis text and save a plot image. "
            "Uses Google's 10-K report (2024). Click 'Submit' to generate.\n\n"
            "**⚠️ Security Warning:** This tool uses an AI agent (smolagent) that can execute Python code based on the prompt. "
            "While guardrails are in place, malicious prompts could potentially lead to unintended code execution. "
            "Review prompts carefully before submitting. Do not input sensitive information or requests that could harm your system. "
            "Use with caution."
        )
    )
    iface.launch()
