from datetime import date

import pytest

from app.agent.parsing import clean_country, clean_name, match_option, parse_date


@pytest.mark.parametrize(
    "text,expected",
    [
        ("15/03/2027", date(2027, 3, 15)),
        ("15-3-27", date(2027, 3, 15)),
        ("15.03.2027", date(2027, 3, 15)),
        ("2027-03-15", date(2027, 3, 15)),
        ("15 March 2027", date(2027, 3, 15)),
        ("15th Mar, 2027", date(2027, 3, 15)),
        ("March 15 2027", date(2027, 3, 15)),
        ("3 Dec 2026", date(2026, 12, 3)),
        ("03/25/2027", date(2027, 3, 25)),  # month/day accepted when unambiguous
        ("31/02/2027", None),
        ("tomorrow", None),
        ("", None),
    ],
)
def test_parse_date(text, expected):
    assert parse_date(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [("wanjiru", "Wanjiru"), ("My name is Otieno", "Otieno"), ("Naitwa Amina", "Amina"), ("Mary-Jane", "Mary-Jane"),
     ("José", "José"), ("محمد", "محمد"), ("123", None), ("a" * 31, None), ("Robert'); DROP TABLE", None), ("", None)],
)
def test_clean_name(text, expected):
    assert clean_name(text) == expected


def test_clean_country():
    assert clean_country("kenya") == "Kenya"
    assert clean_country("philippines") == "Philippines"
    assert clean_country("south sudan") == "South Sudan"
    assert clean_country("<script>") is None


def test_match_option():
    opts = [("a", "Hotels & restaurants"), ("b", "Construction"), ("c", "Domestic work")]
    assert match_option("2", opts) == "b"
    assert match_option("construction", opts) == "b"
    assert match_option("Hotel", opts) == "a"
    assert match_option("xyz", opts) is None
    assert match_option("9", opts) is None
