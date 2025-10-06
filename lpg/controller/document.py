import json
import os
import tempfile
import urllib.parse

import boto3
import openai
from botocore.exceptions import NoCredentialsError
from pdfminer.high_level import extract_text

from lpg.log import logger
from lpg.utils import generate_random_string

current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(current_dir)
resources_dir = os.path.join(parent_dir, 'resources')


def upload_to_s3(file, bucket_name, object_name):
    try:
        # Debug: Check if any parameters are None
        if file is None:
            print("Error: file parameter is None")
            return None
        if bucket_name is None:
            print("Error: bucket_name parameter is None")
            return None
        if object_name is None:
            print("Error: object_name parameter is None")
            return None
            
        # Debug: Check environment variables
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("REGION")
        
        print(f"Debug - AWS_ACCESS_KEY_ID: {'Set' if aws_access_key else 'Not set'}")
        print(f"Debug - AWS_SECRET_ACCESS_KEY: {'Set' if aws_secret_key else 'Not set'}")
        print(f"Debug - AWS_REGION: {aws_region}")
        print(f"Debug - bucket_name: {bucket_name}")
        print(f"Debug - object_name: {object_name}")
        
        s3 = boto3.client('s3', aws_access_key_id=aws_access_key,
                          aws_secret_access_key=aws_secret_key)
        #content_type = file.content_type
        content_type = getattr(file, 'content_type', 'application/octet-stream')
        s3.upload_fileobj(file, bucket_name, object_name, ExtraArgs={'ContentType': content_type})
        file_url = f"https://{bucket_name}.s3.{aws_region}.amazonaws.com/{object_name}"
        return file_url
    except Exception as e:
        print(f'Error uploading file to S3: {e}')
        return None

def extract_pdf(pdf_file):
    text = extract_text(pdf_file)
    return text


def analyze_pdf(pdf_file):
        text = extract_pdf(pdf_file)
        prompt = (
            f"""analyze the following text and return results in proper and exact json format that is parsable by 
            json.loads():\"\"\"{text}\"\"\"

            JSON Format:
            {{
                "word_count": integer,
                "Named Recognition tags": {{
                "organizations": [list of organizations],
                "people": [list of people],
                "other_entities": [list of other entitites]
                }},
                "sentiment_analysis: {{
                    "bullish": integer, 
                    "bearish": integer, 
                    "greedy": integer, 
                    "fearful": integer 
                }},
                "asset_categories": {{
                "crypto": boolean,
                "stock": boolean, 
                "options": boolean,
                "currency": boolean,
                "other": [list of other asset categories]
                }}

            }}
            """
        )
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt}
                    ],
                }
            ],
            temperature=0.5,
            max_tokens=500
        )

        result = response.choices[0].message.content.strip()
        return result

def clean_result(result):
    # Remove any leading text before the JSON
    json_start = result.find('{')
    if json_start != -1:
        result = result[json_start:]

    # Remove any trailing text after the JSON
    json_end = result.rfind('}')
    if json_end != -1:
        result = result[:json_end + 1]

    return result


def parse_result(result):
    data = json.loads(result)
    word_count = data.get("word_count", 0)
    tags = data.get("Named Recognition tags", {})
    sentiment_analysis = data.get("sentiment_analysis", {})
    asset_categories = data.get("asset_categories", {})

    sentiments = ['bullish', 'bearish', 'greedy', 'fearful']
    dom_sentiment = max(sentiments, key=lambda s: sentiment_analysis.get(s, 0))

    asset_list = []
    asset_names = {
        'crypto': 'Crypto',
        'stock': 'Stock',
        'options': 'Options',
        'currency': 'Currency'
    }
    for key, name in asset_names.items():
        if asset_categories.get(key, False):
            asset_list.append(name)
    asset_list.extend(asset_categories.get('other', []))
    return {
        "word_count": word_count,
        "ner_tags": tags,
        "sentiment_analysis": dom_sentiment,
        "asset_categories": ', '.join(asset_list)
    }


