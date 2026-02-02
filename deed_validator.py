"""
Bad Deed Validator - Propy Technical Task
==========================================
A paranoid engineering approach to validating OCR-scanned deeds.

This script:
1. Extracts data using an LLM (stubbed for testing)
2. Enriches data by matching abbreviated county names
3. Performs rigorous sanity checks on dates and amounts
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from pathlib import Path


# =============================================================================
# CUSTOM EXCEPTIONS - Specific errors for different validation failures
# =============================================================================

class DeedValidationError(Exception):
    """Base exception for deed validation errors."""
    pass


class DateLogicError(DeedValidationError):
    """Raised when document dates are logically impossible."""
    def __init__(self, signed_date: str, recorded_date: str):
        self.signed_date = signed_date
        self.recorded_date = recorded_date
        super().__init__(
            f"IMPOSSIBLE DATE SEQUENCE: Document was recorded ({recorded_date}) "
            f"BEFORE it was signed ({signed_date}). "
            f"A deed cannot be recorded before it exists!"
        )


class AmountDiscrepancyError(DeedValidationError):
    """Raised when numeric and written amounts don't match."""
    def __init__(self, numeric_amount: float, written_amount: float, written_text: str):
        self.numeric_amount = numeric_amount
        self.written_amount = written_amount
        self.written_text = written_text
        discrepancy = abs(numeric_amount - written_amount)
        super().__init__(
            f"AMOUNT MISMATCH: Numeric amount ${numeric_amount:,.2f} does not match "
            f"written amount '{written_text}' (parsed as ${written_amount:,.2f}). "
            f"Discrepancy: ${discrepancy:,.2f}"
        )


class CountyNotFoundError(DeedValidationError):
    """Raised when county cannot be matched to reference data."""
    def __init__(self, county_text: str, available_counties: List[str]):
        self.county_text = county_text
        self.available_counties = available_counties
        super().__init__(
            f"COUNTY NOT FOUND: '{county_text}' could not be matched to any known county. "
            f"Available counties: {', '.join(available_counties)}"
        )


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DeedData:
    """Structured representation of extracted deed data."""
    doc_number: str
    county: str
    state: str
    date_signed: str
    date_recorded: str
    grantor: str
    grantee: str
    amount_numeric: float
    amount_written: str
    apn: str
    status: str
    
    # Enriched fields (added during processing)
    county_normalized: Optional[str] = None
    tax_rate: Optional[float] = None
    amount_written_parsed: Optional[float] = None
    closing_costs: Optional[float] = None


@dataclass
class ValidationResult:
    """Result of validation process."""
    is_valid: bool
    deed_data: Optional[DeedData] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# =============================================================================
# WORD TO NUMBER CONVERTER (No external dependencies)
# =============================================================================

