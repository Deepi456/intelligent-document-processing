import os
import sys

import pytest
from unittest.mock import Mock

# Make the repository root importable when running the bare `pytest` console
# script (same bootstrap as tests/test_api.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.service import DocumentQueryService

class MockClient:
    def __init__(self, data):
        self.data = data
        
    def execute_read(self, query, **kwargs):
        if 'RETURN m.entity_type AS entity_type, m.raw_text AS value' in query:
            doc_id = kwargs.get('document_id')
            return [d for d in self.data if d['document_id'] == doc_id]
        if 'RETURN d.document_id AS document_id' in query:
            return [{'document_id': kwargs.get('document_id'), 'filename': 'test.pdf'}]
        return []

class MockDocumentQueryService(DocumentQueryService):
    def get_document(self, document_id, user_id: int | None = None):
        return {'document_id': document_id, 'filename': 'test.pdf'}

@pytest.fixture
def service():
    data = [
        {'document_id': 'docA', 'entity_type': 'Number', 'value': 'Number €@) · Email', 'entity_id': 'm0', 'confidence': 16.0, 'page': 1, 'evidence_id': 'ev0', 'raw_text': 'Number €@) · Email', 'extraction_method': 'layout_value', 'filename': 'docA.pdf'},
        {'document_id': 'docA', 'entity_type': 'Place', 'value': 'Place: Coimbatore', 'entity_id': 'm1', 'confidence': 1.0, 'page': 1, 'evidence_id': 'ev1', 'raw_text': 'Place: Coimbatore', 'extraction_method': 'layout_value', 'filename': 'docA.pdf'},
        {'document_id': 'docA', 'entity_type': 'Name', 'value': 'ASMITA M', 'entity_id': 'm7', 'confidence': 1.0, 'page': 1, 'evidence_id': 'ev7', 'raw_text': 'Name: ASMITA M', 'extraction_method': 'layout_value', 'filename': 'docA.pdf'},
        {'document_id': 'docA', 'entity_type': 'Department', 'value': 'AI & Data Science', 'entity_id': 'm2', 'confidence': 1.0, 'page': 1, 'evidence_id': 'ev2', 'raw_text': 'Department: AI & Data Science', 'extraction_method': 'layout_value', 'filename': 'docA.pdf'},
        {'document_id': 'docA', 'entity_type': "Father's Name", 'value': 'MOHANASUNDARAM', 'entity_id': 'm4', 'confidence': 1.0, 'page': 1, 'evidence_id': 'ev4', 'raw_text': "Father's Name: MOHANASUNDARAM", 'extraction_method': 'layout_value', 'filename': 'docA.pdf'},
        {'document_id': 'docA', 'entity_type': 'Date of Birth', 'value': 'Date of Birth: 23/06/2006', 'entity_id': 'm5', 'confidence': 1.0, 'page': 1, 'evidence_id': 'ev5', 'raw_text': 'Date of Birth: 23/06/2006', 'extraction_method': 'layout_value', 'filename': 'docA.pdf'},
        {'document_id': 'docA', 'entity_type': 'Identifier', 'value': 'FDHPA3470H', 'entity_id': 'm6', 'confidence': 1.0, 'page': 1, 'evidence_id': 'ev6', 'raw_text': 'FDHPA3470H', 'extraction_method': 'generic_pattern', 'filename': 'docA.pdf'},
        {'document_id': 'docB', 'entity_type': 'Author', 'value': 'Ada Lovelace', 'entity_id': 'm3', 'confidence': 1.0, 'page': 1, 'evidence_id': 'ev3', 'raw_text': 'Author: Ada Lovelace', 'extraction_method': 'layout_value', 'filename': 'docB.pdf'}
    ]
    return MockDocumentQueryService(MockClient(data))

def test_extract_attribute_place(service):
    res = service.answer_question('What is the place?', 'docA')
    assert res['answer'] == 'Coimbatore'

def test_extracts_person_name_without_document_specific_matching(service):
    result = service.answer_question('What is the name of the person?', 'docA')
    assert result['answer'] == 'ASMITA M'
    assert result['evidence']
    
def test_extract_attribute_department(service):
    res = service.answer_question('What is the department?', 'docA')
    assert res['answer'] == 'AI & Data Science'

def test_extract_attribute_author(service):
    res = service.answer_question('What is the author?', 'docB')
    assert res['answer'] == 'Ada Lovelace'

def test_normalizes_apostrophes_and_cleans_date(service):
    assert service.answer_question("What is the father's name?", 'docA')['answer'] == 'MOHANASUNDARAM'
    assert service.answer_question('What is the date of birth?', 'docA')['answer'] == '23/06/2006'

def test_retrieves_generic_identifier_with_number_wording(service):
    result = service.answer_question('What is the PAN number?', 'docA')
    assert result['answer'] == 'FDHPA3470H'
    assert result['evidence']

def test_wrong_attribute(service):
    res = service.answer_question('What is the college?', 'docA')
    assert res['answer'] == 'Please include a specific entity, relationship, or value in your question.' or res['answer'] == 'I couldn\'t find enough information in this document to answer that question.'

def test_document_isolation(service):
    # docA has Place, docB does not
    res = service.answer_question('What is the place?', 'docB')
    assert res['answer'] == 'I couldn\'t find enough information in this document to answer that question.'

