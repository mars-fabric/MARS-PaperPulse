import re
import json
import json5
from pathlib import Path

from .prompts import fixer_prompt, LaTeX_prompt
from .parameters import GraphState
from .journal import LatexPresets
from .latex_presets import journal_dict


def LLM_call(prompt, state):
    """
    This function calls the LLM and update tokens
    """

    try:
        from cmbagent.tracing import get_tracer
        _tracer = get_tracer("paperpulse.langgraph.paper")
    except Exception:
        _tracer = None

    if _tracer is not None:
        with _tracer.start_as_current_span("paper.llm_call") as _span:
            message = state['llm']['llm'].invoke(prompt)
            try:
                _span.set_attribute("llm.model", str(state['llm'].get('model', '')))
                _span.set_attribute("llm.input_tokens", message.usage_metadata['input_tokens'])
                _span.set_attribute("llm.output_tokens", message.usage_metadata['output_tokens'])
            except Exception:
                pass
    else:
        message = state['llm']['llm'].invoke(prompt)
    input_tokens  = message.usage_metadata['input_tokens']
    output_tokens = message.usage_metadata['output_tokens']
    if output_tokens>state['llm']['max_output_tokens']:
        print('WARNING!! Max output tokens reach!')
    state['tokens']['ti'] += input_tokens
    state['tokens']['to'] += output_tokens
    state['tokens']['i'] = input_tokens
    state['tokens']['o'] = output_tokens
    with open(state['files']['LLM_calls'], 'a') as f:
        f.write(f"{state['tokens']['i']} {state['tokens']['o']} {state['tokens']['ti']} {state['tokens']['to']}\n")
    
    return state, message.content


def LLM_call_stream(prompt, state):
    """
    Calls the LLM with streaming enabled and writes output to file in real-time.
    Also updates token usage tracking.
    """
    output_file_path = state['files']['f_stream']
    
    # Start streaming and writing/printing immediately
    full_content = ''
    state['tokens']['i'] = 0
    state['tokens']['o'] = 0
    with open(output_file_path, 'a') as f:
        for chunk in state['llm']['llm'].stream(prompt):
            text = chunk.content
            f.write(text)
            f.flush()  # Immediate file write
            if state['llm']['stream_verbose']:
                print(text, end='', flush=True)  # Immediate terminal output
            full_content += text

            # After streaming, get token usage
            usage = chunk.usage_metadata if hasattr(chunk, 'usage_metadata') else None
            if usage:
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                if output_tokens > state['llm']['max_output_tokens']:
                    print('WARNING!! Max output tokens reached!')

                state['tokens']['ti'] += input_tokens
                state['tokens']['to'] += output_tokens
                state['tokens']['i'] += input_tokens
                state['tokens']['o'] += output_tokens
        f.write('\n\n')
    with open(state['files']['LLM_calls'], 'a') as f:
        f.write(f"{state['tokens']['i']} {state['tokens']['o']} {state['tokens']['ti']} {state['tokens']['to']}\n")

    return state, full_content



def temp_file(state, fin, action, text=None, json_file=False):
    """
    This function reads or writes the content of a temporary file
    fin:  the name of the file
    action: either 'read' of 'write'
    text: when action is 'write', the text to write
    json: whether the file is json or not
    """
    
    journaldict: LatexPresets = journal_dict[state['paper']['journal']]

    if action=='read':
        with open(fin, 'r', encoding='utf-8') as f:
            if json_file:
                return json.load(f)
            else:
                latex_text = f.read()
                
                # Extract content between \begin{document} and \end{document}
                match = re.search(r'\\begin{document}(.*?)\\end{document}',
                                  latex_text, re.DOTALL)

                if match:
                    extracted_text = match.group(1).strip()
                    return extracted_text
                else:
                    raise Exception("Text not found on file!")

    elif action=='write':
        with open(fin, 'w', encoding='utf-8') as f:
            if json_file:
                json.dump(text, f, indent=2)
            else:
                latex_text = rf"""\documentclass[{journaldict.layout}]{{{journaldict.article}}}

\usepackage{{amsmath}}
\usepackage{{multirow}}
\usepackage{{natbib}}
\usepackage{{graphicx}} 
{journaldict.usepackage}

\begin{{document}}

{text}

\end{{document}}
                """
                f.write(latex_text)
    else:
        raise Exception("wrong action chosen!")