class WordToNumberConverter:
    """Converts written-out dollar amounts to numeric values."""
    
    ONES = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
        'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
        'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
        'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
        'eighteen': 18, 'nineteen': 19
    }
    
    TENS = {
        'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
        'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90
    }
    
    SCALES = {
        'hundred': 100,
        'thousand': 1_000,
        'million': 1_000_000,
        'billion': 1_000_000_000,
        'trillion': 1_000_000_000_000
    }
    
    def convert(self, text: str) -> float:
        """Convert written amount to float."""
        # Normalize text
        text = text.lower()
        text = re.sub(r'[^a-z\s]', '', text)  # Remove non-alpha except spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove "dollars" and "and"
        text = text.replace('dollars', '').replace('dollar', '')
        text = re.sub(r'\band\b', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        words = text.split()
        
        if not words:
            return 0.0
        
        return self._parse_number(words)
    
    def _parse_number(self, words: List[str]) -> float:
        """Parse a list of number words into a value."""
        total = 0
        current = 0
        
        for word in words:
            if word in self.ONES:
                current += self.ONES[word]
            elif word in self.TENS:
                current += self.TENS[word]
            elif word == 'hundred':
                if current == 0:
                    current = 1
                current *= 100
            elif word in ('thousand', 'million', 'billion', 'trillion'):
                if current == 0:
                    current = 1
                current *= self.SCALES[word]
                total += current
                current = 0
        
        return float(total + current)


# =============================================================================
# COUNTY MATCHER - Smart fuzzy matching for abbreviated names
# =============================================================================

class CountyMatcher:
    """Matches abbreviated or partial county names to full names."""
    
    def __init__(self, counties_file: str = "counties.json"):
        self.counties = self._load_counties(counties_file)
        # Build abbreviation mappings
        self.abbreviation_map = self._build_abbreviation_map()
    
    def _load_counties(self, filepath: str) -> List[dict]:
        """Load county data from JSON file."""
        path = Path(filepath)
        if not path.exists():
            # Try relative to script location
            path = Path(__file__).parent / filepath
        
        with open(path, 'r') as f:
            return json.load(f)
    
    def _build_abbreviation_map(self) -> dict:
        """Build a map of common abbreviations and partial matches."""
        abbrev_map = {}
        
        for county in self.counties:
            name = county['name']
            name_lower = name.lower()
            
            # Full name
            abbrev_map[name_lower] = name
            
            # First word (e.g., "Santa" for "Santa Clara")
            first_word = name.split()[0].lower()
            abbrev_map[first_word] = name
            
            # Common abbreviations (S. -> San/Santa, etc.)
            if name.startswith('San '):
                abbrev_map[f"s. {name[4:].lower()}"] = name
                abbrev_map[f"s {name[4:].lower()}"] = name
            if name.startswith('Santa '):
                abbrev_map[f"s. {name[6:].lower()}"] = name
                abbrev_map[f"s {name[6:].lower()}"] = name
                abbrev_map[f"sta. {name[6:].lower()}"] = name
                abbrev_map[f"sta {name[6:].lower()}"] = name
        
        return abbrev_map
    
    def match(self, county_text: str) -> tuple[str, float]:
        """
        Match county text to a known county.
        Returns (county_name, tax_rate) or raises CountyNotFoundError.
        """
        normalized = county_text.lower().strip()
        
        # Direct match in abbreviation map
        if normalized in self.abbreviation_map:
            matched_name = self.abbreviation_map[normalized]
            for county in self.counties:
                if county['name'] == matched_name:
                    return county['name'], county['tax_rate']
        
        # Fuzzy matching - check if any county name contains the search term
        # or if the search term contains part of a county name
        for county in self.counties:
            county_name = county['name']
            county_lower = county_name.lower()
            
            # Check if normalized text is substring of county name (minus punctuation)
            search_clean = re.sub(r'[^a-z\s]', '', normalized)
            
            for word in search_clean.split():
                if len(word) > 2 and word in county_lower:
                    return county['name'], county['tax_rate']
        
        # No match found
        available = [c['name'] for c in self.counties]
        raise CountyNotFoundError(county_text, available)


# =============================================================================
# DATE VALIDATOR - Paranoid date checking
# =============================================================================

class DateValidator:
    """Validates date logic in deeds."""
    
    DATE_FORMATS = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%B %d, %Y',
        '%b %d, %Y',
    ]
    
    def parse_date(self, date_str: str) -> datetime:
        """Parse a date string into a datetime object."""
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"Could not parse date: {date_str}")
    
    def validate_date_sequence(self, signed_date: str, recorded_date: str) -> None:
        """
        Validate that recorded date is on or after signed date.
        Raises DateLogicError if dates are logically impossible.
        """
        signed = self.parse_date(signed_date)
        recorded = self.parse_date(recorded_date)
        
        if recorded < signed:
            raise DateLogicError(signed_date, recorded_date)


# =============================================================================
# AMOUNT VALIDATOR - Money sanity checks
# =============================================================================

class AmountValidator:
    """Validates that numeric and written amounts match."""
    
    def __init__(self):
        self.word_converter = WordToNumberConverter()
    
    def parse_numeric_amount(self, amount_str: str) -> float:
        """Parse a numeric amount string like '$1,250,000.00' to float."""
        # Remove currency symbols, commas, and whitespace
        cleaned = re.sub(r'[$,\s]', '', amount_str)
        return float(cleaned)
    
    def parse_written_amount(self, amount_text: str) -> float:
        """Parse a written amount like 'One Million Two Hundred Thousand' to float."""
        return self.word_converter.convert(amount_text)
    
    def validate_amounts(self, numeric_str: str, written_str: str, 
                        tolerance: float = 0.01) -> float:
        """
        Validate that numeric and written amounts match.
        
        Args:
            numeric_str: The numeric amount (e.g., "$1,250,000.00")
            written_str: The written amount (e.g., "One Million Two Hundred Thousand Dollars")
            tolerance: Relative tolerance for matching (default 1%)
            
        Returns:
            The validated amount if they match
            
        Raises:
            AmountDiscrepancyError if amounts don't match
        """
        numeric_amount = self.parse_numeric_amount(numeric_str)
        written_amount = self.parse_written_amount(written_str)
        
        # Check if amounts match within tolerance
        if numeric_amount == 0:
            if written_amount != 0:
                raise AmountDiscrepancyError(numeric_amount, written_amount, written_str)
        else:
            relative_diff = abs(numeric_amount - written_amount) / numeric_amount
            if relative_diff > tolerance:
                raise AmountDiscrepancyError(numeric_amount, written_amount, written_str)
        
        return numeric_amount


