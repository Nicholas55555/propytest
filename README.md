# Bad Deed Validator

A "paranoid engineering" approach to validating OCR-scanned deeds for Propy.

## 🎯 Philosophy

At Propy, we can't just trust an LLM to be right. If an AI hallucinates a number on a deed, we could accidentally record a fraudulent transaction on the blockchain. This validator follows a key principle:

> **Use AI for what it's good at (parsing messy text), use CODE for what it's good at (logical validation).**

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Raw OCR Text  │────▶│  LLM Extraction │────▶│ Code Validation │
│   (Messy)       │     │  (Parsing)      │     │  (Paranoid)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                        │
                              │                        ▼
                              │                 ┌─────────────────┐
                              │                 │  Date Logic     │
                              │                 │  Amount Match   │
                              │                 │  County Lookup  │
                              │                 └─────────────────┘
                              │                        │
                              ▼                        ▼
                        ┌─────────────────────────────────────────┐
                        │           ValidationResult              │
                        │  • is_valid: bool                       │
                        │  • errors: [specific error messages]    │
                        │  • deed_data: enriched structured data  │
                        └─────────────────────────────────────────┘
```

## ✅ What Gets Validated (By Code, Not AI)

### 1. Date Logic Check
The document was `Recorded (Jan 10)` before it was `Signed (Jan 15)`. That's impossible.

**How it's caught:** Pure Python datetime comparison—no AI involved.

```python
if recorded_date < signed_date:
    raise DateLogicError(...)
```

### 2. Amount Mismatch Detection  
The text lists `$1,250,000` in digits but writes out `"One Million Two Hundred Thousand"` in words—a $50k discrepancy.

**How it's caught:** Custom word-to-number converter (no external dependencies) compares both values.

```python
numeric = parse_numeric_amount("$1,250,000.00")  # → 1,250,000
written = parse_written_amount("One Million Two Hundred Thousand")  # → 1,200,000
if abs(numeric - written) / numeric > tolerance:
    raise AmountDiscrepancyError(...)
```

### 3. County Name Enrichment
The OCR text says `"S. Clara"`, but our database knows it as `"Santa Clara"`.

**How it's handled:** Smart abbreviation mapping that handles:
- `S. Clara` → `Santa Clara`
- `S. Mateo` → `San Mateo`  
- `S. Cruz` → `Santa Cruz`
- Case-insensitive matching
- Substring matching for robustness

## 🚀 Quick Start

```bash
# Run the validator with test suite
python deed_validator.py

# Run as API (requires Flask)
pip install flask
python api.py
```

## 📁 Project Structure

```
deed_validator/
├── deed_validator.py    # Main validation logic
├── counties.json        # Reference data (tax rates)
├── api.py              # Optional Flask API
└── README.md           # This file
```

## 🔌 API Usage

### Endpoint: `POST /validate`

```bash
curl -X POST http://localhost:5000/validate \
  -H "Content-Type: application/json" \
  -d '{"ocr_text": "*** RECORDING REQ ***\nDoc: DEED-TRUST-0042\n..."}'
```

### Response (Invalid Deed):
```json
{
  "valid": false,
  "errors": [
    "IMPOSSIBLE DATE SEQUENCE: Document was recorded (2024-01-10) BEFORE it was signed (2024-01-15).",
    "AMOUNT MISMATCH: Numeric amount $1,250,000.00 does not match written amount (parsed as $1,200,000.00). Discrepancy: $50,000.00"
  ],
  "data": {
    "doc_number": "DEED-TRUST-0042",
    "county": "S. Clara",
    "county_normalized": "Santa Clara",
    "tax_rate": 0.012,
    "amount_numeric": 1250000.0,
    "amount_written_parsed": 1200000.0,
    "closing_costs": 15000.0
  }
}
```

## 🧪 Test Cases

The validator includes comprehensive tests:

| Test | Description | Status |
|------|-------------|--------|
| 1 | Main "bad deed" validation | ✅ Catches both errors |
| 2 | Word-to-number conversion | ✅ All edge cases pass |
| 3 | County abbreviation matching | ✅ All variations handled |
| 4 | Date sequence validation | ✅ Valid/invalid/same-day |
| 5 | Amount validation | ✅ Match/mismatch detection |
| 6 | Word-to-number edge cases | ✅ 50-2B range covered |
| 7 | County not found handling | ✅ Specific error raised |
| 8 | Valid deed processing | ✅ Passes validation |

## 🔧 Customization

### Adding New Counties

Edit `counties.json`:
```json
[
  { "name": "Santa Clara", "tax_rate": 0.012 },
  { "name": "San Mateo", "tax_rate": 0.011 },
  { "name": "Your New County", "tax_rate": 0.013 }
]
```

### Integrating Real LLM

Replace the stubbed `extract_deed_with_llm()` function:

```python
import anthropic

def extract_deed_with_llm(raw_text: str) -> dict:
    client = anthropic.Anthropic()
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user", 
            "content": f"""Extract the following fields from this deed text as JSON:
            - doc_number, county, state, date_signed, date_recorded
            - grantor, grantee, amount_numeric, amount_written, apn, status
            
            Text:
            {raw_text}
            """
        }]
    )
    
    return json.loads(response.content[0].text)
```

## 🎓 Key Design Decisions

### Why not use AI for validation?

1. **Dates**: LLMs can't reliably detect impossible sequences without explicit prompting
2. **Math**: LLMs frequently make arithmetic errors, especially with large numbers
3. **Determinism**: Code always catches these errors; AI might not

### Why use AI for extraction?

1. **Messy text handling**: LLMs excel at parsing unstructured, OCR-error-prone text
2. **Flexibility**: Handles variations in format without brittle regex
3. **Entity recognition**: Correctly parses "T.E.S.L.A. Holdings LLC" without custom rules

### County matching approach

Rather than fuzzy string matching (which could match "S. Clara" to wrong counties), we use an explicit abbreviation map. This is more predictable and auditable for financial documents.

## 📋 Error Types

| Error Class | Trigger | Message Format |
|-------------|---------|----------------|
| `DateLogicError` | recorded < signed | "IMPOSSIBLE DATE SEQUENCE: ..." |
| `AmountDiscrepancyError` | numeric ≠ written | "AMOUNT MISMATCH: ... Discrepancy: $X" |
| `CountyNotFoundError` | No match in DB | "COUNTY NOT FOUND: ... Available: ..." |

## 📜 License

MIT

## 🤝 Contributing

1. Fork the repository
2. Add your feature/fix
3. Ensure all tests pass: `python deed_validator.py`
4. Submit a PR