def download_parse_clean(asset, file_url, sentiment, tags, word_count):
    s3 = boto3.client('s3')
    bucket_name = os.getenv("AWS_S3_BUCKET")
    # Correct Base URL of the bucket including the region
    base_url = f'https://{bucket_name}.s3.us-east-2.amazonaws.com/'
    # Extract the S3 key from the URL
    s3_key = file_url.replace(base_url, '')
    s3_key = urllib.parse.unquote(s3_key)  # Decode URL-encoded characters
    logger.info(f"Base URL: {base_url}")
    logger.info(f"Extracted S3 Key: {s3_key}")
    
    # Create a proper temporary file that works cross-platform
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_file_path = temp_file.name
    temp_file.close()
    
    try:
        # Download the file using the S3 key
        s3.download_file(bucket_name, s3_key, temp_file_path)
        logger.info("Downloaded the file successfully.")

        # Extract text from the downloaded file
        result = analyze_pdf(temp_file_path)
        logger.info("Extracted and Analyzed text from the file.")
        if result:
            result = clean_result(result)
            parsed = parse_result(result)
            if parsed:
                word_count = parsed['word_count']
                tags = parsed['ner_tags']
                sentiment = parsed['sentiment_analysis']
                asset = parsed['asset_categories']
    except NoCredentialsError:
        logger.error('Credentials not available')
    except Exception as e:
        logger.error(f"Error processing document: {e}")
    finally:
        # Clean up the temporary file
        try:
            os.remove(temp_file_path)
        except OSError as e:
            logger.warning(f"Could not remove temporary file {temp_file_path}: {e}")
    
    return asset, sentiment, tags, word_count, os.path.basename(temp_file_path)

def compare_documents_with_openai(text1, text2, doc1_name, doc2_name):
    try:
        # Check if OpenAI API key is set
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "Error: OpenAI API key not configured. Please set OPENAI_API_KEY in your environment variables."
        # Debug: Check API key format (only show first few characters for security)
        if api_key:
            key_preview = api_key[:7] + "..." + api_key[-4:] if len(api_key) > 11 else "***"
            print(f"Debug: Using OpenAI API key: {key_preview}")
            if not api_key.startswith("sk-"):
                print("Warning: API key doesn't start with 'sk-' - this might indicate an invalid key format")
        # Enhanced prompt for resume vs job description analysis
        prompt = f"""You are an expert HR analyst comparing a job description and a resume. Analyze the following documents and provide a detailed, category-by-category gap analysis in Markdown table format.

{doc1_name} (Job Description):
{text2}

{doc2_name} (Resume):
{text1}

Please provide your analysis in the following format:

🔍 Detailed Comparison:

| Category | Job Description Requirements | Resume Match |
|----------|-----------------------------|--------------|
| Role Title | ... | ... |
| Education | ... | ... |
| Programming Skills | ... | ... |
| UI/UX Understanding | ... | ... |
| Frameworks & Tools | ... | ... |
| Version Control | ... | ... |
| Soft Skills | ... | ... |
| Projects or Internships | ... | ... |
| Design Tools (optional) | ... | ... |
| API Usage | ... | ... |
| Debugging & Testing | ... | ... |

✅ **Strengths in Resume:**
- List the main strengths and matches found in the resume.

❌ **Gaps or Improvements Needed:**
| Area | Suggestion |
|------|------------|
| ...  | ...        |

📌 **Final Verdict:**
A concise summary of how well the resume matches the job description and any final recommendations.

Be specific, actionable, and use the table format above. If a category is not applicable, write 'N/A'. Always use the document names in your analysis instead of generic terms like 'Document 1' or 'Document 2'."""
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1200
        )
        return response.choices[0].message.content.strip()
    except openai.AuthenticationError as e:
        return f"Error: Invalid OpenAI API key. Please check your OPENAI_API_KEY environment variable. Details: {str(e)}"
    except openai.RateLimitError as e:
        return f"Error: OpenAI API rate limit exceeded. Please try again later. Details: {str(e)}"
    except openai.APIError as e:
        return f"Error: OpenAI API error occurred. Please try again. Details: {str(e)}"
    except Exception as e:
        return f"Error: An unexpected error occurred while comparing documents. Details: {str(e)}"

