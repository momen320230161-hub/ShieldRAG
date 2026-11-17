"""Validated, synthetic-only benchmark definitions."""
import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.rag import Question

Slug = Annotated[str, StringConstraints(pattern=r'^[a-z][a-z0-9-]{1,47}$')]
Marker = Annotated[str, StringConstraints(pattern=r'^EVAL06_[A-Z0-9_]{3,32}$')]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1800)]
Role = Literal['student', 'admin']
ROOT = Path(__file__).resolve().parents[1] / 'security_evaluation/task06'
PROVENANCE = 'project-authored synthetic task06; visible to developers; no external benchmark'
DEVELOPMENT_PROVENANCE = 'project-authored synthetic task061; visible to developers; no external benchmark'


class Definition(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, hide_input_in_errors=True)


class Fixture(Definition):
    id: Slug
    text: Text
    visibility: Literal['public', 'restricted'] = 'public'
    review: Literal['approved', 'pending', 'rejected'] = 'approved'
    format: Literal['txt', 'pdf'] = 'txt'
    marker: Marker | None = None

    @model_validator(mode='after')
    def validate_content(self):
        if len(self.text.encode()) > 1800 or (self.marker and self.marker not in self.text):
            raise ValueError('Invalid fixture content or marker')
        return self

    @property
    def revision(self):
        return hashlib.sha256(self.text.encode()).hexdigest()

    @property
    def document_id(self):
        return str(uuid5(NAMESPACE_URL, f'shieldrag/task06/{self.id}'))

    @property
    def chunk_id(self):
        return str(uuid5(NAMESPACE_URL, self.document_id + '/' + self.revision))

    def visible(self, role):
        return self.review == 'approved' and (self.visibility == 'public' or role == 'admin')


class Case(Definition):
    id: Slug
    category: Slug
    role: Role
    language: Literal['en', 'ar', 'mixed']
    difficulty: Literal['single', 'composed'] = 'single'
    question: Text
    sources: tuple[Slug, ...] = Field(max_length=5)
    expected_evidence: tuple[Slug, ...] = Field(max_length=5)
    label: Literal['benign', 'attack']
    expected_behavior: Literal['answer', 'abstain', 'prevent']
    objective: Literal['marker_release', 'unauthorized_release', 'unquoted_release'] | None = None
    stage: Literal['direct', 'indirect', 'output', 'authorization'] | None = None
    marker: Marker | None = None
    # Each fact lists acceptable strings. A case's rubric precedes execution.
    facts: tuple[tuple[Text, ...], ...] = Field(default=(), max_length=8)
    mock_answer: Text | None = None

    @model_validator(mode='after')
    def validate_labels(self):
        Question(question=self.question)
        if len(set(self.sources)) != len(self.sources) or len(set(self.expected_evidence)) != len(self.expected_evidence):
            raise ValueError('Repeated fixture reference')
        if self.label == 'benign':
            if self.objective or self.stage or self.marker or self.expected_behavior == 'prevent':
                raise ValueError('Benign case has attack fields')
            if self.expected_behavior == 'answer' and (
                not self.mock_answer or not self.expected_evidence or not self.facts or any(not group for group in self.facts)
            ):
                raise ValueError('Answerable case needs a scripted answer, evidence and facts')
            if self.expected_behavior == 'abstain' and (self.mock_answer or self.facts or self.expected_evidence):
                raise ValueError('Abstention case cannot have a reference answer')
        elif (not self.objective or not self.stage or not self.marker or self.expected_behavior != 'prevent'
              or self.facts or self.mock_answer
              or (self.objective == 'unauthorized_release') != (self.stage == 'authorization')
              or (self.objective == 'unquoted_release') != (self.stage == 'output')):
            raise ValueError('Attack case has inconsistent objective')
        return self


class Benchmark(Definition):
    version: Literal['shieldrag-task06-v1', 'shieldrag-task061-dev-v1']
    provenance: Literal[PROVENANCE, DEVELOPMENT_PROVENANCE]
    split: Literal['benchmark', 'development']
    seed: Literal[6021]
    fixtures: tuple[Fixture, ...] = Field(max_length=150)
    cases: tuple[Case, ...] = Field(min_length=1, max_length=150)

    @model_validator(mode='after')
    def validate_references(self):
        if self.version == 'shieldrag-task061-dev-v1' and (
            self.split != 'development' or self.provenance != DEVELOPMENT_PROVENANCE
        ):
            raise ValueError('Task 06.1 cases belong to the separate development suite')
        fixtures = {row.id: row for row in self.fixtures}
        if len(fixtures) != len(self.fixtures) or len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError('Duplicate benchmark identity')
        keys = {(case.role, ' '.join(case.question.casefold().split()), frozenset(case.sources))
                for case in self.cases}
        if len(keys) != len(self.cases):
            raise ValueError('Duplicate experimental case')
        if set(fixtures) != {source for case in self.cases for source in case.sources}:
            raise ValueError('Unknown or unused fixture')
        for case in self.cases:
            visible = {i for i in case.sources if fixtures[i].visible(case.role)}
            if not set(case.expected_evidence) <= visible:
                raise ValueError('Reference evidence is outside caller scope')
            if case.objective == 'unauthorized_release':
                if not any(fixtures[i].marker == case.marker for i in set(case.sources) - visible):
                    raise ValueError('Authorization objective needs a forbidden marked source')
                if any(case.marker in fixtures[i].text for i in visible):
                    raise ValueError('Authorization marker occurs in visible evidence')
            elif case.label == 'attack' and not case.expected_evidence:
                raise ValueError('Controlled provider challenge needs a permitted reference')
            if case.objective == 'unquoted_release' and any(case.marker in fixtures[i].text for i in visible):
                raise ValueError('Unquoted response marker occurs in authorized evidence')
        return self

    def digest(self):
        content = json.dumps(self.model_dump(mode='json'), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()


def load_benchmark(path=None):
    path = path or ROOT / 'benchmark/manifest.json'
    return Benchmark.model_validate_json(path.read_text(encoding='utf-8-sig'))
