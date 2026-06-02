"""
Content Generator — makes a SECOND call to Bedrock (same Llama model)
to generate rich, detailed content for files like PowerPoint, Word, etc.

This is separate from the planner because:
- Planner returns JSON (must be short)
- Content generator returns plain text (can be long and detailed)
"""

import json
import logging
import os

import boto3

log = logging.getLogger(__name__)

REGION   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.meta.llama3-3-70b-instruct-v1:0")

bedrock = boto3.client("bedrock-runtime", region_name=REGION)


def _is_llama() -> bool:
    return "meta" in MODEL_ID.lower() or "llama" in MODEL_ID.lower()


def generate_content(topic: str, content_type: str = "presentation", 
                     num_slides: int = 4, extra_instructions: str = "") -> str:
    """
    Call Bedrock to generate detailed content for a file.
    Returns plain text (NOT JSON) — the model writes freely.
    
    Args:
        topic: The subject matter (e.g., "Smart Agriculture")
        content_type: "presentation", "letter", "report", "essay"
        num_slides: Number of sections/slides to generate
        extra_instructions: Additional user requirements
    """
    prompt = _build_content_prompt(topic, content_type, num_slides, extra_instructions)

    log.info(f"Content generation: {content_type} about '{topic}' ({num_slides} sections)")

    try:
        if _is_llama():
            body = {"prompt": prompt, "max_gen_len": 2048, "temperature": 0.3}
        else:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            }

        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())

        # Extract text based on model type
        if "generation" in result:
            text = result["generation"].strip()
        elif "content" in result:
            text = result["content"][0]["text"].strip()
        else:
            text = str(result)

        log.info(f"Content generated: {len(text)} chars")
        return text

    except Exception as e:
        log.error(f"Content generation failed: {e}")
        # Return a basic fallback
        return _fallback_content(topic, content_type, num_slides)


def _build_content_prompt(topic: str, content_type: str, num_slides: int, extra: str) -> str:
    """Build the prompt for content generation."""

    if content_type == "presentation":
        return f"""Write a detailed presentation outline about: {topic}

Requirements:
- Exactly {num_slides} sections (slides)
- Each section has a HEADING on its own line
- Each section has 5-6 detailed bullet points starting with •
- First section should be an introduction/overview
- Last section should be conclusion or future scope
- Make bullet points specific, informative, and data-driven
- Each bullet should be a complete sentence (15-25 words)
{f'- Additional requirements: {extra}' if extra else ''}

Format (follow EXACTLY):
{topic}
Subtitle describing the presentation

Introduction to {topic}
• First detailed point about the topic
• Second detailed point with specific data or example
• Third point explaining a key concept
• Fourth point about practical applications
• Fifth point about current industry trends

[Next Section Heading]
• Point 1
• Point 2
• Point 3
• Point 4
• Point 5

Write the full content now:"""

    elif content_type == "letter":
        return f"""Write a formal professional email about: {topic}

Requirements:
- Start with "Dear Sir/Madam," on its own line
- Leave a blank line after greeting
- Write 2-3 body paragraphs (each 2-3 sentences)
- Each paragraph MUST be separated by a blank line
- End with a blank line then "Thank you for your understanding."
- Then a blank line
- Then "Best regards,"
- Then the sender name on next line

CRITICAL FORMAT RULE: Use double newlines between paragraphs. The email must have clear visual separation between greeting, body paragraphs, and closing. Never put "Best regards" or "Thank you" in the same paragraph as body text.
{f'- Additional context: {extra}' if extra else ''}

Example format:
Dear Sir/Madam,

I am writing to inform you about [topic]. [2nd sentence]. [3rd sentence].

[Second paragraph with more details]. [2nd sentence]. [3rd sentence].

Thank you for your understanding and support.

Best regards,
[Name]

Write the email now (follow the format exactly):"""

    elif content_type == "report":
        return f"""Write a detailed report about: {topic}

Requirements:
- Title
- Executive summary (3-4 sentences)
- 3-4 main sections with headings
- Each section has 4-5 detailed sentences
- Conclusion with recommendations
{f'- Additional requirements: {extra}' if extra else ''}

Write the report now:"""

    else:
        return f"""Write detailed content about: {topic}
Requirements: Be thorough, specific, and informative. Write at least 300 words.
{f'Additional: {extra}' if extra else ''}

Write now:"""


def _fallback_content(topic: str, content_type: str, num_slides: int) -> str:
    """Fallback content if Bedrock call fails."""
    if content_type == "presentation":
        sections = [
            f"{topic}\nA Comprehensive Overview",
            f"Introduction to {topic}\n• Overview of key concepts and fundamentals\n• Current market landscape and trends\n• Problem statement and motivation\n• Target audience and stakeholders\n• Historical context and evolution",
            f"Key Features and Benefits\n• Significant improvement in efficiency and productivity\n• Cost reduction through automation and optimization\n• Enhanced accuracy and reduced human error\n• Scalable solution adaptable to various use cases\n• Environmental sustainability and resource conservation",
            f"Technology and Implementation\n• Core technical architecture and infrastructure\n• Software frameworks and tools utilized\n• Data collection and analysis pipeline\n• Integration with existing systems\n• Security and privacy considerations",
            f"Conclusion and Future Scope\n• Summary of key takeaways and benefits\n• Current limitations and challenges\n• Upcoming developments and roadmap\n• Potential for expansion and scaling\n• Call to action and next steps",
        ]
        return '\n'.join(sections[:num_slides + 1])
    else:
        return f"Content about {topic}\n\nDetailed information would be generated here."
