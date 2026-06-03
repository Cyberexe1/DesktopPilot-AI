"""List all Indian English voices from Amazon Polly."""
import boto3
from dotenv import load_dotenv
load_dotenv()

client = boto3.client('polly', region_name='us-east-1')

# Indian English
print("\n=== Indian English (en-IN) ===")
voices = client.describe_voices(LanguageCode='en-IN')
for v in voices['Voices']:
    print(f"  {v['Id']:12} | {v['Gender']:8} | Engines: {v.get('SupportedEngines', [])}")

# Also check Hindi
print("\n=== Hindi (hi-IN) ===")
voices = client.describe_voices(LanguageCode='hi-IN')
for v in voices['Voices']:
    print(f"  {v['Id']:12} | {v['Gender']:8} | Engines: {v.get('SupportedEngines', [])}")
