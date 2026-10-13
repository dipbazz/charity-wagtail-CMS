"""The onboarding pack is the one source of what we ask a new charity for, so it must keep up
with the charity site standard and stay readable by the tracker's form script.
"""

import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "onboarding"
STANDARD = ROOT / "docs" / "site" / "standard.md"

COLUMNS = [
    "ID",
    "Step",
    "Section",
    "Question",
    "Help",
    "Answer type",
    "Options",
    "In form",
    "Owner",
    "Notes",
]
# The answer types onboarding/form-script.gs knows how to build.
ANSWER_TYPES = {"short", "long", "choice", "checkboxes", "photo", "upload"}
# Filled in for each charity when the pack is uploaded (docs/contributing/onboarding.md).
PLACEHOLDERS = {"name_ne", "name_en", "domain", "version", "demo_url"}
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def standard_menu():
    """The (English, Nepali) names of the standard menu sections, in order."""
    text = STANDARD.read_text(encoding="utf-8")
    section = text.split("## The menu", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")][2:]
    sections = []
    for row in rows:
        english, nepali = (cell.strip() for cell in row.strip("|").split("|")[:2])
        english = re.sub(r"\*\*(.+?)\*\*.*", r"\1", english)
        sections.append((english, nepali))
    return sections


def questions():
    with (PACK / "questions.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def form_rows():
    return [row for row in questions() if row["In form"] == "Yes"]


def guide():
    return (PACK / "guide.md").read_text(encoding="utf-8")


def test_the_standard_menu_is_read_from_the_standard():
    assert [english for english, _ in standard_menu()] == [
        "About us",
        "Appeals",
        "Stories",
        "Get involved",
        "Contact",
        "Donate",
    ]


def test_questions_have_the_columns_the_tracker_reads():
    with (PACK / "questions.csv").open(encoding="utf-8", newline="") as f:
        assert next(csv.reader(f)) == COLUMNS


def test_question_ids_are_unique():
    ids = [row["ID"] for row in questions()]

    assert ids, "expected questions in the pack"
    assert len(ids) == len(set(ids))


def test_every_question_has_an_answer_type_the_form_script_builds():
    bad = {
        row["ID"]: row["Answer type"]
        for row in questions()
        if row["Answer type"] not in ANSWER_TYPES
    }

    assert bad == {}


def test_in_form_is_yes_or_no():
    assert {row["In form"] for row in questions()} <= {"Yes", "No"}


def test_choice_questions_list_their_options():
    missing = [
        row["ID"]
        for row in form_rows()
        if row["Answer type"] in {"choice", "checkboxes"} and not row["Options"]
    ]

    assert missing == []


def test_upload_questions_say_how_many_files():
    """The form script reads "3" or "5; PDF or photos" to tell the user how to add the question."""
    bad = [
        row["ID"]
        for row in form_rows()
        if row["Answer type"] == "upload" and not re.fullmatch(r"\d+(; .+)?", row["Options"])
    ]

    assert bad == []


@pytest.mark.parametrize("column", ["Section", "Question"])
def test_the_charity_reads_every_question_in_nepali_and_english(column):
    english_only = [
        row["ID"]
        for row in form_rows()
        if " / " not in row[column] or not DEVANAGARI.search(row[column])
    ]

    assert english_only == []


def test_every_standard_menu_section_is_asked_for_in_the_form():
    asked = {row["Section"].split(" / ")[0] for row in form_rows()}

    assert [english for english, _ in standard_menu() if english not in asked] == []


def test_every_standard_menu_section_is_explained_in_the_guide():
    """The guide describes the menu every charity gets, in both languages."""
    text = guide()
    headings = re.findall(r"^#+ (.+)$", text, flags=re.MULTILINE)

    missing = [
        english
        for english, nepali in standard_menu()
        if not any(english in heading for heading in headings) or nepali not in text
    ]

    assert missing == []


@pytest.mark.parametrize("name", ["guide.md", "questions.csv"])
def test_the_pack_uses_only_placeholders_we_fill_in(name):
    text = (PACK / name).read_text(encoding="utf-8")

    assert set(re.findall(r"\{(\w+)\}", text)) <= PLACEHOLDERS
    rest = re.sub(r"\{\w+\}", "", text)
    assert "{" not in rest and "}" not in rest, "a stray brace would be mistaken for a placeholder"


def test_the_form_script_comes_with_the_pack():
    script = (PACK / "form-script.gs").read_text(encoding="utf-8")

    assert "function updateFromPack(" in script
    assert "ABSSK" not in script, "the script is shared by every charity"
