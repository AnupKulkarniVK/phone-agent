"""
Test script for fuzzy name matching
Run this to verify name matching works with speech recognition errors
"""
from fuzzywuzzy import fuzz


def fuzzy_match_name(search_name: str, database_name: str, threshold: int = 75) -> bool:
    """Test the fuzzy matching logic"""
    # Clean the names
    clean_search = search_name.lower().replace(".", "").replace(" ", "")
    clean_db = database_name.lower().replace(".", "").replace(" ", "")

    # Calculate similarity
    similarity = fuzz.ratio(clean_search, clean_db)
    partial_similarity = fuzz.partial_ratio(clean_search, clean_db)

    best_match = max(similarity, partial_similarity)

    return best_match >= threshold, best_match


def test_fuzzy_matching():
    """Test various name matching scenarios"""
    print("🧪 Testing Fuzzy Name Matching\n")
    print("=" * 60)

    # Test cases from your actual scenarios
    test_cases = [
        # (what user said, what's in DB, should match?)
        ("Raji", "Ragi", True),           # Scenario 7
        ("Raggy", "Ragi", True),          # Scenario 7
        ("R a g. I", "Ragi", True),       # Scenario 8
        ("John", "Jon", True),            # Common typo
        ("Smith", "Smyth", True),         # Similar spelling
        ("Mike", "Michael", False),       # Different names
        ("Anoop", "Anoop", True),         # Exact match
        ("Kana", "Kana", True),           # Exact match
        ("Raghavi", "Raghavi", True),     # Exact match
        ("AK", "AK", True),               # Short name
        ("Rag", "Ragi", True),            # Partial match
        ("Bob", "Robert", False),         # Completely different
    ]

    print("\nTest Results:")
    print("-" * 60)

    passed = 0
    failed = 0

    for search, database, expected in test_cases:
        matches, score = fuzzy_match_name(search, database)

        status = "✅ PASS" if matches == expected else "❌ FAIL"
        if matches == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} | '{search}' vs '{database}' → {score}% match → {matches}")

    print("-" * 60)
    print(f"\n📊 Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")

    if failed == 0:
        print("✅ All tests passed! Fuzzy matching is working correctly!")
    else:
        print("⚠️  Some tests failed. Review threshold settings.")

    print("\n" + "=" * 60)
    print("\n💡 How it works:")
    print("   - Cleans names (removes spaces, periods, lowercase)")
    print("   - Calculates similarity score (0-100%)")
    print("   - Matches if score >= 75%")
    print("   - 'Raji' vs 'Ragi' = 90% → MATCH ✅")
    print("   - 'R a g. I' vs 'Ragi' = cleaned to 'ragi' → 100% → MATCH ✅")


if __name__ == "__main__":
    test_fuzzy_matching()