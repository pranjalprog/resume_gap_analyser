import os
import re
import uuid

import openai
import requests
from pdfminer.high_level import extract_text
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image

from lpg.log import logger

current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(current_dir)
resources_dir = os.path.join(parent_dir, 'resources')


# Generates the text for a new landing page by examining word count, sentiment, asset, tags, analysis, original text
def generate_similar_page(word_count, sentiment, asset, tags, analysis, original_text):
    prompt = (
        f""" You are tasked with creating text for a new and unique landing page that strictly adheres to these 
        following requirements *IMPORTANT GUIDELINES* Word Count: The text must be of a similar word count to 
        {word_count} words. Ensure the length does not stray
        from a 100 word margin Sentiment: The text should convey the same sentiment as the original, {sentiment}
        Asset Categories: Include references to the asset categories, {asset}
        Tags: Integrate every one of the following NER tags into the text naturally: {tags}

        In addition please include the following with indicator listed afterwards:
        A Title for the PDF : ***
        Headings for different topics : #
        Subheadings : ##
        Bullet point style lists when necessary: --
        Quote Styles: '''
        Description of images that will later be created with OPENAI, please ensure the images are appropriate : [IMG]
        Regular lines: ~

        When these are used, please indicate at the beginning each and every line what is being used with the indicator.
        Please include each and every one of these into the text to creat a unique and clean format
        Remember overall title and headers are different
        *LANGUAGE ANALYSIS INSIGHTS*
        Use the following analysis of the original text to guide your writing. Ensure that the new content 
        incorporates these elements to create a similarly engaging and effective message and storyline:

        {analysis}

        *CREATIVE INSTRUCTION*
        -Do NOT copy the original text, it is only to be used as inpsiration
        -Generate fresh, enganging, new, orginal, and creative content
        - Avoid repetition. Ensure that the text flows naturally and covers different aspects of the subject matter
        - Ensure the content is detailed and informative, with each sentence contributing something new to the reader

        *REFERENCE*
        Below is the original text for reference purposes only. Use it to understand the structure and focus, but create something new:
        "{original_text}"

        *Final Reminder*
        The text must be original, maintaining the structure, sentiment, and themes mentioned above, without unnecessary repetition
        Be creative and ensure content is creative and inspiring. It is also important to use the language and techniques descibred in the
        analysis to create an effective text. Also it is imperative that the images generated DO NOT INCLUDE references
        to real life people in the title as this may affect the safety system. When creating text for images, do not include the likes of real life
        people, including in the tags
        """
    )
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",
             "content": "You are an obedient and helpful scribe that is responsible for writing landing page documents"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ],
            }
        ],
        temperature=0.6,
        max_tokens=3000
    )

    result = response.choices[0].message.content
    return result


# examines text to find image prompts and list them
def extract_image_prompts(text):
    # Use a regular expression to find all occurrences of [IMG: ...]
    pattern = r'\[IMG: (.*?)\]'
    prompts = re.findall(pattern, text)
    return prompts


# generates an image using the prompt
def generate_image(prompt):
    client = openai.OpenAI()
    response = client.images.generate(prompt=prompt, n=1, size="1024x1024")
    image_url = response.data[0].url
    # Generate a unique identifier
    unique_id = uuid.uuid4().hex
    # Create a unique filename
    img_filename = os.path.join(resources_dir, f"generated_image_{unique_id}.png")
    # Download the image
    img_response = requests.get(image_url)
    with open(img_filename, 'wb') as f:
        f.write(img_response.content)
    return img_filename


