"""
Code Controller — generates code using AI, creates files, and runs them.
Supports: Python, JavaScript/Node.js, Java, C, HTML
"""

import json
import logging
import os
import subprocess
import time

log = logging.getLogger(__name__)

_USER = os.environ.get("USERNAME", "User")
CODE_DIR = os.path.join(os.path.expanduser("~/Desktop"), "DesktopPilot_Code")

# Ensure code directory exists
os.makedirs(CODE_DIR, exist_ok=True)

# Language configs: extension, run command, compile command (if needed)
LANGUAGES = {
    "python": {
        "ext": ".py",
        "run": "python {file}",
        "compile": None,
    },
    "javascript": {
        "ext": ".js",
        "run": "node {file}",
        "compile": None,
    },
    "node": {
        "ext": ".js",
        "run": "node {file}",
        "compile": None,
    },
    "java": {
        "ext": ".java",
        "run": "java {classname}",
        "compile": "javac {file}",
    },
    "c": {
        "ext": ".c",
        "run": "{basename}.exe",
        "compile": "gcc {file} -o {basename}.exe",
    },
    "cpp": {
        "ext": ".cpp",
        "run": "{basename}.exe",
        "compile": "g++ {file} -o {basename}.exe",
    },
    "html": {
        "ext": ".html",
        "run": "start {file}",  # Opens in browser
        "compile": None,
    },
}


def generate_and_run_code(description: str, language: str = "python", filename: str = "") -> str:
    """
    Generate code from description using AI, save to file, and run it.
    Returns the output of the program.
    """
    language = language.lower().strip()
    if language not in LANGUAGES:
        return f"Unsupported language: {language}. Supported: {', '.join(LANGUAGES.keys())}"

    lang_config = LANGUAGES[language]

    # Generate code using Bedrock
    code = _generate_code(description, language)
    if not code:
        return "Failed to generate code"

    # Determine filename
    if not filename:
        # Create a name from description
        safe_desc = "".join(c for c in description[:30] if c.isalnum() or c in ' _-').strip()
        safe_desc = safe_desc.replace(' ', '_').lower()
        filename = f"{safe_desc}{lang_config['ext']}"

    filepath = os.path.join(CODE_DIR, filename)

    # For Java, class name must match filename
    if language == "java":
        classname = os.path.splitext(filename)[0]
        # Ensure code has the right class name
        code = code.replace("class Main", f"class {classname}")
        code = code.replace("class Solution", f"class {classname}")
        if f"class {classname}" not in code:
            # Wrap in a class if not present
            if "class " not in code:
                code = f"public class {classname} {{\n    public static void main(String[] args) {{\n        {code}\n    }}\n}}"

    # Save code to file
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        log.info(f"Code saved: {filepath}")
    except Exception as e:
        return f"Failed to save code: {e}"

    # Open in VS Code for viewing
    try:
        subprocess.Popen(["code", filepath], shell=False)
    except Exception:
        pass

    time.sleep(1)

    # Compile if needed
    if lang_config["compile"]:
        compile_result = _compile_code(filepath, lang_config, language)
        if "Error" in compile_result:
            return f"Code saved at {filepath}\n\nCompilation failed:\n{compile_result}"

    # Run the code
    output = _run_code(filepath, lang_config, language)

    result = f"Code saved: {filepath}\n\nOutput:\n{output}"
    log.info(f"Code executed: {result[:100]}")
    return result


