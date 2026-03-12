from src.zotero.client import (
    _extract_annotation,
    _extract_paper_metadata,
    _format_creators,
)


class TestFormatCreators:
    def test_first_last(self):
        creators = [{"firstName": "John", "lastName": "Smith"}]
        assert _format_creators(creators) == ["Smith, John"]

    def test_name_only(self):
        creators = [{"name": "WHO"}]
        assert _format_creators(creators) == ["WHO"]

    def test_last_only(self):
        creators = [{"lastName": "Anonymous"}]
        assert _format_creators(creators) == ["Anonymous"]

    def test_multiple_creators(self):
        creators = [
            {"firstName": "A", "lastName": "B"},
            {"firstName": "C", "lastName": "D"},
        ]
        result = _format_creators(creators)
        assert result == ["B, A", "D, C"]

    def test_empty_list(self):
        assert _format_creators([]) == []


class TestExtractPaperMetadata:
    def test_full_metadata(self):
        item = {
            "data": {
                "title": "Test Paper",
                "creators": [{"firstName": "J", "lastName": "Doe"}],
                "DOI": "10.1234/test",
                "abstractNote": "An abstract.",
                "publicationTitle": "Nature",
                "date": "2024-03-15",
                "itemType": "journalArticle",
                "url": "https://example.com",
            }
        }
        meta = _extract_paper_metadata(item, "KEY1")
        assert meta.key == "KEY1"
        assert meta.title == "Test Paper"
        assert meta.authors == ["Doe, J"]
        assert meta.doi == "10.1234/test"
        assert meta.year == "2024"
        assert meta.item_type == "journalArticle"

    def test_missing_fields_default_empty(self):
        meta = _extract_paper_metadata({"data": {}}, "KEY2")
        assert meta.title == ""
        assert meta.authors == []
        assert meta.doi == ""
        assert meta.year == ""

    def test_flat_dict_no_data_key(self):
        item = {"title": "Flat", "creators": [], "DOI": ""}
        meta = _extract_paper_metadata(item, "KEY3")
        assert meta.title == "Flat"


class TestExtractAnnotation:
    def test_full_annotation(self):
        item = {
            "data": {
                "key": "ANN1",
                "annotationText": "Highlighted text",
                "annotationComment": "My comment",
                "annotationColor": "#ffd400",
                "annotationPageLabel": "42",
                "annotationType": "highlight",
                "dateAdded": "2024-01-01T00:00:00Z",
                "parentItem": "ATT1",
            }
        }
        ann = _extract_annotation(item)
        assert ann.key == "ANN1"
        assert ann.text == "Highlighted text"
        assert ann.comment == "My comment"
        assert ann.color == "#ffd400"
        assert ann.page_label == "42"
        assert ann.parent_key == "ATT1"

    def test_missing_fields_default_empty(self):
        ann = _extract_annotation({"data": {}})
        assert ann.key == ""
        assert ann.text == ""
        assert ann.comment == ""