# =============================================================================
# LLM EXTRACTION (Stubbed)
# =============================================================================

def extract_deed_with_llm(raw_text: str) -> dict:
    """
    Extract structured data from raw OCR text using an LLM.
    
    In production, this would call OpenAI/Anthropic API.
    For this implementation, we're using a stubbed response that simulates
    what the LLM would return.
    
    The key point: We don't TRUST this output. We validate everything afterwards.
    """
    # =========================================================================
    # STUBBED LLM RESPONSE
    # In production, replace this with actual API call:
    #
    # response = anthropic.messages.create(
    #     model="claude-sonnet-4-20250514",
    #     messages=[{"role": "user", "content": EXTRACTION_PROMPT + raw_text}],
    # )
    # return json.loads(response.content[0].text)
    # =========================================================================
    
    # This simulates what the LLM would extract from the messy OCR text
    # The LLM is good at parsing, but we can't trust it for validation
    return {
        "doc_number": "DEED-TRUST-0042",
        "county": "S. Clara",  # LLM preserves the abbreviation - we handle normalization
        "state": "CA",
        "date_signed": "2024-01-15",
        "date_recorded": "2024-01-10",  # LLM extracts what it sees - validation catches the error
        "grantor": "T.E.S.L.A. Holdings LLC",
        "grantee": "John & Sarah Connor",
        "amount_numeric": "$1,250,000.00",
        "amount_written": "One Million Two Hundred Thousand Dollars",  # LLM extracts as-is
        "apn": "992-001-XA",
        "status": "PRELIMINARY"
    }


# =============================================================================
# MAIN VALIDATOR CLASS
# =============================================================================