# creates a pdf and inputted
def create_pdf(text, images_info, filename):
    doc = SimpleDocTemplate(os.path.join(resources_dir, filename), pagesize=letter)
    styles = getSampleStyleSheet()
    # Define custom styles
    title_style = ParagraphStyle(name='Title', fontSize=18, alignment=1, spaceAfter=20)
    header_style = styles['Heading1']
    subheader_style = styles['Heading2']
    bullet_style = ParagraphStyle(name='Bullet', fontSize=12, bulletFontName='Helvetica-Bold', leftIndent=20,
                                  spaceAfter=10)
    quote_style = ParagraphStyle(name='Quote', fontSize=12, italic=True, leftIndent=20, spaceBefore=10, spaceAfter=10)
    img_description_style = ParagraphStyle(name='ImageDescription', fontSize=10, italic=True, spaceBefore=10,
                                           spaceAfter=10)
    normal_style = styles['Normal']

    flowables = []
    image_counter = 0  # Counter to track which image to insert

    # Process the text to recognize formatting
    lines = text.split('\n')
    logger.info("lines counting")
    for line in lines:
        if line.startswith('***'):  # Title
            para = Paragraph(line[3:].strip(), title_style)
            flowables.append(para)
        elif line.startswith('# '):  # Header
            para = Paragraph(line[2:].strip(), header_style)
            flowables.append(para)
        elif line.startswith('## '):  # Subheader
            para = Paragraph(line[3:].strip(), subheader_style)
            flowables.append(para)
        elif line.startswith('-- '):  # Bullet point
            para = Paragraph(line[3:].strip(), bullet_style)
            flowables.append(para)
        elif line.startswith("'''"):  # Quote
            para = Paragraph(line[3:].strip(), quote_style)
            flowables.append(para)
        elif line.startswith('[IMG:'):  # Image placeholder
            if image_counter < len(images_info):
                img_file, _, _ = images_info[image_counter]
                img = Image(img_file, width=2 * inch, height=2 * inch)
                flowables.append(img)  # Insert the image at the correct place
                image_counter += 1  # Move to the next image in the list
            # Add image description
            img_desc = Paragraph(f"[IMG Description] {line[5:].strip()}", img_description_style)
            flowables.append(img_desc)
        elif line.startswith('~'):  # Regular lines
            para = Paragraph(line[1:].strip(), normal_style)
            flowables.append(para)
        else:
            # If there's any other text without indicators, treat it as normal text
            para = Paragraph(line.strip(), normal_style)
            flowables.append(para)

        flowables.append(Spacer(1, 12))  # Add space after each element

    # Build the PDF
    doc.build(flowables)


def analyze_language_patterns(original_text):
    prompt = (
        f"""
        You are tasked with analyzing the following text to identify key language patterns, tension points, and stylistic elements 
        that make the content engaging. Please focus on the following aspects:

        1. **Tension Points**: Identify moments in the text where there is a build-up of tension or contrast. Explain how these contribute to the overall effectiveness of the content.

        2. **Language Patterns**: Look for recurring phrases, word choices, or sentence structures that create rhythm, emphasis, or persuasion. Describe these patterns and their impact.

        3. **Stylistic Elements**: Note any specific stylistic elements such as tone, use of metaphors, rhetorical questions, or other literary devices. Describe how they contribute to the text's persuasive power.

        Provide a detailed analysis with examples from the text.

        Here is the original text:
        "{original_text}"
        """
    )

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a skilled editor and language analyst."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ],
            }
        ],
        temperature=0.5,
        max_tokens=1500
    )

    analysis = response.choices[0].message.content
    return analysis


# statistics for the document, these are stored on the postgres table word_count = 3491 sentiment = "bullish" asset =
# "stock, nuclear energy" tags = {"organizations": ["Nvidia", "Microsoft", "OpenAI", "GE Hitachi", "Holtec",
# "Kairos Power", "NuScale Power", "TerraPower", "X-energy", "Oklo", "NRC", "Fannie Mae", "Freddie Mac",
# "NuScale Power", "DOD"], "people": ["Bill Gates", "Jeff Bezos", "Peter Thiel", "Warren Buffett", "Reid Hoffman",
# "Ken Griffin", "Jim Simons", "Sam Altman", "Elon Musk", "Greta Thunberg", "Jennifer Granholm", "Marty Fridson",
# "Tom Carroll", "Caleb Brooks", "Jean Allain", "David Durham", "William Becker", "Enrico Fermi", "Robert U. Ayres",
# "Matt Bennett", "Caleb Brooks", "Porter Stansberry"], "other_entities": ["AI", "SMRs", "microreactors", "VOYGR-12",
# "AI Keystone"]}


def generate_similar_content(pdf_name, word_count, sentiment, asset, tags, new_file_name="generated.pdf"):
    text = extract_text(pdf_file=os.path.join(resources_dir, pdf_name))
    # analyze the language pattern so the AI will imitate it
    analysis = analyze_language_patterns(text)
    similar = generate_similar_page(word_count, sentiment, asset, tags, analysis, text)
    prompts = extract_image_prompts(similar)
    images_info = []
    for i, prompt in enumerate(prompts):
        img_file = generate_image(prompt)
        images_info.append((img_file, 1 * inch, 1 * inch))  #
    # create the new pdf
    create_pdf(similar, images_info, new_file_name)
