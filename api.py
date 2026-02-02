"""
Flask API for Bad Deed Validator
================================
Simple REST API wrapper for the deed validation logic.

Run: python api.py
Test: curl -X POST http://localhost:5000/validate -H "Content-Type: application/json" -d '{"ocr_text": "..."}'
"""

from flask import Flask, request, jsonify
from deed_validator import DeedValidator, DeedValidationError
import traceback

app = Flask(__name__)

# Initialize validator once
validator = DeedValidator()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "deed-validator"})


@app.route('/validate', methods=['POST'])
def validate_deed():
    """
    Validate a deed from OCR text.
    
    Request body:
    {
        "ocr_text": "*** RECORDING REQ ***\n..."
    }
    
    Response:
    {
        "valid": bool,
        "errors": [...],
        "warnings": [...],
        "data": {...}  // Enriched deed data
    }
    """
    try:
        # Get request data
        data = request.get_json()
        
        if not data or 'ocr_text' not in data:
            return jsonify({
                "error": "Missing required field 'ocr_text' in request body"
            }), 400
        
        ocr_text = data['ocr_text']
        
        # Validate
        result = validator.validate(ocr_text)
        
        # Build response
        response = {
            "valid": result.is_valid,
            "errors": result.errors,
            "warnings": result.warnings,
        }
        
        # Add deed data if available
        if result.deed_data:
            response["data"] = {
                "doc_number": result.deed_data.doc_number,
                "county": result.deed_data.county,
                "county_normalized": result.deed_data.county_normalized,
                "state": result.deed_data.state,
                "date_signed": result.deed_data.date_signed,
                "date_recorded": result.deed_data.date_recorded,
                "grantor": result.deed_data.grantor,
                "grantee": result.deed_data.grantee,
                "amount_numeric": result.deed_data.amount_numeric,
                "amount_written": result.deed_data.amount_written,
                "amount_written_parsed": result.deed_data.amount_written_parsed,
                "apn": result.deed_data.apn,
                "status": result.deed_data.status,
                "tax_rate": result.deed_data.tax_rate,
                "closing_costs": result.deed_data.closing_costs,
            }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({
            "error": f"Validation failed: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500


@app.route('/counties', methods=['GET'])
def list_counties():
    """List all known counties and their tax rates."""
    return jsonify({
        "counties": [
            {"name": c['name'], "tax_rate": c['tax_rate']}
            for c in validator.county_matcher.counties
        ]
    })


# =============================================================================
# Example usage (for testing without Flask server)
# =============================================================================

def example_api_call():
    """Demonstrate API usage programmatically."""
    
    test_ocr = """*** RECORDING REQ ***
Doc: DEED-TRUST-0042
County: S. Clara | State: CA
Date Signed: 2024-01-15
Date Recorded: 2024-01-10

Grantor: T.E.S.L.A. Holdings LLC
Grantee: John & Sarah Connor

Amount: $1,250,000.00 (One Million Two Hundred Thousand Dollars)
APN: 992-001-XA
Status: PRELIMINARY
*** END ***"""

    # Simulate what the API would return
    result = validator.validate(test_ocr)
    
    print("\n" + "=" * 60)
    print("API Response Preview")
    print("=" * 60)
    
    import json
    response = {
        "valid": result.is_valid,
        "errors": result.errors,
        "data": {
            "doc_number": result.deed_data.doc_number,
            "county_normalized": result.deed_data.county_normalized,
            "tax_rate": result.deed_data.tax_rate,
            "amount_numeric": result.deed_data.amount_numeric,
            "amount_written_parsed": result.deed_data.amount_written_parsed,
        } if result.deed_data else None
    }
    
    print(json.dumps(response, indent=2))


if __name__ == '__main__':
    import sys
    
    if '--example' in sys.argv:
        example_api_call()
    else:
        print("Starting Deed Validator API on http://localhost:5000")
        print("Endpoints:")
        print("  GET  /health   - Health check")
        print("  POST /validate - Validate deed OCR text")
        print("  GET  /counties - List known counties")
        print("\nPress Ctrl+C to stop")
        app.run(debug=True, host='0.0.0.0', port=5000)
