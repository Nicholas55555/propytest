# Bad Deed Validator

A "paranoid engineering" approach to validating OCR-scanned deeds for Propy.

## 🎯 Philosophy

At Propy, we can't just trust an LLM to be right. If an AI hallucinates a number on a deed, we could accidentally record a fraudulent transaction on the blockchain. This validator follows a key principle:

> **Use AI for what it's good at (parsing messy text), use CODE for what it's good at (logical validation).**

---

## 📝 Development Process & Methodology

### My Prompt to Claude:

> *"Iteratively (with thorough testing in a python environment to ensure success against multiple test cases) Develop a small Python script (or API) that takes a messy, OCR-scanned deed, cleans it up using an LLM, and then rigorously validates it with code before accepting it. Take as long as you need and show your work and thought process. Give me the resulting python script (use your own output as a stub for the llm api call for now)"*

### Step 1: Creating the Prompt to Generate Initial Prototype

I figured I should use a combination of **metaprompting**—an AI technique where large language models (LLMs) are used to create, refine, and optimize prompts for other tasks—and **agile methodology** (iterative, documented development, with communication prioritized) in lieu of traditional documentation. 

I included the original problem document (the PDF with the technical task), which allowed the AI-generated result to take in context:
- The original problem statement
- What deliverables were expected
- The specific test case with intentional errors

This led Claude to produce not just code, but also a comprehensive README and test suite.

### Step 2: Iterative Development with Testing

The development followed this cycle:

```
┌─────────────────┐
│  Write Code     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Run Tests      │──────┐
└────────┬────────┘      │
         │               │ Failed
         │ Passed        │
         ▼               ▼
┌─────────────────┐  ┌─────────────────┐
│  Add Edge Cases │  │  Debug & Fix    │
└────────┬────────┘  └────────┬────────┘
         │                    │
         └────────────────────┘
```

**Key iterations included:**
1. Initial prototype with stubbed LLM extraction
2. Building the word-to-number converter (custom, no dependencies)
3. Creating the county abbreviation matcher
4. Implementing date logic validation
5. Adding amount discrepancy detection
6. Comprehensive test suite (8 tests, all passing)
7. Live API integration with Anthropic Claude

### Step 3: Key Design Decisions Made During Development

| Decision | Reasoning |
|----------|-----------|
| **Stub the LLM first** | Allows testing validation logic without API costs/latency |
| **Custom word-to-number** | No external dependencies, full control over edge cases |
| **Explicit abbreviation map** | More predictable than fuzzy matching for legal documents |
| **Specific exception classes** | Clear error messages for debugging and audit trails |
| **Configurable extraction function** | Easy to swap between stub/live without code changes |

### Step 4: Final Testing & Verification

```
======================================================================
TEST SUMMARY: 8 passed, 0 failed
======================================================================
✓ TEST 1: Main "bad deed" - catches both date and amount errors
✓ TEST 2: Word-to-number conversion (50 → 2 billion range)
✓ TEST 3: County abbreviation matching (S. Clara → Santa Clara)
✓ TEST 4: Date sequence validation (valid/invalid/same-day)
✓ TEST 5: Amount validation (match/mismatch detection)
✓ TEST 6: Additional word-to-number edge cases
✓ TEST 7: County not found error handling
✓ TEST 8: Valid deed processing

🎉 ALL TESTS PASSED!
```
### Testing on my Local Machine (To Verifify results (Paranoid Engineering)
---<img width="1893" height="1012" alt="image" src="https://github.com/user-attachments/assets/0aa4fe63-6c72-4873-8892-9cb6dcc314f9" />
<img width="1876" height="992" alt="image" src="https://github.com/user-attachments/assets/ec9a9693-53c5-4d06-8b58-9aacc6c9e788" />
<img width="1822" height="975" alt="image" src="https://github.com/user-attachments/assets/dbc12885-85c3-4ab9-a1a8-32e7b87b159d" />
<img width="1898" height="1049" alt="image" src="https://github.com/user-attachments/assets/3db9f61a-445b-4a48-9761-e2095f32a9fb" />
<img width="1865" height="933" alt="image" src="https://github.com/user-attachments/assets/2874c9c5-0d93-4575-a3ae-01fa2f96d8e5" />
<img width="1916" height="1022" alt="image" src="https://github.com/user-attachments/assets/0a96c335-55d6-46fb-bbbf-221823ec3cdf" />
![Uploading image.png…]()
![Uploading image.png…]()



## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Raw OCR Text  │────▶│  LLM Extraction │────▶│ Code Validation │
│   (Messy)       │     │  (Claude API)   │     │  (Paranoid)     │
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

---

## 🚀 Quick Start

### Using the Stubbed Version (No API Key Needed)
```bash
# Run with test suite
python deed_validator.py
```

### Using the Live Version (Requires API Key)
```bash
# Option 1: Set environment variable
export ANTHROPIC_API_KEY="sk-ant-api03-..."
python deed_validator_live.py

# Option 2: Edit the file directly (line 23)
# ANTHROPIC_API_KEY = "sk-ant-api03-YOUR-KEY-HERE"
python deed_validator_live.py
```

### Running Tests
```bash
python test_validator.py
```

---

## 📁 Project Structure

```
deed_validator/
├── deed_validator.py       # Stubbed version (for testing without API)
├── deed_validator_live.py  # Live version with Anthropic API
├── test_validator.py       # Comprehensive test suite
├── api.py                  # Optional Flask API wrapper
├── counties.json           # Reference data (county tax rates)
└── README.md               # This file
```

---

## 🔌 API Usage (Optional)

### Start the Server
```bash
pip install flask
python api.py
```

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

---

## 🎓 Engineering Hygiene: Answering the Review Questions

### Q: What did you use to catch the date error?
**A:** Pure Python `datetime` comparison. The LLM extracts the dates as strings, but the validation is done entirely in code:
```python
signed = datetime.strptime(signed_date, '%Y-%m-%d')
recorded = datetime.strptime(recorded_date, '%Y-%m-%d')
if recorded < signed:
    raise DateLogicError(...)
```
This is deterministic and will **always** catch impossible date sequences, unlike an LLM which might miss subtle issues.

### Q: How did you handle the "S. Clara" lookup?
**A:** Built an explicit abbreviation map during initialization:
```python
# For "Santa Clara", we generate:
abbrev_map["santa clara"] = "Santa Clara"
abbrev_map["s. clara"] = "Santa Clara"
abbrev_map["s clara"] = "Santa Clara"
abbrev_map["sta. clara"] = "Santa Clara"
```
This is more predictable than fuzzy matching for legal/financial documents where precision matters.

### Q: Is your code structured well?
**A:** Yes, following separation of concerns:
- **Custom exceptions** for specific error types (`DateLogicError`, `AmountDiscrepancyError`, `CountyNotFoundError`)
- **Data classes** for structured data (`DeedData`, `ValidationResult`)
- **Single-responsibility classes** (`WordToNumberConverter`, `CountyMatcher`, `DateValidator`, `AmountValidator`)
- **Configurable main validator** (`DeedValidator`) that orchestrates the workflow
- **Comprehensive test suite** with 8 test cases covering all edge cases

---

## 📋 Error Types

| Error Class | Trigger | Message Format |
|-------------|---------|----------------|
| `DateLogicError` | recorded < signed | "IMPOSSIBLE DATE SEQUENCE: ..." |
| `AmountDiscrepancyError` | numeric ≠ written | "AMOUNT MISMATCH: ... Discrepancy: $X" |
| `CountyNotFoundError` | No match in DB | "COUNTY NOT FOUND: ... Available: ..." |

---

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

### Switching Between Stub and Live

```python
# Stubbed (no API needed)
from deed_validator import DeedValidator
validator = DeedValidator()

# Live (requires API key)
from deed_validator_live import DeedValidator
validator = DeedValidator(api_key="sk-ant-api03-...")
```

---

## 📜 License

MIT

## 🤝 Contributing

1. Fork the repository
2. Add your feature/fix
3. Ensure all tests pass: `python test_validator.py`
4. Submit a PR