def _generate_code(description: str, language: str) -> str:
    """Call Bedrock to generate code."""
    import boto3

    REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.meta.llama3-3-70b-instruct-v1:0")

    prompt = f"""Write a {language.upper()} program. ONLY {language.upper()} syntax.

Task: {description}

CRITICAL: Write {language.upper()} code ONLY. 
{"- Use console.log() NOT print(). Use let/const NOT def. Use function NOT def. This is JAVASCRIPT for Node.js." if language in ("javascript", "node") else ""}
{"- Use System.out.println(). Include class and main method." if language == "java" else ""}
{"- Use printf() or puts(). Include #include and main()." if language in ("c", "cpp") else ""}
{"- Use print(). Use def for functions." if language == "python" else ""}

Return ONLY runnable code. No explanations. No markdown. No ```. Maximum 25 lines.

{language.upper()} code:"""

    try:
        client = boto3.client("bedrock-runtime", region_name=REGION)

        if "meta" in MODEL_ID.lower() or "llama" in MODEL_ID.lower():
            body = {"prompt": prompt, "max_gen_len": 1024, "temperature": 0.1}
        elif "nova" in MODEL_ID.lower() or "amazon" in MODEL_ID.lower():
            body = {
                "schemaVersion": "messages-v1",
                "messages": [
                    {"role": "user", "content": [{"text": prompt}]}
                ],
                "inferenceConfig": {
                    "maxTokens": 1024,
                    "temperature": 0.1,
                }
            }
        else:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }

        response = client.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())

        if "generation" in result:
            code = result["generation"].strip()
        elif "output" in result and "message" in result["output"]:
            # Amazon Nova format
            content = result["output"]["message"].get("content", [])
            code = content[0].get("text", "").strip() if content else ""
        elif "content" in result:
            code = result["content"][0]["text"].strip()
        else:
            return ""

        # Clean up: remove markdown code blocks if AI added them
        code = code.strip()
        if code.startswith("```"):
            lines = code.split('\n')
            code = '\n'.join(lines[1:])  # Remove first ``` line
        if code.endswith("```"):
            code = code[:-3].strip()

        # Remove language identifier line (```python, ```javascript etc)
        import re
        code = re.sub(r'^```\w*\n?', '', code)
        code = re.sub(r'\n?```\w*$', '', code)
        code = re.sub(r'\n?```\w*\n?', '\n', code)
        code = code.strip()

        # Remove explanation lines that aren't actual code
        lines = code.split('\n')
        clean_lines = []
        for line in lines:
            s = line.strip()
            if s.startswith('#') and any(w in s.lower() for w in ['fixed', 'solution', 'output:', 'here is', 'this is', 'note:']):
                continue
            if s.startswith('//') and any(w in s.lower() for w in ['fixed', 'solution', 'output:', 'here is', 'this is', 'note:']):
                continue
            clean_lines.append(line)
        code = '\n'.join(clean_lines).strip()

        log.info(f"Code generated: {len(code)} chars")
        return code

    except Exception as e:
        log.error(f"Code generation failed: {e}")
        return _fallback_code(description, language)


def _compile_code(filepath: str, config: dict, language: str) -> str:
    """Compile the code (for Java, C, C++)."""
    basename = os.path.splitext(os.path.basename(filepath))[0]
    compile_cmd = config["compile"].format(
        file=filepath,
        basename=os.path.join(CODE_DIR, basename),
    )

    try:
        result = subprocess.run(
            compile_cmd,
            shell=True,
            cwd=CODE_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"Compilation Error:\n{result.stderr}"
        return "Compiled successfully"
    except subprocess.TimeoutExpired:
        return "Error: Compilation timed out"
    except Exception as e:
        return f"Error: {e}"


def _run_code(filepath: str, config: dict, language: str) -> str:
    """Run the code and capture output."""
    basename = os.path.splitext(os.path.basename(filepath))[0]
    classname = basename

    run_cmd = config["run"].format(
        file=filepath,
        basename=os.path.join(CODE_DIR, basename),
        classname=classname,
    )

    try:
        result = subprocess.run(
            run_cmd,
            shell=True,
            cwd=CODE_DIR,
            capture_output=True,
            text=True,
            timeout=15,
        )

        output = result.stdout.strip()
        if result.stderr:
            output += f"\n\nErrors:\n{result.stderr.strip()}"

        if not output:
            output = "(No output produced)"

        return output[:1000]  # Cap output at 1000 chars

    except subprocess.TimeoutExpired:
        return "Error: Program timed out (15 second limit)"
    except Exception as e:
        return f"Error running code: {e}"


def _fallback_code(description: str, language: str) -> str:
    """Generate basic fallback code if Bedrock fails."""
    desc = description.lower()

    if language == "python":
        if "fibonacci" in desc:
            return "def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):\n        print(a, end=' ')\n        a, b = b, a + b\n    print()\n\nfibonacci(15)"
        elif "sort" in desc:
            return "numbers = [64, 34, 25, 12, 22, 11, 90]\nprint('Original:', numbers)\nnumbers.sort()\nprint('Sorted:', numbers)"
        elif "hello" in desc:
            return "print('Hello, World!')\nprint('Welcome to DesktopPilot AI')"
        else:
            return f"# {description}\nprint('Code generated by DesktopPilot AI')\nprint('Task: {description}')"

    elif language in ("javascript", "node"):
        if "fibonacci" in desc:
            return "function fibonacci(n) {\n  let a = 0, b = 1;\n  for (let i = 0; i < n; i++) {\n    process.stdout.write(a + ' ');\n    [a, b] = [b, a + b];\n  }\n  console.log();\n}\n\nfibonacci(15);"
        else:
            return f"// {description}\nconsole.log('Code generated by DesktopPilot AI');\nconsole.log('Task: {description}');"

    elif language == "java":
        return f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(\"Code generated by DesktopPilot AI\");\n        System.out.println(\"Task: {description}\");\n    }}\n}}"

    return f"// {description}\n// Code generation fallback"