def json_parser(text):
    """
    This function extracts the text between ```json ```
    """
    
    json_pattern = r"```json(.*)```"
    match = re.findall(json_pattern, text, re.DOTALL)
    json_string = match[0].strip()
    json_string = json_string.replace("\\", "\\\\") #deal with unescaped backslashes
    try:
        parsed_json = json.loads(json_string)
    except json.decoder.JSONDecodeError:
        try:
            json_string = json_string.replace("'", "\"")
            parsed_json = json.loads(json_string)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON: {e}")
    return parsed_json



def json_parser2(text: str):
    """
    Extract the first ```json … ``` fenced block and parse it.
    """
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if not m:
        # fallback: any fenced block
        m = re.search(r"```\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not m:
        raise ValueError("No JSON fenced block found.")

    json_string = m.group(1)
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        # Helpful error to see exactly where it failed
        snippet = json_string[max(0, e.pos-40):e.pos+40]
        raise ValueError(f"JSON parse error at pos {e.pos}: {e.msg}\n…{snippet}…")

    
def json_parser3(text: str):
    """
    This function extracts a json data from a text
    """
    
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if not m:
        # fallback: any fenced block
        m = re.search(r"```\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not m:
        new_text = f"```json\n{text}\n```"
        m = re.search(r"```json\s*(\{.*?\})\s*```", new_text, re.DOTALL | re.IGNORECASE)
        if not m:
            raise ValueError("No JSON fenced block found.")
    json_string = m.group(1)
    data = json5.loads(json_string)
    return data


def extract_latex_block(state: GraphState, text: str, block: str) -> str:
    r"""
    This function takes some text and extracts the TEXT located between
    \begin{block}
    TEXT
    \end{block}

    Lenient with markdown code fences: Bedrock Claude often wraps LaTeX in
    ```latex ... ``` blocks, so we strip those before matching.
    """

    # Check if the input 'text' is a list and convert it to a string
    if isinstance(text, list):
        # Join the list items into a single string
        # Use str(item) to ensure all list elements can be joined
        text = "".join([str(item) for item in text])

    # Strip ```latex fenced wrappers if present — Bedrock Claude tends to add
    # them around LaTeX output even when the prompt asks for raw \begin{block}.
    fence_match = re.search(r"```(?:latex|tex)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    candidate = fence_match.group(1) if fence_match else text

    pattern = rf"\\begin{{{block}}}(.*?)\\end{{{block}}}"
    match = re.search(pattern, candidate, re.DOTALL) or re.search(pattern, text, re.DOTALL)

    if match:
        return match.group(1).strip()

    # Open-ended fallback: \begin{block} present but \end{block} missing.
    # This happens when the LLM hit max_tokens mid-section (Claude Sonnet 4.5
    # caps at 8192 output tokens, which a full Results section can exceed).
    # Salvage everything after \begin{block} — better than failing the whole
    # paper.
    open_pattern = rf"\\begin{{{block}}}(.*)"
    open_match = re.search(open_pattern, candidate, re.DOTALL) or re.search(open_pattern, text, re.DOTALL)
    if open_match:
        salvaged = open_match.group(1).strip()
        # Trim trailing incomplete sentence if the cut happened mid-word.
        if salvaged and not salvaged.endswith(('.', '!', '?', '}', ']')):
            # Roll back to the last complete sentence so the LaTeX compiles.
            last_sentence_end = max(
                salvaged.rfind('.'), salvaged.rfind('!'), salvaged.rfind('?')
            )
            if last_sentence_end > 0:
                salvaged = salvaged[:last_sentence_end + 1]
        print(f"WARNING: {block} truncated — \\end{{{block}}} missing, salvaged {len(salvaged)} chars")
        return salvaged

    # in case it fails
    with open(state['files']['Error'], 'w', encoding='utf-8') as f:
        f.write(text)

    # try to fix it using fixer
    try:
        return fixer(state, block)
    except ValueError:
        raise ValueError(f"Failed to extract {block}")

    

def fixer(state: GraphState, section_name):
    """
    This function will try to fix the errors with automatic parsing.

    Lenient with code fences (Bedrock Claude often wraps in ```latex ... ```).
    On terminal failure, raises ValueError instead of calling sys.exit() —
    sys.exit() in a FastAPI worker kills the whole uvicorn process.
    """

    path = Path(state['files']['Error'])
    with path.open("r", encoding="utf-8") as f:
        Text = f.read()

    PROMPT = fixer_prompt(Text, section_name)
    state, result = LLM_call(PROMPT, state)
    #result = llm.invoke(PROMPT).content

    # Strip ```latex code fences before matching (mirror extract_latex_block)
    fence_match = re.search(r"```(?:latex|tex)?\s*\n?(.*?)\n?```", result, re.DOTALL)
    candidate = fence_match.group(1) if fence_match else result

    # Extract caption
    pattern = rf"\\begin{{{section_name}}}(.*?)\\end{{{section_name}}}"
    match = re.search(pattern, candidate, re.DOTALL) or re.search(pattern, result, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Open-ended salvage: \begin present, \end missing (max_tokens cap hit).
    open_pattern = rf"\\begin{{{section_name}}}(.*)"
    open_match = re.search(open_pattern, candidate, re.DOTALL) or re.search(open_pattern, result, re.DOTALL)
    if open_match:
        salvaged = open_match.group(1).strip()
        if salvaged and not salvaged.endswith(('.', '!', '?', '}', ']')):
            last_sentence_end = max(
                salvaged.rfind('.'), salvaged.rfind('!'), salvaged.rfind('?')
            )
            if last_sentence_end > 0:
                salvaged = salvaged[:last_sentence_end + 1]
        print(f"WARNING: fixer salvaged {section_name} ({len(salvaged)} chars) without \\end tag")
        return salvaged

    with open(state['files']['Error'], 'w', encoding='utf-8') as f:
        f.write(result)
    print("Fixer failed to extract block")
    raise ValueError(f"Fixer could not extract \\begin{{{section_name}}}...\\end{{{section_name}}} block")



def LaTeX_checker(state, text):

    PROMPT = LaTeX_prompt(text)
    state, result = LLM_call(PROMPT, state)
    #result = llm.invoke(PROMPT).content
    text = extract_latex_block(state, result, "Text")
    return text


def clean_section(text, section):
    """
    This function performs some clean up of unwanted LaTeX wrappers
    """

    text = text.replace(r"\documentclass{article}", "")
    text = text.replace(r"\begin{document}", "")
    text = text.replace(r"\end{document}", "")
    text = text.replace(fr"\section{{{section}}}", "")
    text = text.replace(fr"\section*{{{section}}}", "")
    text = text.replace(fr"\begin{{{section}}}", "")
    text = text.replace(fr"\end{{{section}}}", "")
    text = text.replace(r"\maketitle", "")
    text = text.replace(r"<PARAGRAPH>", "")
    text = text.replace(r"</PARAGRAPH>", "")
    text = text.replace(r"</{section}>", "")
    text = text.replace(r"<{section}>", "")
    text = text.replace(r"```latex", "")
    text = text.replace(r"```", "")
    text = text.replace(r"\usepackage{amsmath}", "")

    return text


def check_images_in_text(state, images):
    """
    This function checks whether the LLM has put the images in the text or not
    """

    # Check that the images are in the text
    for key, value in images.items():
        if value["name"] not in state['paper']['Results']:
            return False
    return True