class DeedValidator:
    """
    Main orchestrator for deed validation.
    
    This class follows "paranoid engineering" principles:
    1. Use LLM for extraction (it's good at parsing messy text)
    2. Use CODE for validation (don't trust the LLM for logic)
    3. Fail loudly and specifically when something is wrong
    """
    
    def __init__(self, counties_file: str = "counties.json", 
                 extraction_fn: callable = None,
                 verbose: bool = True):
        """
        Initialize the deed validator.
        
        Args:
            counties_file: Path to the counties JSON reference file
            extraction_fn: Optional custom extraction function. If not provided,
                          uses the default stubbed extraction.
            verbose: If True, prints detailed validation steps
        """
        self.county_matcher = CountyMatcher(counties_file)
        self.date_validator = DateValidator()
        self.amount_validator = AmountValidator()
        self.extraction_fn = extraction_fn or extract_deed_with_llm
        self.verbose = verbose
    
    def validate(self, raw_ocr_text: str) -> ValidationResult:
        """
        Validate a deed from raw OCR text.
        
        Returns a ValidationResult with either:
        - is_valid=True and enriched deed_data
        - is_valid=False with specific errors
        """
        errors = []
        warnings = []
        
        # Step 1: Extract data using LLM
        if self.verbose:
            print("=" * 60)
            print("STEP 1: LLM EXTRACTION")
            print("=" * 60)
        try:
            extracted = self.extraction_fn(raw_ocr_text)
            if self.verbose:
                print(f"Extracted data: {json.dumps(extracted, indent=2)}")
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"LLM extraction failed: {str(e)}"]
            )
        
        # Step 2: Enrich - Match county name
        if self.verbose:
            print("\n" + "=" * 60)
            print("STEP 2: COUNTY ENRICHMENT")
            print("=" * 60)
        try:
            county_name, tax_rate = self.county_matcher.match(extracted['county'])
            if self.verbose:
                print(f"Matched '{extracted['county']}' -> '{county_name}' (tax rate: {tax_rate})")
        except CountyNotFoundError as e:
            errors.append(str(e))
            county_name = None
            tax_rate = None
        
        # Step 3: Validate dates (CODE-BASED - Don't trust LLM for date logic!)
        if self.verbose:
            print("\n" + "=" * 60)
            print("STEP 3: DATE VALIDATION (Code-based)")
            print("=" * 60)
        try:
            self.date_validator.validate_date_sequence(
                extracted['date_signed'],
                extracted['date_recorded']
            )
            if self.verbose:
                print(f"✓ Date sequence is valid")
        except DateLogicError as e:
            if self.verbose:
                print(f"✗ DATE ERROR: {e}")
            errors.append(str(e))
        
        # Step 4: Validate amounts (CODE-BASED - Don't trust LLM for math!)
        if self.verbose:
            print("\n" + "=" * 60)
            print("STEP 4: AMOUNT VALIDATION (Code-based)")
            print("=" * 60)
        written_parsed = None
        try:
            numeric_parsed = self.amount_validator.parse_numeric_amount(extracted['amount_numeric'])
            written_parsed = self.amount_validator.parse_written_amount(extracted['amount_written'])
            if self.verbose:
                print(f"Numeric amount: ${numeric_parsed:,.2f}")
                print(f"Written amount parsed: ${written_parsed:,.2f}")
            
            validated_amount = self.amount_validator.validate_amounts(
                extracted['amount_numeric'],
                extracted['amount_written']
            )
            if self.verbose:
                print(f"✓ Amounts match: ${validated_amount:,.2f}")
        except AmountDiscrepancyError as e:
            if self.verbose:
                print(f"✗ AMOUNT ERROR: {e}")
            errors.append(str(e))
            if written_parsed is None:
                written_parsed = self.amount_validator.parse_written_amount(extracted['amount_written'])
        
        # Build the deed data object
        deed_data = DeedData(
            doc_number=extracted['doc_number'],
            county=extracted['county'],
            state=extracted['state'],
            date_signed=extracted['date_signed'],
            date_recorded=extracted['date_recorded'],
            grantor=extracted['grantor'],
            grantee=extracted['grantee'],
            amount_numeric=self.amount_validator.parse_numeric_amount(extracted['amount_numeric']),
            amount_written=extracted['amount_written'],
            apn=extracted['apn'],
            status=extracted['status'],
            county_normalized=county_name,
            tax_rate=tax_rate,
            amount_written_parsed=written_parsed,
        )
        
        # Calculate closing costs if we have valid data
        if tax_rate and deed_data.amount_numeric:
            deed_data.closing_costs = deed_data.amount_numeric * tax_rate
        
        # Final result
        if self.verbose:
            print("\n" + "=" * 60)
            print("VALIDATION RESULT")
            print("=" * 60)
        
        is_valid = len(errors) == 0
        
        if self.verbose:
            if is_valid:
                print("✓ DEED IS VALID")
            else:
                print(f"✗ DEED FAILED VALIDATION with {len(errors)} error(s):")
                for i, error in enumerate(errors, 1):
                    print(f"  {i}. {error}")
        
        return ValidationResult(
            is_valid=is_valid,
            deed_data=deed_data,
            errors=errors,
            warnings=warnings
        )


# =============================================================================
# TEST CASES
# =============================================================================

