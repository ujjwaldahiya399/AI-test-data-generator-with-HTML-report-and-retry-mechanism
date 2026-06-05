from groq import Groq
import os
import json
import re

from pathlib import Path

# Load API key
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# This is the core brain of the project
# It takes a schema (description of a form/database), sends it to the AI,
# and gets back organised test data in 4 categories: positive, negative, edge, and security cases.

def generate_test_data(schema):
    """Send schema to AI and get back categorised test data"""
    prompt = f"""
    You are an expert QA Engineer and SDET specializing in test data generation.
    Given the following JSON schema, generate exactly 8 rows of test data.
    Return a valid JSON object with exactly these 4 keys:
    - "positive_cases": array of 2 valid happy path records
    - "negative_cases": array of 2 invalid records that should fail validation
    - "edge_cases": array of 2 boundary/extreme value records
    - "security_cases": array of 2 records with SQL injection or XSS attack strings
    Rules:
    - Return ONLY the JSON object, no explanation, no markdown, no extra text
    - Every record must include ALL fields from the schema
    - Make the data realistic and varied
    Schema: {json.dumps(schema, indent=2)}
    """

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a JSON-only response bot. Return raw JSON with no markdown, no explanation, no extra text."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0
            )
            raw = response.choices[0].message.content.strip()
            raw = clean_json_response(raw)
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as e:
            print(f"   JSON parse failed, retrying... (attempt {attempt + 1}/3)")

    print(f"   Could not parse JSON after 3 attempts, skipping this schema")
    return {
        "positive_cases": [],
        "negative_cases": [],
        "edge_cases": [],
        "security_cases": []
    }


def clean_json_response(raw):
    """Strip markdown fences and extract JSON object from AI response"""
    raw = raw.strip()

    # Remove markdown code blocks
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    # Fallback: regex to find the first { ... } block
    if not raw.startswith("{"):
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            raw = match.group()

    return raw.strip()

def save_categorised_output(entity_name, data):
    """Save each category into its own JSON file"""
    # Takes the AI output and saves each category (positive, negative, etc.)
    # into its own separate JSON file inside the output/ folder
    safe_name = entity_name.lower().replace(" ", "_")
    
    for category, records in data.items():
        # Loop through each category and its records in the data dictionary
        # data.items() gives us pairs like ("positive_cases", [{...}, {...}])
        filepath = f"output/{safe_name}_{category}.json"
        with open(filepath, "w") as f:
            json.dump(records, f, indent=2)
        print(f"   Saved {filepath}")

def generate_html_report(all_results):
    # The showstopper function — takes all generated data and builds
    # a visual, colour-coded HTML report you can open in any browser
    """Generate a clean visual HTML report"""
    
    category_colors = {
        "positive_cases": "#22c55e",
        "negative_cases": "#ef4444",
        "edge_cases": "#f59e0b",
        "security_cases": "#8b5cf6"
    }

    category_labels = {
        "positive_cases": "✅ Positive Cases",
        "negative_cases": "❌ Negative Cases",
        "edge_cases": "⚠️ Edge Cases",
        "security_cases": "🔐 Security Cases"
    }

    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI Test Data Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa; color: #333; }
        h1 { color: #1e293b; border-bottom: 3px solid #6366f1; padding-bottom: 10px; }
        h2 { color: #1e293b; margin-top: 40px; }
        h3 { padding: 8px 14px; border-radius: 6px; color: white; display: inline-block; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0 30px 0; background: white;
                box-shadow: 0 1px 4px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
        th { background: #1e293b; color: white; padding: 12px 15px; text-align: left; font-size: 13px; }
        td { padding: 10px 15px; border-bottom: 1px solid #e2e8f0; font-size: 13px; word-break: break-all; }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: #f1f5f9; }
        .summary { display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }
        .card { background: white; padding: 20px 30px; border-radius: 10px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.1); text-align: center; }
        .card h3 { font-size: 28px; margin: 0; color: #6366f1; background: none; padding: 0; }
        .card p { margin: 5px 0 0; color: #64748b; font-size: 14px; }
        .badge { padding: 4px 10px; border-radius: 20px; color: white; font-size: 12px; font-weight: bold; }
    </style>
</head>
<body>
    <h1>🤖 AI Generated Test Data Report</h1>
    <p>Auto-generated by AI Test Data Generator | Powered by LLaMA 3.3 via Groq</p>
"""

    total_records = sum(
        len(records)
        for data in all_results.values()
        for records in data.values()
    )

    html += f"""
    <div class="summary">
        <div class="card"><h3>{len(all_results)}</h3><p>Schemas Tested</p></div>
        <div class="card"><h3>{total_records}</h3><p>Total Records Generated</p></div>
        <div class="card"><h3>4</h3><p>Categories Per Schema</p></div>
    </div>
"""

    for entity_name, data in all_results.items():
        html += f"<h2>📋 {entity_name}</h2>"
        
        for category, records in data.items():
            color = category_colors.get(category, "#6366f1")
            label = category_labels.get(category, category)
            
            if not records:
                continue
                
            headers = records[0].keys()
            
            html += f'<h3 style="background:{color}">{label}</h3>'
            html += "<table><tr>"
            for header in headers:
                html += f"<th>{header}</th>"
            html += "</tr>"
            
            for record in records:
                html += "<tr>"
                for value in record.values():
                    html += f"<td>{value}</td>"
                html += "</tr>"
            
            html += "</table>"

    html += """
</body>
</html>
"""
    with open("output/report.html", "w") as f:
        f.write(html)
    print("\n   Saved output/report.html")

# ── Main Runner ───────────────────────────────────────────────────────────────
# Wrapping everything in a main() function is Python best practice
# It keeps the code organised and prevents it from running if this file
# is ever imported as a module into another Python file
def main():

    # Find all .json files inside the schemas/ folder
    # glob("*.json") matches any filename ending in .json
    # This means adding a new schema file automatically gets picked up
    schema_files = list(Path("schemas").glob("*.json"))

    # Dictionary to collect results from all schemas
    # Will be passed to generate_html_report() at the end
    all_results = {}

    print("\n Starting AI Test Data Generation...\n")

    # Process each schema file one by one
    for schema_file in schema_files:

        # Open and read the schema JSON file
        with open(schema_file, "r") as f:
            schema = json.load(f)

        # Get the human readable name from the schema
        entity_name = schema["entity"]
        print(f"  Processing: {entity_name}")

        # Step 1: Send schema to AI → get back categorised test data
        data = generate_test_data(schema)

        # Step 2: Store in all_results for the HTML report later
        all_results[entity_name] = data

        # Step 3: Save each category as its own JSON file
        save_categorised_output(entity_name, data)

    # Step 4: Generate the final visual HTML report from all results
    generate_html_report(all_results)

    print("\n Done! Open output/report.html in your browser to see the full report.")


# This is the entry point of the script
# if __name__ == "__main__" means:
# "only run main() if this file is being run directly"
# "do NOT run it if this file is imported by another Python file"
# This is considered standard Python best practice in every professional codebase
if __name__ == "__main__":
    main()
