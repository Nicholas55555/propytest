"""
Test Suite for Deed Validator
==============================
Tests both the stubbed version and live API version.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from deed_validator_live import (
    DeedValidator,
    WordToNumberConverter,
    CountyMatcher,
    DateValidator,
    AmountValidator,
    DateLogicError,
    AmountDiscrepancyError,
    CountyNotFoundError,
    DeedData,
    ValidationResult
)


def create_mock_extractor(extracted_data: dict):
    """Factory function to create mock extractors with specific data."""
    def mock_extract(raw_text: str, api_key: str = None) -> dict:
        return extracted_data
    return mock_extract


# Monkey-patch the extraction function for testing
import deed_validator_live as dv


def run_all_tests(verbose: bool = True):
    """Run comprehensive test suite."""
    
    if verbose:
        print("\n" + "#" * 70)
        print("# COMPREHENSIVE TEST SUITE")
        print("# Testing Deed Validator Components")
        print("#" * 70)
    
    passed = 0
    failed = 0
    
    # =========================================================================
    # TEST 1: Main "Bad Deed" Validation
    # =========================================================================
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 1: Validate the 'bad' deed (should catch 2 errors)")
        print("=" * 70)
    
    # Mock the extraction to return the "bad" deed data
    bad_deed_data = {
        "doc_number": "DEED-TRUST-0042",
        "county": "S. Clara",
        "state": "CA",
        "date_signed": "2024-01-15",
        "date_recorded": "2024-01-10",  # ERROR: Before signed!
        "grantor": "T.E.S.L.A. Holdings LLC",
        "grantee": "John & Sarah Connor",
        "amount_numeric": "$1,250,000.00",
        "amount_written": "One Million Two Hundred Thousand Dollars",  # ERROR: $50k short!
        "apn": "992-001-XA",
        "status": "PRELIMINARY"
    }
    
    # Temporarily replace extraction function
    original_extract = dv.extract_deed_with_llm
    dv.extract_deed_with_llm = create_mock_extractor(bad_deed_data)
    
    try:
        validator = DeedValidator(verbose=verbose)
        result = validator.validate("mock OCR text")
        
        assert not result.is_valid, "TEST 1 FAILED: Deed should be invalid"
        assert len(result.errors) == 2, f"TEST 1 FAILED: Expected 2 errors, got {len(result.errors)}"
        
        has_date_error = any("DATE" in e or "recorded" in e.lower() for e in result.errors)
        has_amount_error = any("AMOUNT" in e or "MISMATCH" in e for e in result.errors)
        
        assert has_date_error, "TEST 1 FAILED: Should have date error"
        assert has_amount_error, "TEST 1 FAILED: Should have amount error"
        
        if verbose:
            print("\n✓ TEST 1 PASSED: Both errors detected correctly")
        passed += 1
    except AssertionError as e:
        if verbose:
            print(f"\n✗ TEST 1 FAILED: {e}")
        failed += 1
    finally:
        dv.extract_deed_with_llm = original_extract
    
    # =========================================================================
    # TEST 2: Word to Number Conversion
    # =========================================================================
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
    
    test2_passed = True
    for text, expected in test_cases:
        result = converter.convert(text)
        status = "✓" if result == expected else "✗"
        if verbose:
            print(f"{status} '{text}' -> {result:,.0f} (expected {expected:,})")
        if result != expected:
            test2_passed = False
    
    if test2_passed:
        if verbose:
            print("\n✓ TEST 2 PASSED: All word-to-number conversions correct")
        passed += 1
    else:
        if verbose:
            print("\n✗ TEST 2 FAILED: Some conversions incorrect")
        failed += 1
    
    # =========================================================================
    # TEST 3: County Matching
    # =========================================================================
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
        ("santa clara", "Santa Clara"),
    ]
    
    test3_passed = True
    for input_name, expected in county_tests:
        try:
            name, rate = matcher.match(input_name)
            status = "✓" if name == expected else "✗"
            if verbose:
                print(f"{status} '{input_name}' -> '{name}' (expected '{expected}')")
            if name != expected:
                test3_passed = False
        except Exception as e:
            if verbose:
                print(f"✗ '{input_name}' raised exception: {e}")
            test3_passed = False
    
    if test3_passed:
        if verbose:
            print("\n✓ TEST 3 PASSED: All county matches correct")
        passed += 1
    else:
        if verbose:
            print("\n✗ TEST 3 FAILED: Some matches incorrect")
        failed += 1
    
    # =========================================================================
    # TEST 4: Date Validation
    # =========================================================================
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 4: Date Validation")
        print("=" * 70)
    
    date_validator = DateValidator()
    test4_passed = True
    
    # Valid date sequence
    try:
        date_validator.validate_date_sequence("2024-01-10", "2024-01-15")
        if verbose:
            print("✓ Valid sequence (signed before recorded) - passed")
    except DateLogicError:
        if verbose:
            print("✗ Valid sequence raised error incorrectly")
        test4_passed = False
    
    # Same day - should be valid
    try:
        date_validator.validate_date_sequence("2024-01-10", "2024-01-10")
        if verbose:
            print("✓ Same day signing and recording - passed")
    except DateLogicError:
        if verbose:
            print("✗ Same day raised error incorrectly")
        test4_passed = False
    
    # Invalid sequence (recorded before signed)
    try:
        date_validator.validate_date_sequence("2024-01-15", "2024-01-10")
        if verbose:
            print("✗ Invalid sequence did NOT raise error")
        test4_passed = False
    except DateLogicError as e:
        if verbose:
            print(f"✓ Invalid sequence detected: {e.signed_date} signed, {e.recorded_date} recorded")
    
    if test4_passed:
        if verbose:
            print("\n✓ TEST 4 PASSED: Date validation working correctly")
        passed += 1
    else:
        if verbose:
            print("\n✗ TEST 4 FAILED")
        failed += 1
    
    # =========================================================================
    # TEST 5: Amount Validation
    # =========================================================================
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 5: Amount Validation")
        print("=" * 70)
    
    amount_validator = AmountValidator()
    test5_passed = True
    
    # Matching amounts
    try:
        result = amount_validator.validate_amounts(
            "$1,250,000.00",
            "One Million Two Hundred Fifty Thousand Dollars"
        )
        if verbose:
            print(f"✓ Matching amounts validated: ${result:,.2f}")
    except AmountDiscrepancyError:
        if verbose:
            print("✗ Matching amounts raised error incorrectly")
        test5_passed = False
    
    # Mismatched amounts (the original error case)
    try:
        amount_validator.validate_amounts(
            "$1,250,000.00",
            "One Million Two Hundred Thousand Dollars"
        )
        if verbose:
            print("✗ Mismatched amounts did NOT raise error")
        test5_passed = False
    except AmountDiscrepancyError as e:
        if verbose:
            print(f"✓ Mismatch detected: ${e.numeric_amount:,.2f} vs ${e.written_amount:,.2f}")
        discrepancy = abs(e.numeric_amount - e.written_amount)
        if discrepancy != 50_000:
            if verbose:
                print(f"✗ Expected $50k discrepancy, got ${discrepancy:,.2f}")
            test5_passed = False
        else:
            if verbose:
                print(f"✓ Discrepancy correctly identified as ${discrepancy:,.2f}")
    
    if test5_passed:
        if verbose:
            print("\n✓ TEST 5 PASSED: Amount validation working correctly")
        passed += 1
    else:
        if verbose:
            print("\n✗ TEST 5 FAILED")
        failed += 1
    
    # =========================================================================
    # TEST 6: Additional Word-to-Number Edge Cases
    # =========================================================================
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
    
    test6_passed = True
    for text, expected in edge_cases:
        result = converter.convert(text)
        status = "✓" if result == expected else "✗"
        if verbose:
            print(f"{status} '{text}' -> {result:,.0f} (expected {expected:,})")
        if result != expected:
            test6_passed = False
    
    if test6_passed:
        if verbose:
            print("\n✓ TEST 6 PASSED: Edge cases handled correctly")
        passed += 1
    else:
        if verbose:
            print("\n✗ TEST 6 FAILED")
        failed += 1
    
    # =========================================================================
    # TEST 7: County Not Found Error
    # =========================================================================
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 7: County Not Found Error Handling")
        print("=" * 70)
    
    test7_passed = True
    try:
        matcher.match("Unknown County")
        if verbose:
            print("✗ Unknown county did NOT raise error")
        test7_passed = False
    except CountyNotFoundError as e:
        if verbose:
            print(f"✓ Unknown county correctly raised error: {e.county_text}")
        if "Unknown County" not in str(e):
            test7_passed = False
    
    if test7_passed:
        if verbose:
            print("\n✓ TEST 7 PASSED: County not found error works correctly")
        passed += 1
    else:
        if verbose:
            print("\n✗ TEST 7 FAILED")
        failed += 1
    
    # =========================================================================
    # TEST 8: Valid Deed (No Errors)
    # =========================================================================
    if verbose:
        print("\n" + "=" * 70)
        print("TEST 8: Valid Deed (No Errors)")
        print("=" * 70)
    
    valid_deed_data = {
        "doc_number": "DEED-VALID-001",
        "county": "San Mateo",
        "state": "CA",
        "date_signed": "2024-01-10",
        "date_recorded": "2024-01-15",
        "grantor": "Valid Seller LLC",
        "grantee": "Valid Buyer",
        "amount_numeric": "$500,000.00",
        "amount_written": "Five Hundred Thousand Dollars",
        "apn": "123-456-78",
        "status": "FINAL"
    }
    
    dv.extract_deed_with_llm = create_mock_extractor(valid_deed_data)
    
    test8_passed = True
    try:
        validator = DeedValidator(verbose=False)
        result = validator.validate("mock input")
        
        if not result.is_valid:
            if verbose:
                print(f"✗ Valid deed failed: {result.errors}")
            test8_passed = False
        elif len(result.errors) != 0:
            if verbose:
                print(f"✗ Expected 0 errors, got {len(result.errors)}")
            test8_passed = False
        elif result.deed_data.county_normalized != "San Mateo":
            if verbose:
                print(f"✗ County mismatch: {result.deed_data.county_normalized}")
            test8_passed = False
        elif result.deed_data.tax_rate != 0.011:
            if verbose:
                print(f"✗ Tax rate mismatch: {result.deed_data.tax_rate}")
            test8_passed = False
        else:
            if verbose:
                print(f"✓ Valid deed passed validation")
                print(f"✓ County matched: {result.deed_data.county_normalized}")
                print(f"✓ Tax rate: {result.deed_data.tax_rate}")
                print(f"✓ Closing costs: ${result.deed_data.closing_costs:,.2f}")
    except Exception as e:
        if verbose:
            print(f"✗ Exception: {e}")
        test8_passed = False
    finally:
        dv.extract_deed_with_llm = original_extract
    
    if test8_passed:
        if verbose:
            print("\n✓ TEST 8 PASSED: Valid deed processed correctly")
        passed += 1
    else:
        if verbose:
            print("\n✗ TEST 8 FAILED")
        failed += 1
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    if verbose:
        print("\n" + "#" * 70)
        print(f"# TEST SUMMARY: {passed} passed, {failed} failed")
        print("#" * 70)
    
    if failed == 0:
        if verbose:
            print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        if verbose:
            print(f"\n❌ {failed} TEST(S) FAILED")
        return False


if __name__ == "__main__":
    success = run_all_tests(verbose=True)
    sys.exit(0 if success else 1)