def run_tests(verbose: bool = True):
    """Run comprehensive test cases."""
    
    if verbose:
        print("\n" + "#" * 70)
        print("# TEST SUITE")
        print("#" * 70)
    
    # The original messy OCR text from the task
    MESSY_OCR_TEXT = """*** RECORDING REQ ***
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

    # Test 1: Main validation (should catch both errors)
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 1: Validate the 'bad' deed (should catch 2 errors)")
        print("=" * 70)
    
    validator = DeedValidator()
    result = validator.validate(MESSY_OCR_TEXT)
    
    assert not result.is_valid, "TEST 1 FAILED: Deed should be invalid"
    assert len(result.errors) == 2, f"TEST 1 FAILED: Expected 2 errors, got {len(result.errors)}"
    assert any("DATE" in e or "recorded" in e.lower() for e in result.errors), \
        "TEST 1 FAILED: Should have date error"
    assert any("AMOUNT" in e or "MISMATCH" in e for e in result.errors), \
        "TEST 1 FAILED: Should have amount error"
    if verbose:
        print("\n✓ TEST 1 PASSED: Both errors detected correctly")
    
    # Test 2: Word to number conversion
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 2: Word to Number Conversion")
        print("=" * 70)
    
    converter = WordToNumberConverter()
    
    test_cases = [
        ("One Million Two Hundred Thousand Dollars", 1_200_000),
        ("One Million Two Hundred Fifty Thousand Dollars", 1_250_000),
        ("Five Hundred Thousand Dollars", 500_000),
        ("One Hundred Twenty Three Thousand Four Hundred Fifty Six Dollars", 123_456),
        ("One Million Dollars", 1_000_000),
        ("Two Billion Dollars", 2_000_000_000),
    ]
    
    for text, expected in test_cases:
        result = converter.convert(text)
        status = "✓" if result == expected else "✗"
        if verbose:
            print(f"{status} '{text}' -> {result:,.0f} (expected {expected:,})")
        assert result == expected, f"Conversion failed for '{text}'"
    
    if verbose:
        print("\n✓ TEST 2 PASSED: All word-to-number conversions correct")
    
    # Test 3: County matching
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 3: County Matching")
        print("=" * 70)
    
    matcher = CountyMatcher()
    
    county_tests = [
        ("S. Clara", "Santa Clara"),
        ("Santa Clara", "Santa Clara"),
        ("S. Mateo", "San Mateo"),
        ("San Mateo", "San Mateo"),
        ("S. Cruz", "Santa Cruz"),
        ("santa clara", "Santa Clara"),  # Case insensitive
    ]
    
    for input_name, expected in county_tests:
        name, rate = matcher.match(input_name)
        status = "✓" if name == expected else "✗"
        if verbose:
            print(f"{status} '{input_name}' -> '{name}' (expected '{expected}')")
        assert name == expected, f"Match failed for '{input_name}'"
    
    if verbose:
        print("\n✓ TEST 3 PASSED: All county matches correct")
    
    # Test 4: Date validation
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 4: Date Validation")
        print("=" * 70)
    
    date_validator = DateValidator()
    
    # Valid date sequence
    try:
        date_validator.validate_date_sequence("2024-01-10", "2024-01-15")
        if verbose:
            print("✓ Valid sequence (signed before recorded) - passed")
    except DateLogicError:
        assert False, "Should not raise error for valid sequence"
    
    # Same day - should be valid
    try:
        date_validator.validate_date_sequence("2024-01-10", "2024-01-10")
        if verbose:
            print("✓ Same day signing and recording - passed")
    except DateLogicError:
        assert False, "Should not raise error for same-day"
    
    # Invalid sequence (recorded before signed)
    try:
        date_validator.validate_date_sequence("2024-01-15", "2024-01-10")
        assert False, "Should have raised DateLogicError"
    except DateLogicError as e:
        if verbose:
            print(f"✓ Invalid sequence detected: {e.signed_date} signed, {e.recorded_date} recorded")
    
    if verbose:
        print("\n✓ TEST 4 PASSED: Date validation working correctly")
    
    # Test 5: Amount validation
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 5: Amount Validation")
        print("=" * 70)
    
    amount_validator = AmountValidator()
    
    # Matching amounts
    try:
        result = amount_validator.validate_amounts(
            "$1,250,000.00",
            "One Million Two Hundred Fifty Thousand Dollars"
        )
        if verbose:
            print(f"✓ Matching amounts validated: ${result:,.2f}")
    except AmountDiscrepancyError:
        assert False, "Should not raise error for matching amounts"
    
    # Mismatched amounts (the original error case)
    try:
        amount_validator.validate_amounts(
            "$1,250,000.00",
            "One Million Two Hundred Thousand Dollars"  # Missing "Fifty" = $50k discrepancy
        )
        assert False, "Should have raised AmountDiscrepancyError"
    except AmountDiscrepancyError as e:
        if verbose:
            print(f"✓ Mismatch detected: ${e.numeric_amount:,.2f} vs ${e.written_amount:,.2f}")
        discrepancy = abs(e.numeric_amount - e.written_amount)
        assert discrepancy == 50_000, f"Expected $50k discrepancy, got ${discrepancy:,.2f}"
        if verbose:
            print(f"✓ Discrepancy correctly identified as ${discrepancy:,.2f}")
    
    if verbose:
        print("\n✓ TEST 5 PASSED: Amount validation working correctly")
    
    # Test 6: Edge cases for word to number
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 6: Additional Word-to-Number Edge Cases")
        print("=" * 70)
    
    edge_cases = [
        ("Fifty Dollars", 50),
        ("Nine Hundred Ninety Nine Dollars", 999),
        ("Twelve Thousand Dollars", 12_000),
        ("One Hundred Dollars", 100),
        ("Twenty One Thousand Dollars", 21_000),
        ("Three Hundred Forty Five Thousand Six Hundred Seventy Eight Dollars", 345_678),
    ]
    
    for text, expected in edge_cases:
        result = converter.convert(text)
        status = "✓" if result == expected else "✗"
        if verbose:
            print(f"{status} '{text}' -> {result:,.0f} (expected {expected:,})")
        assert result == expected, f"Conversion failed for '{text}'"
    
    if verbose:
        print("\n✓ TEST 6 PASSED: Edge cases handled correctly")
    
    # Test 7: County not found error
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 7: County Not Found Error Handling")
        print("=" * 70)
    
    try:
        matcher.match("Unknown County")
        assert False, "Should have raised CountyNotFoundError"
    except CountyNotFoundError as e:
        if verbose:
            print(f"✓ Unknown county correctly raised error: {e.county_text}")
        assert "Unknown County" in str(e)
    
    if verbose:
        print("\n✓ TEST 7 PASSED: County not found error works correctly")
    
    # Test 8: Valid deed (no errors) - using configurable extraction
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 8: Valid Deed (No Errors)")
        print("=" * 70)
    
    # Define a mock extraction function that returns valid data
    def mock_valid_extract(raw_text: str) -> dict:
        return {
            "doc_number": "DEED-VALID-001",
            "county": "San Mateo",
            "state": "CA",
            "date_signed": "2024-01-10",  # Signed BEFORE recorded - correct!
            "date_recorded": "2024-01-15",
            "grantor": "Valid Seller LLC",
            "grantee": "Valid Buyer",
            "amount_numeric": "$500,000.00",
            "amount_written": "Five Hundred Thousand Dollars",  # Matches!
            "apn": "123-456-78",
            "status": "FINAL"
        }
    
    # Create validator with custom extraction function
    valid_validator = DeedValidator(extraction_fn=mock_valid_extract, verbose=False)
    result_valid = valid_validator.validate("mock input")
    
    assert result_valid.is_valid, f"TEST 8 FAILED: Valid deed should pass. Errors: {result_valid.errors}"
    assert len(result_valid.errors) == 0, f"TEST 8 FAILED: Expected 0 errors, got {len(result_valid.errors)}"
    assert result_valid.deed_data.county_normalized == "San Mateo"
    assert result_valid.deed_data.tax_rate == 0.011
    
    if verbose:
        print(f"✓ Valid deed passed validation")
        print(f"✓ County matched: {result_valid.deed_data.county_normalized}")
        print(f"✓ Tax rate: {result_valid.deed_data.tax_rate}")
        print(f"✓ Closing costs: ${result_valid.deed_data.closing_costs:,.2f}")
        print("\n✓ TEST 8 PASSED: Valid deed processed correctly")
    
    if verbose:
        print("\n" + "#" * 70)
        print("# ALL TESTS PASSED!")
        print("#" * 70)
    
    return True


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Run the test suite
    run_tests()
    
    print("\n\n")
    print("=" * 70)
    print("DEMONSTRATION: Processing the 'Bad' Deed")
    print("=" * 70)
    
    # The exact messy OCR text from the task
    RAW_OCR_TEXT = """*** RECORDING REQ ***
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

    validator = DeedValidator()
    result = validator.validate(RAW_OCR_TEXT)
    
    print("\n" + "=" * 70)
    print("FINAL OUTPUT")
    print("=" * 70)
    print(f"Valid: {result.is_valid}")
    print(f"Errors: {result.errors}")
    if result.deed_data:
        print(f"\nExtracted Data:")
        print(f"  Document: {result.deed_data.doc_number}")
        print(f"  County: {result.deed_data.county} -> {result.deed_data.county_normalized}")
        print(f"  Tax Rate: {result.deed_data.tax_rate}")
        print(f"  Amount (numeric): ${result.deed_data.amount_numeric:,.2f}")
        print(f"  Amount (written): {result.deed_data.amount_written}")
        print(f"  Amount (written parsed): ${result.deed_data.amount_written_parsed:,.2f}")
        if result.deed_data.closing_costs:
            print(f"  Closing Costs (estimate): ${result.deed_data.closing_costs:,.2f}")
